"""Recent tasks dashboard widget."""
from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtWidgets import QListWidget, QVBoxLayout, QWidget

from gui.pyqt6.dashboard.widget_base import DashboardWidget
from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.theme.widget_styles import LIST_STYLE

locale = get_locale_manager()


class RecentTasksWidget(DashboardWidget):
    """Shows recent task history."""

    def __init__(self, title: str, bridge, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, "recent_tasks", parent)
        self._bridge = bridge
        self._list = QListWidget()
        self._list.setStyleSheet(LIST_STYLE)
        self._list.setAccessibleName(locale.tr("recent_tasks_list", "Recent tasks list"))
        layout = self._content_layout
        layout.addWidget(self._list)
        self.start_auto_refresh()

    def update_data(self, result: Any) -> None:
        """Update recent tasks from bridge data."""
        if not isinstance(result, dict):
            return
        tasks = result.get("recent_tasks") or []
        self._list.clear()
        for task in tasks[:10]:
            self._list.addItem(str(task))
