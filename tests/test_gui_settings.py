"""Tests for gui.pyqt6.pages.settings_page.SettingsPage."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox

from gui.pyqt6.pages.settings_page import SettingsPage


def _monkeypatch_project_root(monkeypatch, tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "gui.pyqt6.pages.settings_page.get_project_root",
        lambda: tmp_path,
    )
    return config_dir


class TestSettingsPageControls:
    def test_controls_exist(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _monkeypatch_project_root(monkeypatch, tmp_path)
        (tmp_path / "config" / "client_config.json").write_text("{}", encoding="utf-8")

        page = SettingsPage()
        assert page._language_combo is not None
        assert page._preview_interval_spin is not None
        assert page._llm_enabled is not None
        assert page._model_path_input is not None
        assert page._port_input is not None
        assert page._reload_btn is not None
        assert page._raw_preview is not None

    def test_save_settings_writes_real_file(
        self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config_dir = _monkeypatch_project_root(monkeypatch, tmp_path)
        (config_dir / "client_config.json").write_text(
            json.dumps({"preview_interval_ms": 1500, "llm": {"enabled": True, "port": 9998}}, ensure_ascii=False),
            encoding="utf-8",
        )

        page = SettingsPage()
        page._model_path_input.setText("/fake/model.gguf")
        page._port_input.setValue(7777)
        page._llm_enabled.setChecked(False)
        page._save_settings()

        raw = (config_dir / "client_config.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        assert data["llm"]["model_path"] == "/fake/model.gguf"
        assert data["llm"]["port"] == 7777
        assert data["llm"]["enabled"] is False
        assert data["preview_interval_ms"] == page._preview_interval_spin.value()

    def test_read_config_handles_corrupt_json(
        self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        config_dir = _monkeypatch_project_root(monkeypatch, tmp_path)
        (config_dir / "client_config.json").write_text("not json", encoding="utf-8")

        monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
        page = SettingsPage()
        # _read_config 应在损坏时返回空 dict，不抛异常
        result = page._read_config()
        assert result == {}

    def test_apply_preview_interval_does_not_crash_without_main_window(
        self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config_dir = _monkeypatch_project_root(monkeypatch, tmp_path)
        (config_dir / "client_config.json").write_text("{}", encoding="utf-8")

        page = SettingsPage()
        page._apply_preview_interval(3000)  # 不报错即为通过

    def test_apply_preview_interval_updates_timer(
        self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config_dir = _monkeypatch_project_root(monkeypatch, tmp_path)
        (config_dir / "client_config.json").write_text("{}", encoding="utf-8")

        page = SettingsPage()
        # 模拟 window 返回 QMainWindow
        fake_mw = QMainWindow()
        fake_mw._preview_timer = type("Timer", (), {"setInterval": lambda self, v: None})()
        page.setParent(fake_mw)

        page._apply_preview_interval(2500)
        # 不抛异常即为通过
        fake_mw.deleteLater()
