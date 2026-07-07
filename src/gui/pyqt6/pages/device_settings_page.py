from __future__ import annotations

import json
from typing import Any, Dict, Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
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


from gui.pyqt6.theme.hero import HeroHeader
from gui.pyqt6.theme.icons import get_action_icon


class DeviceSettingsPage(QWidget):
    def __init__(self, bridge: CLIBridge, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._bridge = bridge
        self._config_path = get_project_root() / "config" / "client_config.json"
        self._connected = False
        self._bridge.commandFinished.connect(self._on_command_finished)
        self._bridge.commandError.connect(self._on_command_error)
        self._setup_ui()
        self._load_device_preferences()
        self._refresh_devices()
        QTimer.singleShot(0, self._auto_connect_last_device)

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

        header = HeroHeader("设备连接", "管理 ADB 设备连接与自动重连。", content)
        content_root.addWidget(header)

        connection_card = QGroupBox("连接管理")
        connection_layout = QVBoxLayout(connection_card)
        connection_layout.setSpacing(10)

        address_row = QHBoxLayout()
        address_row.setSpacing(8)
        self._address_input = QLineEdit()
        self._address_input.setPlaceholderText("请输入设备地址，例如 localhost:16512")
        address_row.addWidget(self._address_input)

        self._connect_btn = QPushButton("连接")
        self._connect_btn.setIcon(get_action_icon("连接"))
        self._connect_btn.clicked.connect(self._connect)
        address_row.addWidget(self._connect_btn)

        self._disconnect_btn = QPushButton("断开")
        self._disconnect_btn.setIcon(get_action_icon("断开"))
        self._disconnect_btn.clicked.connect(self._disconnect)
        address_row.addWidget(self._disconnect_btn)

        self._refresh_btn = QPushButton("刷新")
        self._refresh_btn.setIcon(get_action_icon("刷新"))
        self._refresh_btn.clicked.connect(self._refresh_devices)
        address_row.addWidget(self._refresh_btn)
        connection_layout.addLayout(address_row)

        status_form = QFormLayout()
        self._connection_status = QLabel("未连接")
        self._selected_device = QLabel("-")
        status_form.addRow("状态", self._connection_status)
        status_form.addRow("当前设备", self._selected_device)
        connection_layout.addLayout(status_form)
        content_root.addWidget(connection_card)

        history_card = QGroupBox("历史连接")
        history_layout = QVBoxLayout(history_card)
        history_layout.setSpacing(8)
        self._history_list = QListWidget()
        self._history_list.itemClicked.connect(lambda item: self._address_input.setText(item.text()))
        history_layout.addWidget(self._history_list)
        history_hint = QLabel("点击历史地址可直接填入。")
        history_hint.setProperty("variant", "secondary")
        history_layout.addWidget(history_hint)
        content_root.addWidget(history_card)

        devices_card = QGroupBox("设备列表")
        devices_layout = QVBoxLayout(devices_card)
        devices_layout.setSpacing(8)
        self._device_list = QListWidget()
        devices_layout.addWidget(self._device_list)
        content_root.addWidget(devices_card, 1)

        runtime_card = QGroupBox("连接日志")
        runtime_layout = QVBoxLayout(runtime_card)
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        runtime_layout.addWidget(self._log_text)
        content_root.addWidget(runtime_card, 1)

    def _connect(self) -> None:
        serial = self._address_input.text().strip()
        if not serial:
            self._append_log("未填写设备地址，无法连接。")
            return
        self._append_log(f"请求连接: {serial}")
        self._bridge.execute("system connect", {"serial": serial})

    def _disconnect(self) -> None:
        serial = self._address_input.text().strip()
        self._append_log(f"请求断开: {serial or '当前设备'}")
        params = {"serial": serial} if serial else {}
        self._bridge.execute("system disconnect", params)

    def _refresh_devices(self) -> None:
        self._bridge.execute("device info")

    def _auto_connect_last_device(self) -> None:
        config = self._read_config()
        device_cfg = config.get("device", {})
        if not device_cfg.get("auto_connect_last", True):
            return
        serial = str(device_cfg.get("last_connected") or "").strip()
        if not serial:
            return
        self._address_input.setText(serial)
        self._append_log(f"自动连接上次设备: {serial}")
        self._connect()

    def _on_command_finished(self, command: str, result: dict) -> None:
        if command == "device info":
            self._update_device_info(result)
        elif command.startswith("system connect"):
            ok = bool(result.get("status") == "success")
            serial = self._address_input.text().strip()
            self._connected = ok
            self._connection_status.setText("已连接" if ok else "连接失败")
            self._selected_device.setText(serial or "-")
            self._append_log(f"连接结果: {result}")
            if ok and serial:
                self._remember_device(serial)
        elif command.startswith("system disconnect"):
            self._connected = False
            self._connection_status.setText("未连接")
            self._append_log(f"断开结果: {result}")

    def _on_command_error(self, command: str, message: str) -> None:
        self._append_log(f"{command} 失败: {message}")

    def _update_device_info(self, result: dict) -> None:
        self._device_list.clear()
        if result.get("status") != "success":
            self._append_log(f"刷新设备失败: {result}")
            return
        devices = result.get("devices") or []
        if not devices:
            self._device_list.addItem("未发现设备")
        for device in devices:
            self._device_list.addItem(self._format_device_entry(device))
        self._append_log(f"设备刷新完成，共 {len(devices)} 个。")

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
