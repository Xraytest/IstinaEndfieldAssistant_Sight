"""触控模块 - MaaFramework 触控集成"""

from .touch_manager import TouchManager, TouchDeviceType
from .maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig

__all__ = [
    'TouchManager',
    'TouchDeviceType',
    'MaaFwTouchExecutor',
    'MaaFwTouchConfig'
]
