"""Tests for gui.pyqt6.main_window.MainWindow."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication, QListWidget, QMessageBox, QStackedWidget

from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.main_window import MainWindow


@pytest.fixture(autouse=True)
def _suppress_message_boxes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **kw: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **kw: None)


@pytest.fixture(autouse=True)
def _patch_page_init(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "gui.pyqt6.pages.maaend_control_page.MaaEndControlPage._delayed_init",
        lambda self: None,
    )
    monkeypatch.setattr(
        "gui.pyqt6.pages.maaend_control_page.MaaEndControlPage._load_metadata_cache",
        lambda self: None,
    )
    monkeypatch.setattr(
        "gui.pyqt6.pages.device_settings_page.DeviceSettingsPage._refresh_devices",
        lambda self: None,
    )


def _make_bridge(monkeypatch: pytest.MonkeyPatch) -> CLIBridge:
    bridge = CLIBridge()
    monkeypatch.setattr(bridge, "execute", lambda command, params=None: None)
    return bridge


class TestMainWindowSetup:
    """测试 _build_shell 创建导航列表和页面栈。"""

    def test_build_shell_creates_navigation_and_stack(
        self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_path = tmp_path / "config" / "client_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("{}", encoding="utf-8")
        monkeypatch.setattr("gui.pyqt6.main_window.get_project_root", lambda: tmp_path)
        bridge = _make_bridge(monkeypatch)
        window = MainWindow(bridge_factory=lambda: bridge)
        nav = window.findChild(QListWidget, "mainNavigation")
        stack = window.findChild(QStackedWidget)
        assert nav is not None
        assert stack is not None
        assert nav.count() == 4
        assert stack.count() == 4


class TestMainWindowNavigation:
    """测试 _on_nav_changed 切换页面。"""

    def test_on_nav_changed_switches_page(
        self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_path = tmp_path / "config" / "client_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("{}", encoding="utf-8")
        monkeypatch.setattr("gui.pyqt6.main_window.get_project_root", lambda: tmp_path)
        bridge = _make_bridge(monkeypatch)
        window = MainWindow(bridge_factory=lambda: bridge)
        stack = window.findChild(QStackedWidget)
        assert stack is not None
        window._on_nav_changed(1)
        assert stack.currentIndex() == 1


class TestMainWindowResponsiveMode:
    """测试 _update_responsive_mode 响应式切换。"""

    def test_update_responsive_mode_changes_nav_width(
        self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_path = tmp_path / "config" / "client_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("{}", encoding="utf-8")
        monkeypatch.setattr("gui.pyqt6.main_window.get_project_root", lambda: tmp_path)
        bridge = _make_bridge(monkeypatch)
        window = MainWindow(bridge_factory=lambda: bridge)
        window.resize(1280, 800)
        window._update_responsive_mode()
        normal_width = window._navigation_list.width()
        window.resize(600, 400)
        window._update_responsive_mode()
        compact_width = window._navigation_list.width()
        assert compact_width < normal_width


class TestMainWindowPreviewInterval:
    """测试 _preview_interval_ms 读取配置。"""

    def test_preview_interval_ms_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_path = tmp_path / "config" / "client_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("{}", encoding="utf-8")
        monkeypatch.setattr("gui.pyqt6.main_window.get_project_root", lambda: tmp_path)
        interval = MainWindow._preview_interval_ms(MainWindow)
        assert interval == 1500

    def test_preview_interval_ms_from_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_path = tmp_path / "config" / "client_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps({"preview_interval_ms": 500}), encoding="utf-8")
        monkeypatch.setattr("gui.pyqt6.main_window.get_project_root", lambda: tmp_path)
        interval = MainWindow._preview_interval_ms(MainWindow)
        assert interval == 500

    def test_preview_interval_ms_malformed_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_path = tmp_path / "config" / "client_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("{bad", encoding="utf-8")
        monkeypatch.setattr("gui.pyqt6.main_window.get_project_root", lambda: tmp_path)
        interval = MainWindow._preview_interval_ms(MainWindow)
        assert interval == 1500


class TestMainWindowCloseEvent:
    """测试 closeEvent 持久化队列状态。"""

    def test_close_event_persists_queue_state(
        self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_path = tmp_path / "config" / "client_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("{}", encoding="utf-8")
        monkeypatch.setattr("gui.pyqt6.main_window.get_project_root", lambda: tmp_path)
        bridge = _make_bridge(monkeypatch)
        window = MainWindow(bridge_factory=lambda: bridge)
        maaend_page = getattr(window, "_maaend_page", None)
        assert maaend_page is not None
        persisted = []

        def fake_persist():
            persisted.append(True)

        monkeypatch.setattr(maaend_page, "_persist_state", fake_persist)
        window.close()
        assert len(persisted) == 1


class TestMainWindowBridge:
    """测试 bridge() 返回 CLIBridge。"""

    def test_bridge_returns_cli_bridge(
        self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_path = tmp_path / "config" / "client_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("{}", encoding="utf-8")
        monkeypatch.setattr("gui.pyqt6.main_window.get_project_root", lambda: tmp_path)
        bridge = _make_bridge(monkeypatch)
        window = MainWindow(bridge_factory=lambda: bridge)
        assert window.bridge() is bridge
        assert isinstance(window.bridge(), CLIBridge)
