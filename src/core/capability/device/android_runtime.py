"""AndroidRuntime - 进程内单例守护线程

同一 serial 只创建一个实例，通过 Unix domain socket / JSON-RPC 暴露能力，
截图等二进制数据通过 mmap 文件映射传递。
"""

from __future__ import annotations

import json
import mmap
import multiprocessing.connection as mp_connection
import os
import secrets
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import av
import cv2
import numpy as np

from core.capability.device.adb_manager import ADBDeviceInfo, ADBDeviceManager
from core.capability.device.touch_manager import TouchManager
from core.foundation.logger import get_logger
from core.foundation.paths import get_cache_subdir, get_project_root
from core.foundation.shell_security import (
    ALLOWED_SHELL_PREFIXES as _ALLOWED_SHELL_PREFIXES,
    KNOWN_KEYEVENT_NAMES as _KNOWN_KEYEVENT_NAMES,
    is_allowed_shell_cmd as _is_allowed_shell_cmd,
    is_valid_keyevent as _is_valid_keyevent,
)


class AndroidRuntimeError(Exception):
    """AndroidRuntime 基础异常"""


class _ScrcpySession:
    """单设备 scrcpy 视频流会话，内部维护最新帧缓存。

    实现 scrcpy v2.7 tunnel_forward 协议：
      [1B dummy] [64B device_name] [12B video_header: codec_id(4) + w(4) + h(4)]
      → 循环: [12B frame_header] [N B frame_data]
      帧标志: bit63=CONFIG, bit62=KEY_FRAME, bits0-61=PTS

    使用 av.CodecContext 持续解码，避免每帧重建容器。
    """

    def __init__(self, adb_manager: ADBDeviceManager, logger: Any):
        self._adb_manager = adb_manager
        self._logger = logger
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._local_port: Optional[int] = None
        self._server_proc: Optional[subprocess.Popen] = None
        self._serial: Optional[str] = None
        self._codec: Optional[av.CodecContext] = None
        self._device_name: Optional[str] = None
        self._frame_count = 0
        self._socket_ready = threading.Event()
        self._last_frame_ts: float = 0.0

    def start(self, serial: str, jar_path: str, max_size: int = 1280, bit_rate: int = 8000000, wait_first_frame: bool = True) -> None:
        if self._thread is not None:
            if self._thread.is_alive():
                return
            self._thread = None
        self._serial = serial
        self._stop_event.clear()
        self._latest_frame = None
        self._socket_ready.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(jar_path, max_size, bit_rate),
            daemon=True,
        )
        self._thread.start()
        if not wait_first_frame:
            return
        import time
        # H-01: 首帧计时从 socket 建立成功起算，而非线程启动；总超时放大到 15s
        self._socket_ready.wait(timeout=10.0)
        deadline = time.time() + 15.0
        while time.time() < deadline:
            if self._latest_frame is not None:
                return
            time.sleep(0.005)
        raise TimeoutError("scrcpy 未在 15s 内收到首帧")

    def stop(self, serial: Optional[str] = None) -> None:
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        self._close_codec()
        self._cleanup()

    def get_latest_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame

    def _run(self, jar_path: str, max_size: int, bit_rate: int) -> None:
        consecutive_failures = 0
        while not self._stop_event.is_set():
            try:
                if not self._serial:
                    return
                if not self._check_jar_cached():
                    self._push_jar(jar_path)
                self._start_server(max_size, bit_rate)
                if not self._wait_for_socket():
                    if self._stop_event.is_set():
                        return
                    self._logger.warning("scrcpy 等待 socket 超时，2s 后重试")
                    time.sleep(2.0)
                    continue
                self._decode_loop()
            except TimeoutError:
                # DIAG-01: 记录 server 进程状态，区分"server 被杀"vs"ADB 隧道断开"vs"编码器停滞"
                _srv_alive = self._server_proc is not None and self._server_proc.poll() is None
                _srv_rc = self._server_proc.returncode if self._server_proc is not None and self._server_proc.poll() is not None else None
                self._logger.warning(
                    "scrcpy socket 读取超时，2s 后重建会话",
                    server_alive=_srv_alive, server_returncode=_srv_rc,
                )
            except Exception:
                self._logger.exception("scrcpy 会话异常，2s 后重试")
            finally:
                had_frame = self._last_frame_ts > 0.0
                self._close_codec()
                self._cleanup()
                if had_frame:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
            if self._stop_event.is_set():
                return
            backoff = min(2.0 * (2 ** consecutive_failures), 60.0) if consecutive_failures > 0 else 2.0
            if consecutive_failures >= 3:
                self._logger.warning(f"scrcpy 连续 {consecutive_failures} 次未收到帧，{int(backoff)}s 后重试")
            time.sleep(backoff)

    def _check_jar_cached(self) -> bool:
        try:
            output = self._adb_manager.run_adb(
                ["shell", "test -f /data/local/tmp/scrcpy-server.jar && echo yes || echo no"],
                serial=self._serial or "",
            )
            return "yes" in str(output).strip()
        except Exception as exc:
            self._logger.warning("scrcpy jar 缓存检查失败", serial=self._serial, error=str(exc))
            return False

    def _host_shell(self, cmd: str) -> str:
        return self._adb_manager.run_adb(["shell", cmd], serial=self._serial or "")

    def _push_jar(self, jar_path: str) -> None:
        remote_path = "/data/local/tmp/scrcpy-server.jar"
        try:
            self._host_shell("mkdir -p /data/local/tmp")
        except Exception:
            pass
        local = Path(jar_path)
        if not local.exists():
            raise AndroidRuntimeError(f"scrcpy-server.jar 不存在: {jar_path}")
        self._adb_manager.run_adb(
            ["push", str(local.resolve()), remote_path],
            serial=self._serial or "",
        )
        self._logger.info("scrcpy jar 推送完成", serial=self._serial, jar=jar_path)

    def _wait_for_socket(self, timeout: float = 8.0, interval: float = 0.1) -> bool:
        import re
        import time

        deadline = time.time() + timeout
        while time.time() < deadline and not self._stop_event.is_set():
            try:
                output = self._adb_manager.run_adb(
                    ["forward", "tcp:0", "localabstract:scrcpy"],
                    serial=self._serial or "",
                )
                text = str(output).strip()
                m = re.search(r"(\d+)\s*$", text)
                if m:
                    self._local_port = int(m.group(1))
                    self._socket_ready.set()
                    return True
            except Exception:
                pass
            time.sleep(interval)
        return False

    def _ensure_device_online(self) -> None:
        try:
            self._adb_manager.run_adb(["connect", self._serial or ""], serial=None)
        except Exception:
            pass

    def _start_server(self, max_size: int, bit_rate: int) -> None:
        # PKILL-01: 不再使用 `pkill -f com.genymobile.scrcpy.Server`，因为该命令
        # 会杀死设备上所有 scrcpy server 进程，包括其他会话（如预览通道）的 server。
        # 改为只终止本会话管理的上一个 server 进程，避免跨会话干扰。
        if self._server_proc is not None and self._server_proc.poll() is None:
            try:
                self._server_proc.terminate()
                try:
                    self._server_proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._server_proc.kill()
            except Exception:
                pass
        self._server_proc = None
        self._ensure_device_online()
        server_cmd = (
            f"CLASSPATH=/data/local/tmp/scrcpy-server.jar "
            "app_process /system/bin com.genymobile.scrcpy.Server "
            "2.7 tunnel_forward=true audio=false "
            "video=true control=false show_touches=false stay_awake=true "
            "power_on=true send_dummy_byte=true send_device_meta=true "
            "send_frame_meta=true cleanup=false "
            f"max_size={max_size} video_bit_rate={bit_rate} "
            # ENCODER-01: 模拟器软件编码器 c2.android.avc.encoder 不实现
            # KEY_REPEAT_PREVIOUS_FRAME_AFTER，静态画面下仅按 KEY_I_FRAME_INTERVAL
            # (默认 10s) 产出关键帧。将 i-frame-interval 压到 2s 保证帧流不中断。
            "video_codec_options=i-frame-interval:int=2"
        )
        adb = str(self._adb_manager._resolve_adb_path())
        cmd = [adb, "-s", self._serial or "", "shell", server_cmd]
        try:
            self._server_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if self._server_proc.stdout is not None:
                threading.Thread(target=self._drain_pipe, args=(self._server_proc.stdout,), daemon=True).start()
        except Exception as exc:
            self._logger.exception(f"scrcpy server 启动失败 error={exc}")

    def _recv_exact(self, fileobj, n: int) -> Optional[bytes]:
        """从 fileobj 精确读取 n 字节，处理 partial read 和超时。

        socket.makefile("rb", buffering=0) 的 read(n) 仅做一次 recv()，对大帧
        （数十 KB）常返回 < n 字节——这是 TCP 正常的 partial read，不是 EOF。
        原代码把 partial read 误判为 socket 断开，导致重连死循环。

        本方法循环读取直到收齐 n 字节。socket.timeout 时检查 server 进程：
        存活则继续等待（编码器可能因 ADB 传输争用暂时停滞），已退出则返回 None。
        recv 返回空（真 EOF）也返回 None。
        """
        data = bytearray()
        stall_count = 0
        while len(data) < n:
            if self._stop_event.is_set():
                return None
            try:
                chunk = fileobj.read(n - len(data))
            except socket.timeout:
                if self._server_proc is not None and self._server_proc.poll() is not None:
                    self._logger.warning(
                        "scrcpy 读取超时且 server 已退出，重建会话",
                        bytes_read=len(data), bytes_expected=n,
                        server_returncode=self._server_proc.returncode,
                    )
                    return None
                stall_count += 1
                if stall_count == 1:
                    self._logger.info(
                        "scrcpy socket 等待数据中（server 存活，不重建）",
                        bytes_read=len(data), bytes_expected=n,
                    )
                continue
            if not chunk:
                _srv_alive = self._server_proc is not None and self._server_proc.poll() is None
                self._logger.warning(
                    "scrcpy socket EOF（通道关闭），重建会话",
                    bytes_read=len(data), bytes_expected=n,
                    server_alive=_srv_alive,
                )
                return None
            data.extend(chunk)
            stall_count = 0
        return bytes(data)

    def _decode_loop(self) -> None:
        import struct
        import time

        deadline = time.time() + 8.0

        while time.time() < deadline and not self._stop_event.is_set():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            try:
                sock.connect(("127.0.0.1", self._local_port))
            except (ConnectionRefusedError, ConnectionError):
                sock.close()
                time.sleep(0.2)
                continue

            fileobj = sock.makefile("rb", buffering=0)
            try:
                dummy = fileobj.read(1)
            except socket.timeout:
                fileobj.close()
                sock.close()
                time.sleep(0.2)
                continue

            if not dummy or dummy != b"\x00":
                fileobj.close()
                sock.close()
                time.sleep(0.2)
                continue

            sock.settimeout(30.0)
            sock.sendall(b"\x00")

            name_raw = fileobj.read(64)
            if len(name_raw) < 64:
                fileobj.close()
                sock.close()
                time.sleep(0.2)
                continue
            self._device_name = name_raw.rstrip(b"\x00").decode("utf-8", errors="replace")

            video_header = fileobj.read(12)
            if len(video_header) < 12:
                fileobj.close()
                sock.close()
                time.sleep(0.2)
                continue
            codec_id = struct.unpack(">I", video_header[0:4])[0]
            w = struct.unpack(">I", video_header[4:8])[0]
            h = struct.unpack(">I", video_header[8:12])[0]

            if codec_id not in (0x68323634, 0x68323635, 0x00617631):
                fileobj.close()
                sock.close()
                return

            codec_name = {0x68323634: "h264", 0x68323635: "hevc", 0x00617631: "av1"}[codec_id]
            self._codec = av.CodecContext.create(codec_name, "r")
            self._codec.width = w
            self._codec.height = h
            self._codec.pix_fmt = "yuv420p"
            self._codec.flags |= 1 << 19
            # CONFIG-01: 不显式 open()，让首次 decode() 自动打开。
            # scrcpy 2.7 的 config packet 是 AVCC 格式 SPS/PPS，需在 open 前设为 extradata
            # 才能被 ffmpeg 正确解析。显式 open() 后 extradata 不生效，导致 config 解码失败。
            self._logger.info(
                "scrcpy 握手成功",
                device=self._device_name,
                codec=codec_name,
                width=w,
                height=h,
                port=self._local_port,
            )

            # RECV-01: socket 超时设为 5s。_recv_exact 内部捕获 socket.timeout，
            # server 存活时继续等待，不触发重建。这消除了「大帧 partial read 被误判
            # 为断开」和「编码器暂时停滞触发重建」两个根因导致的重连死循环。
            sock.settimeout(5.0)
            first_frame_logged = False
            frame_counter = 0
            try:
                while not self._stop_event.is_set():
                    # SERVER-01: server 进程存活检测
                    if self._server_proc is not None and self._server_proc.poll() is not None:
                        self._logger.warning("scrcpy server 进程已退出", returncode=self._server_proc.returncode, frames_received=frame_counter)
                        break
                    header = self._recv_exact(fileobj, 12)
                    if header is None:
                        break

                    pts_flags = struct.unpack(">Q", header[:8])[0]
                    pkt_size = struct.unpack(">I", header[8:12])[0]

                    if pkt_size == 0 or pkt_size > 2 * 1024 * 1024:
                        self._logger.warning("scrcpy 异常包大小", pkt_size=pkt_size, pts_flags=hex(pts_flags))
                        continue

                    data = self._recv_exact(fileobj, pkt_size)
                    if data is None:
                        break

                    is_config = bool(pts_flags & (1 << 63))
                    is_keyframe = bool(pts_flags & (1 << 62))

                    if is_config:
                        self._logger.info("scrcpy 收到 config packet", size=pkt_size)
                        # CONFIG-01: scrcpy 2.7 config packet 是 AVCC 格式 SPS/PPS，
                        # 设为 extradata 让 ffmpeg 在首次 decode 自动 open 时解析。
                        # 不直接 decode()，因为 AVCC 格式不是 Annex-B，decode 会报 Invalid data。
                        try:
                            self._codec.extradata = bytes(data)
                        except Exception as e:
                            self._logger.warning("scrcpy config extradata 设置失败", error=str(e))
                        continue

                    try:
                        pkt = av.Packet(data)
                        if is_keyframe:
                            pkt.is_keyframe = True
                        pkt.pts = pts_flags & ((1 << 62) - 1)
                        for frame in self._codec.decode(pkt):
                            img = frame.to_ndarray(format="bgr24")
                            with self._lock:
                                self._latest_frame = img
                                self._last_frame_ts = time.time()
                            frame_counter += 1
                            if not first_frame_logged:
                                first_frame_logged = True
                                self._logger.info("scrcpy 首帧接收成功", codec=codec_name, width=w, height=h)
                    except Exception as e:
                        self._logger.warning("scrcpy 帧解码失败", error=str(e), pkt_size=pkt_size, is_keyframe=is_keyframe)
            finally:
                # 确保正常退出或异常时释放 socket 和 fileobj，避免文件描述符泄漏
                try:
                    fileobj.close()
                except Exception:
                    pass
                try:
                    sock.close()
                except Exception:
                    pass
            return

        self._logger.error("scrcpy 连接握手超时")

    def _close_codec(self) -> None:
        if self._codec is None:
            return
        try:
            self._codec.close()
        except Exception:
            pass
        self._codec = None

    def _cleanup(self) -> None:
        self._close_codec()
        self._last_frame_ts = 0.0
        try:
            if self._local_port:
                self._adb_manager.run_adb(
                    ["forward", "--remove", f"tcp:{self._local_port}"],
                    serial=self._serial or "",
                )
        except Exception:
            pass
        try:
            if self._server_proc is not None:
                try:
                    self._server_proc.kill()
                    self._server_proc.wait(timeout=2)
                except Exception:
                    pass
                self._server_proc = None
        except Exception:
            pass

    def _drain_pipe(self, pipe) -> None:
        # 诊断关键：scrcpy-server 的 stdout/stderr 必须可见，否则无法判断
        # 编码器初始化失败、协议版本不匹配、屏幕关闭等根因。按行读取并记录到日志。
        buf = b""
        try:
            while True:
                chunk = pipe.read(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    text = line.decode("utf-8", errors="replace").rstrip("\r")
                    if text.strip():
                        self._logger.info("scrcpy-server: " + text)
            if buf.strip():
                text = buf.decode("utf-8", errors="replace").rstrip("\r")
                if text.strip():
                    self._logger.info("scrcpy-server: " + text)
        except Exception:
            pass
        finally:
            try:
                pipe.close()
            except Exception:
                pass


class _Daemon:
    """最小 JSON-RPC 守护进程，单 serial 单实例。

    进程内通信使用命名管道（Windows）/ Unix domain socket（POSIX），
    不占用任何 TCP 网络端口。
    """

    def __init__(self, serial: str, socket_path: str, mmap_path: str, adb_path: str):
        self._serial = serial
        self._socket_path = socket_path
        self._mmap_path = mmap_path
        self._logger = get_logger(__name__)
        self._adb_manager = ADBDeviceManager(adb_path=adb_path)
        self._touch = TouchManager(adb_path=adb_path, device_address=serial)
        self._lock = threading.Lock()
        self._listener: Any = None
        self._running = False
        self._ipc_address: Optional[str] = None
        self._auth_token = secrets.token_hex(16)
        self._pipe_token = secrets.token_hex(8)  # 命名管道唯一后缀，避免 FILE_FLAG_FIRST_PIPE_INSTANCE 碰撞
        self._scrcpy_session: Optional[_ScrcpySession] = None
        self._scrcpy_jar_path = str(get_project_root() / "3rd-part" / "scrcpy" / "scrcpy-server.jar")

    @staticmethod
    def _ipc_family() -> Optional[str]:
        """选择不占用网络端口的 IPC 传输层：Windows 用命名管道，POSIX 用 Unix domain socket。"""
        if os.name == "nt":
            return "AF_PIPE"
        return "AF_UNIX"

    def _resolve_ipc_address(self) -> str:
        if os.name == "nt":
            safe = self._serial.replace(":", "_").replace("/", "_").replace("\\", "_")
            return r"\\.\pipe\istina-android-" + safe + "-" + self._pipe_token
        return self._socket_path

    def start(self) -> None:
        if self._running:
            return
        family = self._ipc_family()
        address = self._resolve_ipc_address()
        # POSIX 下清理可能残留的 socket 文件，避免 bind 失败
        if family == "AF_UNIX" and os.path.exists(address):
            try:
                os.unlink(address)
            except OSError:
                pass
        try:
            self._listener = mp_connection.Listener(address, family=family)
            self._ipc_address = self._listener.address
            self._running = True
            threading.Thread(target=self._accept_loop, daemon=True).start()
        except Exception:
            self._running = False
            self._logger.exception("守护进程 Listener 创建失败", address=address, family=family)
            if self._listener is not None:
                try:
                    self._listener.close()
                except Exception:
                    pass
            self._listener = None
            self._ipc_address = None
            raise

    def stop(self) -> None:
        self._running = False
        if self._scrcpy_session is not None:
            try:
                self._scrcpy_session.stop()
            except Exception:
                pass
            self._scrcpy_session = None
        if self._listener is not None:
            try:
                self._listener.close()
            except Exception:
                pass
            self._listener = None
        # POSIX 下删除残留的 socket 文件
        if self._ipc_family() == "AF_UNIX" and self._ipc_address and os.path.exists(self._ipc_address):
            try:
                os.unlink(self._ipc_address)
            except OSError:
                pass

    def _accept_loop(self) -> None:
        while self._running and self._listener is not None:
            try:
                conn = self._listener.accept()
            except Exception:
                break
            threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()

    def _handle_client(self, conn: Any) -> None:
        try:
            while True:
                # 使用带超时的轮询，避免对端异常断开时永久阻塞守护线程
                if not conn.poll(30):
                    break
                try:
                    raw = conn.recv_bytes()
                except EOFError:
                    break
                except Exception:
                    break
                try:
                    request = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                response = self._dispatch(request)
                try:
                    conn.send_bytes(json.dumps(response, ensure_ascii=False).encode("utf-8"))
                except Exception:
                    break
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _dispatch(self, request: Dict[str, Any]) -> Dict[str, Any]:
        if request.get("auth") != self._auth_token:
            self._logger.warning("守护进程收到未认证请求，已拒绝")
            return {"error": "unauthorized"}
        method = request.get("method")
        params = request.get("params", {})
        with self._lock:
            try:
                if method == "getDevices":
                    devices = self._adb_manager.get_devices()
                    return {"result": [{"serial": d.serial, "state": d.state} for d in devices]}
                if method == "version":
                    output = self._adb_manager.version()
                    return {"result": output}
                if method == "startScrcpy":
                    if self._scrcpy_session is not None:
                        thread = getattr(self._scrcpy_session, "_thread", None)
                        if thread is not None and not thread.is_alive():
                            self._scrcpy_session = None
                    if self._scrcpy_session is None:
                        self._scrcpy_session = _ScrcpySession(self._adb_manager, self._logger)
                    try:
                        self._scrcpy_session.start(
                            serial=params.get("serial", self._serial),
                            jar_path=self._scrcpy_jar_path,
                            max_size=int(params.get("maxSize", 1280)),
                            bit_rate=int(params.get("bitRate", 8000000)),
                        )
                    except Exception as exc:
                        return {"error": str(exc)}
                    return {"result": True}
                if method == "stopScrcpy":
                    if self._scrcpy_session is not None:
                        self._scrcpy_session.stop(params.get("serial", self._serial))
                        self._scrcpy_session = None
                    return {"result": True}
                if method == "screenshot":
                    serial = params.get("serial", self._serial)
                    frame = None
                    if self._scrcpy_session is not None:
                        thread = getattr(self._scrcpy_session, "_thread", None)
                        if thread is not None and not thread.is_alive():
                            self._scrcpy_session = None
                    if self._scrcpy_session is None:
                        try:
                            self._scrcpy_session = _ScrcpySession(self._adb_manager, self._logger)
                            self._scrcpy_session.start(
                                serial=serial,
                                jar_path=self._scrcpy_jar_path,
                                max_size=1280,
                                bit_rate=8000000,
                                wait_first_frame=False,
                            )
                        except Exception:
                            self._scrcpy_session = None
                    if self._scrcpy_session is not None:
                        frame = self._scrcpy_session.get_latest_frame()
                    if frame is not None:
                        self._logger.debug("daemon screenshot 使用 scrcpy 帧", serial=serial, frame_shape=frame.shape if hasattr(frame, 'shape') else None)
                        _, buf = cv2.imencode(".png", frame)
                        return self._encode_binary(buf.tobytes())
                    # H-01: 不再回退到 ADB 截图，scrcpy 无帧即视为未就绪
                    self._logger.error("daemon screenshot scrcpy 无帧", serial=serial)
                    return {"error": "scrcpy not ready"}
                if method == "tap":
                    self._touch.tap(int(params.get("x", 0)), int(params.get("y", 0)), serial=params.get("serial", self._serial))
                    return {"result": True}
                if method == "swipe":
                    self._touch.swipe(
                        int(params.get("x1", 0)),
                        int(params.get("y1", 0)),
                        int(params.get("x2", 0)),
                        int(params.get("y2", 0)),
                        duration_ms=int(params.get("durationMs", 300)),
                        serial=params.get("serial", self._serial),
                    )
                    return {"result": True}
                if method == "keyevent":
                    key = params.get("key")
                    # keyevent 必须为纯数字或已知常量名，防止 shell 注入
                    if not _is_valid_keyevent(key):
                        return {"error": f"invalid keyevent: {key!r}"}
                    output = self._adb_manager.shell(f"input keyevent {key}", serial=params.get("serial", self._serial))
                    return {"result": output}
                if method == "shell":
                    cmd = params.get("cmd", "")
                    # 限制允许的 shell 命令前缀，防止任意命令执行
                    if not _is_allowed_shell_cmd(cmd):
                        self._logger.warning("守护进程拒绝 shell 命令", cmd=cmd[:80])
                        return {"error": "shell command not allowed"}
                    output = self._adb_manager.shell(cmd, serial=params.get("serial", self._serial))
                    return {"result": output}
                return {"error": f"unknown method: {method}"}
            except Exception as exc:
                self._logger.error("守护进程执行失败 [method=%s]: %s", method, str(exc))
                return {"error": str(exc)}

    def _encode_binary(self, data: Optional[bytes]) -> Dict[str, Any]:
        if data is None:
            return {"result": None}
        fd = None
        mm = None
        try:
            flags = os.O_CREAT | os.O_TRUNC | os.O_RDWR
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            fd = os.open(self._mmap_path, flags)
            if data:
                os.write(fd, data)
                os.ftruncate(fd, len(data))
            mm = mmap.mmap(fd, len(data) if data else 0, access=mmap.ACCESS_WRITE)
            return {
                "result": {
                    "mmapPath": self._mmap_path,
                    "size": len(data) if data else 0,
                }
            }
        except Exception as exc:
            return {"error": f"mmap encode failed: {exc}"}
        finally:
            if mm is not None:
                try:
                    mm.close()
                except Exception:
                    pass
            if fd is not None:
                try:
                    os.close(fd)
                except Exception:
                    pass


class AndroidRuntime:
    """跨进程单例客户端连接器，向守护进程发 JSON-RPC 请求。"""

    def __init__(self, serial: str, adb_path: str = "3rd-part/adb/adb.exe"):
        self._serial = serial
        self._adb_path = str(get_project_root() / adb_path)
        safe_serial = serial.replace(":", "_")
        self._socket_path = str(get_cache_subdir("ipc") / f"android-{safe_serial}.sock")
        self._mmap_path = str(get_cache_subdir("ipc") / f"android-{safe_serial}.mmap")
        self._logger = get_logger(__name__)
        self._lock = threading.Lock()
        self._daemon: Optional[_Daemon] = None

    def _get_daemon(self) -> _Daemon:
        with self._lock:
            if self._daemon is None:
                self._daemon = _Daemon(self._serial, self._socket_path, self._mmap_path, self._adb_path)
                self._daemon.start()
            return self._daemon

    def _call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        daemon: Optional[_Daemon] = None
        conn: Any = None
        try:
            daemon = self._get_daemon()
            request = json.dumps(
                {"method": method, "params": params, "auth": daemon._auth_token},
                ensure_ascii=False,
            ).encode("utf-8")
            conn = mp_connection.Client(daemon._ipc_address, family=daemon._ipc_family())
            conn.send_bytes(request)
            if not conn.poll(30):  # 防止 recv 永久阻塞导致 GUI/自动化线程挂起
                self._logger.warning("daemon _call 超时", method=method)
                return {"error": "timeout"}
            try:
                raw = conn.recv_bytes()
            except EOFError:
                return {"error": "empty response"}
            if not raw:
                return {"error": "empty response"}
            return json.loads(raw.decode("utf-8"))
        except Exception:
            addr = getattr(daemon, "_ipc_address", None)
            self._logger.exception("daemon _call 连接失败", method=method, address=addr)
            return {"error": "connection failed"}
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_devices(self) -> List[ADBDeviceInfo]:
        response = self._call("getDevices")
        devices: List[ADBDeviceInfo] = []
        for item in response.get("result", []) or []:
            devices.append(ADBDeviceInfo(serial=item.get("serial", ""), state=item.get("state", "device")))
        return devices

    def version(self) -> str:
        response = self._call("version")
        return str(response.get("result", ""))

    def screenshot(self, serial: Optional[str] = None) -> Optional[bytes]:
        serial = serial or self._serial
        self._logger.debug("调用 daemon screenshot", serial=serial)
        response = self._call("screenshot", {"serial": serial})
        result = response.get("result")
        if result is None:
            self._logger.warning("daemon screenshot 返回 None", response=response)
            return None
        mmap_path = result.get("mmapPath")
        size = result.get("size", 0)
        if not mmap_path or size <= 0:
            self._logger.warning("daemon screenshot mmap 无效", mmap_path=mmap_path, size=size)
            return None
        fd = None
        try:
            flags = os.O_RDONLY
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            fd = os.open(mmap_path, flags)
            mm = mmap.mmap(fd, size, access=mmap.ACCESS_READ)
            try:
                data = mm.read(size)
                self._logger.debug("daemon screenshot mmap 读取成功", size=size)
                return data
            finally:
                mm.close()
        except Exception as exc:
            self._logger.error("daemon screenshot mmap 读取失败", error=str(exc))
            return None
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except Exception:
                    pass

    def start_scrcpy(self, max_size: int = 1280, bit_rate: int = 8000000, serial: Optional[str] = None) -> Dict[str, Any]:
        return self._call("startScrcpy", {
            "maxSize": max_size,
            "bitRate": bit_rate,
            "serial": serial or self._serial,
        })

    def stop_scrcpy(self, serial: Optional[str] = None) -> Dict[str, Any]:
        return self._call("stopScrcpy", {"serial": serial or self._serial})

    def tap(self, x: int, y: int, serial: Optional[str] = None) -> None:
        response = self._call("tap", {"x": x, "y": y, "serial": serial or self._serial})
        if response.get("error"):
            raise AndroidRuntimeError(f"tap 失败: {response['error']}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300, serial: Optional[str] = None) -> None:
        response = self._call("swipe", {
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "durationMs": duration_ms, "serial": serial or self._serial,
        })
        if response.get("error"):
            raise AndroidRuntimeError(f"swipe 失败: {response['error']}")

    def keyevent(self, key: str, serial: Optional[str] = None) -> str:
        response = self._call("keyevent", {"key": key, "serial": serial or self._serial})
        if response.get("error"):
            raise AndroidRuntimeError(f"keyevent 失败: {response['error']}")
        return response.get("result", "")

    def shell(self, cmd: str, serial: Optional[str] = None) -> str:
        response = self._call("shell", {"cmd": cmd, "serial": serial or self._serial})
        return response.get("result", "")
