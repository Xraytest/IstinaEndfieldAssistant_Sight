"""截图模块 - 最简实现

提供基于 ADB 的截图能力。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from core.foundation.logger import get_logger, LogCategory


class ScreenCapture:
    """最简截图管理器

    基于 ADB screencap 实现，可后续扩展 scrcpy / MAA 截图通道。
    """

    def __init__(self, adb_manager):
        self._adb_manager = adb_manager
        self._logger = get_logger(__name__)

    def capture(self, serial: Optional[str] = None) -> Optional[bytes]:
        """执行一次截图，返回 PNG 二进制数据"""
        try:
            return self._adb_manager.screencap(serial=serial)
        except Exception as e:
            self._logger.error(LogCategory.EXECUTION, "截图失败", error=str(e))
            return None
