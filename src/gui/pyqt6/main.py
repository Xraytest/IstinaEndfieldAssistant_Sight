from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is importable before importing core.* / gui.* modules.
# main.py is at src/gui/pyqt6/main.py; src/ is three parents up.
_SRC_DIR = Path(__file__).resolve().parent.parent.parent
_src_str = str(_SRC_DIR)
if _src_str not in sys.path:
    sys.path.insert(0, _src_str)

from PyQt6.QtWidgets import QApplication

from core.foundation.paths import ensure_src_path
from gui.pyqt6.main_window import MainWindow
from gui.pyqt6.theme.theme_manager import apply_theme

ensure_src_path(__file__)


def run_application() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("IstinaEndfieldAssistant")
    app.setQuitOnLastWindowClosed(True)

    # Apply Endfield industrial sci-fi theme (dark + terminal cyan).
    apply_theme(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_application()