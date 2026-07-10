"""Tests for SettingsPage PyQt6 GUI controls and config file I/O."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import QTimer

from gui.pyqt6.pages.settings_page import SettingsPage


class TestSettingsPageControls:
    """Verify SettingsPage creates all expected controls."""

    def test_controls_exist(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.pages.settings_page as _mod
        from gui.pyqt6.i18n import get_locale_manager

        monkeypatch.setattr(_mod, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        page = SettingsPage()
        assert page is not None
        assert hasattr(page, "_language_combo")
        assert hasattr(page, "_preview_interval_spin")
        assert hasattr(page, "_llm_enabled")
        assert hasattr(page, "_model_path_input")
        assert hasattr(page, "_port_input")
        assert hasattr(page, "_reload_btn")
        assert hasattr(page, "_raw_preview")

    def test_initial_control_states(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.pages.settings_page as _mod
        from gui.pyqt6.i18n import get_locale_manager

        config_path = tmp_path / "config"
        config_path.mkdir(parents=True, exist_ok=True)
        (config_path / "client_config.json").write_text(
            json.dumps({
                "llm": {"enabled": False, "model_path": "/models/model.bin", "port": 8888, "threads": 8},
                "preview_interval_ms": 2500,
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        monkeypatch.setattr(_mod, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        page = SettingsPage()
        assert page._llm_enabled.isChecked() is False
        assert page._model_path_input.text() == "/models/model.bin"
        assert page._port_input.value() == 8888
        assert page._preview_interval_spin.value() == 2500


class TestSettingsPageFileIO:
    """Test _save_settings writes real files and _read_config handles corrupt JSON."""

    def test_save_settings_writes_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.pages.settings_page as _mod
        from gui.pyqt6.i18n import get_locale_manager

        monkeypatch.setattr(_mod, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        page = SettingsPage()
        page._llm_enabled.setChecked(True)
        page._model_path_input.setText("/models/test.gguf")
        page._port_input.setValue(1234)
        page._preview_interval_spin.setValue(3000)
        page._save_settings()

        config_path = tmp_path / "config" / "client_config.json"
        assert config_path.exists()
        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert data["llm"]["enabled"] is True
        assert data["llm"]["model_path"] == "/models/test.gguf"
        assert data["llm"]["port"] == 1234
        assert data["preview_interval_ms"] == 3000
        assert data.get("cache") is None

    def test_read_config_corrupt_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.pages.settings_page as _mod
        from gui.pyqt6.i18n import get_locale_manager

        config_path = tmp_path / "config"
        config_path.mkdir(parents=True, exist_ok=True)
        (config_path / "client_config.json").write_text("not valid json {{{", encoding="utf-8")

        monkeypatch.setattr(_mod, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        page = SettingsPage()
        result = page._read_config()
        assert result == {}

    def test_read_config_missing_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.pages.settings_page as _mod
        from gui.pyqt6.i18n import get_locale_manager

        monkeypatch.setattr(_mod, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        page = SettingsPage()
        assert page._read_config() == {}


class TestSettingsPagePreviewInterval:
    """Test _apply_preview_interval effect on MainWindow._preview_timer."""

    def test_apply_preview_interval_sets_timer(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.pages.settings_page as _mod
        from gui.pyqt6.i18n import get_locale_manager

        config_path = tmp_path / "client_config.json"
        config_path.write_text(
            json.dumps({"llm": {"enabled": True, "model_path": "", "port": 9998, "threads": 12}, "preview_interval_ms": 1500}, ensure_ascii=False),
            encoding="utf-8",
        )
        monkeypatch.setattr(_mod, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        page = SettingsPage()
        # Use a real QMainWindow as parent so window() returns it
        window = QMainWindow()
        window._preview_timer = QTimer()
        page.setParent(window)

        page._apply_preview_interval(5000)
        assert window._preview_timer.interval() == 5000

    def test_apply_preview_interval_no_main_window(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.pages.settings_page as _mod
        from gui.pyqt6.i18n import get_locale_manager

        config_path = tmp_path / "client_config.json"
        config_path.write_text(
            json.dumps({"llm": {"enabled": True, "model_path": "", "port": 9998, "threads": 12}, "preview_interval_ms": 1500}, ensure_ascii=False),
            encoding="utf-8",
        )
        monkeypatch.setattr(_mod, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        page = SettingsPage()
        # No parent window set -> should not raise
        page._apply_preview_interval(9999)
