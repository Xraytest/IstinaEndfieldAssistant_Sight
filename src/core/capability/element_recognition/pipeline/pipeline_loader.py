from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from core.foundation.paths import get_project_root, ensure_src_path
from .pipeline_node import PipelineNode, PipelineGraph
from .template_registry import TemplateRegistry

logger = logging.getLogger(__name__)


class PipelineLoader:
    def __init__(self, registry: Optional[TemplateRegistry] = None):
        self._registry = registry or TemplateRegistry()
        self._pipelines_root = get_project_root() / "assets" / "pipelines"
        self._maaend_root = get_project_root() / "SampleProgram" / "MaaEnd_Release" / "resource" / "pipeline"
        self._loaded_modules: Set[str] = set()

    def load_module(self, module_name: str) -> PipelineGraph:
        graph = PipelineGraph()
        candidates = [
            self._pipelines_root / f"{module_name}.json",
            self._pipelines_root / module_name / f"{module_name}.json",
        ]
        loaded = False
        for path in candidates:
            if path.is_file():
                self._load_file(path, graph)
                loaded = True
                break
        if not loaded:
            logger.debug(f"Pipeline module not found: {module_name}")
        self._loaded_modules.add(module_name)
        return graph

    def load_all(self) -> PipelineGraph:
        graph = PipelineGraph()
        if not self._pipelines_root.is_dir():
            logger.warning(f"Pipelines root not found: {self._pipelines_root}")
            return graph
        for fpath in sorted(self._pipelines_root.glob("*.json")):
            self._load_file(fpath, graph)
        return graph

    def load_maaend_pipeline(self) -> PipelineGraph:
        graph = PipelineGraph()
        path = self._maaend_root / "nodes.json"
        if not path.is_file():
            path_alt = self._maaend_root.parent.parent / "resource" / "pipeline" / "nodes.json"
            if path_alt.is_file():
                path = path_alt
        if path.is_file():
            self._load_file(path, graph)
            logger.info(f"Loaded MaaEnd pipeline: {path} ({len(graph.nodes)} nodes)")
        return graph

    def extract_module_nodes(
        self, graph: PipelineGraph, module_prefix: str
    ) -> PipelineGraph:
        sub = PipelineGraph()
        for name, node in graph.nodes.items():
            if name.startswith(module_prefix):
                sub.add_node(node)
        return sub

    def _load_file(self, path: Path, graph: PipelineGraph) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load pipeline file {path}: {e}")
            return
        count = 0
        for name, node_data in data.items():
            if not isinstance(node_data, dict):
                continue
            if not name.startswith("__"):
                try:
                    node = PipelineNode.from_dict(name, node_data)
                    graph.add_node(node)
                    if not node.next and not node.all_of and not node.any_of:
                        pass
                    count += 1
                except Exception as e:
                    logger.debug(f"Failed to parse pipeline node '{name}' in {path}: {e}")
        logger.debug(f"Loaded {count} pipeline nodes from {path}")
