"""Tests for gui.pyqt6.queue_state.QueueState lifecycle and edge cases."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gui.pyqt6.queue_state import QueueState


class TestQueueStateLifecycle:
    def test_full_lifecycle(self, tmp_path: Path) -> None:
        state_file = tmp_path / "queue_state.json"
        state = QueueState(state_path=state_file)

        assert state.queue_items == []
        assert state.saved_task_options == {}
        assert state.selected_task is None
        assert state.selected_preset is None

        state.set_selected_task("TaskA")
        state.set_selected_preset("PresetX")
        state.save_options("TaskA", {"repeat": 2, "speed": "fast"})
        state.set_queue_items([
            {"name": "TaskA", "display_name": "TaskA", "type": "task", "options": {"repeat": 2}},
            {"name": "TaskB", "display_name": "TaskB", "type": "task", "options": {}},
        ])

        assert state.persist() is True
        assert state_file.exists()

        reloaded = QueueState(state_path=state_file)
        reloaded.load()

        assert reloaded.selected_task == "TaskA"
        assert reloaded.selected_preset == "PresetX"
        assert reloaded.saved_task_options["TaskA"] == {"repeat": 2, "speed": "fast"}
        assert [item["name"] for item in reloaded.queue_items] == ["TaskA", "TaskB"]

    def test_round_trip_preserves_options(self, tmp_path: Path) -> None:
        state_file = tmp_path / "round_trip.json"
        original = QueueState(state_path=state_file)
        original.save_options("TaskX", {"mode": "hard", "count": 5})
        original.set_queue_items([
            {"name": "TaskX", "display_name": "TaskX", "type": "task", "options": {"mode": "hard"}},
        ])
        original.persist()

        restored = QueueState(state_path=state_file)
        restored.load()
        assert restored.get_queue_item(0)["options"] == {"mode": "hard"}
        assert restored.load_options("TaskX") == {"mode": "hard", "count": 5}


class TestQueueStateEdgeCases:
    def test_empty_queue_and_options(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "empty.json")
        state.persist()

        reloaded = QueueState(state_path=tmp_path / "empty.json")
        reloaded.load()
        assert reloaded.queue_items == []
        assert reloaded.saved_task_options == {}

    def test_illegal_index_returns_none(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "idx.json")
        assert state.get_queue_item(-1) is None
        assert state.get_queue_item(0) is None
        assert state.get_queue_item(999) is None

    def test_update_queue_item_out_of_range(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "update.json")
        state.set_queue_items([
            {"name": "TaskA", "display_name": "TaskA", "type": "task", "options": {}},
        ])
        state.update_queue_item_options(0, {"a": 1})
        assert state.get_queue_item(0)["options"] == {"a": 1}
        state.update_queue_item_options(5, {"a": 2})  # 不应崩溃
        assert state.get_queue_item(0)["options"] == {"a": 1}

    def test_corrupted_json_is_ignored(self, tmp_path: Path) -> None:
        state_file = tmp_path / "corrupt.json"
        state_file.write_text("not json", encoding="utf-8")

        state = QueueState(state_path=state_file)
        state.load()
        assert state.queue_items == []
        assert state.saved_task_options == {}

    def test_missing_file_is_ignored(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "missing.json")
        state.load()
        assert state.queue_items == []
        assert state.saved_task_options == {}

    def test_empty_queue_items_skipped_on_load(self, tmp_path: Path) -> None:
        state_file = tmp_path / "skip.json"
        state_file.write_text(
            json.dumps({"queue_items": [
                {"name": "", "options": {}},
                {"name": "TaskA", "options": {"x": 1}},
            ]}, ensure_ascii=False),
            encoding="utf-8",
        )
        state = QueueState(state_path=state_file)
        state.load()
        assert [item["name"] for item in state.queue_items] == ["TaskA"]

    def test_non_dict_queue_entries_skipped(self, tmp_path: Path) -> None:
        state_file = tmp_path / "skip_dict.json"
        state_file.write_text(
            json.dumps({"queue_items": [
                "bad_entry",
                {"name": "TaskA", "options": {}},
            ]}, ensure_ascii=False),
            encoding="utf-8",
        )
        state = QueueState(state_path=state_file)
        state.load()
        assert [item["name"] for item in state.queue_items] == ["TaskA"]


class TestQueueStateMutations:
    def test_clear_queue(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "clear.json")
        state.set_queue_items([
            {"name": "TaskA", "display_name": "TaskA", "type": "task", "options": {}},
        ])
        assert len(state.queue_items) == 1

        state.clear_queue()
        assert state.queue_items == []

    def test_clear_saved_options(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "clear_opts.json")
        state.save_options("TaskA", {"x": 1})
        state.save_options("TaskB", {"y": 2})
        assert len(state.saved_task_options) == 2

        state.clear_saved_options("TaskA")
        assert "TaskA" not in state.saved_task_options
        assert state.saved_task_options["TaskB"] == {"y": 2}

    def test_clear_saved_options_nonexistent(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "clear_none.json")
        state.save_options("TaskA", {"x": 1})
        state.clear_saved_options("TaskZ")  # 不应崩溃
        assert state.saved_task_options["TaskA"] == {"x": 1}

    def test_load_options_returns_copy(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "copy.json")
        state.save_options("TaskA", {"x": 1})
        opts = state.load_options("TaskA")
        opts["x"] = 999
        assert state.load_options("TaskA")["x"] == 1

    def test_selected_task_preset_persistence(self, tmp_path: Path) -> None:
        state_file = tmp_path / "sel.json"
        state = QueueState(state_path=state_file)
        state.set_selected_task("TaskA")
        state.set_selected_preset("PresetX")
        state.persist()

        reloaded = QueueState(state_path=state_file)
        reloaded.load()
        assert reloaded.selected_task == "TaskA"
        assert reloaded.selected_preset == "PresetX"

    def test_persist_failure_returns_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import logging

        state = QueueState(state_path=tmp_path / "fail.json")
        # 让父目录无法创建
        monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: (_ for _ in ()).throw(OSError("no space")))
        assert state.persist() is False

    def test_set_queue_items_shallow_copies(self, tmp_path: Path) -> None:
        state = QueueState(state_path=tmp_path / "copy_items.json")
        source = [{"name": "TaskA", "options": {"x": 1}}]
        state.set_queue_items(source)
        # 外层是新的 dict，但内层 options 仍是同一引用（浅拷贝）
        assert state.queue_items[0] is not source[0]
        source[0]["options"]["x"] = 999
        assert state.queue_items[0]["options"]["x"] == 999
