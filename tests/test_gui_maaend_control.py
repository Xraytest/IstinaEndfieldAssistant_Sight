"""Tests for gui.pyqt6.pages.maaend_control_page.MaaEndControlPage."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def _suppress_message_boxes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "gui.pyqt6.pages.maaend_control_page.QMessageBox.warning",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "gui.pyqt6.pages.maaend_control_page.QMessageBox.information",
        lambda *args, **kwargs: None,
    )


@pytest.fixture()
def control_page(qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from gui.pyqt6.cli_bridge import CLIBridge
    from gui.pyqt6.pages.maaend_control_page import MaaEndControlPage

    bridge = CLIBridge()
    monkeypatch.setattr(bridge, "execute", lambda command, params=None: None)
    monkeypatch.setattr(
        MaaEndControlPage,
        "_sync_execute",
        lambda self, command, params=None, timeout_ms=300000: {
            "status": "success",
            "tasks": {},
            "presets": {},
            "task_option_defs": {},
        },
    )
    monkeypatch.setattr(
        MaaEndControlPage,
        "_delayed_init",
        lambda self: None,
    )
    monkeypatch.setattr(
        MaaEndControlPage,
        "_load_metadata_cache",
        lambda self: None,
    )
    monkeypatch.setattr(
        "gui.pyqt6.pages.maaend_control_page.QueueState._resolve_state_path",
        lambda self: tmp_path / "maaend_task_state.json",
    )
    page = MaaEndControlPage(bridge=bridge)
    page._poll_timer = None
    return page


class TestMaaEndControlPage:
    def test_instantiation(self, control_page) -> None:
        assert control_page is not None

    def test_format_queue_label(self, control_page) -> None:
        label = control_page._format_queue_label("TaskA", "task", {"repeat": 2})
        assert label == "[TASK] TaskA"

    def test_parse_inline_task_name_with_options(self, control_page) -> None:
        name, options = control_page._parse_inline_task_name('TaskA|{"repeat": 2}')
        assert name == "TaskA"
        assert options == {"repeat": 2}

    def test_parse_inline_task_name_no_pipe(self, control_page) -> None:
        name, options = control_page._parse_inline_task_name("TaskA")
        assert name == "TaskA"
        assert options == {}

    def test_normalize_task_entry(self, control_page) -> None:
        name, options = control_page._normalize_task_entry({
            "name": 'TaskA|{"repeat": 2}',
            "option": {"speed": "fast"},
        })
        assert name == "TaskA"
        assert options == {"repeat": 2, "speed": "fast"}

    def test_normalize_runtime_entry(self, control_page) -> None:
        name, options = control_page._normalize_runtime_entry({
            "name": 'TaskA|{"repeat": 2}',
            "options": {"speed": "fast"},
        })
        assert name == "TaskA"
        assert options == {"repeat": 2, "speed": "fast"}

    def test_build_option_editor_with_task(self, control_page) -> None:
        control_page._tasks_cache = {
            "TaskA": {"option": ["mode"], "_option_defs": {"mode": {"type": "switch", "cases": [{"name": "Yes"}, {"name": "No"}]}}},
        }
        control_page._task_option_defs = {"mode": {"type": "switch", "cases": [{"name": "Yes"}, {"name": "No"}]}}
        control_page._selected_task = "TaskA"
        control_page._build_option_editor()
        assert len(control_page._option_widgets) == 1
        assert "mode" in control_page._option_widgets

    def test_collect_options(self, control_page) -> None:
        control_page._tasks_cache = {
            "TaskA": {"option": ["mode"], "_option_defs": {"mode": {"type": "switch", "cases": [{"name": "Yes"}, {"name": "No"}]}}},
        }
        control_page._task_option_defs = {"mode": {"type": "switch", "cases": [{"name": "Yes"}, {"name": "No"}]}}
        control_page._selected_task = "TaskA"
        control_page._build_option_editor()
        toggle = control_page._option_widgets["mode"]
        toggle.setChecked(True)
        options = control_page._collect_options()
        assert options["mode"] == "Yes"

    def test_update_execution_ui_idle(self, control_page) -> None:
        control_page._is_executing = False
        control_page._update_execution_ui()
        assert control_page._stop_btn.isEnabled() is False
        assert control_page._run_queue_btn.isEnabled() is True

    def test_update_execution_ui_running(self, control_page) -> None:
        control_page._is_executing = True
        control_page._update_execution_ui()
        assert control_page._stop_btn.isEnabled() is True
        assert control_page._run_queue_btn.isEnabled() is False

    def test_add_to_queue_task(self, control_page) -> None:
        control_page._tasks_cache = {"TaskA": {}}
        control_page._selected_task = "TaskA"
        control_page._build_option_editor()
        control_page._add_to_queue()
        assert len(control_page._queue_state.queue_items) == 1
        assert control_page._queue_state.queue_items[0]["name"] == "TaskA"

    def test_queue_move_up_down(self, control_page) -> None:
        control_page._queue_state.set_queue_items([
            {"name": "TaskA", "display_name": "TaskA", "type": "task", "options": {}},
            {"name": "TaskB", "display_name": "TaskB", "type": "task", "options": {}},
        ])
        control_page._restore_queue_ui()
        control_page._queue_list.setCurrentCell(1, 0)
        control_page._queue_move_up()
        assert control_page._queue_state.queue_items[0]["name"] == "TaskB"
        # move_up 后当前选中行为 0，move_down 将 TaskB 下移
        control_page._queue_move_down()
        assert control_page._queue_state.queue_items[1]["name"] == "TaskB"

    def test_queue_clear(self, control_page) -> None:
        control_page._queue_state.set_queue_items([
            {"name": "TaskA", "display_name": "TaskA", "type": "task", "options": {}},
        ])
        control_page._restore_queue_ui()
        control_page._queue_clear()
        assert len(control_page._queue_state.queue_items) == 0
        assert control_page._queue_list.rowCount() == 0

    def test_apply_preset_to_queue(self, control_page) -> None:
        control_page._presets_cache = {
            "PresetX": {"task": [{"name": "TaskA"}, {"name": "TaskB"}]},
        }
        control_page._selected_preset = "PresetX"
        control_page._apply_preset_to_queue()
        assert len(control_page._queue_state.queue_items) == 2
        assert control_page._queue_state.queue_items[0]["name"] == "TaskA"
        assert control_page._queue_state.queue_items[1]["name"] == "TaskB"

    def test_restore_queue_ui_populates_table(self, control_page) -> None:
        control_page._queue_state.set_queue_items([
            {"name": "TaskA", "display_name": "TaskA", "type": "task", "options": {}},
        ])
        control_page._restore_queue_ui()
        assert control_page._queue_list.rowCount() == 1

    def test_refresh_queue_list_updates_text(self, control_page) -> None:
        control_page._queue_state.set_queue_items([
            {"name": "TaskA", "display_name": "TaskA", "type": "task", "options": {"x": 1}},
        ])
        control_page._restore_queue_ui()
        control_page._refresh_queue_list()
        assert control_page._queue_list.item(0, 0).text() == "[TASK] TaskA"

    def test_persist_state_writes_file(self, control_page, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        control_page._state_path = state_file
        control_page._queue_state.set_state_path(state_file)
        control_page._selected_task = "TaskA"
        control_page._selected_preset = "PresetX"
        control_page._queue_state.set_queue_items([
            {"name": "TaskA", "display_name": "TaskA", "type": "task", "options": {}},
        ])
        control_page._persist_state()
        assert state_file.exists()
        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert data["selected_task"] == "TaskA"
        assert data["selected_preset"] == "PresetX"
        assert len(data["queue_items"]) == 1

    def test_delayed_init_is_noop_when_patched(self, control_page) -> None:
        control_page._delayed_init = lambda: None
        control_page._delayed_init()

    def test_sync_execute_returns_patched_value(self, control_page) -> None:
        result = control_page._sync_execute("metadata list", timeout_ms=5000)
        assert result is not None
        assert result.get("status") == "success"
