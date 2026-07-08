from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from ..pipeline import PipelineGraph, PipelineLoader, PipelineNode, PipelineRunner
from .task_loader import TaskLoader

logger = logging.getLogger(__name__)


class TaskRunner:
    def __init__(
        self,
        task_loader: Optional[TaskLoader] = None,
        pipeline_loader: Optional[PipelineLoader] = None,
        pipeline_runner: Optional[PipelineRunner] = None,
    ):
        self._task_loader = task_loader or TaskLoader(pipeline_loader)
        self._pipeline_loader = pipeline_loader or PipelineLoader()
        self._pipeline_runner = pipeline_runner or PipelineRunner()

    def execute_task(
        self,
        screen: np.ndarray,
        task_name: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        task = self._task_loader.tasks().get(task_name)
        if not task:
            return {"status": "error", "message": f"Task '{task_name}' not found"}
        entry = task.get("entry", task_name)
        graph = self._build_task_graph(task, options or {})
        result = self._pipeline_runner.run(screen, graph, entry)
        result["task"] = task_name
        return result

    def execute_preset(
        self,
        screen: np.ndarray,
        preset_name: str,
    ) -> List[Dict[str, Any]]:
        preset = self._task_loader.presets().get(preset_name)
        if not preset:
            return [{"status": "error", "message": f"Preset '{preset_name}' not found"}]
        results = []
        task_list = preset.get("task", [])
        for task_entry in task_list:
            name = task_entry.get("name")
            options = task_entry.get("option") or {}
            result = self.execute_task(screen, name, options)
            results.append(result)
            if result.get("status") == "error":
                break
        return results

    def _build_task_graph(
        self,
        task: Dict[str, Any],
        options: Dict[str, Any],
    ) -> PipelineGraph:
        graph = PipelineGraph()
        task_options = task.get("option", [])
        if not isinstance(task_options, list):
            task_options = []
        for option_name in task_options:
            value = options.get(option_name)
            if value is None:
                continue
            opt_def = self._task_loader.get_option_def(option_name)
            if opt_def:
                override = self._build_option_override(opt_def, value)
                for node_name, node_data in override.items():
                    if isinstance(node_data, dict):
                        node = PipelineNode.from_dict(node_name, node_data)
                        graph.add_node(node)
        return graph

    def _build_option_override(
        self, opt_def: Dict[str, Any], value: Any
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        opt_type = opt_def.get("type", "switch")
        cases = opt_def.get("cases", [])
        if opt_type == "switch":
            case_name = "Yes" if value else "No"
            for case in cases:
                if case.get("name") == case_name:
                    result.update(case.get("pipeline_override") or {})
                    return result
            default_case = opt_def.get("default_case")
            if default_case:
                for case in cases:
                    if case.get("name") == default_case:
                        result.update(case.get("pipeline_override") or {})
                        return result
        return result
