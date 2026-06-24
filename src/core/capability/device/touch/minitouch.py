"""
Minitouch 触控执行器 - 简化实现
通过 ADB shell input 命令实现基本触控功能
"""
import socket
import struct
import time
from typing import Optional, Tuple, Any

from core.foundation.logger import get_logger, LogCategory
from core.capability.device.adb_manager import ADBDeviceManager


class MinitouchError(Exception):
    """Minitouch 相关错误"""
    pass


class MinitouchExecutor:
    """
    Minitouch 执行器（简化版）

    注意：完整 minitouch 需要设备上运行 minitouch 服务并通过 socket 通信。
    此处使用 ADB shell input 命令作为简化实现，保证兼容性。

    未来可扩展为真实的 minitouch socket 连接。
    """

    def __init__(self, adb_manager: ADBDeviceManager, device_serial: str, config: dict = None):
        """
        初始化 Minitouch 执行器

        Args:
            adb_manager: ADB 设备管理器
            device_serial: 设备序列号
            config: 配置字典，可包含：
                - port: minitouch 服务端口（默认 1111）
                - use_socket: 是否使用 socket 连接（False=使用 ADB shell）
        """
        self.adb_manager = adb_manager
        self.device_serial = device_serial
        self.config = config or {}
        self.logger = get_logger()

        # 配置参数
        self.port = self.config.get('port', 1111)
        self.use_socket = self.config.get('use_socket', False)  # 简化：默认使用 ADB shell

        # 连接状态
        self._connected = False
        self._socket = None

    def connect(self) -> bool:
        """
        连接设备

        Returns:
            bool: 是否连接成功
        """
        try:
            if self.use_socket:
                # TODO: 实现真实的 minitouch socket 连接
                self.logger.warning(LogCategory.MAIN, "Minitouch socket 模式未实现，回退到 ADB shell")
                self.use_socket = False

            # 使用 ADB shell 方式，无需特殊连接
            self._connected = True
            self.logger.info(LogCategory.MAIN, "Minitouch 连接成功（ADB shell 模式）",
                            device_serial=self.device_serial)
            return True

        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "Minitouch 连接失败", error=str(e))
            return False

    def disconnect(self) -> bool:
        """
        断开连接

        Returns:
            bool: 是否断开成功
        """
        try:
            if self._socket:
                self._socket.close()
                self._socket = None

            self._connected = False
            self.logger.info(LogCategory.MAIN, "Minitouch 已断开", device_serial=self.device_serial)
            return True
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "Minitouch 断开异常", error=str(e))
            return False

    def click(self, x: int, y: int) -> bool:
        """
        点击

        Args:
            x, y: 坐标

        Returns:
            bool: 是否成功
        """
        if not self._connected:
            self.logger.error(LogCategory.MAIN, "设备未连接")
            return False

        try:
            # 使用 ADB shell input tap
            cmd = f"input tap {x} {y}"
            returncode, output = self.adb_manager.shell_command(self.device_serial, cmd, timeout=5)

            if returncode == 0:
                self.logger.debug(LogCategory.MAIN, "点击成功", x=x, y=y)
                return True
            else:
                self.logger.error(LogCategory.MAIN, "点击失败", x=y, y=y, output=output)
                return False

        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "点击异常", x=x, y=y, error=str(e))
            return False

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        """
        滑动

        Args:
            x1, y1: 起点坐标
            x2, y2: 终点坐标
            duration: 滑动时长（毫秒）

        Returns:
            bool: 是否成功
        """
        if not self._connected:
            self.logger.error(LogCategory.MAIN, "设备未连接")
            return False

        try:
            # 使用 ADB shell input swipe
            # 注意：duration 单位是毫秒，但 ADB 输入可能期望其他单位，先按毫秒传
            cmd = f"input swipe {x1} {y1} {x2} {y2} {duration}"
            returncode, output = self.adb_manager.shell_command(self.device_serial, cmd, timeout=5)

            if returncode == 0:
                self.logger.debug(LogCategory.MAIN, "滑动成功",
                                x1=x1, y1=y1, x2=x2, y2=y2, duration=duration)
                return True
            else:
                self.logger.error(LogCategory.MAIN, "滑动失败",
                                x1=x1, y1=y1, x2=x2, y2=y2, output=output)
                return False

        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "滑动异常",
                                 x1=x1, y1=y1, x2=x2, y2=y2, error=str(e))
            return False

    def long_press(self, x: int, y: int, duration: int = 1000) -> bool:
        """
        长按

        Args:
            x, y: 坐标
            duration: 长按时长（毫秒）

        Returns:
            bool: 是否成功
        """
        if not self._connected:
            self.logger.error(LogCategory.MAIN, "设备未连接")
            return False

        try:
            # 使用 swipe 实现长按：起点终点相同，duration 为按压时长
            return self.swipe(x, y, x, y, duration)
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "长按异常", x=x, y=y, error=str(e))
            return False

    def screencap(self) -> Optional[Any]:
        """
        截图（返回 numpy 数组）

        Returns:
            numpy.ndarray 或 None
        """
        if not self._connected:
            self.logger.error(LogCategory.MAIN, "设备未连接")
            return None

        try:
            # 使用 ADB exec-out screencap
            cmd = [self.adb_manager.adb_path, "-s", self.device_serial, "exec-out", "screencap", "-p"]
            result = subprocess.run(cmd, capture_output=True, timeout=5)

            if result.returncode != 0:
                self.logger.error(LogCategory.MAIN, "截图失败", returncode=result.returncode)
                return None

            png_data = result.stdout
            if not png_data.startswith(b'\x89PNG\r\n\x1a\n'):
                self.logger.error(LogCategory.MAIN, "截图数据无效")
                return None

            # 转换为 numpy 数组
            import cv2
            import numpy as np
            image = cv2.imdecode(np.frombuffer(png_data, np.uint8), cv2.IMREAD_COLOR)
            return image

        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "截图异常", error=str(e))
            return None

    def get_resolution(self) -> Tuple[int, int]:
        """
        获取设备分辨率

        Returns:
            (width, height)
        """
        try:
            return self.adb_manager.get_device_resolution(self.device_serial)
        except Exception as e:
            self.logger.warning(LogCategory.MAIN, "获取分辨率失败", error=str(e))
            return 0, 0