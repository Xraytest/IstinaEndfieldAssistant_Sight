"""Tests for gui.pyqt6.pages.device_settings_page.DeviceSettingsPage."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication, QLineEdit

from gui.pyqt6.pages.device_settings_page import DeviceSettingsPage


class _FakeProcess:
    def __init__(self) -> None:
        self.state = lambda: None
        self.waitForStarted = lambda *args, **kwargs: True


@pytest.fixture()
def device_page(qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from gui.pyqt6.cli_bridge import CLIBridge

    monkeypatch.setattr(
        "gui.pyqt6.pages.device_settings_page.get_project_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        DeviceSettingsPage,
        "_refresh_devices",
        lambda self: None,
        raising=False,
    )
    bridge = CLIBridge()
    bridge._process = _FakeProcess()
    page = DeviceSettingsPage(bridge=bridge)
    return page


class TestDeviceSettingsPage:
    def test_setup_ui_widgets_exist(self, device_page):
        page = device_page
        assert isinstance(page._address_input, QLineEdit)
        assert page._connect_btn is not None
        assert page._disconnect_btn is not None
        assert page._refresh_btn is not None
        assert page._connection_status is not None
        assert page._selected_device is not None
        assert page._auto_reconnect_check is not None
        assert page._history_list is not None
        assert page._device_list is not None
        assert page._log_text is not None

    def test_load_device_preferences(self, device_page, tmp_path: Path):
        config_path = tmp_path / "config" / "client_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(
                {
                    "device": {
                        "last_connected": "127.0.0.1:5555",
                        "serial": "127.0.0.1:5555",
                        "history": ["127.0.0.1:5555", "localhost:16512"],
                        "auto_reconnect": True,
                        "adb_restart_on_timeout": True,
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        page = device_page
        page._load_device_preferences()
        assert page._address_input.text() == "127.0.0.1:5555"
        assert page._history_list.count() == 2

    def test_remember_device_writes_history(self, device_page, tmp_path: Path):
        page = device_page
        page._remember_device("127.0.0.1:5555")
        config_path = tmp_path / "config" / "client_config.json"
        assert config_path.exists()
        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert data["device"]["last_connected"] == "127.0.0.1:5555"
        assert "127.0.0.1:5555" in data["device"]["history"]

    def test_on_command_finished_device_info(self, device_page):
        page = device_page
        page._on_command_finished(
            "device info",
            {"status": "success", "devices": [{"serial": "abc", "status": "device"}]},
        )
        assert page._device_list.count() == 1
        assert "abc" in page._device_list.item(0).text()

    def test_on_command_finished_connect_success(self, device_page):
        from gui.pyqt6.i18n import get_locale_manager
        locale = get_locale_manager()
        page = device_page
        page._address_input.setText("127.0.0.1:5555")
        page._on_command_finished("system connect", {"status": "success"})
        assert page._connected is True
        assert locale.tr("connection_ok", "Connected") in page._connection_status.text()

    def test_on_command_finished_connect_failure(self, device_page):
        from gui.pyqt6.i18n import get_locale_manager
        locale = get_locale_manager()
        page = device_page
        page._address_input.setText("127.0.0.1:5555")
        page._on_command_finished("system connect", {"status": "error"})
        assert page._connected is False
        assert locale.tr("connection_failed", "Connection Failed") in page._connection_status.text()

    def test_on_command_finished_disconnect(self, device_page):
        from gui.pyqt6.i18n import get_locale_manager
        locale = get_locale_manager()
        page = device_page
        page._connected = True
        page._on_command_finished("system disconnect", {"status": "success"})
        assert page._connected is False
        assert locale.tr("connection_disconnected", "Disconnected") in page._connection_status.text()

    def test_on_command_error_restores_buttons(self, device_page):
        from gui.pyqt6.i18n import get_locale_manager
        locale = get_locale_manager()
        page = device_page
        page._on_command_error("system connect", "timeout")
        assert page._connect_btn.isEnabled() is True
        assert locale.tr("connection_failed", "Connection Failed") in page._connection_status.text()

    def test_set_connecting_state_disables_buttons(self, device_page):
        from gui.pyqt6.i18n import get_locale_manager
        locale = get_locale_manager()
        page = device_page
        page._set_connecting_state()
        assert page._connect_btn.isEnabled() is False
        assert page._disconnect_btn.isEnabled() is False
        assert page._refresh_btn.isEnabled() is False
        assert locale.tr("connecting", "Connecting...") in page._connection_status.text()

    def test_attempt_reconnect_triggers_connect(self, device_page, monkeypatch):
        called = {}

        def fake_execute(self, cmd, params=None):
            called["cmd"] = cmd

        page = device_page
        monkeypatch.setattr(page._bridge, "execute", fake_execute)
        page._address_input.setText("127.0.0.1:5555")
        page._reconnect_enabled = True
        page._connected = False
        page._attempt_reconnect()
        assert called.get("cmd") == {"serial": "127.0.0.1:5555"}
