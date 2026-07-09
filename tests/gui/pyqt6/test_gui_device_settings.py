"""Tests for DeviceSettingsPage PyQt6 GUI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.pages.device_settings_page import DeviceSettingsPage


def _create_device_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bridge=None) -> DeviceSettingsPage:
    import gui.pyqt6.pages.device_settings_page as _mod
    from gui.pyqt6.i18n import get_locale_manager

    monkeypatch.setattr(_mod, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

    if bridge is None:
        bridge = CLIBridge()
        bridge._start_interactive_process = lambda: None
        bridge._start_next_process = lambda: None

    page = DeviceSettingsPage(bridge=bridge)
    return page


class TestDeviceSettingsPageControls:
    """Verify DeviceSettingsPage creates all expected controls."""

    def test_controls_exist(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_device_page(tmp_path, monkeypatch)
        assert page is not None
        assert hasattr(page, "_address_input")
        assert hasattr(page, "_connect_btn")
        assert hasattr(page, "_disconnect_btn")
        assert hasattr(page, "_refresh_btn")
        assert hasattr(page, "_connection_status")
        assert hasattr(page, "_selected_device")
        assert hasattr(page, "_auto_reconnect_check")
        assert hasattr(page, "_history_list")
        assert hasattr(page, "_device_list")
        assert hasattr(page, "_log_text")

    def test_load_device_preferences(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        config_path = tmp_path / "client_config.json"
        config_path.write_text(
            json.dumps({
                "device": {
                    "last_connected": "localhost:16512",
                    "history": ["localhost:16512", "localhost:5555"],
                    "auto_reconnect": True,
                    "adb_restart_on_timeout": False,
                }
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        page = _create_device_page(tmp_path, monkeypatch)
        assert page._address_input.text() == "localhost:16512"
        assert page._selected_device.text() == "localhost:16512"
        assert page._history_list.count() == 2
        assert page._auto_reconnect_check.isChecked() is True
        assert page._auto_kill_adb_check.isChecked() is False


class TestDeviceSettingsPageConfigIO:
    """Test _remember_device writes config and _load_device_preferences reads it."""

    def test_remember_device_updates_history(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        config_path = tmp_path / "client_config.json"
        config_path.write_text(json.dumps({"device": {}}, ensure_ascii=False), encoding="utf-8")
        page = _create_device_page(tmp_path, monkeypatch)
        page._address_input.setText("localhost:9999")
        page._remember_device("localhost:9999")
        data = json.loads(config_path.read_text(encoding="utf-8"))
        device_cfg = data.get("device", {})
        assert device_cfg["last_connected"] == "localhost:9999"
        assert device_cfg["serial"] == "localhost:9999"
        assert device_cfg["history"] == ["localhost:9999"]


class TestDeviceSettingsPageCommandHandling:
    """Test _on_command_finished handling of device info / connect / disconnect."""

    def test_on_command_finished_device_info(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_device_page(tmp_path, monkeypatch)
        page._on_command_finished("device info", {"status": "success", "devices": [{"serial": "abc", "status": "device"}]})
        assert page._device_list.count() == 1
        assert "abc" in page._device_list.item(0).text()

    def test_on_command_finished_connect_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_device_page(tmp_path, monkeypatch)
        page._address_input.setText("localhost:8888")
        page._on_command_finished("system connect", {"status": "success"})
        assert page._connected is True
        assert "Connected" in page._connection_status.text()
        assert page._selected_device.text() == "localhost:8888"

    def test_on_command_finished_connect_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_device_page(tmp_path, monkeypatch)
        page._address_input.setText("localhost:8888")
        page._on_command_finished("system connect", {"status": "error"})
        assert page._connected is False
        assert "Connection Failed" in page._connection_status.text()

    def test_on_command_finished_disconnect(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_device_page(tmp_path, monkeypatch)
        page._connected = True
        page._on_command_finished("system disconnect", {"status": "success"})
        assert page._connected is False
        assert "Disconnected" in page._connection_status.text()

    def test_on_command_error_restores_buttons(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_device_page(tmp_path, monkeypatch)
        page._on_command_error("system connect", "timeout")
        assert "Connection Failed" in page._connection_status.text()
        assert page._connect_btn.isEnabled()

    def test_set_connecting_state_disables_buttons(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_device_page(tmp_path, monkeypatch)
        page._set_connecting_state()
        assert not page._connect_btn.isEnabled()
        assert not page._disconnect_btn.isEnabled()
        assert not page._refresh_btn.isEnabled()
        assert "Connecting" in page._connection_status.text()

    def test_attempt_reconnect_triggers_execute(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_device_page(tmp_path, monkeypatch)
        page._address_input.setText("localhost:5555")
        page._reconnect_enabled = True
        page._connected = False
        page._set_connecting_state = lambda: None
        page._append_log = lambda *a, **k: None
        page._attempt_reconnect()
        assert len(page._bridge._pending_commands) == 1
        assert page._bridge._pending_commands[0][0] == "system"
        assert page._bridge._pending_commands[0][1] == "connect"

    def test_update_device_info_no_devices(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_device_page(tmp_path, monkeypatch)
        page._update_device_info({"status": "success", "devices": []})
        assert page._device_list.count() == 0
