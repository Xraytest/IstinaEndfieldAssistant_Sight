from __future__ import annotations

import json
from typing import Any, Dict, Optional

from PyQt6.QtCore import QPropertyAnimation, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.foundation.paths import get_project_root
from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.theme.hero import HeroHeader
from gui.pyqt6.theme.widget_styles import LIST_STYLE


locale = get_locale_manager()


class DeviceSettingsPage(QWidget):
    def __init__(self, bridge: CLIBridge, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._bridge = bridge
        self._config_path = get_project_root() / "config" / "client_config.json"
        self._connected = False
        self._bridge.commandFinished.connect(self._on_command_finished)
        self._bridge.commandError.connect(self._on_command_error)
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(5000)
        self._reconnect_timer.timeout.connect(self._attempt_reconnect)
        self._reconnect_enabled = True
        self._setup_ui()
        self._load_device_preferences()
        self._refresh_devices()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        content_root = QVBoxLayout(content)
        content_root.setContentsMargins(16, 16, 16, 16)
        content_root.setSpacing(12)

        header = HeroHeader(locale.tr("device_title", "Device"), locale.tr("device_subtitle", "Manage ADB device connections and auto-reconnect."), content)
        content_root.addWidget(header)

        connection_card = QGroupBox(locale.tr("connection_management", "Connection Management"))
        connection_layout = QVBoxLayout(connection_card)
        connection_layout.setSpacing(10)

        address_row = QHBoxLayout()
        address_row.setSpacing(8)
        self._address_input = QLineEdit()
        self._address_input.setPlaceholderText(locale.tr("address_placeholder", "Enter device address, e.g. localhost:16512"))
        address_row.addWidget(self._address_input)

        self._connect_btn = QPushButton(locale.tr("btn_connect", "Connect"))
        self._connect_btn.clicked.connect(self._connect)
        address_row.addWidget(self._connect_btn)

        self._disconnect_btn = QPushButton(locale.tr("btn_disconnect", "Disconnect"))
        self._disconnect_btn.clicked.connect(self._disconnect)
        address_row.addWidget(self._disconnect_btn)

        self._refresh_btn = QPushButton(locale.tr("btn_refresh", "Refresh"))
        self._refresh_btn.clicked.connect(self._refresh_devices)
        address_row.addWidget(self._refresh_btn)
        connection_layout.addLayout(address_row)

        status_form = QFormLayout()
        self._connection_status = QLabel(locale.tr("connection_disconnected", "Disconnected"))
        self._selected_device = QLabel("-")
        status_form.addRow(locale.tr("status_label", "Status"), self._connection_status)
        status_form.addRow(locale.tr("current_device", "Current Device"), self._selected_device)
        self._auto_reconnect_check = QCheckBox(locale.tr("auto_reconnect", "Auto-reconnect on disconnect"))
        self._auto_reconnect_check.setChecked(True)
        self._auto_reconnect_check.toggled.connect(self._on_auto_reconnect_toggled)
        status_form.addRow("", self._auto_reconnect_check)
        connection_layout.addLayout(status_form)
        content_root.addWidget(connection_card)

        history_card = QGroupBox(locale.tr("connection_history", "Connection History"))
        history_layout = QVBoxLayout(history_card)
        history_layout.setSpacing(8)
        self._history_list = QListWidget()
        self._history_list.setStyleSheet(LIST_STYLE)
        self._history_list.setMinimumHeight(120)
        self._history_list.itemClicked.connect(lambda item: self._address_input.setText(item.text()))
        history_layout.addWidget(self._history_list)
        history_hint = QLabel(locale.tr("history_hint", "Click a history address to fill it in."))
        history_hint.setProperty("variant", "secondary")
        history_layout.addWidget(history_hint)
        content_root.addWidget(history_card)

        devices_card = QGroupBox(locale.tr("device_list", "Device List"))
        devices_layout = QVBoxLayout(devices_card)
        devices_layout.setSpacing(8)
        self._device_list = QListWidget()
        self._device_list.setStyleSheet(LIST_STYLE)
        devices_layout.addWidget(self._device_list)
        content_root.addWidget(devices_card, 1)

        runtime_card = QGroupBox(locale.tr("connection_log", "Connection Log"))
        runtime_layout = QVBoxLayout(runtime_card)
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        runtime_layout.addWidget(self._log_text)
        content_root.addWidget(runtime_card, 1)

    def _on_auto_reconnect_toggled(self, checked: bool) -> None:
        self._reconnect_enabled = checked
        if checked and self._connected:
            self._reconnect_timer.start()
        else:
            self._reconnect_timer.stop()

    def _attempt_reconnect(self) -> None:
        if self._connected or not self._reconnect_enabled:
            return
        serial = self._address_input.text().strip()
        if not serial:
            return
        self._append_log(locale.tr("auto_reconnect_attempt", "Auto-reconnect attempt: {serial}").format(serial=serial))
        self._bridge.execute("system connect", {"serial": serial})

    def _connect(self) -> None:
        serial = self._address_input.text().strip()
        if not serial:
            self._append_log(locale.tr("address_required", "Device address not filled, cannot connect."))
            return
        self._append_log(locale.tr("connect_request", "Request connect: {serial}").format(serial=serial))
        self._bridge.execute("system connect", {"serial": serial})

    def _disconnect(self) -> None:
        serial = self._address_input.text().strip()
        self._append_log(locale.tr("disconnect_request", "Request disconnect: {serial}").format(serial=serial or locale.tr("current_device", "Current Device")))
        params = {"serial": serial} if serial else {}
        self._bridge.execute("system disconnect", params)

    def _refresh_devices(self) -> None:
        self._bridge.execute("device info")

    def _on_command_finished(self, command: str, result: dict) -> None:
        if command == "device info":
            self._update_device_info(result)
        elif command.startswith("system connect"):
            ok = bool(result.get("status") == "success")
            serial = self._address_input.text().strip()
            self._connected = ok
            self._connection_status.setText(locale.tr("connection_ok" if ok else "connection_failed", "Connected" if ok else "Connection Failed"))
            self._selected_device.setText(serial or "-")
            self._append_log(locale.tr("connect_result", "Connect result: {result}").format(result=result))
            if ok and serial:
                self._remember_device(serial)
                if self._reconnect_enabled:
                    self._reconnect_timer.start()
                self._pulse_connection_status()
            else:
                self._reconnect_timer.stop()
        elif command.startswith("system disconnect"):
            self._connected = False
            self._connection_status.setText(locale.tr("connection_disconnected", "Disconnected"))
            self._append_log(locale.tr("disconnect_result", "Disconnect result: {result}").format(result=result))
            if self._reconnect_enabled:
                self._reconnect_timer.start()

    def _pulse_connection_status(self) -> None:
        animation = QPropertyAnimation(self._connection_status, b"windowOpacity")
        animation.setDuration(400)
        animation.setStartValue(1.0)
        animation.setKeyValueAt(0.5, 0.4)
        animation.setEndValue(1.0)
        animation.setLoopCount(2)
        animation.start()

    def _on_command_error(self, command: str, message: str) -> None:
        self._append_log(locale.tr("command_failed", "Command failed: {command}").format(command=command) + f" {message}")

    def _update_device_info(self, result: dict) -> None:
        self._device_list.clear()
        if result.get("status") != "success":
            self._append_log(locale.tr("refresh_devices_failed", "Failed to refresh devices: {result}").format(result=result))
            return
        devices = result.get("devices") or []
        if not devices:
            self._device_list.addItem(locale.tr("no_devices_found", "No devices found"))
        for device in devices:
            self._device_list.addItem(self._format_device_entry(device))
        self._append_log(locale.tr("devices_refreshed", "Devices refreshed, {count} found.").format(count=len(devices)))

    def _format_device_entry(self, device: Any) -> str:
        if isinstance(device, dict):
            serial = device.get("serial") or device.get("address") or "unknown"
            status = device.get("status") or device.get("state") or "unknown"
            return f"{serial} [{status}]"
        return str(device)

    def _append_log(self, message: str) -> None:
        self._log_text.append(message)

    def _load_device_preferences(self) -> None:
        config = self._read_config()
        device_cfg = config.get("device", {})
        serial = str(device_cfg.get("last_connected") or device_cfg.get("serial") or "").strip()
        if serial:
            self._address_input.setText(serial)
            self._selected_device.setText(serial)

        self._history_list.clear()
        for item in device_cfg.get("history", []) or []:
            if item:
                self._history_list.addItem(str(item))

    def _remember_device(self, serial: str) -> None:
        config = self._read_config()
        device_cfg = dict(config.get("device", {}))
        history = [str(item) for item in device_cfg.get("history", []) if str(item).strip()]
        history = [item for item in history if item != serial]
        history.insert(0, serial)
        device_cfg["last_connected"] = serial
        device_cfg["serial"] = serial
        device_cfg["history"] = history[:10]
        device_cfg["auto_connect_last"] = True
        config["device"] = device_cfg
        self._write_config(config)
        self._load_device_preferences()

    def _read_config(self) -> Dict[str, Any]:
        if not self._config_path.exists():
            return {}
        try:
            return json.loads(self._config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write_config(self, config: Dict[str, Any]) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
