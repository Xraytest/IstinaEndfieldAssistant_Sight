"""触控管理器 - 非 MaaTouch 通道

⚠️ 重要：此模块封装的是 adb shell input 触控（AdbShell 通道），不是 MaaTouch。
严禁作为生产任务（VisitFriends/AutoCollect 等 MaaFW pipeline 任务）的触控通道。

触控通道分工：
  - MaaFW 任务（pipeline 节点）：走 MaaEndRuntime._controller.post_click/post_swipe
    （MaaTouch 高速 socket 协议，Maatouch=4，位掩码枚举）— 在 maa_end/runtime.py
    的 _connect_once 中设置。
  - 自定义 Python 任务（runtime.py 的 _handle_*_task）：走 AndroidRuntime.tap/swipe
    → 本 TouchManager（adb shell input，fallback 通道）。
  - 严禁：把自定义 Python 任务标记为 MaaFW 任务并使用本通道。

历史：TouchManager 早于 MaaTouch 集成而存在；为兼容遗留 Python 自定义任务保留。
"""

from __future__ import annotations

import threading
from typing import Optional

from core.foundation.logger import LogCategory, get_logger


class TouchManager:
    """非 MaaTouch 通道的 fallback 触控管理器

    ⚠️ 此实现走 adb shell input（AdbShell 通道），延迟高、易被反外挂检测、
    无法被 MaaFW input_method 状态机管理。生产任务严禁使用。

    生产任务必须走 MaaTouch：MaaEndRuntime._controller.post_click/post_swipe。
    """

    def __init__(self, adb_path: str = "3rd-part/adb/adb.exe", device_address: Optional[str] = None):
        self._adb_path = adb_path
        self._device_address = device_address
        self._logger = get_logger(__name__)

    def tap(self, x: int, y: int, serial: Optional[str] = None) -> None:
        """点击屏幕坐标 — ⚠️ 走 adb shell input tap（AdbShell 通道，fallback）"""
        try:
            self._tap_adb(x, y, serial)
        except Exception as e:
            self._logger.error(LogCategory.EXECUTION, "点击失败", x=x, y=y, error=str(e))
            raise

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300, serial: Optional[str] = None) -> None:
        """滑动操作 — ⚠️ 走 adb shell input swipe（AdbShell 通道，fallback）"""
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
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls, adb_path: str = "3rd-part/adb/adb.exe", device_address: Optional[str] = None) -> "TouchManager":
        if cls._instance is None:
            with cls._lock:  # D10: 双重检查锁，避免并发首访创建多实例
                if cls._instance is None:
                    cls._instance = cls(adb_path, device_address)
        return cls._instance

    def _tap_adb(self, x: int, y: int, serial: Optional[str]) -> None:
        # ⚠️ adb shell input tap：AdbShell 通道，fallback。
        # 生产任务必须走 MaaTouch：MaaEndRuntime._controller.post_click(x, y)。
        import subprocess
        args = self._adb_base_args(serial) + ["shell", "input", "tap", str(x), str(y)]
        subprocess.check_output(args, timeout=10)

    def _swipe_adb(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int, serial: Optional[str]) -> None:
        # ⚠️ adb shell input swipe：AdbShell 通道，fallback。
        # 生产任务必须走 MaaTouch：MaaEndRuntime._controller.post_swipe(x1,y1,x2,y2,duration)。
        import subprocess
        args = self._adb_base_args(serial) + [
            "shell", "input", "swipe",
            str(x1), str(y1), str(x2), str(y2), str(duration_ms),
        ]
        subprocess.check_output(args, timeout=10)
