"""Recent tasks dashboard widget."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QListWidget, QVBoxLayout, QWidget

from gui.pyqt6.dashboard.widget_base import DashboardWidget
from gui.pyqt6.i18n import get_locale_manager

locale = get_locale_manager()


class RecentTasksWidget(DashboardWidget):
    """Shows recent task history."""

    def __init__(self, title: str, bridge, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self._bridge = bridge
        self._list = QListWidget()
        content = self.content_widget()
        layout = QVBoxLayout(content)
        layout.addWidget(self._list)
