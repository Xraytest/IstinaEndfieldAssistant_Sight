"""Queue progress dashboard widget."""
from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gui.pyqt6.dashboard.widget_base import DashboardWidget
from gui.pyqt6.i18n import get_locale_manager

locale = get_locale_manager()


class QueueProgressWidget(DashboardWidget):
    """Shows queue execution progress."""

    def __init__(self, title: str, bridge, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, "queue", parent)
        self._bridge = bridge
        self._status_label = QLabel(locale.tr("maaend_idle", "Idle"))
        self._status_label.setProperty("variant", "success")
        content = self.content_widget()
        layout = QVBoxLayout(content)
        layout.addWidget(self._status_label)
        self.start_auto_refresh()

    def update_data(self, result: Any) -> None:
        """Update queue progress from bridge data."""
        if not isinstance(result, dict):
            return
        status = result.get("status", "unknown")
        if status == "running":
            self._status_label.setText(locale.tr("maaend_running", "Running"))
            self._status_label.setProperty("variant", "danger")
        elif status == "success":
            self._status_label.setText(locale.tr("execution_completed", "Completed"))
            self._status_label.setProperty("variant", "success")
        elif status == "failed":
            self._status_label.setText(locale.tr("execution_failed", "Failed"))
            self._status_label.setProperty("variant", "danger")
        else:
            self._status_label.setText(locale.tr("maaend_idle", "Idle"))
            self._status_label.setProperty("variant", "success")

    def refresh(self) -> None:
        """Refresh queue progress from bridge."""
        pass
