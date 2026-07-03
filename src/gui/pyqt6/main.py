from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from core.foundation.paths import ensure_src_path
from gui.pyqt6.main_window import MainWindow

ensure_src_path(__file__)


def run_application() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("IstinaEndfieldAssistant")
    app.setQuitOnLastWindowClosed(True)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_application()
