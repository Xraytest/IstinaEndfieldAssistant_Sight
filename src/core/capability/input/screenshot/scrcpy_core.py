"""
Scrcpy 视频流核心实现 - 基于 StarRailCopilot 设计
使用 scrcpy-server v1.25 + PyAV 解码，提供低延迟持续视频流
"""
import os
import select
import socket
import struct
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from core.foundation.paths import ensure_src_path
ensure_src_path(__file__)

from core.foundation.logger import get_logger, LogCategory, LogLevel
from core.capability.device.adb_manager import ADBDeviceManager

try:
    import av
    from av.codec import CodecContext
    from av.error import InvalidDataError
    PYAV_AVAILABLE = True
except ImportError:
    PYAV_AVAILABLE = False
    av = None

try:
    from adbutils import AdbConnection, Network as AdbNetwork
    ADBUTILS_AVAILABLE = True
except ImportError:
    ADBUTILS_AVAILABLE = False
    AdbConnection = None
    AdbNetwork = None


class ScrcpyError(Exception):
    """scrcpy 相关错误基类"""
    pass


class ScrcpyServerError(ScrcpyError):
    """scrcpy server 启动或运行错误"""
    pass


class ScrcpyConnectionError(ScrcpyError):
    """scrcpy socket 连接错误"""
    pass


class ScrcpyDecodeError(ScrcpyError):
    """scrcpy 视频解码错误"""
    pass


