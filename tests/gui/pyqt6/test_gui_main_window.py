"""Tests for MainWindow PyQt6 GUI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent

from gui.pyqt6.main_window import MainWindow


class TestMainWindow:
    """Test MainWindow shell, navigation, responsive mode, preview interval, and bridge."""

    def test_bridge_returns_clibridge(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.main_window as _mw
        from gui.pyqt6.i18n import get_locale_manager
        from gui.pyqt6.pages.maaend_control_page import MaaEndControlPage

        monkeypatch.setattr(_mw, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(_mw, "check_gpu", lambda: type("R", (), {"is_nvidia": True, "warning": None})())
        monkeypatch.setattr(_mw, "format_gpu_warning", lambda r: None)
        monkeypatch.setattr(_mw, "TrayIcon", lambda *a, **k: type("T", (), {"is_available": lambda self: False})())
        monkeypatch.setattr(MaaEndControlPage, "_delayed_init", lambda self: None, raising=False)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        window = MainWindow()
        assert window is not None
        assert hasattr(window, "_bridge")
        assert window.bridge() is window._bridge

    def test_build_shell_creates_navigation_and_pages(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.main_window as _mw
        from gui.pyqt6.i18n import get_locale_manager
        from gui.pyqt6.pages.maaend_control_page import MaaEndControlPage

        monkeypatch.setattr(_mw, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(_mw, "check_gpu", lambda: type("R", (), {"is_nvidia": True, "warning": None})())
        monkeypatch.setattr(_mw, "format_gpu_warning", lambda r: None)
        monkeypatch.setattr(_mw, "TrayIcon", lambda *a, **k: type("T", (), {"is_available": lambda self: False})())
        monkeypatch.setattr(MaaEndControlPage, "_delayed_init", lambda self: None, raising=False)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        window = MainWindow()
        assert window._navigation_list is not None
        assert window._page_stack is not None
        assert window._navigation_list.count() == 5
        assert window._page_stack.count() == 5

    def test_on_nav_changed_switches_page(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.main_window as _mw
        from gui.pyqt6.i18n import get_locale_manager
        from gui.pyqt6.pages.maaend_control_page import MaaEndControlPage

        monkeypatch.setattr(_mw, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(_mw, "check_gpu", lambda: type("R", (), {"is_nvidia": True, "warning": None})())
        monkeypatch.setattr(_mw, "format_gpu_warning", lambda r: None)
        monkeypatch.setattr(_mw, "TrayIcon", lambda *a, **k: type("T", (), {"is_available": lambda self: False})())
        monkeypatch.setattr(MaaEndControlPage, "_delayed_init", lambda self: None, raising=False)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        window = MainWindow()
        initial = window._page_stack.currentIndex()
        window._on_nav_changed((initial + 1) % window._page_stack.count())
        assert window._page_stack.currentIndex() != initial

    def test_update_responsive_mode_changes_width(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.main_window as _mw
        from gui.pyqt6.i18n import get_locale_manager
        from gui.pyqt6.pages.maaend_control_page import MaaEndControlPage

        monkeypatch.setattr(_mw, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(_mw, "check_gpu", lambda: type("R", (), {"is_nvidia": True, "warning": None})())
        monkeypatch.setattr(_mw, "format_gpu_warning", lambda r: None)
        monkeypatch.setattr(_mw, "TrayIcon", lambda *a, **k: type("T", (), {"is_available": lambda self: False})())
        monkeypatch.setattr(MaaEndControlPage, "_delayed_init", lambda self: None, raising=False)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        window = MainWindow()
        window.resize(600, 500)
        window._update_responsive_mode()
        assert window._navigation_list.width() in (180, 220)

    def test_preview_interval_ms_reads_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.main_window as _mw
        from gui.pyqt6.i18n import get_locale_manager
        from gui.pyqt6.pages.maaend_control_page import MaaEndControlPage

        config_path = tmp_path / "config" / "client_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps({"preview_interval_ms": 3333}, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(_mw, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(_mw, "check_gpu", lambda: type("R", (), {"is_nvidia": True, "warning": None})())
        monkeypatch.setattr(_mw, "format_gpu_warning", lambda r: None)
        monkeypatch.setattr(_mw, "TrayIcon", lambda *a, **k: type("T", (), {"is_available": lambda self: False})())
        monkeypatch.setattr(MaaEndControlPage, "_delayed_init", lambda self: None, raising=False)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        window = MainWindow()
        assert window._preview_timer.interval() == 3333

    def test_close_event_persists_queue(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.main_window as _mw
        from gui.pyqt6.i18n import get_locale_manager
        from gui.pyqt6.pages.maaend_control_page import MaaEndControlPage

        monkeypatch.setattr(_mw, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(_mw, "check_gpu", lambda: type("R", (), {"is_nvidia": True, "warning": None})())
        monkeypatch.setattr(_mw, "format_gpu_warning", lambda r: None)
        monkeypatch.setattr(_mw, "TrayIcon", lambda *a, **k: type("T", (), {"is_available": lambda self: False})())
        monkeypatch.setattr(MaaEndControlPage, "_delayed_init", lambda self: None, raising=False)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        window = MainWindow()
        calls = []
        original_persist = window._maaend_page._persist_state
        def fake_persist():
            calls.append(True)
        window._maaend_page._persist_state = fake_persist
        window.closeEvent(QCloseEvent())
        assert len(calls) == 1

    def test_bridge_accessible(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.main_window as _mw
        from gui.pyqt6.i18n import get_locale_manager
        from gui.pyqt6.pages.maaend_control_page import MaaEndControlPage

        monkeypatch.setattr(_mw, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(_mw, "check_gpu", lambda: type("R", (), {"is_nvidia": True, "warning": None})())
        monkeypatch.setattr(_mw, "format_gpu_warning", lambda r: None)
        monkeypatch.setattr(_mw, "TrayIcon", lambda *a, **k: type("T", (), {"is_available": lambda self: False})())
        monkeypatch.setattr(MaaEndControlPage, "_delayed_init", lambda self: None, raising=False)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        window = MainWindow()
        bridge = window.bridge()
        assert bridge is window._bridge
