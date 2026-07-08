"""Customizable dashboard framework for IstinaEndfieldAssistant Sight."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.theme.widget_styles import CARD_STYLE

locale = get_locale_manager()


class DashboardWidget(QFrame):
    """Base class for dashboard widgets."""

    def __init__(self, title: str, widget_id: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setStyleSheet(CARD_STYLE)
        self._widget_id = widget_id
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

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(2000)
        self._refresh_timer.timeout.connect(self.refresh)

        # Enable drag
        self.setAcceptDrops(True)

    def enterEvent(self, event):
        self.setStyleSheet(
            CARD_STYLE
            + "\nQFrame#metricCard:hover {"
            + " border: 1px solid rgba(24, 209, 255, 0.35);"
            + " background-color: rgba(24, 209, 255, 0.04);"
            + "}"
        )
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(CARD_STYLE)
        super().leaveEvent(event)

    def set_selected(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet(
                CARD_STYLE
                + "\nQFrame#metricCard {"
                + " border: 1px solid rgba(24, 209, 255, 0.5);"
                + " background-color: rgba(24, 209, 255, 0.08);"
                + "}"
            )
        else:
            self.setStyleSheet(CARD_STYLE)

    def fade_in(self, duration: int = 200) -> None:
        self.setWindowOpacity(0.0)
        self._fade_anim = self._fade_anim = __import__("PyQt6.QtCore", fromlist=["QPropertyAnimation"]).QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(duration)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def content_widget(self) -> QWidget:
        return self._content

    def update_content(self, widget: QWidget) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._content_layout.addWidget(widget)

    def refresh(self) -> None:
        """Override in subclasses to refresh widget data."""

    def start_auto_refresh(self) -> None:
        self._refresh_timer.start()

    def stop_auto_refresh(self) -> None:
        self._refresh_timer.stop()

    def mousePressEvent(self, event):
        if event.button() == "left button":
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if hasattr(self, '_drag_start_pos') and (event.pos() - self._drag_start_pos).manhattanLength() > 10:
            drag = QDrag(self)
            pixmap = self.grab()
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())
            mime = drag.mimeData()
            mime.setData("application/x-dashboard-widget", self._widget_id.encode())
            drag.exec()
