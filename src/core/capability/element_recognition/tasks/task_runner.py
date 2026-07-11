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
            # F05: 收集所有失败而非在首个错误处终止，便于上层汇总
            if result.get("status") == "error":
                logger.warning("预设任务 '%s' 执行失败，继续后续任务", name)
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
        # F06: 处理所有 option 类型（switch/checkbox/select/input），与 MaaEnd 侧一致。
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
        elif opt_type == "checkbox":
            selected = value if isinstance(value, list) else ([value] if value else [])
            default_case = opt_def.get("default_case") or []
            active_cases = selected if selected else default_case
            for case in cases:
                if case.get("name") in active_cases:
                    result.update(case.get("pipeline_override") or {})
        elif opt_type == "select":
            case_name = str(value)
            default_case = str(opt_def.get("default_case")) if opt_def.get("default_case") is not None else None
            active_case = case_name if case_name else default_case
            for case in cases:
                if case.get("name") == active_case:
                    result.update(case.get("pipeline_override") or {})
                    break
        elif opt_type == "input":
            result.update(opt_def.get("pipeline_override") or {})
        return result
