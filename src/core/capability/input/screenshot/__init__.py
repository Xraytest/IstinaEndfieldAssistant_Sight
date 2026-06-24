"""截图模块 - 屏幕捕获功能"""

from .screen_capture import ScreenCapture
try:
    from .scrcpy_core import ScrcpyCore, ScrcpyError, ScrcpyServerError, ScrcpyConnectionError, ScrcpyDecodeError
    __all__ = ["ScreenCapture", "ScrcpyCore", "ScrcpyError", "ScrcpyServerError", "ScrcpyConnectionError", "ScrcpyDecodeError"]
except ImportError:
    __all__ = ["ScreenCapture"]
