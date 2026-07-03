"""Tests for the modular template matching pipeline."""
from pathlib import Path

import cv2
import numpy as np
import pytest


def test_template_registry_singleton():
    from core.capability.element_recognition.pipeline import TemplateRegistry

    r1 = TemplateRegistry()
    r2 = TemplateRegistry()
    assert r1 is r2


def test_template_registry_load_module():
    from core.capability.element_recognition.pipeline import TemplateRegistry

    registry = TemplateRegistry()
    registry.clear()
    count = registry.load_module("Common")
    assert count > 0
    assert registry.is_module_loaded("Common")
    assert registry.get("Common/CameraMode") is not None


def test_template_registry_load_maaend_module():
    from core.capability.element_recognition.pipeline import TemplateRegistry

    registry = TemplateRegistry()
    registry.clear()
    count = registry.load_maaend_module("Common")
    assert count > 0


def test_template_registry_load_all():
    from core.capability.element_recognition.pipeline import TemplateRegistry

    registry = TemplateRegistry()
    registry.clear()
    total = registry.load_all()
    assert total > 0


def test_template_registry_resolve():
    from core.capability.element_recognition.pipeline import TemplateRegistry

    registry = TemplateRegistry()
    registry.clear()
    registry.load_module("Common")

    tpl = registry.resolve("Common/CameraMode.png")
    assert tpl is not None
    assert tpl.shape[0] > 0

    tpl2 = registry.resolve("Common/CameraMode")
    assert tpl2 is not None


def test_template_matcher_no_screen():
    from core.capability.element_recognition.pipeline import (
        TemplateRegistry, TemplateMatcher,
    )

    registry = TemplateRegistry()
    registry.clear()
    registry.load_module("Common")

    matcher = TemplateMatcher(registry)
    screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
    results = matcher.match(screen, "Common/CameraMode", threshold=0.99)
    assert isinstance(results, list)


def test_template_matcher_invalid_template():
    from core.capability.element_recognition.pipeline import (
        TemplateRegistry, TemplateMatcher,
    )

    registry = TemplateRegistry()
    registry.clear()

    matcher = TemplateMatcher(registry)
    screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
    results = matcher.match(screen, "NonExistentTemplate", threshold=0.8)
    assert results == []


def test_pipeline_node_from_dict():
    from core.capability.element_recognition.pipeline import (
        PipelineNode, RecognitionType,
    )

    data = {
        "recognition": "TemplateMatch",
        "template": "Common/Button/YellowConfirmButtonType1.png",
        "roi": [100, 200, 300, 400],
        "threshold": 0.85,
        "action": "Click",
        "next": ["NextNode"],
        "pre_delay": 500,
        "post_delay": 300,
    }
    node = PipelineNode.from_dict("TestNode", data)
    assert node.name == "TestNode"
    assert node.recognition == RecognitionType.TemplateMatch
    assert node.template == "Common/Button/YellowConfirmButtonType1.png"
    assert node.roi == [100, 200, 300, 400]
    assert node.threshold == 0.85
    assert node.action == "Click"
    assert node.next == ["NextNode"]
    assert node.pre_delay == 500
    assert node.post_delay == 300
    assert node.enabled is True


def test_pipeline_node_direct_hit():
    from core.capability.element_recognition.pipeline import (
        PipelineNode, RecognitionType,
    )

    node = PipelineNode.from_dict("DirectHitNode", {"recognition": "DirectHit"})
    assert node.recognition == RecognitionType.DirectHit


def test_pipeline_graph():
    from core.capability.element_recognition.pipeline import PipelineGraph, PipelineNode

    graph = PipelineGraph()
    node1 = PipelineNode(name="Start", next=["Middle"])
    node2 = PipelineNode(name="Middle", next=["End"])
    node3 = PipelineNode(name="End")

    graph.add_node(node1)
    graph.add_node(node2)
    graph.add_node(node3)

    assert graph.get_node("Start") is node1
    assert graph.get_node("End") is node3
    assert graph.get_entry("Start") is node1
    assert graph.get_entry("NonExistent") is None


def test_pipeline_loader_load_module():
    from core.capability.element_recognition.pipeline import PipelineLoader

    loader = PipelineLoader()
    graph = loader.load_module("common_buttons")
    assert len(graph.nodes) > 0


def test_pipeline_loader_load_all():
    from core.capability.element_recognition.pipeline import PipelineLoader

    loader = PipelineLoader()
    graph = loader.load_all()
    assert len(graph.nodes) > 0


def test_pipeline_runner_basic():
    from core.capability.element_recognition.pipeline import (
        TemplateRegistry, PipelineRunner, PipelineGraph,
        PipelineNode, RecognitionType,
    )

    registry = TemplateRegistry()
    registry.clear()
    registry.load_module("Common")

    runner = PipelineRunner(registry)
    graph = PipelineGraph()
    graph.add_node(PipelineNode(
        name="Start",
        recognition=RecognitionType.DirectHit,
        action="DoNothing",
        next=["End"],
    ))
    graph.add_node(PipelineNode(
        name="End",
        recognition=RecognitionType.DirectHit,
        action="DoNothing",
    ))

    screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
    result = runner.run(screen, graph, "Start", max_steps=5)
    assert result["status"] == "matched"
    assert "Start" in result["executed"]
    assert "End" in result["executed"]


def test_template_backend_load_module():
    from core.capability.element_recognition.backends import TemplateBackend

    backend = TemplateBackend(auto_load_modules=False)
    count = backend.load_module("Common")
    assert count > 0
    templates = backend.get_available_templates()
    assert len(templates) > 0


def test_template_backend_recognize():
    from core.capability.element_recognition.backends import TemplateBackend

    backend = TemplateBackend(auto_load_modules=False)
    backend.load_module("Common")

    screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
    results = backend.recognize(screen, template_names=["Common/CameraMode"], threshold=0.99)
    assert isinstance(results, list)


def test_task_loader():
    from core.capability.element_recognition.tasks import TaskLoader

    loader = TaskLoader()
    tasks = loader.load_all_tasks()
    assert len(tasks) > 0

    presets = loader.load_presets()
    assert len(presets) > 0


def test_assets_structure():
    """Verify the modular asset structure exists."""
    root = Path("assets")
    assert (root / "templates").is_dir()
    assert (root / "templates" / "Common").is_dir()
    assert (root / "templates" / "SceneManager").is_dir()
    assert (root / "templates" / "template_index.json").is_file()

    assert (root / "pipelines").is_dir()
    assert (root / "pipelines" / "pipeline_index.json").is_file()
    assert (root / "pipelines" / "common_buttons.json").is_file()
    assert (root / "pipelines" / "scene_manager.json").is_file()

    assert (root / "tasks").is_dir()
    assert (root / "tasks" / "task_index.json").is_file()
    assert (root / "tasks" / "preset").is_dir()
