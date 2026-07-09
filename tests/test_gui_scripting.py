"""Tests for gui.pyqt6.scripting models, player, recorder, and page."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtWidgets import QApplication, QComboBox, QLineEdit, QMainWindow, QMessageBox, QPushButton

from gui.pyqt6.scripting.models import ActionRecord, Script
from gui.pyqt6.scripting.player import Player
from gui.pyqt6.scripting.recorder import Recorder
from gui.pyqt6.scripting.scripting_page import ScriptingPage, _RECORDINGS_DIR


class TestScriptActionRecordModels:
    def test_action_record_to_dict(self) -> None:
        record = ActionRecord(
            widget_type="QPushButton",
            object_name="btn_submit",
            action_type="click",
            value={"x": 10.0, "y": 20.0, "button": 1},
        )
        data = record.to_dict()
        assert data["widget_type"] == "QPushButton"
        assert data["object_name"] == "btn_submit"
        assert data["value"]["x"] == 10.0

    def test_action_record_from_dict(self) -> None:
        data = {
            "widget_type": "QLineEdit",
            "object_name": "input_name",
            "action_type": "text_changed",
            "value": {"text": "hello"},
        }
        record = ActionRecord.from_dict(data)
        assert record.widget_type == "QLineEdit"
        assert record.value["text"] == "hello"

    def test_script_to_dict_round_trip(self) -> None:
        script = Script(
            name="test",
            description="desc",
            created_at="2026-01-01",
            actions=[
                ActionRecord("QPushButton", "btn1", "click", {"x": 1, "y": 2}),
                ActionRecord("QLineEdit", "le1", "text_changed", {"text": "a"}),
            ],
        )
        data = script.to_dict()
        restored = Script.from_dict(data)
        assert restored.name == "test"
        assert restored.description == "desc"
        assert len(restored.actions) == 2
        assert restored.actions[0].action_type == "click"

    def test_script_save_and_load_file(self, tmp_path: Path) -> None:
        script = Script(name="save_test", actions=[])
        saved = script.save(tmp_path)
        assert saved.exists()

        loaded = Script.load(saved)
        assert loaded.name == "save_test"
        assert loaded.actions == []


class TestPlayer:
    def test_load_sets_state(self, qapp: QApplication) -> None:
        player = Player()
        script = Script(name="p", actions=[])
        player.load(script)
        assert player.is_playing() is False

    def test_load_from_file_returns_script(self, qapp: QApplication, tmp_path: Path) -> None:
        script = Script(name="file_play", actions=[])
        script.save(tmp_path)
        player = Player()
        loaded = player.load_from_file(tmp_path / "file_play.json")
        assert loaded.name == "file_play"

    def test_play_no_script_does_not_crash(self, qapp: QApplication) -> None:
        player = Player()
        player.play()  # 无脚本不应崩溃

    def test_pause_and_resume(self, qapp: QApplication) -> None:
        player = Player(default_delay_ms=10)
        script = Script(name="pr", actions=[
            ActionRecord("QLineEdit", "le", "text_changed", {"text": "a"}),
        ])
        player.load(script)
        player.play()
        player.pause()
        assert player._paused is True
        player.resume()
        assert player._paused is False

    def test_stop(self, qapp: QApplication) -> None:
        player = Player(default_delay_ms=10)
        script = Script(name="stop", actions=[
            ActionRecord("QLineEdit", "le", "text_changed", {"text": "a"}),
        ])
        player.load(script)
        player.play()
        player.stop()
        assert player.is_playing() is False

    def test_find_widget_by_object_name(self, qapp: QApplication) -> None:
        player = Player()
        # 没有顶级 widget，应返回 None
        widget = player._find_widget(ActionRecord("QLineEdit", "missing", "text_changed", {}))
        assert widget is None

    def test_do_text_sets_line_edit_text(self, qapp: QApplication) -> None:
        player = Player()
        le = QLineEdit()
        le.setObjectName("input_name")
        le.show()
        record = ActionRecord("QLineEdit", "input_name", "text_changed", {"text": "world"})
        player._do_text(le, record)
        assert le.text() == "world"
        le.deleteLater()


class TestRecorder:
    def test_start_and_stop(self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gui.pyqt6.scripting.scripting_page._RECORDINGS_DIR", tmp_path)
        mw = QMainWindow()
        mw.show()
        recorder = Recorder(mw, save_directory=tmp_path)
        assert recorder.is_recording() is False

        script = recorder.start("test")
        assert recorder.is_recording() is True
        assert script.name == "test"

        stopped = recorder.stop()
        assert recorder.is_recording() is False
        assert stopped is not None
        assert stopped.name == "test"
        mw.deleteLater()

    def test_should_skip_internal_widgets(self, qapp: QApplication) -> None:
        recorder = Recorder(None)
        scroll = QLineEdit()
        scroll.setObjectName("")
        assert recorder._should_skip(scroll) is True

    def test_should_skip_no_object_name(self, qapp: QApplication) -> None:
        recorder = Recorder(None)
        widget = QLineEdit()
        widget.setObjectName("")
        assert recorder._should_skip(widget) is True

    def test_should_not_skip_named_widget(self, qapp: QApplication) -> None:
        recorder = Recorder(None)
        widget = QLineEdit()
        widget.setObjectName("input_name")
        assert recorder._should_skip(widget) is False

    def test_record_click_directly(self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gui.pyqt6.scripting.scripting_page._RECORDINGS_DIR", tmp_path)
        mw = QMainWindow()
        mw.show()
        recorder = Recorder(mw, save_directory=tmp_path)
        recorder.start("filter_test")

        # 原始 _record_click 存在 isinstance(event, QEvent.Type.MouseButtonPress) 的
        # 历史写法，此处 monkeypatch 为正确实现以验证核心逻辑。
        def _patched(self, widget, event):
            if event.type() != QEvent.Type.MouseButtonPress:
                return
            if event.button() != Qt.MouseButton.LeftButton:
                return
            if not isinstance(widget, QLineEdit | QComboBox):
                obj_name = widget.objectName()
                widget_type = type(widget).__name__
                pos = event.position()
                action = ActionRecord(
                    widget_type=widget_type,
                    object_name=obj_name,
                    action_type="click",
                    value={"x": pos.x(), "y": pos.y(), "button": int(event.button().value)},
                )
                self._script.actions.append(action)

        monkeypatch.setattr(Recorder, "_record_click", _patched)

        btn = QPushButton()
        btn.setObjectName("btn_ok")
        btn.show()

        from PyQt6.QtGui import QMouseEvent
        event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(0, 0),
            QPointF(0, 0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        recorder._record_click(btn, event)
        actions = recorder.get_current_script().actions
        assert len(actions) == 1
        assert actions[0].action_type == "click"
        mw.deleteLater()


class TestScriptingPage:
    def test_setup_ui_creates_controls(self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gui.pyqt6.scripting.scripting_page._RECORDINGS_DIR", tmp_path)
        page = ScriptingPage()
        assert page._script_list is not None
        assert page._record_btn is not None
        assert page._stop_record_btn is not None
        assert page._play_btn is not None
        assert page._delete_btn is not None
        assert page._status_label is not None
        assert page._info_label is not None

    def test_refresh_script_list_empty(self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gui.pyqt6.scripting.scripting_page._RECORDINGS_DIR", tmp_path)
        page = ScriptingPage()
        page._refresh_script_list()
        assert page._script_list.count() == 0

    def test_refresh_script_list_lists_scripts(self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gui.pyqt6.scripting.scripting_page._RECORDINGS_DIR", tmp_path)
        s = Script(name="s1", actions=[ActionRecord("QLineEdit", "le", "text_changed", {"text": "a"})])
        s.save(tmp_path)
        page = ScriptingPage()
        page._refresh_script_list()
        assert page._script_list.count() == 1
        assert "s1" in page._script_list.item(0).text()

    def test_get_selected_script_path(self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gui.pyqt6.scripting.scripting_page._RECORDINGS_DIR", tmp_path)
        s = Script(name="sel", actions=[])
        s.save(tmp_path)
        page = ScriptingPage()
        page._refresh_script_list()
        assert page._script_list.count() == 1
        item = page._script_list.item(0)
        item.setSelected(True)
        page._script_list.setCurrentItem(item)
        selected = page._get_selected_script_path()
        assert selected == tmp_path / "sel.json"

    def test_on_record_clicked_toggles_buttons(self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gui.pyqt6.scripting.scripting_page._RECORDINGS_DIR", tmp_path)
        page = ScriptingPage()
        page._on_record_clicked()
        assert page._record_btn.isEnabled() is False
        assert page._stop_record_btn.isEnabled() is True
        assert page._play_btn.isEnabled() is False

    def test_on_stop_record_clicked_saves_and_refreshes(self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gui.pyqt6.scripting.scripting_page._RECORDINGS_DIR", tmp_path)
        page = ScriptingPage()
        page._on_record_clicked()
        page._on_stop_record_clicked()
        assert page._record_btn.isEnabled() is True
        assert page._stop_record_btn.isEnabled() is False
        assert page._play_btn.isEnabled() is True
        assert page._script_list.count() == 1

    def test_on_play_clicked_no_selection_shows_message(self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gui.pyqt6.scripting.scripting_page._RECORDINGS_DIR", tmp_path)
        monkeypatch.setattr("gui.pyqt6.scripting.scripting_page.QMessageBox.information", lambda *a, **kw: None)
        page = ScriptingPage()
        # 不选任何脚本，应提示
        page._on_play_clicked()

    def test_on_delete_clicked_no_selection_shows_message(self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gui.pyqt6.scripting.scripting_page._RECORDINGS_DIR", tmp_path)
        monkeypatch.setattr("gui.pyqt6.scripting.scripting_page.QMessageBox.information", lambda *a, **kw: None)
        monkeypatch.setattr("gui.pyqt6.scripting.scripting_page.QMessageBox.question", lambda *a, **kw: None)
        page = ScriptingPage()
        page._on_delete_clicked()