class ScrcpyCore:
    """
    Scrcpy 核心类 - 管理 scrcpy server 生命周期和视频流解码

    功能：
    - 推送 scrcpy-server.jar 到设备
    - 启动 scrcpy server（v1.25）
    - 建立视频和控制 Socket 连接
    - 后台线程持续接收和解码 H.264 视频流
    - 提供最新帧的即时访问
    - 发送控制命令（触摸、滑动等）
    """

    # scrcpy server 配置常量
    FRAME_RATE = 10
    MAX_RESOLUTION = 1280
    BITRATE = 20000000  # 20Mbps
    FORWARD_PORT = 27183  # scrcpy 默认转发端口

    # 控制消息格式常量（与 scrcpy 协议一致）
    TOUCH_ACTION_DOWN = 0
    TOUCH_ACTION_UP = 1
    TOUCH_ACTION_MOVE = 2

    def __init__(self, adb_manager: ADBDeviceManager, device_serial: str, config: dict = None):
        """
        初始化 ScrcpyCore

        Args:
            adb_manager: ADB 设备管理器
            device_serial: 设备序列号
            config: 配置字典，可包含：
                - frame_rate: 帧率（默认 10）
                - max_resolution: 最大分辨率（默认 1280）
                - bitrate: 码率（默认 20000000）
        """
        self.adb_manager = adb_manager
        self.device_serial = device_serial
        self.config = config or {}

        # 日志
        self.logger = get_logger()

        # 配置参数
        self.frame_rate = self.config.get('frame_rate', self.FRAME_RATE)
        self.max_resolution = self.config.get('max_resolution', self.MAX_RESOLUTION)
        self.bitrate = self.config.get('bitrate', self.BITRATE)

        # scrcpy server JAR 路径
        self.jar_path = self._get_jar_path()

        # 连接状态
        self._scrcpy_alive = False
        self._server_stream = None  # shell 流连接 (AdbConnection)
        self._video_socket = None  # 视频 socket
        self._control_socket = None  # 控制 socket
        self._control_socket_lock = threading.Lock()

        # 视频流状态
        self._stream_loop_thread = None
        self._last_frame: Optional[np.ndarray] = None
        self._last_frame_time: float = 0.0
        self._resolution: Tuple[int, int] = (0, 0)
        self._first_frame_event = threading.Event()

        # 解码器
        self._codec: Optional[CodecContext] = None

        # 检查依赖
        if not PYAV_AVAILABLE:
            raise ScrcpyDecodeError("PyAV 库未安装，请安装 PyAV>=10.0.0")
        if not ADBUTILS_AVAILABLE:
            raise ScrcpyServerError("adbutils 未安装，请安装 adbutils>=0.15.0")

    def _get_jar_path(self) -> Path:
        """获取 scrcpy-server 路径"""
        project_root = Path(__file__).resolve()
        # 向上回溯到项目根目录：src/core/capability/input/screenshot/scrcpy_core.py
        # 需要回溯 6 层：screenshot -> input -> capability -> core -> src -> project_root
        for _ in range(6):
            project_root = project_root.parent
        # 优先使用 v2.7 server，当前客户端实现与 v2.7 兼容性更稳定
        jar_path = project_root / "3rd-part" / "scrcpy" / "scrcpy-server-v2.7"
        if not jar_path.exists():
            # 回退到旧版 JAR
            jar_path = project_root / "3rd-part" / "scrcpy" / "scrcpy-server.jar"
        if not jar_path.exists():
            # 最后回退到 v4.0 server
            jar_path = project_root / "3rd-part" / "scrcpy" / "scrcpy-server-v4.0"
        return jar_path

    def start(self) -> None:
        """
        启动 scrcpy：推送 JAR、启动 server、建立连接、启动解码线程

        Raises:
            ScrcpyServerError: server 启动失败
            ScrcpyConnectionError: socket 连接失败
            ScrcpyDecodeError: 解码器初始化失败
        """
        if not PYAV_AVAILABLE:
            raise ScrcpyDecodeError("PyAV 库未安装，请安装 PyAV>=10.0.0")

        self.logger.info(LogCategory.MAIN, "开始启动 scrcpy",
                         device_serial=self.device_serial,
                         jar_path=str(self.jar_path))

        # 启动前检查：确保设备在线
        self._preflight_check()

        try:
            self._server_start()
            self._socket_setup()
            self._scrcpy_alive = True
            self._start_stream_loop()

            self.logger.info(LogCategory.MAIN, "scrcpy 启动成功",
                             device_serial=self.device_serial,
                             resolution=f"{self._resolution[0]}x{self._resolution[1]}")
        except Exception as e:
            self._cleanup_on_error()
            if isinstance(e, ScrcpyError):
                raise
            raise ScrcpyServerError(f"scrcpy 启动失败: {e}") from e

    def _preflight_check(self) -> None:
        """启动前检查：确保设备和 ADB 可用"""
        try:
            # 检查设备是否在线
            devices = self.adb_manager.get_devices()
            device_found = any(d.serial == self.device_serial and d.status == 'device' for d in devices)
            if not device_found:
                raise ScrcpyServerError(f"设备不在线: {self.device_serial}")

            # 检查 ADB 连接是否正常
            try:
                self.adb_manager.shell_command(self.device_serial, "echo ok", timeout=5)
            except Exception as e:
                raise ScrcpyServerError(f"ADB 连接异常: {e}") from e

            self.logger.debug(LogCategory.MAIN, "启动前检查通过",
                               device_serial=self.device_serial)
        except ScrcpyError:
            raise
        except Exception as e:
            raise ScrcpyServerError(f"启动前检查失败: {e}") from e

    def stop(self) -> None:
        """停止 scrcpy，清理所有资源"""
        self.logger.info(LogCategory.MAIN, "停止 scrcpy", device_serial=self.device_serial)
        self._scrcpy_alive = False

        # 停止解码线程
        if self._stream_loop_thread and self._stream_loop_thread.is_alive():
            self._stream_loop_thread.join(timeout=2.0)
            if self._stream_loop_thread.is_alive():
                self.logger.warning(LogCategory.MAIN, "解码线程未正常退出", device_serial=self.device_serial)

        # 关闭 socket
        self._cleanup_socket(self._control_socket)
        self._control_socket = None
        self._cleanup_socket(self._video_socket)
        self._video_socket = None

        # 关闭 shell 流
        if self._server_stream:
            try:
                self._server_stream.close()
            except Exception as e:
                self.logger.warning(LogCategory.MAIN, "关闭 server stream 异常", error=str(e))
            self._server_stream = None

        self.logger.info(LogCategory.MAIN, "scrcpy 已停止", device_serial=self.device_serial)

    def restart(self) -> bool:
        """重启 scrcpy（用于自动恢复）"""
        self.logger.info(LogCategory.MAIN, "重启 scrcpy", device_serial=self.device_serial)
        try:
            self.stop()
            self.start()
            return True
        except Exception as e:
            self.logger.error(LogCategory.MAIN, "重启 scrcpy 失败", error=str(e))
            self._cleanup_on_error()
            return False

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """
        获取最新解码帧（rgb24 格式）

        Returns:
            numpy.ndarray: 形状为 (H, W, 3) 的 RGB 图像数组，或 None（无可用帧）
        """
        # 运行时健康检查
        self._health_check()
        
        if self._last_frame is not None:
            return self._last_frame.copy()
        return None

    def _health_check(self) -> None:
        """运行时健康检查：确保 scrcpy 还在正常工作"""
        if not self._scrcpy_alive:
            return

        # 检查解码线程是否还活着
        if self._stream_loop_thread is None or not self._stream_loop_thread.is_alive():
            self.logger.warning(LogCategory.MAIN, "解码线程已停止",
                                device_serial=self.device_serial)
            self._scrcpy_alive = False
            return

        # 检查是否长时间没有收到新帧（超过 5 秒）
        if self._last_frame_time > 0 and (time.time() - self._last_frame_time) > 5.0:
            self.logger.warning(LogCategory.MAIN, "长时间未收到新帧",
                                device_serial=self.device_serial,
                                last_frame_time=self._last_frame_time)
            # 不立即停止，但记录警告

    def get_resolution(self) -> Tuple[int, int]:
        """获取设备分辨率"""
        return self._resolution

    def is_alive(self) -> bool:
        """检查 scrcpy 是否正在运行"""
        return self._scrcpy_alive and (self._stream_loop_thread is not None and self._stream_loop_thread.is_alive())

    # ==================== 内部方法 ====================

    def _server_start(self) -> None:
        """启动 scrcpy server 在设备上"""
        # 0. 清理旧进程
        self._cleanup_old_server()

        # 1. 推送 JAR
        self._push_jar()

        # 2. 执行启动命令
        self._execute_server_command()

    def _cleanup_old_server(self) -> None:
        """清理设备上旧的 scrcpy server 进程"""
        try:
            # 杀掉所有 app_process 进程（scrcpy server 运行在 app_process 中）
            self.adb_manager.shell_command(self.device_serial, "killall -9 app_process 2>/dev/null; true", timeout=5)
            # 清理本地 socket 文件
            self.adb_manager.shell_command(self.device_serial, "rm -f /data/local/tmp/scrcpy.log 2>/dev/null; true", timeout=5)
        except Exception as e:
            self.logger.debug(LogCategory.MAIN, "清理旧 server 失败", error=str(e))

    def _push_jar(self) -> None:
        """推送 scrcpy-server 到设备"""
        if not self.jar_path.exists():
            raise ScrcpyServerError(f"scrcpy-server 不存在: {self.jar_path}")

        # 统一推送到 scrcpy-server.jar（兼容不同版本）
        remote_path = "/data/local/tmp/scrcpy-server.jar"
        self.logger.info(LogCategory.MAIN, "推送 scrcpy-server 到设备",
                         device_serial=self.device_serial,
                         local_path=str(self.jar_path),
                         remote_path=remote_path)

        success = self.adb_manager.push_file(
            self.device_serial,
            str(self.jar_path),
            remote_path
        )
        if not success:
            raise ScrcpyServerError("推送 scrcpy-server 失败")

    def _execute_server_command(self) -> None:
        """在设备上执行 scrcpy server 启动命令（流式）"""
        commands = self._build_server_command()
        cmd_str = " ".join(commands)
        self.logger.debug(LogCategory.MAIN, "执行 scrcpy server 命令",
                          device_serial=self.device_serial,
                          command=cmd_str)

        try:
            # 使用 adbutils 流式 shell
            adb_client = self.adb_manager.adb
            if not adb_client:
                raise ScrcpyServerError("adbutils 客户端未初始化")

            device = adb_client.device(self.device_serial)
            self._server_stream = device.shell(commands, stream=True)

            # 不阻塞读取 server 输出，直接进入 socket 建连，由后续连接结果判断是否启动成功
            pass

            # 快速探测 server 是否已开始输出，避免过早建连
            try:
                if hasattr(self._server_stream, 'read'):
                    self._server_stream.read(64)
                elif hasattr(self._server_stream, 'recv'):
                    self._server_stream.recv(64)
            except Exception:
                pass

        except Exception as e:
            raise ScrcpyServerError(f"执行 server 命令失败: {e}") from e

    def _check_server_startup_output(self) -> None:
        """检查 server 启动输出，识别错误"""
        try:
            # 只做快速探测，避免阻塞 socket 建连
            max_retries = 2
            retry_delay = 0.1
            ret = b''

            for attempt in range(max_retries):
                try:
                    if hasattr(self._server_stream, 'read'):
                        ret = self._server_stream.read(64)
                    elif hasattr(self._server_stream, 'recv'):
                        ret = self._server_stream.recv(64)
                    else:
                        ret = b''

                    if ret:
                        break

                    if attempt < max_retries - 1:
                        pass
                except Exception:
                    if attempt < max_retries - 1:
                        pass

            if b'Aborted' in ret:
                raise ScrcpyServerError('Server aborted (可能 JAR 文件不存在)')
            if ret.startswith(b'[server] E'):
                if hasattr(self._server_stream, 'read'):
                    try:
                        ret += self._server_stream.read(1024)
                    except Exception:
                        pass
                self.logger.error(LogCategory.MAIN, f"Server error: {ret}")
                if b'does not match the client' in ret:
                    raise ScrcpyServerError('Server 版本与客户端不匹配')
                raise ScrcpyServerError('Unknown scrcpy server error')

            if ret:
                self.logger.debug(LogCategory.MAIN, f"Server startup: {ret}")
                if b'Unknown server option' in ret:
                    self.logger.warning(LogCategory.MAIN, "Server 有未知参数警告", output=ret.decode('utf-8', errors='replace'))
        except ScrcpyServerError:
            raise
        except Exception as e:
            self.logger.warning(LogCategory.MAIN, "读取 server 输出失败", error=str(e))

    def _build_server_command(self) -> list:
        """
        构建 scrcpy server v1.25 启动命令

        Returns:
            list: 命令参数列表
        """
        arguments = [
            'log_level=warn',
            'tunnel_forward=true',
            'audio=false',
            'video=true',
            'control=false',
            'show_touches=false',
            'stay_awake=true',
            'send_dummy_byte=true',
            'send_device_meta=true',
            'send_frame_meta=true',
            'max_size=1280',
            'video_bit_rate=8000000',
        ]

        commands = [
            'CLASSPATH=/data/local/tmp/scrcpy-server.jar',
            'app_process',
            '/system/bin',
            'com.genymobile.scrcpy.Server',
            '2.7',  # server 版本（与 scrcpy-server-v2.7 匹配）
        ] + arguments

        return commands

    def _build_codec_options(self) -> str:
        """
        构建编码器选项字符串

        Returns:
            str: key1=value1,key2=value2,...
        """
        options = {
            # H.264 Baseline Profile（仅 I/P 帧）
            'key_profile': 1,
            # Level 4.1，支持 1280x720@30fps
            'key_level': 4096,
            # 最高质量
            'key_quality': 100,
            # 恒定质量模式
            'key_bitrate_mode': 0,
            # 全部关键帧（零间隔）
            'key_i_frame_interval': 0,
            # 24位 BGR 格式
            'key_color_format': 12,
            # 与输出帧率相同，降低 CPU 消耗
            'key_capture_rate': self.frame_rate,
            # 码率
            'key_bit_rate': self.bitrate,
        }
        return ','.join([f'{k}={v}' for k, v in options.items()])

    def _socket_setup(self) -> None:
        """建立视频 socket 连接"""
        self.logger.info(LogCategory.MAIN, "建立 scrcpy socket 连接", device_serial=self.device_serial)

        # 设置 ADB 端口转发（tunnel_forward 模式）
        self._setup_port_forward()

        # 建立视频 socket，带快速重试，兼容 server 尚未完全准备好
        self._video_socket = self._create_video_socket(timeout=12.0)

        # 读取设备信息
        self._read_device_info()

    def _setup_port_forward(self) -> None:
        """设置 ADB 端口转发（tunnel_forward 模式）"""
        adb_client = self.adb_manager.adb
        if not adb_client:
            raise ScrcpyServerError("adbutils 客户端未初始化")

        device = adb_client.device(self.device_serial)
        # 先移除旧的端口转发
        try:
            device.forward_remove(f"tcp:{self.FORWARD_PORT}")
        except Exception:
            pass
        # 转发本地端口到设备的 abstract socket
        device.forward(f"tcp:{self.FORWARD_PORT}", "localabstract:scrcpy")
        self.logger.info(LogCategory.MAIN, "ADB 端口转发设置完成",
                         device_serial=self.device_serial,
                         port=self.FORWARD_PORT)

    def _create_video_socket(self, timeout: float = 15.0) -> socket.socket:
        """创建视频 socket 连接（通过端口转发）"""
        start_time = time.time()
        attempt = 0
        while time.time() - start_time < timeout:
            try:
                # 清理旧 socket（如果有）
                self._cleanup_socket(self._video_socket)

                # 通过 ADB 端口转发连接
                sock = socket.create_connection(("127.0.0.1", self.FORWARD_PORT), timeout=3)
                self.logger.info(LogCategory.MAIN, "视频 socket 连接成功",
                                 device_serial=self.device_serial, attempt=attempt)

                # 等待 server 开始输出，避免过早返回未就绪 socket
                try:
                    sock.settimeout(3.0)
                    ready = select.select([sock], [], [], 3.0)[0]
                    if not ready:
                        raise ScrcpyConnectionError("server 尚未开始输出")
                    peek = sock.recv(1, socket.MSG_PEEK)
                    if not peek:
                        raise ScrcpyConnectionError("server 已关闭连接")
                except Exception as e:
                    self.logger.debug(LogCategory.MAIN, "视频 socket 尚未就绪，将重试",
                                      device_serial=self.device_serial, error=str(e))
                    self._cleanup_socket(sock)
                    attempt += 1
                    continue

                return sock
            except Exception as e:
                self.logger.debug(LogCategory.MAIN, "视频 socket 连接重试",
                                  device_serial=self.device_serial,
                                  attempt=attempt, error=str(e))
                attempt += 1

        raise ScrcpyConnectionError("视频 socket 连接超时")

    def _create_control_socket(self, timeout: float = 15.0) -> socket.socket:
        """创建控制 socket 连接（通过端口转发）"""
        start_time = time.time()
        attempt = 0
        while time.time() - start_time < timeout:
            try:
                # 清理旧 socket（如果有）
                self._cleanup_socket(self._control_socket)

                # 通过 ADB 端口转发连接
                sock = socket.create_connection(("127.0.0.1", self.FORWARD_PORT), timeout=30)
                self.logger.info(LogCategory.MAIN, "控制 socket 连接成功",
                                 device_serial=self.device_serial, attempt=attempt)
                return sock
            except Exception as e:
                self.logger.debug(LogCategory.MAIN, "控制 socket 连接重试",
                                  device_serial=self.device_serial,
                                  attempt=attempt, error=str(e))
                attempt += 1

        raise ScrcpyConnectionError("控制 socket 连接超时")

    def _cleanup_socket(self, sock: Optional[socket.socket]) -> None:
        """清理 socket 连接"""
        if sock is None:
            return
        try:
            sock.close()
        except Exception:
            pass

    def _read_device_info(self) -> None:
        """从视频 socket 读取设备名称，分辨率从 ADB 获取"""
        # 临时设置为阻塞模式，确保能读取到设备名称
        old_timeout = self._video_socket.gettimeout()
        self._video_socket.settimeout(5.0)

        try:
            # scrcpy server 发送格式（当 send_dummy_byte=true, send_device_meta=true）：
            # 1 字节 dummy byte (0x00) + 64 字节设备名称
            # 如果 send_dummy_byte=false，则直接是 64 字节设备名称
            first_byte = self._video_socket.recv(1)
            if first_byte == b'\x00':
                # 跳过 dummy byte，读取 64 字节设备名称
                device_name_bytes = self._recv_exact_on_video_socket(64)
            else:
                # 没有 dummy byte，first_byte 是设备名称的第一个字节
                remaining = self._recv_exact_on_video_socket(63)
                device_name_bytes = first_byte + remaining if first_byte else b''

            device_name = device_name_bytes.decode("utf-8").rstrip("\x00") if device_name_bytes else ""
            if device_name:
                self.logger.info(LogCategory.MAIN, f"Scrcpy Device: {device_name}",
                                 device_serial=self.device_serial)
            else:
                self.logger.warning(LogCategory.MAIN, "未收到设备名称", device_serial=self.device_serial)
        except socket.timeout:
            self.logger.warning(LogCategory.MAIN, "读取设备名称超时", device_serial=self.device_serial)
        except Exception as e:
            self.logger.warning(LogCategory.MAIN, "读取设备名称失败", error=str(e))
        finally:
            # 恢复超时设置
            self._video_socket.settimeout(old_timeout)

        # 从 ADB 获取分辨率
        try:
            return_code, output = self.adb_manager.shell_command(self.device_serial, "wm size", timeout=5)
            if return_code == 0 and output:
                # 解析 "Physical size: 1080x2400" 格式
                parts = output.strip().split(":")
                if len(parts) == 2:
                    size = parts[1].strip()
                    width, height = map(int, size.split("x"))
                    self._resolution = (width, height)
                    self.logger.info(LogCategory.MAIN, f"Scrcpy Resolution: {width}x{height}",
                                     device_serial=self.device_serial)
        except Exception as e:
            self.logger.warning(LogCategory.MAIN, "获取分辨率失败", error=str(e))

        if not self._resolution or self._resolution == (0, 0):
            raise ScrcpyConnectionError("读取分辨率失败")

        # 恢复阻塞模式，避免 2 秒超时导致首包读取失败
        try:
            self._video_socket.setblocking(True)
            self._video_socket.settimeout(None)
            self.logger.info(LogCategory.MAIN, "video socket prepared: blocking=True",
                             device_serial=self.device_serial)
        except Exception as e:
            self.logger.warning(LogCategory.MAIN, f"video socket prepare failed: {e}",
                                device_serial=self.device_serial)

    def _start_stream_loop(self) -> None:
        """启动后台解码线程"""
        if not PYAV_AVAILABLE:
            raise ScrcpyDecodeError("PyAV 不可用")

        # 初始化解码器
        self._codec = CodecContext.create("h264", "r")

        # 重置首帧事件
        self._first_frame_event.clear()

        self._stream_loop_thread = threading.Thread(
            target=self._stream_loop,
            daemon=True,
            name=f"ScrcpyStream-{self.device_serial}"
        )
        self._stream_loop_thread.start()

        # 等待线程启动
        timeout = 2.0
        start = time.time()
        while time.time() - start < timeout:
            if self._stream_loop_thread.is_alive():
                self.logger.debug(LogCategory.MAIN, "解码线程已启动", device_serial=self.device_serial)
                break
        else:
            raise ScrcpyDecodeError("解码线程启动失败")

        # 缩短首帧等待，优先快速返回，由调用方按需重试/恢复
        self.logger.info(LogCategory.MAIN, "等待首帧到达（最多12秒）", device_serial=self.device_serial)
        if not self._first_frame_event.wait(timeout=12.0):
            self.logger.warning(LogCategory.MAIN, "等待首帧超时", device_serial=self.device_serial)
        else:
            self.logger.info(LogCategory.MAIN, "首帧已到达", device_serial=self.device_serial)

    def _stream_loop(self) -> None:
        """
        视频流解码循环（在后台线程运行）

        使用 scrcpy 自定义 demuxer 格式解析视频流：
        1. 4 字节 codec_id（例如 0x68323634 = "h264"）
        2. 12 字节 session header（包含分辨率）
        3. 循环读取 12 字节 packet header + packet data
        """
        self.logger.debug(LogCategory.MAIN, "解码循环开始", device_serial=self.device_serial)

        try:
            codec_id_data = self._recv_exact(4)
            if not codec_id_data:
                raise ScrcpyError("读取 codec_id 失败")
            codec_id = int.from_bytes(codec_id_data, 'big')
            self.logger.debug(LogCategory.MAIN, f"Codec ID: 0x{codec_id:08x}",
                              device_serial=self.device_serial)

            session_header = self._recv_exact(12)
            if not session_header:
                raise ScrcpyError("读取 session header 失败")

            if session_header[0] & 0x80:
                width = int.from_bytes(session_header[4:8], 'big')
                height = int.from_bytes(session_header[8:12], 'big')
                self._resolution = (width, height)
            elif session_header[8] & 0x80:
                width = int.from_bytes(session_header[0:4], 'big')
                height = int.from_bytes(session_header[4:8], 'big')
                self._resolution = (width, height)
            else:
                raise ScrcpyError("无效的 session header")

            self.logger.debug(LogCategory.MAIN, f"Session: {self._resolution[0]}x{self._resolution[1]}",
                              device_serial=self.device_serial)

            while self._scrcpy_alive:
                packet_data = self._recv_packet()
                if packet_data is None:
                    break

                try:
                    frames = self._decode_packet_data(packet_data)
                except Exception as e:
                    self.logger.warning(LogCategory.MAIN, f"解码 packet 失败: {e}",
                                        device_serial=self.device_serial)
                    continue

                for frame in frames:
                    rgb_frame = frame.to_ndarray(format="rgb24")
                    self._last_frame = rgb_frame
                    self._last_frame_time = time.time()
                    self._first_frame_event.set()
                    self.logger.debug(LogCategory.MAIN, f"解码帧: {frame.width}x{frame.height}",
                                      device_serial=self.device_serial)
                    break

                # 不退出循环，继续接收后续 packet，保持流式更新

        except Exception as e:
            self.logger.error(LogCategory.MAIN, f"解码循环异常: {e}",
                              device_serial=self.device_serial)
        except BaseException as e:
            self.logger.error(LogCategory.MAIN, f"解码循环 BaseException: {type(e).__name__}: {e}",
                              device_serial=self.device_serial)
        finally:
            self.logger.debug(LogCategory.MAIN, "解码循环结束", device_serial=self.device_serial)

    def _recv_exact_on_video_socket(self, n: int, timeout: float = 5.0) -> bytes:
        """从视频 socket 精确接收 n 字节（阻塞模式，带超时）"""
        old_timeout = self._video_socket.gettimeout()
        self._video_socket.settimeout(timeout)
        try:
            data = b''
            while len(data) < n:
                chunk = self._video_socket.recv(n - len(data))
                if not chunk:
                    raise ScrcpyConnectionError("socket 已关闭")
                data += chunk
            return data
        finally:
            self._video_socket.settimeout(old_timeout)

    def _recv_exact(self, n: int) -> Optional[bytes]:
        """精确接收 n 字节"""
        data = b''
        while len(data) < n:
            self.logger.debug(LogCategory.MAIN, f"recv_exact waiting {n-len(data)} bytes from fd={self._video_socket.fileno()} timeout={self._video_socket.gettimeout()}",
                              device_serial=self.device_serial)
            chunk = self._video_socket.recv(n - len(data))
            if not chunk:
                self.logger.warning(LogCategory.MAIN, f"socket 返回空数据，已接收 {len(data)}/{n} 字节",
                                    device_serial=self.device_serial)
                return None
            data += chunk
        self.logger.debug(LogCategory.MAIN, f"recv exact {n} bytes: {data[:64].hex()}",
                          device_serial=self.device_serial)
        return data

    def _recv_packet(self) -> Optional[bytes]:
        """接收一个 scrcpy packet（12 字节 header + data）"""
        header = self._recv_exact(12)
        if not header:
            self.logger.warning(LogCategory.MAIN, "读取 packet header 失败（socket 可能已关闭）",
                                device_serial=self.device_serial)
            return None

        packet_size = int.from_bytes(header[4:8], 'big')
        if packet_size <= 0 or packet_size > 2 * 1024 * 1024:
            self.logger.warning(LogCategory.MAIN, f"无效的 packet size: {packet_size}",
                                device_serial=self.device_serial)
            return None

        packet_data = self._recv_exact(packet_size)
        if not packet_data:
            self.logger.warning(LogCategory.MAIN, f"读取 packet data 失败，size={packet_size}",
                                device_serial=self.device_serial)
            return None

        return packet_data

    def decode_packet_data(self, packet_data: bytes):
        """
        解码单个 scrcpy packet 的 H.264 数据

        兼容 PyAV 10+ 的 packet/frame API 变化，避免旧版
        CodecContext.decode(packet) 路径在某些数据流下失效。
        """
        if not hasattr(self, "_av_packet"):
            try:
                self._av_packet = av.Packet.new(self._codec.name)
            except Exception:
                self._av_packet = None

        if self._av_packet is not None:
            try:
                self._av_packet.data = packet_data
                self._av_packet.size = len(packet_data)
                return self._codec.decode(self._av_packet)
            except Exception:
                pass

        try:
            return self._codec.decode(packet_data)
        except TypeError:
            parsed = self._codec.parse(packet_data)
            if not parsed:
                return []
            return self._codec.decode(parsed[0])
        except Exception as e:
            self.logger.warning(LogCategory.MAIN, f"解码 packet 异常: {e}", device_serial=self.device_serial)
            return []

    def _decode_packet_data(self, packet_data: bytes):
        try:
            frames = self._decode_h264_packet(packet_data)
        except Exception as e:
            self.logger.warning(LogCategory.MAIN, f"解码 packet 异常: {e}", device_serial=self.device_serial)
            frames = []
        self.logger.debug(LogCategory.MAIN, f"decode result frames={len(frames)} packet_len={len(packet_data)}", device_serial=self.device_serial)
        return frames

    @staticmethod
    def _is_avc_nalu_type(data: bytes, offset: int) -> int:
        if offset + 1 >= len(data):
            return -1
        return data[offset + 1] & 0x1F

    def _feed_nalu(self, nalu_data: bytes) -> list:
        try:
            return self._codec.decode(nalu_data)
        except TypeError:
            parsed = self._codec.parse(nalu_data)
            if not parsed:
                return []
            return self._codec.decode(parsed[0])
        except Exception as e:
            self.logger.debug(LogCategory.MAIN, f"feed nalu exception: {e} nalu_len={len(nalu_data)}", device_serial=self.device_serial)
            return []

    def _decode_h264_packet(self, packet_data: bytes) -> list:
        if not packet_data:
            return []

        # 优先整包送入解码器，减少 NALU 拆分开销
        try:
            decoded = self._feed_nalu(packet_data)
            if decoded:
                self.logger.debug(LogCategory.MAIN, f"raw decode success frames={len(decoded)}", device_serial=self.device_serial)
                return decoded
        except Exception:
            pass

        # 回退：按 Annex B start code 拆分解码
        start_code = b'\x00\x00\x00\x01'
        annex_b = start_code + packet_data
        frames: list = []
        offset = 0
        nalu_index = 0
        while True:
            next_offset = annex_b.find(start_code, offset + len(start_code))
            if next_offset == -1:
                next_offset = len(annex_b)
            nalu = annex_b[offset:next_offset]
            if nalu:
                nalu_index += 1
                decoded = self._feed_nalu(nalu)
                if decoded:
                    frames.extend(decoded)
            offset = next_offset
            if offset >= len(annex_b):
                break

        if frames:
            self.logger.debug(LogCategory.MAIN, f"nalu decode success frames={len(frames)}", device_serial=self.device_serial)
        return frames

    def _cleanup_on_error(self) -> None:
        """错误发生时的清理"""
        self.stop()

    # ==================== 控制协议 ====================

    def send_touch(self, x: int, y: int, action: int = TOUCH_ACTION_DOWN, touch_id: int = -1) -> bool:
        """
        发送触摸事件

        Args:
            x: x 坐标
            y: y 坐标
            action: 动作（DOWN=0, UP=1, MOVE=2）
            touch_id: 触摸点 ID（-1 为虚拟 ID）

        Returns:
            bool: 是否发送成功
        """
        with self._control_socket_lock:
            try:
                # 构建触摸事件二进制数据
                # 格式：action(1B) + touch_id(8B) + x(4B) + y(4B) + width(2B) + height(2B) + pressure(2B) + buttons(4B)
                width, height = self._resolution
                data = struct.pack(
                    ">BqiiHHHi",
                    action,          # 1 字节：动作
                    touch_id,        # 8 字节：触摸 ID
                    int(x),          # 4 字节：x
                    int(y),          # 4 字节：y
                    int(width),      # 2 字节：屏幕宽度
                    int(height),     # 2 字节：屏幕高度
                    0xFFFF,          # 2 字节：压力值（最大）
                    1,               # 4 字节：主按钮（1）
                )
                self._control_socket.sendall(data)
                self.logger.debug(LogCategory.MAIN, "发送触摸事件",
                                 device_serial=self.device_serial,
                                 x=x, y=y, action=action)
                return True
            except Exception as e:
                self.logger.error(LogCategory.MAIN, "发送触摸事件失败", error=str(e))
                return False

    def send_swipe(self, points: list, duration_ms: int = 300) -> bool:
        """
        发送滑动事件

        Args:
            points: 滑动路径点列表 [(x1, y1), (x2, y2), ...]
            duration_ms: 滑动总时长（毫秒）

        Returns:
            bool: 是否发送成功
        """
        if not points:
            return False

        try:
            # 计算每个点的时间间隔
            n_points = len(points)
            interval = duration_ms / 1000.0 / max(1, n_points - 1)

            # 发送 DOWN
            x0, y0 = points[0]
            if not self.send_touch(x0, y0, self.TOUCH_ACTION_DOWN):
                return False

            # 发送 MOVE
            for x, y in points[1:]:
                if not self.send_touch(x, y, self.TOUCH_ACTION_MOVE):
                    return False

            # 发送 UP
            xn, yn = points[-1]
            if not self.send_touch(xn, yn, self.TOUCH_ACTION_UP):
                return False

            self.logger.debug(LogCategory.MAIN, "发送滑动事件完成",
                             device_serial=self.device_serial,
                             point_count=n_points,
                             duration_ms=duration_ms)
            return True
        except Exception as e:
            self.logger.error(LogCategory.MAIN, "发送滑动事件失败", error=str(e))
            return False

    def send_keyevent(self, keycode: int) -> bool:
        """
        发送按键事件（通过 ADB shell 实现）

        Args:
            keycode: Android 键码

        Returns:
            bool: 是否发送成功
        """
        try:
            cmd = f"input keyevent {keycode}"
            returncode, output = self.adb_manager.shell_command(self.device_serial, cmd, timeout=10)
            success = returncode == 0
            if success:
                self.logger.debug(LogCategory.MAIN, "按键事件发送成功", keycode=keycode)
            else:
                self.logger.warning(LogCategory.MAIN, "按键事件发送失败", keycode=keycode, output=output)
            return success
        except Exception as e:
            self.logger.error(LogCategory.MAIN, "按键事件发送异常", keycode=keycode, error=str(e))
            return False
