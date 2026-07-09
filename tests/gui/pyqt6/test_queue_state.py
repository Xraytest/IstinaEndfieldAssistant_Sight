"""Tests for QueueState lifecycle and boundary conditions."""
from __future__ import annotations

import json

import pytest
from pathlib import Path

from gui.pyqt6.queue_state import QueueState


class TestQueueStateLifecycle:
    """Test QueueState full lifecycle: create, set items, save options, persist, reload, verify consistency."""

    def test_empty_initialization(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "state.json")
        assert state.queue_items == []
        assert state.saved_task_options == {}
        assert state.selected_task is None
        assert state.selected_preset is None

    def test_set_queue_items(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "state.json")
        items = [
            {"name": "task_a", "display_name": "Task A", "type": "task", "options": {"x": 1}},
            {"name": "task_b", "display_name": "Task B", "type": "task", "options": {"y": 2}},
        ]
        state.set_queue_items(items)
        assert len(state.queue_items) == 2
        assert state.queue_items[0]["name"] == "task_a"
        assert state.get_queue_item(0)["options"] == {"x": 1}
        assert state.get_queue_item(1)["name"] == "task_b"
        # Out-of-bounds returns None
        assert state.get_queue_item(5) is None

    def test_save_and_load_options(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "state.json")
        state.save_options("task_a", {"count": 3, "mode": "fast"})
        loaded = state.load_options("task_a")
        assert loaded == {"count": 3, "mode": "fast"}
        # Overwrite
        state.save_options("task_a", {"count": 5})
        assert state.load_options("task_a") == {"count": 5}
        # Non-existent returns empty dict
        assert state.load_options("missing") == {}

    def test_selected_task_and_preset_persistence(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        state = QueueState(state_path=path)
        state.set_selected_task("TaskA")
        state.set_selected_preset("DailyFull")
        state.save_options("TaskA", {"mode": "smart"})
        state.set_queue_items([{"name": "TaskA", "display_name": "TaskA", "type": "task", "options": {"mode": "smart"}}])
        assert state.persist() is True

        # Reload
        reloaded = QueueState(state_path=path)
        reloaded.load()
        assert reloaded.selected_task == "TaskA"
        assert reloaded.selected_preset == "DailyFull"
        assert reloaded.load_options("TaskA") == {"mode": "smart"}
        assert len(reloaded.queue_items) == 1

    def test_clear_queue(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "state.json")
        state.set_queue_items([
            {"name": "a", "display_name": "A", "type": "task", "options": {}},
            {"name": "b", "display_name": "B", "type": "task", "options": {}},
        ])
        state.clear_queue()
        assert state.queue_items == []

    def test_clear_saved_options(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "state.json")
        state.save_options("task_a", {"v": 1})
        state.save_options("task_b", {"v": 2})
        assert len(state.saved_task_options) == 2
        state.clear_saved_options("task_a")
        assert "task_a" not in state.saved_task_options
        assert state.saved_task_options["task_b"] == {"v": 2}

    def test_update_queue_item_options(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "state.json")
        state.set_queue_items([
            {"name": "a", "display_name": "A", "type": "task", "options": {"old": 1}},
        ])
        state.update_queue_item_options(0, {"new": 2})
        assert state.queue_items[0]["options"] == {"new": 2}

    def test_full_roundtrip_persistence(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        state = QueueState(state_path=path)
        state.set_selected_task("TaskX")
        state.set_selected_preset("QuickDaily")
        state.save_options("TaskX", {"repeat": 10})
        state.save_options("TaskY", {"repeat": 5})
        state.set_queue_items([
            {"name": "TaskX", "display_name": "TaskX", "type": "task", "options": {"repeat": 10}},
            {"name": "TaskY", "display_name": "TaskY", "type": "preset", "options": {"repeat": 5}},
        ])
        assert state.persist() is True
        assert path.exists()

        other = QueueState(state_path=path)
        other.load()
        assert other.selected_task == "TaskX"
        assert other.selected_preset == "QuickDaily"
        assert other.saved_task_options["TaskX"] == {"repeat": 10}
        assert other.saved_task_options["TaskY"] == {"repeat": 5}
        assert len(other.queue_items) == 2
        assert other.queue_items[0]["type"] == "task"
        assert other.queue_items[1]["type"] == "preset"


class TestQueueStateBoundaries:
    """Test boundary conditions: empty queue, illegal index, corrupt JSON, missing file."""

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "does_not_exist.json")
        # load should not raise
        state.load()
        assert state.queue_items == []
        assert state.selected_task is None

    def test_persist_creates_parent_dirs(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "deep" / "nested" / "state.json")
        state.set_queue_items([{"name": "x", "display_name": "X", "type": "task", "options": {}}])
        assert state.persist() is True
        assert (tmp_path / "deep" / "nested" / "state.json").exists()

    def test_load_corrupt_json(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("not json {{{", encoding="utf-8")
        state = QueueState(state_path=path)
        # Should not raise
        state.load()
        assert state.queue_items == []

    def test_load_json_with_invalid_queue_items(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        path.write_text(
            json.dumps({
                "queue_items": [
                    {"name": "valid", "type": "task", "options": {}},
                    "",  # invalid: not a dict
                    {"type": "task", "options": {}},  # invalid: no name
                    {"name": "  ", "type": "task", "options": {}},  # invalid: blank name after strip
                ]
            }),
            encoding="utf-8",
        )
        state = QueueState(state_path=path)
        state.load()
        # Only the first valid item should be loaded
        assert len(state.queue_items) == 1
        assert state.queue_items[0]["name"] == "valid"

    def test_get_queue_item_negative_index(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "state.json")
        state.set_queue_items([
            {"name": "a", "display_name": "A", "type": "task", "options": {}},
        ])
        assert state.get_queue_item(-1) is None

    def test_selected_task_preserved_when_missing_in_file(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        path.write_text(json.dumps({"selected_task": None, "selected_preset": None}), encoding="utf-8")
        state = QueueState(state_path=path)
        state.set_selected_task("Existing")
        state.load()
        # When file has None, existing value should be preserved (or logic may overwrite — verify actual behavior)
        # Actual logic: state.get("selected_task") or self._selected_task
        # So if file has None, it falls back to current value
        assert state.selected_task == "Existing"

    def test_empty_options_dict(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "state.json")
        state.save_options("task_a", {})
        assert state.load_options("task_a") == {}
        state.set_queue_items([{"name": "task_a", "display_name": "TaskA", "type": "task", "options": {}}])
        state.persist()
        reloaded = QueueState(state_path=tmp_path / "state.json")
        reloaded.load()
        assert reloaded.queue_items == [{"name": "task_a", "display_name": "TaskA", "type": "task", "options": {}}]
