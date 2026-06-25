"""
Scrcpy 视频流核心实现 - 基于 StarRailCopilot 设计
使用 scrcpy-server v1.25 + PyAV 解码，提供低延迟持续视频流
"""
import os
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
    from av.codec import CodecContext
    from av.error import InvalidDataError
    PYAV_AVAILABLE = True
except ImportError:
    PYAV_AVAILABLE = False

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

        # 解码器
        self._codec: Optional[CodecContext] = None

        # 检查依赖
        if not PYAV_AVAILABLE:
            raise ScrcpyDecodeError("PyAV 库未安装，请安装 PyAV>=10.0.0")
        if not ADBUTILS_AVAILABLE:
            raise ScrcpyServerError("adbutils 未安装，请安装 adbutils>=0.15.0")

    def _get_jar_path(self) -> Path:
        """获取 scrcpy-server.jar 路径"""
        project_root = Path(__file__).resolve()
        # 向上回溯到项目根目录：src/core/capability/input/screenshot/scrcpy_core.py
        # 需要回溯 6 层：screenshot -> input -> capability -> core -> src -> project_root
        for _ in range(6):
            project_root = project_root.parent
        jar_path = project_root / "3rd-part" / "scrcpy" / "scrcpy-server.jar"
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
            self._start_stream_loop()
            self._scrcpy_alive = True

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
            time.sleep(1.0)
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
        # 1. 推送 JAR
        self._push_jar()

        # 2. 执行启动命令
        self._execute_server_command()

    def _push_jar(self) -> None:
        """推送 scrcpy-server.jar 到设备"""
        if not self.jar_path.exists():
            raise ScrcpyServerError(f"scrcpy-server.jar 不存在: {self.jar_path}")

        self.logger.info(LogCategory.MAIN, "推送 scrcpy-server.jar 到设备",
                         device_serial=self.device_serial,
                         remote_path="/data/local/tmp/scrcpy-server.jar")

        success = self.adb_manager.push_file(
            self.device_serial,
            str(self.jar_path),
            "/data/local/tmp/scrcpy-server.jar"
        )
        if not success:
            raise ScrcpyServerError("推送 scrcpy-server.jar 失败")

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

            # 设置超时（增加超时时间，确保 MuMu 等模拟器有足够时间启动）
            stream_timeout = 10.0
            if hasattr(self._server_stream, 'conn'):
                self._server_stream.conn.settimeout(stream_timeout)
            elif hasattr(self._server_stream, 'socket'):
                self._server_stream.socket.settimeout(stream_timeout)

            # 读取初始输出，检查错误（增加重试和等待）
            self._check_server_startup_output()

        except Exception as e:
            raise ScrcpyServerError(f"执行 server 命令失败: {e}") from e

    def _check_server_startup_output(self) -> None:
        """检查 server 启动输出，识别错误"""
        try:
            # 读取初始字节（增加重试，确保 server 完全启动）
            max_retries = 5
            retry_delay = 0.5
            ret = b''
            
            for attempt in range(max_retries):
                try:
                    if hasattr(self._server_stream, 'read'):
                        ret = self._server_stream.read(10)
                    elif hasattr(self._server_stream, 'recv'):
                        ret = self._server_stream.recv(10)
                    else:
                        ret = b''
                    
                    if ret:
                        break
                    
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                    else:
                        raise

            # 检查错误
            if b'Aborted' in ret:
                raise ScrcpyServerError('Server aborted (可能 JAR 文件不存在)')
            if ret == b'[server] E':
                # 读取完整错误信息
                if hasattr(self._server_stream, 'read'):
                    ret += self._server_stream.read(4096)
                self.logger.error(f"Server error: {ret}")
                if b'does not match the client' in ret:
                    raise ScrcpyServerError('Server 版本与客户端不匹配')
                else:
                    raise ScrcpyServerError('Unknown scrcpy server error')
            else:
                # 读取并记录 INFO 信息
                if hasattr(self._server_stream, 'read'):
                    try:
                        ret += self._server_stream.read(1024)
                    except Exception:
                        pass
                self.logger.info(f"Server startup: {ret}")

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
        # 使用 v1.25 命令格式
        codec_options = self._build_codec_options()
        arguments = [
            'log_level=info',
            f'max_size={self.max_resolution}',
            f'bit_rate={self.bitrate}',
            f'max_fps={self.frame_rate}',
            'lock_video_orientation=-1',  # 无方向锁定
            'tunnel_forward=true',
            'control=true',
            'display_id=0',
            'show_touches=false',
            'stay_awake=false',
            f'codec_options={codec_options}',
            'power_off_on_close=false',
            'clipboard_autosync=false',
            'downsize_on_error=false',
        ]

        commands = [
            'CLASSPATH=/data/local/tmp/scrcpy-server.jar',
            'app_process',
            '/',
            'com.genymobile.scrcpy.Server',
            '1.25',  # server 版本
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
        """建立视频和控制 socket 连接"""
        self.logger.info(LogCategory.MAIN, "建立 scrcpy socket 连接", device_serial=self.device_serial)

        # 等待 server 完全启动（MuMu 等模拟器可能需要更长时间）
        time.sleep(1.0)

        # 建立视频 socket
        self._video_socket = self._create_video_socket()
        # 建立控制 socket
        self._control_socket = self._create_control_socket()

        # 读取设备信息
        self._read_device_info()

    def _create_video_socket(self, timeout: float = 15.0) -> socket.socket:
        """创建视频 socket 连接"""
        start_time = time.time()
        attempt = 0
        while time.time() - start_time < timeout:
            try:
                # 清理旧 socket（如果有）
                self._cleanup_socket(self._video_socket)
                
                # 使用 adbutils 的 create_connection
                # LOCAL_ABSTRACT = 1 (abstract namespace)
                sock = self.adb_manager.create_connection(
                    self.device_serial,
                    1,  # AdbNetwork.LOCAL_ABSTRACT
                    "scrcpy"
                )
                sock.settimeout(15.0)
                self.logger.info(LogCategory.MAIN, "视频 socket 连接成功",
                                 device_serial=self.device_serial, attempt=attempt)
                return sock
            except Exception as e:
                self.logger.debug(LogCategory.MAIN, "视频 socket 连接重试",
                                  device_serial=self.device_serial,
                                  attempt=attempt, error=str(e))
                time.sleep(0.5)
                attempt += 1

        raise ScrcpyConnectionError("视频 socket 连接超时")

    def _create_control_socket(self, timeout: float = 15.0) -> socket.socket:
        """创建控制 socket 连接"""
        start_time = time.time()
        attempt = 0
        while time.time() - start_time < timeout:
            try:
                # 清理旧 socket（如果有）
                self._cleanup_socket(self._control_socket)
                
                sock = self.adb_manager.create_connection(
                    self.device_serial,
                    1,  # AdbNetwork.LOCAL_ABSTRACT
                    "scrcpy"
                )
                sock.settimeout(15.0)
                self.logger.info(LogCategory.MAIN, "控制 socket 连接成功",
                                 device_serial=self.device_serial, attempt=attempt)
                return sock
            except Exception as e:
                self.logger.debug(LogCategory.MAIN, "控制 socket 连接重试",
                                  device_serial=self.device_serial,
                                  attempt=attempt, error=str(e))
                time.sleep(0.5)
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
        """从视频 socket 读取设备名称和分辨率"""
        # 读取设备名称（64 字节）
        device_name_bytes = self._video_socket.recv(64)
        device_name = device_name_bytes.decode("utf-8").rstrip("\x00")
        if device_name:
            self.logger.attr('Scrcpy Device', device_name)
        else:
            self.logger.warning(LogCategory.MAIN, "未收到设备名称", device_serial=self.device_serial)

        # 读取分辨率（4 字节，大端序）
        resolution_bytes = self._video_socket.recv(4)
        if len(resolution_bytes) == 4:
            width, height = struct.unpack(">HH", resolution_bytes)
            self._resolution = (width, height)
            self.logger.attr('Scrcpy Resolution', self._resolution)
        else:
            raise ScrcpyConnectionError("读取分辨率失败")

        # 设置视频 socket 为非阻塞模式
        self._video_socket.setblocking(False)

    def _start_stream_loop(self) -> None:
        """启动后台解码线程"""
        if not PYAV_AVAILABLE:
            raise ScrcpyDecodeError("PyAV 不可用")

        # 初始化解码器
        self._codec = CodecContext.create("h264", "r")

        self._stream_loop_thread = threading.Thread(
            target=self._stream_loop,
            daemon=True,
            name=f"ScrcpyStream-{self.device_serial}"
        )
        self._stream_loop_thread.start()

        # 等待线程启动
        timeout = 3.0
        start = time.time()
        while time.time() - start < timeout:
            if self._stream_loop_thread.is_alive():
                self.logger.debug(LogCategory.MAIN, "解码线程已启动", device_serial=self.device_serial)
                return
            time.sleep(0.01)

        raise ScrcpyDecodeError("解码线程启动失败")

    def _stream_loop(self) -> None:
        """
        视频流解码循环（在后台线程运行）

        持续从 video socket 读取 H.264 数据，解码为 RGB 帧
        """
        self.logger.debug(LogCategory.MAIN, "解码循环开始", device_serial=self.device_serial)

        consecutive_errors = 0
        max_consecutive_errors = 5

        while self._scrcpy_alive:
            try:
                # 读取 H.264 数据（最多 64KB）
                raw_h264 = self._video_socket.recv(0x10000)

                if raw_h264 == b"":
                    if self._scrcpy_alive:
                        raise ScrcpyError("视频流断开连接")
                    break

                # 解析和解码
                packets = self._codec.parse(raw_h264)
                for packet in packets:
                    frames = self._codec.decode(packet)
                    for frame in frames:
                        # 转换为 RGB numpy 数组
                        rgb_frame = frame.to_ndarray(format="rgb24")
                        self._last_frame = rgb_frame
                        self._last_frame_time = time.time()
                        # 更新分辨率（可能因设备旋转而变化）
                        self._resolution = (frame.width, frame.height)

                # 重置错误计数
                consecutive_errors = 0

            except (BlockingIOError, InvalidDataError):
                # 非阻塞模式下无数据，或无效数据
                time.sleep(0.001)
                consecutive_errors += 1
            except (ConnectionError, OSError) as e:
                if self._scrcpy_alive:
                    self.logger.error(LogCategory.MAIN, f"视频流 socket 错误: {e}",
                                      device_serial=self.device_serial)
                    # 尝试恢复连接
                    if consecutive_errors < max_consecutive_errors:
                        self.logger.warning(LogCategory.MAIN, "尝试恢复视频流连接",
                                            device_serial=self.device_serial)
                        time.sleep(1.0)
                        consecutive_errors += 1
                        continue
                    raise ScrcpyConnectionError(f"Socket 错误: {e}") from e
                break
            except Exception as e:
                self.logger.error(LogCategory.MAIN, f"解码循环异常: {e}",
                                  device_serial=self.device_serial)
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    raise ScrcpyDecodeError(f"解码失败: {e}") from e
                time.sleep(0.5)

        self.logger.debug(LogCategory.MAIN, "解码循环结束", device_serial=self.device_serial)

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
                time.sleep(interval)

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
