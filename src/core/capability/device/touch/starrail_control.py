"""
StarRailCopilot 触控方法集 - 简化移植
提供多种触控方式的框架和基础实现

注意：此类设计为 Mixin，需配合 ADBDeviceManager 和 logger 使用
"""
import subprocess
from typing import Optional, Tuple, Any

from core.foundation.logger import get_logger, LogCategory

try:
    from adbutils import AdbError
    ADBUTILS_AVAILABLE = True
except ImportError:
    ADbutils = None


class StarRailControlMixin:
    """
    StarRailCopilot 触控方法 Mixin

    提供多种触控方式：
    - ADB: 通过 shell input 命令
    - minitouch: 通过 socket 连接 minitouch 服务
    - scrcpy: 通过 scrcpy control socket
    - nemu_ipc: MuMu IPC 共享内存
    - hermit: Hermit 触控

    需在宿主类中提供：
    - self.adb_manager: ADBDeviceManager 实例
    - self.config: 配置对象
    - self.logger: 日志器
    - self.device_serial: 设备序列号
    """

    # ==================== ADB 触控（基础保障）====================

    def click_adb(self, x: int, y: int) -> bool:
        """
        ADB 点击

        Args:
            x, y: 坐标

        Returns:
            bool: 是否成功
        """
        try:
            cmd = f"input tap {x} {y}"
            returncode, output = self.adb_manager.shell_command(self.device_serial, cmd, timeout=5)

            if returncode == 0:
                self.logger.debug(LogCategory.MAIN, "ADB 点击成功", x=x, y=y)
                return True
            else:
                self.logger.error(LogCategory.MAIN, "ADB 点击失败", x=x, y=y, output=output)
                return False

        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "ADB 点击异常", x=x, y=y, error=str(e))
            return False

    def swipe_adb(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        """
        ADB 滑动

        Args:
            x1, y1: 起点
            x2, y2: 终点
            duration: 时长（毫秒）

        Returns:
            bool: 是否成功
        """
        try:
            cmd = f"input swipe {x1} {y1} {x2} {y2} {duration}"
            returncode, output = self.adb_manager.shell_command(self.device_serial, cmd, timeout=5)

            if returncode == 0:
                self.logger.debug(LogCategory.MAIN, "ADB 滑动成功",
                                x1=x1, y1=y1, x2=x2, y2=y2, duration=duration)
                return True
            else:
                self.logger.error(LogCategory.MAIN, "ADB 滑动失败",
                                x1=x1, y1=y1, x2=x2, y2=y2, output=output)
                return False

        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "ADB 滑动异常", error=str(e))
            return False

    def long_press_adb(self, x: int, y: int, duration: int = 1000) -> bool:
        """
        ADB 长按

        Args:
            x, y: 坐标
            duration: 时长（毫秒）

        Returns:
            bool: 是否成功
        """
        # 使用 swipe 实现长按
        return self.swipe_adb(x, y, x, y, duration)

    # ==================== Minitouch 触控（简化版）====================

    def click_minitouch(self, x: int, y: int) -> bool:
        """
        Minitouch 点击（简化实现，回退到 ADB）

        Args:
            x, y: 坐标

        Returns:
            bool: 是否成功
        """
        self.logger.debug(LogCategory.MAIN, "minitouch 点击未完全实现，回退到 ADB")
        return self.click_adb(x, y)

    def swipe_minitouch(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> bool:
        """
        Minitouch 滑动（简化实现，回退到 ADB）

        Args:
            p1: 起点 (x, y)
            p2: 终点 (x, y)

        Returns:
            bool: 是否成功
        """
        self.logger.debug(LogCategory.MAIN, "minitouch 滑动未完全实现，回退到 ADB")
        return self.swipe_adb(p1[0], p1[1], p2[0], p2[1], 300)

    def long_press_minitouch(self, x: int, y: int, duration: int = 1000) -> bool:
        """
        Minitouch 长按（简化实现，回退到 ADB）

        Args:
            x, y: 坐标
            duration: 时长（毫秒）

        Returns:
            bool: 是否成功
        """
        self.logger.debug(LogCategory.MAIN, "minitouch 长按未完全实现，回退到 ADB")
        return self.long_press_adb(x, y, duration)

    # ==================== Scrcpy 触控（框架）====================

    def click_scrcpy(self, x: int, y: int) -> bool:
        """
        Scrcpy 点击（需要 scrcpy control socket）

        Args:
            x, y: 坐标

        Returns:
            bool: 是否成功
        """
        self.logger.warning(LogCategory.MAIN, "scrcpy 触控未实现，回退到 ADB")
        return self.click_adb(x, y)

    def swipe_scrcpy(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> bool:
        """
        Scrcpy 滑动

        Args:
            p1: 起点
            p2: 终点

        Returns:
            bool: 是否成功
        """
        self.logger.warning(LogCategory.MAIN, "scrcpy 滑动未实现，回退到 ADB")
        return self.swipe_adb(p1[0], p1[1], p2[0], p2[1], 300)

    def drag_scrcpy(self, p1: Tuple[int, int], p2: Tuple[int, int], point_random: Tuple[int, int] = (-10, -10, 10, 10)) -> bool:
        """
        Scrcpy 拖拽

        Args:
            p1: 起点
            p2: 终点
            point_random: 随机偏移范围 (x_min, y_min, x_max, y_max)

        Returns:
            bool: 是否成功
        """
        self.logger.warning(LogCategory.MAIN, "scrcpy 拖拽未实现，回退到 ADB")
        return self.swipe_adb(p1[0], p1[1], p2[0], p2[1], 400)

    # ==================== nemu_ipc 触控（框架）====================

    def click_nemu_ipc(self, x: int, y: int) -> bool:
        """MuMu IPC 点击"""
        self.logger.warning(LogCategory.MAIN, "nemu_ipc 触控未实现，回退到 ADB")
        return self.click_adb(x, y)

    def swipe_nemu_ipc(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> bool:
        """MuMu IPC 滑动"""
        self.logger.warning(LogCategory.MAIN, "nemu_ipc 滑动未实现，回退到 ADB")
        return self.swipe_adb(p1[0], p1[1], p2[0], p2[1], 300)

    def drag_nemu_ipc(self, p1: Tuple[int, int], p2: Tuple[int, int], point_random: Tuple[int, int] = (-10, -10, 10, 10)) -> bool:
        """MuMu IPC 拖拽"""
        self.logger.warning(LogCategory.MAIN, "nemu_ipc 拖拽未实现，回退到 ADB")
        return self.swipe_adb(p1[0], p1[1], p2[0], p2[1], 400)

    # ==================== Hermit 触控（框架）====================

    def click_hermit(self, x: int, y: int) -> bool:
        """Hermit 点击"""
        self.logger.warning(LogCategory.MAIN, "Hermit 触控未实现，回退到 ADB")
        return self.click_adb(x, y)

    def swipe_hermit(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> bool:
        """Hermit 滑动"""
        self.logger.warning(LogCategory.MAIN, "Hermit 滑动未实现，回退到 ADB")
        return self.swipe_adb(p1[0], p1[1], p2[0], p2[1], 300)

    def drag_hermit(self, p1: Tuple[int, int], p2: Tuple[int, int], point_random: Tuple[int, int] = (-10, -10, 10, 10)) -> bool:
        """Hermit 拖拽"""
        self.logger.warning(LogCategory.MAIN, "Hermit 拖拽未实现，回退到 ADB")
        return self.swipe_adb(p1[0], p1[1], p2[0], p2[1], 400)

    # ==================== 工具方法 ====================

    def safe_press(self, x: int, y: int, duration: int = 50) -> bool:
        """
        安全点击（带抖动）

        Args:
            x, y: 坐标
            duration: 按压时长（毫秒）

        Returns:
            bool: 是否成功
        """
        # 读取抖动配置
        jitter = self.config.get('touch', {}).get('press_jitter_px', 0)

        actual_x = x
        actual_y = y

        if jitter > 0:
            import random
            actual_x += random.randint(-jitter, jitter)
            actual_y += random.randint(-jitter, jitter)

        return self.click_adb(actual_x, actual_y)

    def safe_swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        """
        安全滑动

        Args:
            x1, y1: 起点
            x2, y2: 终点
            duration: 滑动时长（毫秒）

        Returns:
            bool: 是否成功
        """
        # 滑动距离检查
        import math
        distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        if distance < 10:
            self.logger.debug(LogCategory.MAIN, "滑动距离过小，跳过", distance=distance)
            return True  # 视为成功

        return self.swipe_adb(x1, y1, x2, y2, duration)

    def safe_long_press(self, x: int, y: int, duration: int = 1000) -> bool:
        """
        安全长按

        Args:
            x, y: 坐标
            duration: 长按时长（毫秒）

        Returns:
            bool: 是否成功
        """
        return self.long_press_adb(x, y, duration)