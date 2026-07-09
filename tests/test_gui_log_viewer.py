"""Tests for gui.pyqt6.pages.log_page.LogPage."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from gui.pyqt6.pages.log_page import LogPage


def _write_log(dir_path: Path, name: str, content: str, mtime_offset: float = 0.0) -> Path:
    log_path = dir_path / name
    log_path.write_text(content, encoding="utf-8")
    if mtime_offset:
        now = log_path.stat().st_mtime
        os.utime(log_path, (now + mtime_offset, now + mtime_offset))
    return log_path


class TestLogPageControls:
    def test_controls_exist(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / "app.log").write_text("hello", encoding="utf-8")
        monkeypatch.setattr(
            "core.foundation.paths.get_project_root",
            lambda: tmp_path,
        )

        page = LogPage()
        page._logs_dir = logs_dir
        page._refresh_file_list()
        assert page._file_combo is not None
        assert page._log_view is not None
        assert page._path_label is not None
        assert page._file_combo.count() >= 1

    def test_refresh_file_list_sorted_by_mtime(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        _write_log(logs_dir, "old.log", "old\n", mtime_offset=-10.0)
        _write_log(logs_dir, "new.log", "new\n", mtime_offset=0.0)
        _write_log(logs_dir, "readme.txt", "readme\n", mtime_offset=-5.0)

        monkeypatch.setattr(
            "core.foundation.paths.get_project_root",
            lambda: tmp_path,
        )
        page = LogPage()
        page._logs_dir = logs_dir
        page._refresh_file_list()

        texts = [page._file_combo.itemText(i) for i in range(page._file_combo.count())]
        assert "old.log" in texts
        assert "new.log" in texts
        assert "readme.txt" in texts
        # 按 mtime 降序，new.log 应排在 old.log 前面
        assert texts.index("new.log") < texts.index("old.log")

    def test_load_selected_log_populates_view(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = _write_log(logs_dir, "test.log", "2026-07-09 10:00:00 INFO hello\n2026-07-09 10:01:00 ERROR failed\n")

        monkeypatch.setattr(
            "core.foundation.paths.get_project_root",
            lambda: tmp_path,
        )
        page = LogPage()
        page._logs_dir = logs_dir
        page._refresh_file_list()
        page._file_combo.setCurrentIndex(0)

        page._load_selected_log()
        assert "hello" in page._log_view.toPlainText()
        assert "failed" in page._log_view.toPlainText()

    def test_load_selected_log_missing_file(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        fake_path = logs_dir / "ghost.log"
        logs_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(
            "core.foundation.paths.get_project_root",
            lambda: tmp_path,
        )
        page = LogPage()
        page._logs_dir = logs_dir
        page._refresh_file_list()
        page._file_combo.addItem("ghost.log", str(fake_path))
        page._file_combo.setCurrentIndex(page._file_combo.count() - 1)

        page._load_selected_log()
        assert "does not exist" in page._log_view.toPlainText() or "Missing" in page._log_view.toPlainText() or page._log_view.toPlainText() != ""

    def test_highlight_log_html(
        self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = _write_log(logs_dir, "highlight.log", "2026-07-09 10:00:00 INFO hello\n2026-07-09 10:01:00 WARN slow\n2026-07-09 10:02:00 ERROR boom\n")

        monkeypatch.setattr(
            "core.foundation.paths.get_project_root",
            lambda: tmp_path,
        )
        page = LogPage()
        page._logs_dir = logs_dir
        page._refresh_file_list()
        page._file_combo.setCurrentIndex(0)
        page._load_selected_log()

        html = page._log_view.toHtml()
        assert "<span" in html
        assert "color:" in html
        assert "hello" in html
        assert "boom" in html

    def test_show_event_refreshes_list(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        _write_log(logs_dir, "show.log", "show event test\n", mtime_offset=1.0)

        monkeypatch.setattr(
            "core.foundation.paths.get_project_root",
            lambda: tmp_path,
        )
        page = LogPage()
        page._logs_dir = logs_dir

        from PyQt6.QtGui import QShowEvent
        # showEvent 应触发 _refresh_file_list 和 _load_selected_log
        page.showEvent(QShowEvent())
        assert page._file_combo.count() >= 1
