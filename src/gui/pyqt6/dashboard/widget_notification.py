"""Notification and warning system for dashboard widgets."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.theme.widget_styles import GREEN_STYLE, RED_STYLE, YELLOW_STYLE

locale = get_locale_manager()


@dataclass
class Notification:
    """Single notification message."""
    message: str
    level: str = "info"  # info, warning, error, success
    duration: int = 5000  # ms, 0 for persistent
    widget_id: Optional[str] = None


class NotificationCenter:
    """Central notification manager for dashboard widgets."""

    def __init__(self) -> None:
        self._notifications: list[Notification] = []
        self._listeners: dict[str, list] = {}

    def notify(self, message: str, level: str = "info", duration: int = 5000, widget_id: Optional[str] = None) -> Notification:
        n = Notification(message, level, duration, widget_id)
        self._notifications.append(n)
        self._emit("notify", n)
        return n

    def warning(self, message: str, duration: int = 5000, widget_id: Optional[str] = None) -> Notification:
        return self.notify(message, "warning", duration, widget_id)

    def error(self, message: str, duration: int = 5000, widget_id: Optional[str] = None) -> Notification:
        return self.notify(message, "error", duration, widget_id)

    def success(self, message: str, duration: int = 5000, widget_id: Optional[str] = None) -> Notification:
        return self.notify(message, "success", duration, widget_id)

    def listen(self, widget_id: str, callback) -> None:
        if widget_id not in self._listeners:
            self._listeners[widget_id] = []
        self._listeners[widget_id].append(callback)

    def _emit(self, event: str, notification: Notification) -> None:
        widget_id = notification.widget_id
        if widget_id and widget_id in self._listeners:
            for cb in self._listeners[widget_id]:
                cb(notification)
        for cb_list in self._listeners.get(None, []):
            cb_list(notification)


# Global notification center
_center: Optional[NotificationCenter] = None


def get_notification_center() -> NotificationCenter:
    global _center
    if _center is None:
        _center = NotificationCenter()
    return _center


class NotificationBadge(QLabel):
    """Badge widget showing notification count or warning icon."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._count = 0
        self._level = "info"
        self.setAlignment(int(self.textAlignment()))
        self._update_style()

    def set_count(self, count: int) -> None:
        self._count = max(0, count)
        self.setText(str(self._count) if self._count > 0 else "")
        self._update_style()

    def set_level(self, level: str) -> None:
        self._level = level
        self._update_style()

    def _update_style(self) -> None:
        if self._level == "error":
            self.setStyleSheet(RED_STYLE)
        elif self._level == "warning":
            self.setStyleSheet(YELLOW_STYLE)
        elif self._level == "success":
            self.setStyleSheet(GREEN_STYLE)
        else:
            self.setStyleSheet(YELLOW_STYLE)


class WidgetNotificationMixin:
    """Mixin for dashboard widgets to show notifications."""

    def __init__(self) -> None:
        self._notification_timer = QTimer(self)
        self._notification_timer.setSingleShot(True)
        self._notification_timer.timeout.connect(self._clear_notification)

    def show_notification(self, message: str, level: str = "info", duration: int = 5000) -> None:
        badge = getattr(self, "_notification_badge", None)
        if badge is None:
            return
        badge.setText(message)
        badge.set_level(level)
        self._notification_timer.stop()
        if duration > 0:
            self._notification_timer.start(duration)
        else:
            pass  # Persistent

    def _clear_notification(self) -> None:
        badge = getattr(self, "_notification_badge", None)
        if badge is not None:
            badge.clear()
