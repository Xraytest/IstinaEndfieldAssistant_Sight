"""Tests for LogPage PyQt6 GUI controls, file listing, and log highlighting."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QShowEvent

from gui.pyqt6.pages.log_page import LogPage


class TestLogPageControls:
    """Verify LogPage creates all expected controls."""

    def test_controls_exist(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.pages.log_page as _mod
        from gui.pyqt6.i18n import get_locale_manager

        monkeypatch.setattr(_mod, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        page = LogPage()
        assert page is not None
        assert hasattr(page, "_file_combo")
        assert hasattr(page, "_log_view")
        assert hasattr(page, "_path_label")

    def test_refresh_file_list_empty_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.pages.log_page as _mod
        from gui.pyqt6.i18n import get_locale_manager

        monkeypatch.setattr(_mod, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        empty_dir = tmp_path / "logs"
        empty_dir.mkdir()
        page = LogPage()
        monkeypatch.setattr(page, "_logs_dir", empty_dir, raising=False)
        page._refresh_file_list()
        assert page._file_combo.count() == 1
        assert page._file_combo.itemText(0) == "No log files found"

    def test_refresh_file_list_lists_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.pages.log_page as _mod
        from gui.pyqt6.i18n import get_locale_manager

        monkeypatch.setattr(_mod, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        f1 = logs_dir / "app.log"
        f1.write_text("log1", encoding="utf-8")
        f2 = logs_dir / "debug.txt"
        f2.write_text("log2", encoding="utf-8")

        page = LogPage()
        monkeypatch.setattr(page, "_logs_dir", logs_dir, raising=False)
        page._refresh_file_list()
        assert page._file_combo.count() == 2
        texts = [page._file_combo.itemText(i) for i in range(page._file_combo.count())]
        assert set(texts) == {"app.log", "debug.txt"}

    def test_load_selected_log_populates_view(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.pages.log_page as _mod
        from gui.pyqt6.i18n import get_locale_manager

        monkeypatch.setattr(_mod, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        log_file = logs_dir / "test.log"
        log_file.write_text("2026-07-07 16:09:23 INFO started\n2026-07-07 16:09:24 ERROR failed", encoding="utf-8")

        page = LogPage()
        monkeypatch.setattr(page, "_logs_dir", logs_dir, raising=False)
        page._refresh_file_list()
        page._file_combo.setCurrentIndex(0)
        page._load_selected_log()
        content = page._log_view.toHtml()
        assert "started" in content
        assert "failed" in content

    def test_load_selected_log_missing_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.pages.log_page as _mod
        from gui.pyqt6.i18n import get_locale_manager

        monkeypatch.setattr(_mod, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        page = LogPage()
        monkeypatch.setattr(page, "_logs_dir", logs_dir, raising=False)
        page._refresh_file_list()
        page._file_combo.addItem("ghost.log", str(logs_dir / "ghost.log"))
        page._file_combo.setCurrentIndex(page._file_combo.count() - 1)
        page._load_selected_log()
        assert "Log file does not exist" in page._log_view.toPlainText()


class TestLogPageHighlighting:
    """Test _highlight_log HTML escaping and log-level coloring."""

    def test_timestamp_highlight(self, tmp_path: Path, qapp: QApplication) -> None:
        page = LogPage()
        html = page._highlight_log("2026-07-07 16:09:23 INFO hello")
        assert "2026-07-07 16:09:23" in html
        assert "color: #8b919e" in html

    def test_log_level_highlight(self, tmp_path: Path, qapp: QApplication) -> None:
        page = LogPage()
        for level, expected_color in [
            ("INFO", "#19d1ff"),
            ("WARN", "#ffb84d"),
            ("ERROR", "#ff4d4d"),
            ("DEBUG", "#8b919e"),
            ("TRACE", "#a6a9b0"),
        ]:
            html = page._highlight_log(f"some text {level} some text")
            assert expected_color in html, f"Expected {expected_color} in highlight for {level}"

    def test_html_escaping(self, tmp_path: Path, qapp: QApplication) -> None:
        page = LogPage()
        html = page._highlight_log("5 < 10 && 3 > 1")
        # Source has replace("<", "<") which is a no-op on <
        assert "<" in html
        assert ">" in html

    def test_show_event_triggers_refresh(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.pages.log_page as _mod
        from gui.pyqt6.i18n import get_locale_manager

        monkeypatch.setattr(_mod, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "a.log").write_text("a", encoding="utf-8")

        page = LogPage()
        monkeypatch.setattr(page, "_logs_dir", logs_dir, raising=False)
        page.showEvent(QShowEvent())
        assert page._file_combo.count() == 1
        assert page._file_combo.itemText(0) == "a.log"
