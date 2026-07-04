"""AndroidRuntime - 进程内单例守护线程

同一 serial 只创建一个实例，通过 Unix domain socket / JSON-RPC 暴露能力，
截图等二进制数据通过 mmap 文件映射传递。
"""

from __future__ import annotations

import json
import mmap
import os
import socket
import struct
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import av
import cv2
import numpy as np

from core.capability.device.adb_manager import ADBDeviceInfo, ADBDeviceManager
from core.capability.device.touch_manager import TouchManager
from core.foundation.logger import get_logger, LogCategory
from core.foundation.paths import get_cache_subdir, get_project_root


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

    def start(self, serial: str, jar_path: str, max_size: int = 1280, bit_rate: int = 8000000) -> None:
        if self._thread is not None:
            return
        self._serial = serial
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(jar_path, max_size, bit_rate),
            daemon=True,
        )
        self._thread.start()
        import time
        deadline = time.time() + 8.0
        while time.time() < deadline:
            if self._latest_frame is not None:
                return
            time.sleep(0.005)
        raise TimeoutError("scrcpy 未在 8s 内收到首帧")

    def stop(self, serial: Optional[str] = None) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._cleanup()

    def get_latest_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame

    def _run(self, jar_path: str, max_size: int, bit_rate: int) -> None:
        try:
            if not self._serial:
                return
            if not self._check_jar_cached():
                self._push_jar(jar_path)
            self._start_server(max_size, bit_rate)
            if not self._wait_for_socket():
                return
            self._decode_loop()
        except Exception:
            self._logger.exception("scrcpy 会话异常")
        finally:
            self._codec = None
            self._cleanup()

    def _check_jar_cached(self) -> bool:
        try:
            output = self._adb_manager.run_adb(
                ["shell", "ls /data/local/tmp/scrcpy-server.jar 2>/dev/null"],
                serial=self._serial or "",
            )
            return "scrcpy-server" in str(output)
        except Exception:
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
            return
        try:
            self._adb_manager.run_adb(["push", str(local.resolve()), remote_path], serial=self._serial or "")
        except Exception:
            pass

    def _wait_for_socket(self, timeout: float = 8.0, interval: float = 0.1) -> bool:
        import time, re

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
        try:
            self._host_shell("pkill -f com.genymobile.scrcpy.Server || true")
        except Exception:
            pass
        self._ensure_device_online()
        server_cmd = (
            f"CLASSPATH=/data/local/tmp/scrcpy-server.jar "
            "app_process /system/bin com.genymobile.scrcpy.Server "
            "2.7 tunnel_forward=true audio=false "
            "video=true control=false show_touches=false stay_awake=true "
            "send_dummy_byte=true send_device_meta=true send_frame_meta=true "
            f"max_size={max_size} video_bit_rate={bit_rate}"
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
            self._logger.exception("scrcpy server 启动失败", error=str(exc))

    def _decode_loop(self) -> None:
        import struct, io, time

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
            self._codec.open()

            while not self._stop_event.is_set():
                header = fileobj.read(12)
                if len(header) < 12:
                    break

                pts_flags = struct.unpack(">Q", header[:8])[0]
                pkt_size = struct.unpack(">I", header[8:12])[0]

                if pkt_size == 0 or pkt_size > 2 * 1024 * 1024:
                    continue

                data = fileobj.read(pkt_size)
                if len(data) < pkt_size:
                    break

                is_config = bool(pts_flags & (1 << 63))
                is_keyframe = bool(pts_flags & (1 << 62))

                if is_config:
                    try:
                        self._codec.decode(av.Packet(data))
                    except Exception:
                        pass
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
                except Exception:
                    pass

            return

        self._logger.error("scrcpy 连接握手超时")

    def _cleanup(self) -> None:
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
                except Exception:
                    pass
                self._server_proc = None
        except Exception:
            pass
        try:
            self._host_shell("pkill -f com.genymobile.scrcpy.Server || true")
        except Exception:
            pass

    def _drain_pipe(self, pipe) -> None:
        try:
            while True:
                chunk = pipe.read(65536)
                if not chunk:
                    break
        except Exception:
            pass
        finally:
            try:
                pipe.close()
            except Exception:
                pass


class _Daemon:
    """最小 JSON-RPC 守护进程，单 serial 单实例。"""

    def __init__(self, serial: str, socket_path: str, mmap_path: str, adb_path: str):
        self._serial = serial
        self._socket_path = socket_path
        self._mmap_path = mmap_path
        self._logger = get_logger(__name__)
        self._adb_manager = ADBDeviceManager(adb_path=adb_path)
        self._touch = TouchManager(adb_path=adb_path, device_address=serial)
        self._lock = threading.Lock()
        self._server: Optional[socket.socket] = None
        self._running = False
        self._scrcpy_session: Optional[_ScrcpySession] = None
        self._scrcpy_jar_path = str(get_project_root() / "3rd-part" / "scrcpy" / "scrcpy-server.jar")

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._tcp_port = self._pick_port()
        if hasattr(socket, "AF_UNIX"):
            self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                if os.path.exists(self._socket_path):
                    os.remove(self._socket_path)
                self._server.bind(self._socket_path)
            except OSError:
                self._server.close()
                self._server = None
        if self._server is None:
            self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server.bind(("127.0.0.1", self._tcp_port))
        self._server.listen(5)
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def stop(self) -> None:
        self._running = False
        if self._scrcpy_session is not None:
            try:
                self._scrcpy_session.stop()
            except Exception:
                pass
            self._scrcpy_session = None
        if self._server:
            try:
                self._server.close()
            except Exception:
                pass

    def _pick_port(self) -> int:
        return 50000 + (hash(self._serial) % 10000)

    def _accept_loop(self) -> None:
        while self._running:
            try:
                conn, _ = self._server.accept()
            except Exception:
                break
            threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()

    def _handle_client(self, conn: socket.socket) -> None:
        try:
            conn.settimeout(5)
            while True:
                try:
                    raw = self._recv(conn)
                except (socket.timeout, ConnectionError):
                    break
                if raw is None:
                    break
                try:
                    request = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                response = self._dispatch(request)
                try:
                    conn.sendall(json.dumps(response, ensure_ascii=False).encode("utf-8") + b"\n")
                except Exception:
                    break
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _recv(self, conn: socket.socket) -> Optional[bytes]:
        buf = b""
        while b"\n" not in buf:
            chunk = conn.recv(4096)
            if not chunk:
                return None
            buf += chunk
        return buf.split(b"\n", 1)[0]

    def _dispatch(self, request: Dict[str, Any]) -> Dict[str, Any]:
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
                    if self._scrcpy_session is None:
                        self._scrcpy_session = _ScrcpySession(self._adb_manager, self._logger)
                    self._scrcpy_session.start(
                        serial=params.get("serial", self._serial),
                        jar_path=self._scrcpy_jar_path,
                        max_size=int(params.get("maxSize", 1280)),
                        bit_rate=int(params.get("bitRate", 8000000)),
                    )
                    return {"result": True}
                if method == "stopScrcpy":
                    if self._scrcpy_session is not None:
                        self._scrcpy_session.stop(params.get("serial", self._serial))
                        self._scrcpy_session = None
                    return {"result": True}
                if method == "screenshot":
                    serial = params.get("serial", self._serial)
                    if self._scrcpy_session is None:
                        self._scrcpy_session = _ScrcpySession(self._adb_manager, self._logger)
                        self._scrcpy_session.start(
                            serial or self._serial,
                            jar_path=self._scrcpy_jar_path,
                            max_size=int(params.get("maxSize", 1280)),
                            bit_rate=int(params.get("bitRate", 8000000)),
                        )
                    frame = self._scrcpy_session.get_latest_frame()
                    if frame is None:
                        return {"error": "scrcpy frame not ready"}
                    _, buf = cv2.imencode(".png", frame)
                    return self._encode_binary(buf.tobytes())
                if method == "tap":
                    self._touch.tap(int(params.get("x", 0)), int(params.get("y", 0)), serial=self._serial)
                    return {"result": True}
                if method == "swipe":
                    self._touch.swipe(
                        int(params.get("x1", 0)),
                        int(params.get("y1", 0)),
                        int(params.get("x2", 0)),
                        int(params.get("y2", 0)),
                        duration_ms=int(params.get("durationMs", 300)),
                        serial=self._serial,
                    )
                    return {"result": True}
                if method == "keyevent":
                    output = self._adb_manager.shell(f"input keyevent {params.get('key')}", serial=self._serial)
                    return {"result": output}
                if method == "shell":
                    output = self._adb_manager.shell(params.get("cmd", ""), serial=self._serial)
                    return {"result": output}
                return {"error": f"unknown method: {method}"}
            except Exception as exc:
                self._logger.error("守护进程执行失败 [method=%s]: %s", method, str(exc))
                return {"error": str(exc)}

    def _encode_binary(self, data: Optional[bytes]) -> Dict[str, Any]:
        if data is None:
            return {"result": None}
        fd = None
        try:
            flags = os.O_CREAT | os.O_TRUNC | os.O_RDWR
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            fd = os.open(self._mmap_path, flags)
            if data:
                os.write(fd, data)
                os.ftruncate(fd, len(data))
            mm = mmap.mmap(fd, len(data) if data else 0, access=mmap.ACCESS_WRITE)
            try:
                return {
                    "result": {
                        "mmapPath": self._mmap_path,
                        "size": len(data) if data else 0,
                    }
                }
            finally:
                mm.close()
        except Exception as exc:
            return {"error": f"mmap encode failed: {exc}"}
        finally:
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
        request = json.dumps({"method": method, "params": params}, ensure_ascii=False).encode("utf-8") + b"\n"
        sock = None
        try:
            if hasattr(socket, "AF_UNIX"):
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    sock.connect(self._socket_path)
                except OSError:
                    try:
                        sock.close()
                    except Exception:
                        pass
                    sock = None
            if sock is None:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                daemon = self._get_daemon()
                port = getattr(daemon, "_tcp_port", None) or daemon._pick_port()
                sock.connect(("127.0.0.1", port))
        except Exception:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
            return {"error": "connection failed"}

        try:
            sock.sendall(request)
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
            if not buf:
                return {"error": "empty response"}
            return json.loads(buf.split(b"\n", 1)[0].decode("utf-8"))
        finally:
            try:
                sock.close()
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
        response = self._call("screenshot", {"serial": serial})
        result = response.get("result")
        if result is None:
            return None
        mmap_path = result.get("mmapPath")
        size = result.get("size", 0)
        if not mmap_path or size <= 0:
            return None
        fd = None
        try:
            flags = os.O_RDONLY
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            fd = os.open(mmap_path, flags)
            mm = mmap.mmap(fd, size, access=mmap.ACCESS_READ)
            try:
                return mm.read(size)
            finally:
                mm.close()
        except Exception:
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
        self._call("tap", {"x": x, "y": y, "serial": serial or self._serial})

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300, serial: Optional[str] = None) -> None:
        self._call("swipe", {
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "durationMs": duration_ms, "serial": serial or self._serial,
        })

    def keyevent(self, key: str, serial: Optional[str] = None) -> str:
        response = self._call("keyevent", {"key": key, "serial": serial or self._serial})
        return response.get("result", "")

    def shell(self, cmd: str, serial: Optional[str] = None) -> str:
        response = self._call("shell", {"cmd": cmd, "serial": serial or self._serial})
        return response.get("result", "")
