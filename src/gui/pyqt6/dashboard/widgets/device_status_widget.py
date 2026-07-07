"""Device status dashboard widget."""
from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gui.pyqt6.dashboard.widget_base import DashboardWidget
from gui.pyqt6.i18n import get_locale_manager

locale = get_locale_manager()


class DeviceStatusWidget(DashboardWidget):
    """Shows device connection status."""

    def __init__(self, title: str, bridge, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self._bridge = bridge
        self._status_label = QLabel(locale.tr("offline", "Offline"))
        self._status_label.setProperty("variant", "danger")
        self._serial_label = QLabel("-")
        content = self.content_widget()
        layout = QVBoxLayout(content)
        layout.addWidget(self._status_label)
        layout.addWidget(self._serial_label)
        self.start_auto_refresh()

    def update_data(self, devices: Any) -> None:
        """Update device status from bridge data."""
        if not devices:
            self._status_label.setText(locale.tr("offline", "Offline"))
            self._status_label.setProperty("variant", "danger")
            self._serial_label.setText("-")
            return
        serial = devices[0].get("serial", "-") if isinstance(devices, list) else "-"
        self._status_label.setText(locale.tr("online", "Online"))
        self._status_label.setProperty("variant", "success")
        self._serial_label.setText(serial)

    def refresh(self) -> None:
        """Refresh device status from bridge."""
        pass
