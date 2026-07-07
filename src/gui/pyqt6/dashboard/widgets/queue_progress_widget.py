"""Queue progress dashboard widget."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gui.pyqt6.dashboard.widget_base import DashboardWidget
from gui.pyqt6.i18n import get_locale_manager

locale = get_locale_manager()


class QueueProgressWidget(DashboardWidget):
    """Shows queue execution progress."""

    def __init__(self, title: str, bridge, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self._bridge = bridge
        self._status_label = QLabel(locale.tr("maaend_idle", "Idle"))
        self._status_label.setProperty("variant", "success")
        content = self.content_widget()
        layout = QVBoxLayout(content)
        layout.addWidget(self._status_label)
