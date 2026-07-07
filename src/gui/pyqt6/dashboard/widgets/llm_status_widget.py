"""LLM status dashboard widget."""
from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gui.pyqt6.dashboard.widget_base import DashboardWidget
from gui.pyqt6.i18n import get_locale_manager

locale = get_locale_manager()


class LLMStatusWidget(DashboardWidget):
    """Shows LLM service status."""

    def __init__(self, title: str, bridge, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, "llm", parent)
        self._bridge = bridge
        self._status_label = QLabel(locale.tr("disabled_status", "Disabled"))
        self._status_label.setProperty("variant", "danger")
        self._status_label.setAccessibleName(locale.tr("llm_status_label", "LLM service status"))
        content = self.content_widget()
        layout = QVBoxLayout(content)
        layout.addWidget(self._status_label)
        self.start_auto_refresh()

    def update_data(self, result: Any) -> None:
        """Update LLM status from bridge data."""
        if not isinstance(result, dict):
            return
        enabled = result.get("enabled", False)
        if enabled:
            self._status_label.setText(locale.tr("online", "Online"))
            self._status_label.setProperty("variant", "success")
            self.play_success()
        else:
            self._status_label.setText(locale.tr("disabled_status", "Disabled"))
            self._status_label.setProperty("variant", "danger")

    def refresh(self) -> None:
        """Refresh LLM status from bridge."""
        pass
