from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.foundation.paths import get_project_root, ensure_src_path
from ..pipeline import PipelineGraph, PipelineNode, PipelineLoader, RecognitionType

logger = logging.getLogger(__name__)


class TaskLoader:
    def __init__(self, pipeline_loader: Optional[PipelineLoader] = None):
        self._pipeline_loader = pipeline_loader or PipelineLoader()
        self._tasks_root = get_project_root() / "assets" / "tasks"
        self._maaend_tasks_root = (
            get_project_root() / "SampleProgram" / "MaaEnd_Release" / "tasks"
        )
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._option_defs: Dict[str, Dict[str, Any]] = {}
        self._presets: Dict[str, Dict[str, Any]] = {}

    def load_task(self, task_name: str) -> Optional[Dict[str, Any]]:
        candidates = [
            self._tasks_root / f"{task_name}.json",
            self._tasks_root / task_name / f"{task_name}.json",
            self._maaend_tasks_root / f"{task_name}.json",
        ]
        for path in candidates:
            if path.is_file():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return data
                except Exception as e:
                    logger.error(f"Failed to load task '{task_name}' from {path}: {e}")
                    return None
        logger.debug(f"Task not found: {task_name}")
        return None

    def load_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        self._tasks = {}
        self._option_defs = {}
        sources = [
            self._tasks_root,
            self._maaend_tasks_root,
        ]
        for root in sources:
            if not root.is_dir():
                continue
            for json_path in root.rglob("*.json"):
                if json_path.name == "nodes.json":
                    continue
                if "preset" in json_path.parts:
                    continue
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    global_options = data.get("option")
                    if isinstance(global_options, dict):
                        self._option_defs.update(global_options)
                    task_list = data.get("task", [])
                    for task in task_list:
                        name = task.get("name")
                        if name:
                            self._tasks[name] = task
                            self._tasks[name]["_source"] = str(
                                json_path.relative_to(
                                    get_project_root()
                                )
                            )
                except Exception as e:
                    logger.debug(f"Failed to load task file {json_path}: {e}")
        return self._tasks

    def load_presets(self) -> Dict[str, Dict[str, Any]]:
        self._presets = {}
        sources = [
            self._tasks_root / "preset",
            self._maaend_tasks_root / "preset",
        ]
        for preset_dir in sources:
            if not preset_dir.is_dir():
                continue
            for json_path in preset_dir.glob("*.json"):
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    preset_list = data.get("preset", [])
                    for preset in preset_list:
                        name = preset.get("name")
                        if name:
                            self._presets[name] = preset
                            self._presets[name]["_source"] = str(
                                json_path.relative_to(get_project_root())
                            )
                except Exception as e:
                    logger.debug(f"Failed to load preset {json_path}: {e}")
        return self._presets

    def get_option_def(self, option_name: str) -> Optional[Dict[str, Any]]:
        return self._option_defs.get(option_name)

    def tasks(self) -> Dict[str, Dict[str, Any]]:
        if not self._tasks:
            return self.load_all_tasks()
        return self._tasks

    def presets(self) -> Dict[str, Dict[str, Any]]:
        if not self._presets:
            return self.load_presets()
        return self._presets
