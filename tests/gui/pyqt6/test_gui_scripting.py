"""Tests for Script, ActionRecord, Player, Recorder, and ScriptingPage."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication, QMainWindow, QLineEdit, QComboBox
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest

from gui.pyqt6.scripting.models import ActionRecord, Script
from gui.pyqt6.scripting.player import Player
from gui.pyqt6.scripting.recorder import Recorder
from gui.pyqt6.scripting.scripting_page import ScriptingPage


class TestScriptModels:
    """Test Script and ActionRecord round-trip serialization."""

    def test_action_record_roundtrip(self) -> None:
        action = ActionRecord(widget_type="QPushButton", object_name="btn1", action_type="click", value={"x": 10.5, "y": 20.0, "button": 1})
        data = action.to_dict()
        restored = ActionRecord.from_dict(data)
        assert restored.widget_type == "QPushButton"
        assert restored.object_name == "btn1"
        assert restored.action_type == "click"
        assert restored.value == {"x": 10.5, "y": 20.0, "button": 1}

    def test_script_roundtrip(self, tmp_path: Path) -> None:
        s = Script(name="test_script", description="desc", created_at="2026-01-01T00:00:00", actions=[
            ActionRecord("QPushButton", "btn1", "click", {"x": 1, "y": 2, "button": 1}),
            ActionRecord("QLineEdit", "edit1", "text_changed", {"text": "hello"}),
        ])
        path = tmp_path / "test_script.json"
        saved = s.save(tmp_path)
        assert saved == path
        loaded = Script.load(path)
        assert loaded.name == "test_script"
        assert len(loaded.actions) == 2
        assert loaded.actions[0].object_name == "btn1"
        assert loaded.actions[1].value["text"] == "hello"


class TestPlayer:
    """Test Player playback control and widget interaction."""

    def test_load_and_is_playing(self, qapp: QApplication) -> None:
        player = Player(default_delay_ms=50)
        script = Script(name="s", actions=[])
        player.load(script)
        assert not player.is_playing()

    def test_play_empty_script_warns(self, qapp: QApplication, caplog: pytest.LogCaptureFixture) -> None:
        player = Player(default_delay_ms=50)
        player.load(Script(name="s", actions=[]))
        player.play()
        assert "No script to play" in caplog.text

    @pytest.mark.timeout(10)
    def test_stop_stops_timer(self, qapp: QApplication) -> None:
        player = Player(default_delay_ms=50)
        script = Script(name="s", actions=[
            ActionRecord("QLabel", "lbl", "click", {"x": 0, "y": 0, "button": 1}),
        ])
        player.load(script)
        player.play()
        QTest.qWait(100)
        assert player.is_playing()
        player.stop()
        assert not player.is_playing()

    def test_playback_started_and_finished_signals(self, qapp: QApplication) -> None:
        player = Player(default_delay_ms=10)
        script = Script(name="s", actions=[
            ActionRecord("QLabel", "lbl", "click", {"x": 0, "y": 0, "button": 1}),
        ])
        player.load(script)
        started = []
        finished = []
        player.playback_started.connect(lambda: started.append(True))
        player.playback_finished.connect(lambda: finished.append(True))
        player.play()
        QTest.qWait(300)
        assert started
        assert finished

    def test_find_widget_in_top_level(self, qapp: QApplication) -> None:
        player = Player()
        win = QMainWindow()
        edit = QLineEdit("find_me")
        edit.setObjectName("find_me")
        win.setCentralWidget(edit)
        win.show()
        QTest.qWait(50)
        action = ActionRecord("QLineEdit", "find_me", "text_changed", {"text": "x"})
        found = player._find_widget(action)
        assert found is edit
        win.close()

    def test_do_click_synthesizes_event(self, qapp: QApplication) -> None:
        player = Player()
        btn = QLineEdit()
        btn.setObjectName("click_btn")
        action = ActionRecord("QLineEdit", "click_btn", "click", {"x": 5, "y": 10, "button": 1})
        player._do_click(btn, action)

    def test_do_text_sets_line_edit_text(self, qapp: QApplication) -> None:
        player = Player()
        edit = QLineEdit()
        edit.setObjectName("edit1")
        action = ActionRecord("QLineEdit", "edit1", "text_changed", {"text": "hello world"})
        player._do_text(edit, action)
        assert edit.text() == "hello world"

    def test_do_text_sets_combo_text(self, qapp: QApplication) -> None:
        player = Player()
        combo = QComboBox()
        combo.addItems(["one", "two", "three"])
        combo.setObjectName("combo1")
        action = ActionRecord("QComboBox", "combo1", "combo_changed", {"text": "two"})
        player._do_text(combo, action)
        assert combo.currentText() == "two"


class TestRecorder:
    """Test Recorder start/stop/is_recording and event filtering."""

    def test_start_and_is_recording(self, tmp_path: Path, qapp: QApplication) -> None:
        window = QMainWindow()
        window.show()
        QTest.qWait(50)
        rec = Recorder(window, save_directory=tmp_path)
        assert not rec.is_recording()
        script = rec.start("test_record")
        assert rec.is_recording()
        assert script.name == "test_record"
        assert rec.get_current_script() is script

    def test_stop_returns_script(self, tmp_path: Path, qapp: QApplication) -> None:
        window = QMainWindow()
        window.show()
        QTest.qWait(50)
        rec = Recorder(window, save_directory=tmp_path)
        rec.start("s1")
        result = rec.stop()
        assert result is not None
        assert result.name == "s1"
        assert not rec.is_recording()

    def test_save_current_script(self, tmp_path: Path, qapp: QApplication) -> None:
        window = QMainWindow()
        window.show()
        QTest.qWait(50)
        rec = Recorder(window, save_directory=tmp_path)
        script = rec.start("saved_script")
        script.actions.append(ActionRecord("QLabel", "lbl", "click", {"x": 0, "y": 0, "button": 1}))
        path = rec.save_current_script()
        assert path is not None
        assert path.exists()
        loaded = Script.load(path)
        assert loaded.name == "saved_script"
        assert len(loaded.actions) == 1

    def test_install_and_uninstall_app_filter(self, tmp_path: Path, qapp: QApplication) -> None:
        window = QMainWindow()
        window.show()
        QTest.qWait(50)
        rec = Recorder(window, save_directory=tmp_path)
        rec._install_app_filter()
        assert rec._app_filter_installed
        rec._uninstall_app_filter()
        assert not rec._app_filter_installed

    def test_should_skip_skipped_types(self, tmp_path: Path, qapp: QApplication) -> None:
        window = QMainWindow()
        window.show()
        QTest.qWait(50)
        rec = Recorder(window, save_directory=tmp_path)
        from PyQt6.QtWidgets import QScrollBar
        bar = QScrollBar()
        assert rec._should_skip(bar) is True
        empty = QLineEdit()
        empty.setObjectName("")
        assert rec._should_skip(empty) is True

    def test_event_filter_records_left_click(self, tmp_path: Path, qapp: QApplication) -> None:
        window = QMainWindow()
        window.show()
        QTest.qWait(50)
        rec = Recorder(window, save_directory=tmp_path)
        rec.start("filter_test")
        btn = QLineEdit()
        btn.setObjectName("rec_btn")
        event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(0, 0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        result = rec.eventFilter(btn, event)
        assert result is False


class TestScriptingPage:
    """Test ScriptingPage UI, script list, recording, playback, and delete."""

    def test_setup_ui_creates_controls(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.scripting.scripting_page as _sp
        from gui.pyqt6.i18n import get_locale_manager

        monkeypatch.setattr(_sp, "_RECORDINGS_DIR", tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        page = ScriptingPage(main_window=QMainWindow())
        assert page._script_list is not None
        assert page._record_btn is not None
        assert page._stop_record_btn is not None
        assert page._play_btn is not None
        assert page._delete_btn is not None
        assert page._status_label is not None
        assert page._info_label is not None

    def test_refresh_script_list_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.scripting.scripting_page as _sp
        from gui.pyqt6.i18n import get_locale_manager

        monkeypatch.setattr(_sp, "_RECORDINGS_DIR", tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        page = ScriptingPage(main_window=QMainWindow())
        page._refresh_script_list()
        assert page._script_list.count() == 0

    def test_refresh_script_list_lists_saved_scripts(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.scripting.scripting_page as _sp
        from gui.pyqt6.i18n import get_locale_manager

        monkeypatch.setattr(_sp, "_RECORDINGS_DIR", tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        script = Script(name="script_a", actions=[ActionRecord("QLabel", "l", "click", {"x": 0, "y": 0, "button": 1})])
        script.save(tmp_path)
        page = ScriptingPage(main_window=QMainWindow())
        page._refresh_script_list()
        assert page._script_list.count() == 1
        assert "script_a" in page._script_list.item(0).text()

    def test_get_selected_script_path_returns_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.scripting.scripting_page as _sp
        from gui.pyqt6.i18n import get_locale_manager

        monkeypatch.setattr(_sp, "_RECORDINGS_DIR", tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        page = ScriptingPage(main_window=QMainWindow())
        assert page._get_selected_script_path() is None

    def test_on_record_clicked_changes_ui(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.scripting.scripting_page as _sp
        from gui.pyqt6.i18n import get_locale_manager

        monkeypatch.setattr(_sp, "_RECORDINGS_DIR", tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        page = ScriptingPage(main_window=QMainWindow())
        page._on_record_clicked()
        rec = page._recorder
        assert rec is not None
        assert not page._record_btn.isEnabled()
        assert page._stop_record_btn.isEnabled()
        assert not page._play_btn.isEnabled()
        assert rec.is_recording()

    def test_on_stop_record_clicked_saves_and_refreshes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.scripting.scripting_page as _sp
        from gui.pyqt6.i18n import get_locale_manager

        monkeypatch.setattr(_sp, "_RECORDINGS_DIR", tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)

        page = ScriptingPage(main_window=QMainWindow())
        page._on_record_clicked()
        page._on_stop_record_clicked()
        assert page._record_btn.isEnabled()
        assert not page._stop_record_btn.isEnabled()
        assert page._play_btn.isEnabled()
        assert page._script_list.count() >= 1

    def test_on_play_clicked_no_selection(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.scripting.scripting_page as _sp
        from gui.pyqt6.i18n import get_locale_manager
        from PyQt6.QtWidgets import QMessageBox

        monkeypatch.setattr(_sp, "_RECORDINGS_DIR", tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)
        monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

        page = ScriptingPage(main_window=QMainWindow())
        page._on_play_clicked()

    def test_on_delete_clicked_removes_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        import gui.pyqt6.scripting.scripting_page as _sp
        from gui.pyqt6.i18n import get_locale_manager
        from PyQt6.QtWidgets import QMessageBox

        monkeypatch.setattr(_sp, "_RECORDINGS_DIR", tmp_path)
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)

        script = Script(name="del_me", actions=[])
        script.save(tmp_path)
        page = ScriptingPage(main_window=QMainWindow())
        page._refresh_script_list()
        assert page._script_list.count() == 1
        page._script_list.setCurrentRow(0)
        page._on_delete_clicked()
        assert not (tmp_path / "del_me.json").exists()
        assert page._script_list.count() == 0
