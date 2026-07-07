"""Customizable dashboard framework for IstinaEndfieldAssistant Sight."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.theme.widget_styles import BTN_DEFAULT, CARD_STYLE

locale = get_locale_manager()


class DashboardWidget(QFrame):
    """Base class for dashboard widgets."""

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setStyleSheet(CARD_STYLE)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 10, 12, 10)
        self._layout.setSpacing(6)

        header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setProperty("variant", "secondary")
        header.addWidget(title_label)
        header.addStretch()
        self._layout.addLayout(header)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(4)
        self._layout.addWidget(self._content)

    def content_widget(self) -> QWidget:
        return self._content

    def update_content(self, widget: QWidget) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._content_layout.addWidget(widget)
