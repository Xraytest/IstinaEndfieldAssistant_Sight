"""Tests for MaaEndControlPage PyQt6 GUI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.pages.maaend_control_page import MaaEndControlPage


def _create_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bridge=None) -> MaaEndControlPage:
    """Create a MaaEndControlPage with _delayed_init disabled and paths redirected to tmp_path."""
    import gui.pyqt6.pages.maaend_control_page as _mod
    from gui.pyqt6.i18n import get_locale_manager

    monkeypatch.setattr(_mod.MaaEndControlPage, "_delayed_init", lambda self: None)
    monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)
    monkeypatch.setattr("core.foundation.paths.get_project_root", lambda: tmp_path)

    if bridge is None:
        bridge = CLIBridge()
        # Prevent process start from crashing
        bridge._start_interactive_process = lambda: None

    page = MaaEndControlPage(bridge=bridge, parent=None)
    return page


class TestMaaEndControlPageInitAndFormatting:
    """Test _format_queue_label, _parse_inline_task_name, _normalize_task_entry, _normalize_runtime_entry."""

    def test_format_queue_label_task(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        assert page._format_queue_label("SellProduct", "task", {}) == "[TASK] 🛒售卖产品"

    def test_format_queue_label_preset(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        assert page._format_queue_label("DailyFull", "preset", {}) == "[PRESET] 全套日常"

    def test_format_queue_label_with_options(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        assert page._format_queue_label("TaskX", "task", {"count": 3}) == "[TASK] TaskX"

    def test_parse_inline_task_name_no_pipe(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        name, opts = page._parse_inline_task_name("SellProduct")
        assert name == "SellProduct"
        assert opts == {}

    def test_parse_inline_task_name_with_inline_options(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        name, opts = page._parse_inline_task_name("TaskX|{\"count\": 5}")
        assert name == "TaskX"
        assert opts == {"count": 5}

    def test_parse_inline_task_name_invalid_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        name, opts = page._parse_inline_task_name("TaskX|not json")
        assert name == "TaskX"
        assert opts == {"_inline": "not json"}

    def test_normalize_task_entry_simple(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        name, opts = page._normalize_task_entry({"name": "SellProduct", "option": {"count": 1}})
        assert name == "SellProduct"
        assert opts == {"count": 1}

    def test_normalize_task_entry_inline(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        name, opts = page._normalize_task_entry({"name": "TaskX|{\"x\": 1}", "option": {"y": 2}})
        assert name == "TaskX"
        assert opts == {"x": 1, "y": 2}

    def test_normalize_runtime_entry_with_display_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        entry = {"name": "SellProduct", "display_name": "SellProduct", "options": {"count": 1}}
        name, opts = page._normalize_runtime_entry(entry)
        assert name == "SellProduct"
        assert opts == {"count": 1}

    def test_normalize_runtime_entry_fallback_display_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        entry = {"display_name": "Fallback", "options": {}}
        name, opts = page._normalize_runtime_entry(entry)
        assert name == "Fallback"
        assert opts == {}


class TestMaaEndControlPageSyncExecute:
    """Test _sync_execute QEventLoop + QTimer timeout mechanism."""

    def test_sync_execute_times_out(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        # Very short timeout to force timeout
        result = page._sync_execute("task run", timeout_ms=10)
        assert result is None

    def test_sync_execute_returns_result(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)

        def emit_result():
            page._bridge.commandFinished.emit("task run", {"status": "success"})

        QTimer.singleShot(5, emit_result)
        result = page._sync_execute("task run", timeout_ms=100)
        assert result == {"status": "success"}


class TestMaaEndControlPageQueueOperations:
    """Test _add_to_queue, _queue_move_up/down, _queue_clear, _apply_preset_to_queue."""

    def test_queue_move_up(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        page._queue_state.set_queue_items([
            {"name": "a", "type": "task", "options": {}},
            {"name": "b", "type": "task", "options": {}},
        ])

        class FakeList:
            def currentRow(self):
                return 1
            def rowCount(self):
                return len(page._queue_state.queue_items)
            def setRowCount(self, n):
                pass
            def insertRow(self, n):
                pass
            def setItem(self, r, c, item):
                pass
            def setCurrentCell(self, row, col):
                pass

        page._queue_list = FakeList()
        page._queue_move_up()
        assert page._queue_state.queue_items[0]["name"] == "b"
        assert page._queue_state.queue_items[1]["name"] == "a"

    def test_queue_move_up_at_top_noop(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        page._queue_state.set_queue_items([
            {"name": "a", "type": "task", "options": {}},
        ])

        class FakeList:
            def currentRow(self):
                return 0
            def rowCount(self):
                return len(page._queue_state.queue_items)
            def setRowCount(self, n):
                pass
            def insertRow(self, n):
                pass
            def setItem(self, r, c, item):
                pass
            def setCurrentCell(self, row, col):
                pass

        page._queue_list = FakeList()
        page._queue_move_up()
        assert page._queue_state.queue_items[0]["name"] == "a"

    def test_queue_move_down(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        page._queue_state.set_queue_items([
            {"name": "a", "type": "task", "options": {}},
            {"name": "b", "type": "task", "options": {}},
        ])

        class FakeList:
            def currentRow(self):
                return 0
            def rowCount(self):
                return len(page._queue_state.queue_items)
            def setRowCount(self, n):
                pass
            def insertRow(self, n):
                pass
            def setItem(self, r, c, item):
                pass
            def setCurrentCell(self, row, col):
                pass

        page._queue_list = FakeList()
        page._queue_move_down()
        assert page._queue_state.queue_items[0]["name"] == "b"
        assert page._queue_state.queue_items[1]["name"] == "a"

    def test_queue_move_down_at_bottom_noop(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        page._queue_state.set_queue_items([
            {"name": "a", "type": "task", "options": {}},
        ])

        class FakeList:
            def currentRow(self):
                return 0
            def rowCount(self):
                return 1
            def setRowCount(self, n):
                pass
            def insertRow(self, n):
                pass
            def setItem(self, r, c, item):
                pass
            def setCurrentCell(self, row, col):
                pass

        page._queue_list = FakeList()
        page._queue_move_down()
        assert page._queue_state.queue_items[0]["name"] == "a"

    def test_queue_clear(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        page._queue_state.set_queue_items([
            {"name": "a", "type": "task", "options": {}},
        ])
        page._queue_state.clear_saved_options = lambda name: None

        class FakeList:
            def setRowCount(self, n):
                pass

        page._queue_list = FakeList()
        page._queue_clear()
        assert page._queue_state.queue_items == []

    def test_apply_preset_to_queue(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        page._selected_preset = "DailyFull"
        page._presets_cache = {
            "DailyFull": {"task": [{"name": "SellProduct", "option": {}}]}
        }
        page._queue_state.set_queue_items([
            {"name": "Old", "type": "task", "options": {}},
        ])
        page._queue_state.clear_saved_options = lambda name: None
        page._queue_state.set_queue_items = lambda items: setattr(page._queue_state, "_queue_items", items)
        page._queue_state.load_options = lambda name: {}
        page._queue_state.save_options = lambda name, opts: None
        page._queue_state.persist = lambda: None
        page._restore_queue_ui = lambda: None
        page._append_log = lambda *a, **k: None

        page._apply_preset_to_queue()
        assert page._queue_state.queue_items[0]["name"] == "SellProduct"


class TestMaaEndControlPageBuildOptionEditor:
    """Test _build_option_editor constructs widgets for task options."""

    def test_build_option_editor_with_options(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        page._selected_task = "TaskA"
        page._tasks_cache = {"TaskA": {"option": ["count", "mode"]}}
        page._task_option_defs = {
            "count": {"type": "input", "label": "Count", "inputs": [{"name": "val", "default": "1"}]},
            "mode": {"type": "switch", "label": "Mode", "cases": [{"name": "On"}, {"name": "Off"}], "default_case": "On"},
        }

        class FakeForm:
            def __init__(self):
                self.widgets = []
            def addWidget(self, w):
                self.widgets.append(w)
            def addStretch(self):
                pass
            def setEnabled(self, v):
                pass
            def count(self):
                return len(self.widgets)
            def takeAt(self, i):
                class FakeItem:
                    def widget(self):
                        return None
                return FakeItem()

        page._option_form = FakeForm()
        page._option_widgets = {}
        page._build_option_editor()
        assert "count" in page._option_widgets
        assert "mode" in page._option_widgets

    def test_build_option_editor_no_selected_task(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        page._selected_task = None

        class FakeForm:
            def addWidget(self, w):
                pass
            def addStretch(self):
                pass
            def setEnabled(self, v):
                pass
            def count(self):
                return 0
            def takeAt(self, i):
                class FakeItem:
                    def widget(self):
                        return None
                return FakeItem()

        page._option_form = FakeForm()
        page._build_option_editor()


class TestMaaEndControlPageCollectOptions:
    """Test _collect_options reads values from option widgets."""

    def test_collect_options_switch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        page._selected_task = "T"
        page._tasks_cache = {"T": {"option": ["mode"]}}
        page._task_option_defs = {"mode": {"type": "switch"}}
        toggle = type("T", (), {"value": lambda self: "On"})()
        page._option_widgets = {"mode": toggle}
        opts = page._collect_options()
        assert opts["mode"] == "On"

    def test_collect_options_select(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        page._selected_task = "T"
        page._tasks_cache = {"T": {"option": ["item"]}}
        page._task_option_defs = {"item": {"type": "select"}}
        combo = type("C", (), {"currentData": lambda self: "data_val", "currentText": lambda self: "text_val"})()
        page._option_widgets = {"item": combo}
        opts = page._collect_options()
        assert opts["item"] == "data_val"


class TestMaaEndControlPageUIUpdates:
    """Test _update_execution_ui state switching."""

    def test_update_execution_ui_idle(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        page._is_executing = False

        class Btn:
            def setEnabled(self, v):
                pass

        page._apply_preset_to_queue_btn = Btn()
        page._run_queue_btn = Btn()
        page._add_queue_btn = Btn()
        page._queue_up_btn = Btn()
        page._queue_down_btn = Btn()
        page._queue_clear_btn = Btn()
        page._stop_btn = Btn()
        page._retry_btn = Btn()

        class Progress:
            def setVisible(self, v):
                pass
            def setValue(self, v):
                pass

        page._progress_bar = Progress()

        class Label:
            def setText(self, t):
                pass
            def setStyleSheet(self, s):
                pass

        page._status_label = Label()
        page._failed_indices = []
        page.execution_state_changed = type("S", (), {"emit": lambda self, v: None})()
        page._pulse_status_label = lambda: None
        page._update_execution_ui()

    def test_update_execution_ui_running(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        page._is_executing = True

        class Btn:
            def setEnabled(self, v):
                pass

        page._apply_preset_to_queue_btn = Btn()
        page._run_queue_btn = Btn()
        page._add_queue_btn = Btn()
        page._queue_up_btn = Btn()
        page._queue_down_btn = Btn()
        page._queue_clear_btn = Btn()
        page._stop_btn = Btn()
        page._retry_btn = Btn()

        class Progress:
            def setVisible(self, v):
                pass
            def setValue(self, v):
                pass

        page._progress_bar = Progress()

        class Label:
            def setText(self, t):
                pass
            def setStyleSheet(self, s):
                pass

        page._status_label = Label()
        page._failed_indices = [1]
        page.execution_state_changed = type("S", (), {"emit": lambda self, v: None})()
        page._pulse_status_label = lambda: None
        page._update_execution_ui()

    def test_restore_queue_ui(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        page._queue_state.set_queue_items([
            {"name": "A", "type": "task", "options": {}},
            {"name": "B", "type": "task", "options": {}},
        ])

        class FakeList:
            def setRowCount(self, n):
                pass
            def rowCount(self):
                return len(page._queue_state.queue_items)
            def insertRow(self, n):
                pass
            def setItem(self, r, c, item):
                pass

        page._queue_list = FakeList()
        page._format_queue_label = lambda name, t, opts: f"[{t}] {name}"
        page._restore_queue_ui()

    def test_refresh_queue_list(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        page._queue_state.set_queue_items([{"name": "A", "type": "task", "options": {}}])
        page._queue_state.get_queue_item = lambda i: {"name": "A", "type": "task", "options": {}}

        class FakeItem:
            def setText(self, t):
                pass

        class FakeList:
            def rowCount(self):
                return 1
            def item(self, r, c):
                return FakeItem()

        page._queue_list = FakeList()
        page._format_queue_label = lambda n, t, o: f"[{t}] {n}"
        page._refresh_queue_list()

    def test_persist_state(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        page = _create_page(tmp_path, monkeypatch)
        page._queue_state.set_state_path = lambda p: None
        page._queue_state.set_selected_task = lambda n: None
        page._queue_state.set_selected_preset = lambda n: None
        page._queue_state.persist = lambda: True
        page._state_path = tmp_path / "state.json"
        page._selected_task = "TaskX"
        page._selected_preset = "DailyFull"
        page._persist_state()
