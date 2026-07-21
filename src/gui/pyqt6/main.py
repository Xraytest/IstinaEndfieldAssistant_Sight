from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure src/ is importable before importing core.* / gui.* modules.
# main.py is at src/gui/pyqt6/main.py; src/ is three parents up.
_SRC_DIR = Path(__file__).resolve().parent.parent.parent
_src_str = str(_SRC_DIR)
if _src_str not in sys.path:
    sys.path.insert(0, _src_str)

# 方案 A2：在 import core.*/gui.* 之前注入 MAAFW_BINARY_PATH，确保 GUI 主进程
# 及其 QProcess 启动的 CLI 子进程（自动继承父进程环境变量）都加载项目自带的
# MaaFramework.dll（与 3rd-part/maaend/resource 版本匹配）。详见 incident 报告
# 2026-07-21_adb_connected_false_multi_cause_analysis.md 方案 A。
_MAAFW_DLL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "3rd-part" / "maaend" / "agent" / "maafw"
if _MAAFW_DLL_DIR.is_dir() and os.environ.get("MAAFW_BINARY_PATH") is None:
    os.environ["MAAFW_BINARY_PATH"] = str(_MAAFW_DLL_DIR.resolve())

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
    # 多实例支持：解析 --instance 启动参数（仅决定启动时的初始活动实例）
    # 默认从 IEA_INSTANCE 环境变量读取，再回退到 "default"
    import os
    from core.foundation.instance import set_instance_id
    initial_instance = "default"
    args = sys.argv[1:]
    if "--instance" in args:
        idx = args.index("--instance")
        if idx + 1 < len(args):
            initial_instance = args[idx + 1]
    elif os.environ.get("IEA_INSTANCE"):
        initial_instance = os.environ["IEA_INSTANCE"]
    try:
        set_instance_id(initial_instance)
    except ValueError as exc:
        sys.stderr.write(f"[IEA] 实例 id 非法: {exc}\n")
        sys.exit(2)

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
