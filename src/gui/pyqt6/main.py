from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is importable before importing core.* / gui.* modules.
# main.py is at src/gui/pyqt6/main.py; src/ is three parents up.
_SRC_DIR = Path(__file__).resolve().parent.parent.parent
_src_str = str(_SRC_DIR)
if _src_str not in sys.path:
    sys.path.insert(0, _src_str)

from PyQt6.QtGui import QFont, QPixmapCache  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.foundation.paths import ensure_src_path  # noqa: E402
from gui.pyqt6.i18n import get_locale_manager  # noqa: E402
from gui.pyqt6.main_window import MainWindow  # noqa: E402
from gui.pyqt6.qt_log_filter import install_qt_message_filter  # noqa: E402
from gui.pyqt6.theme.theme_manager import apply_theme  # noqa: E402

ensure_src_path(__file__)

# 必须在 QApplication() 之前接管 Qt 日志，否则最早的字体探测噪声已打印到 stderr
install_qt_message_filter()

# 性能优化：全局 QFont 缓存，避免重复创建等价 QFont 对象
_FONT_CACHE: dict = {}


def get_cached_font(family: str = "Microsoft YaHei UI", point_size: int = -1, bold: bool = False) -> QFont:
    """获取缓存的 QFont 实例。QFont 隐式共享，缓存键值命中时零构造开销。"""
    key = (family, point_size, bold)
    f = _FONT_CACHE.get(key)
    if f is None:
        f = QFont(family)
        if point_size > 0:
            f.setPointSize(point_size)
        f.setBold(bold)
        _FONT_CACHE[key] = f
    return f


def run_application() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("IstinaEndfieldAssistant")
    app.setQuitOnLastWindowClosed(True)

    # 性能优化：扩大 QPixmapCache 上限到 100MB（默认 100KB 过小，
    # 频繁 scaled pixmap 会反复淘汰复用，导致重新生成）
    QPixmapCache.setCacheLimit(102400)

    get_locale_manager().load_saved_locale()
    get_locale_manager().install_qt_translator(app)

    apply_theme(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_application()
