"""Queue state persistence and management for MaaEnd control page."""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional


class QueueState:
    """Manages queue items and task options persistence."""

    def __init__(self, state_path: Optional[Path] = None) -> None:
        self._state_path = state_path or self._resolve_state_path()
        self._queue_items: List[Dict[str, Any]] = []
        self._saved_task_options: Dict[str, Dict[str, Any]] = {}
        self._selected_task: Optional[str] = None
        self._selected_preset: Optional[str] = None
        self._lock = threading.Lock()

    @staticmethod
    def _resolve_state_path() -> Path:
        try:
            from core.foundation.paths import get_project_root
            base = Path(get_project_root()) / "config"
        except Exception:
            base = Path(__file__).resolve().parent.parent.parent.parent / "config"
        base.mkdir(parents=True, exist_ok=True)
        return base / "maaend_task_state.json"

    @property
    def state_path(self) -> Path:
        return self._state_path

    @property
    def queue_items(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._queue_items)

    @property
    def saved_task_options(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {k: dict(v) for k, v in self._saved_task_options.items()}

    @property
    def selected_task(self) -> Optional[str]:
        with self._lock:
            return self._selected_task

    @property
    def selected_preset(self) -> Optional[str]:
        with self._lock:
            return self._selected_preset

    def set_selected_task(self, name: Optional[str]) -> None:
        with self._lock:
            self._selected_task = name

    def set_selected_preset(self, name: Optional[str]) -> None:
        with self._lock:
            self._selected_preset = name

    def set_state_path(self, path: Path) -> None:
        with self._lock:
            self._state_path = path

    def load(self) -> None:
        with self._lock:
            if not self._state_path.exists():
                return
            try:
                state = json.loads(self._state_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logging.getLogger(__name__).warning("QueueState load failed: %s", exc)
                self._backup_corrupt_state()
                return
            self._selected_task = state.get("selected_task") or self._selected_task
            self._selected_preset = state.get("selected_preset") or self._selected_preset
            task_options = state.get("task_options")
            if isinstance(task_options, dict):
                self._saved_task_options = {str(k): dict(v) for k, v in task_options.items() if isinstance(v, dict)}
            queue_items = state.get("queue_items")
            if isinstance(queue_items, list):
                self._queue_items = []
                for entry in queue_items:
                    if not isinstance(entry, dict):
                        continue
                    name = str(entry.get("name") or "").strip()
                    if not name:
                        continue
                    self._queue_items.append({
                        "name": name,
                        "display_name": str(entry.get("display_name") or name),
                        "type": entry.get("type", "task"),
                        "options": dict(entry.get("options") or {}),
                    })

    def _backup_corrupt_state(self) -> None:
        """将损坏的状态文件备份，避免每次启动都失败。"""
        try:
            backup = self._state_path.with_suffix(".json.bak")
            counter = 0
            while backup.exists():
                backup = self._state_path.with_suffix(f".json.bak.{counter}")
                counter += 1
            os.replace(self._state_path, backup)
        except Exception as exc:
            logging.getLogger(__name__).warning("QueueState backup corrupt file failed: %s", exc)

    def persist(self) -> bool:
        with self._lock:
            try:
                state = {
                    "selected_task": self._selected_task,
                    "selected_preset": self._selected_preset,
                    "queue_items": self._queue_items,
                    "task_options": self._saved_task_options,
                }
                self._state_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = self._state_path.with_suffix(".tmp")
                tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(tmp_path, self._state_path)
                return True
            except Exception as exc:
                logging.getLogger(__name__).warning("QueueState persist failed: %s", exc)
                return False

    def clear_queue(self) -> None:
        with self._lock:
            self._queue_items.clear()

    def clear_saved_options(self, task_name: str) -> None:
        with self._lock:
            self._saved_task_options.pop(task_name, None)

    def load_options(self, task_name: str) -> Dict[str, Any]:
        with self._lock:
            saved = self._saved_task_options.get(task_name)
            if isinstance(saved, dict):
                return dict(saved)
            return {}

    def save_options(self, task_name: str, options: Dict[str, Any]) -> None:
        with self._lock:
            self._saved_task_options[task_name] = dict(options)

    def update_queue_item_options(self, index: int, options: Dict[str, Any]) -> None:
        with self._lock:
            if 0 <= index < len(self._queue_items):
                self._queue_items[index]["options"] = dict(options)

    def update_queue_item_status(self, index: int, status: str) -> None:
        """安全地更新队列项的执行状态（running/success/failed）。"""
        with self._lock:
            if 0 <= index < len(self._queue_items):
                self._queue_items[index]["status"] = str(status)

    def set_queue_items(self, items: List[Dict[str, Any]]) -> None:
        with self._lock:
            self._queue_items = [dict(item) for item in items]

    def get_queue_item(self, index: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            if 0 <= index < len(self._queue_items):
                return dict(self._queue_items[index])
            return None
