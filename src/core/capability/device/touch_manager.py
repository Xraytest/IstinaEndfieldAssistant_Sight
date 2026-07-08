"""触控管理器 - 最简实现

提供基于 ADB 的 tap/swipe 输入能力。
"""

from __future__ import annotations

from typing import Optional

from core.foundation.logger import LogCategory, get_logger


class TouchManager:
    """最简触控管理器

    默认使用 ADB 输入事件，可后续扩展 MaaTouch / scrcpy 控制通道。
    """

    def __init__(self, adb_path: str = "3rd-part/adb/adb.exe", device_address: Optional[str] = None):
        self._adb_path = adb_path
        self._device_address = device_address
        self._logger = get_logger(__name__)

    def tap(self, x: int, y: int, serial: Optional[str] = None) -> None:
        """点击屏幕坐标"""
        try:
            self._tap_adb(x, y, serial)
        except Exception as e:
            self._logger.error(LogCategory.EXECUTION, "点击失败", x=x, y=y, error=str(e))
            raise

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300, serial: Optional[str] = None) -> None:
        """滑动操作"""
        try:
            self._swipe_adb(x1, y1, x2, y2, duration_ms, serial)
        except Exception as e:
            self._logger.error(LogCategory.EXECUTION, "滑动失败", x1=x1, y1=y1, x2=x2, y2=y2, error=str(e))
            raise

    def _adb_base_args(self, serial: Optional[str]) -> list:
        args = [self._adb_path]
        if serial:
            args += ["-s", serial]
        return args

    def long_press(self, x: int, y: int, duration_ms: int = 1000, serial: Optional[str] = None) -> None:
        try:
            self._swipe_adb(x, y, x, y, duration_ms, serial)
        except Exception as e:
            self._logger.error(LogCategory.EXECUTION, "长按失败", x=x, y=y, error=str(e))
            raise

    def back(self, serial: Optional[str] = None) -> None:
        import subprocess
        args = self._adb_base_args(serial) + ["shell", "input", "keyevent", "KEYCODE_BACK"]
        subprocess.check_output(args, timeout=10)

    _instance = None

    @classmethod
    def get_instance(cls, adb_path: str = "3rd-part/adb/adb.exe", device_address: Optional[str] = None) -> "TouchManager":
        if cls._instance is None:
            cls._instance = cls(adb_path, device_address)
        return cls._instance

    def _tap_adb(self, x: int, y: int, serial: Optional[str]) -> None:
        import subprocess
        args = self._adb_base_args(serial) + ["shell", "input", "tap", str(x), str(y)]
        subprocess.check_output(args, timeout=10)

    def _swipe_adb(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int, serial: Optional[str]) -> None:
        import subprocess
        args = self._adb_base_args(serial) + [
            "shell", "input", "swipe",
            str(x1), str(y1), str(x2), str(y2), str(duration_ms),
        ]
        subprocess.check_output(args, timeout=10)
