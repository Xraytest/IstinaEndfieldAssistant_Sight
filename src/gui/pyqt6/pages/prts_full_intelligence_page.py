from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.theme.hero import HeroHeader


locale = get_locale_manager()


class PrtsFullIntelligencePage(QWidget):
    def __init__(self, bridge: CLIBridge, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._bridge = bridge
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        content_root = QVBoxLayout(content)
        content_root.setContentsMargins(16, 16, 16, 16)
        content_root.setSpacing(10)

        header = HeroHeader(locale.tr("prts_title", "PRTS Intelligence"), locale.tr("prts_subtitle", "Automated analysis and intelligent decision console."), content)
        content_root.addWidget(header)

        placeholder = QLabel(locale.tr("prts_empty", "This page has been cleared."))
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setProperty("variant", "secondary")
        content_root.addWidget(placeholder, 1)
