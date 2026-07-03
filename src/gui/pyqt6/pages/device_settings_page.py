from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.pyqt6.cli_bridge import CLIBridge


class DeviceSettingsPage(QWidget):
    def __init__(self, bridge: CLIBridge, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._bridge = bridge
        self._bridge.commandFinished.connect(self._on_command_finished)
        self._setup_ui()
        self._refresh_devices()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        address_row = QHBoxLayout()
        address_row.setSpacing(8)
        self._address_input = QLineEdit()
        self._address_input.setPlaceholderText("Device address")
        address_row.addWidget(self._address_input)

        connect_btn = QPushButton("Connect")
        connect_btn.clicked.connect(self._connect)
        address_row.addWidget(connect_btn)

        disconnect_btn = QPushButton("Disconnect")
        disconnect_btn.clicked.connect(self._disconnect)
        address_row.addWidget(disconnect_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_devices)
        address_row.addWidget(refresh_btn)

        root.addLayout(address_row)

        self._device_list = QListWidget()
        root.addWidget(self._device_list)

    def _connect(self) -> None:
        serial = self._address_input.text().strip()
        if serial:
            self._bridge.execute("system connect", {"serial": serial})

    def _disconnect(self) -> None:
        serial = self._address_input.text().strip()
        if serial:
            self._bridge.execute("system disconnect", {"serial": serial})

    def _refresh_devices(self) -> None:
        self._bridge.execute("device info")

    def _on_command_finished(self, command: str, result: dict) -> None:
        if command == "device info" and result.get("status") == "success":
            devices = result.get("devices") or []
            self._device_list.clear()
            for device in devices:
                self._device_list.addItem(str(device))
