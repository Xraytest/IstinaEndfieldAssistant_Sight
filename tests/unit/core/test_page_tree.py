"""Tests for core/cloud/page_tree.py"""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any

import pytest

from core.cloud.page_tree import (
    ElementType,
    PageState,
    UIElement,
    PageNode,
    PageEdge,
    PageTree,
    hash_screenshot,
    hash_element,
)


class TestHashFunctions:
    def test_hash_screenshot_deterministic(self):
        h1 = hash_screenshot("base64data")
        h2 = hash_screenshot("base64data")
        assert h1 == h2
        assert len(h1) == 16

    def test_hash_screenshot_different_input(self):
        h1 = hash_screenshot("data1")
        h2 = hash_screenshot("data2")
        assert h1 != h2

    def test_hash_screenshot_empty_string(self):
        h = hash_screenshot("")
        assert isinstance(h, str)
        assert len(h) == 16

    def test_hash_element_deterministic(self):
        h1 = hash_element("box_coords")
        h2 = hash_element("box_coords")
        assert h1 == h2
        assert len(h1) == 8

    def test_hash_element_different_input(self):
        h1 = hash_element("box1")
        h2 = hash_element("box2")
        assert h1 != h2


class TestUIElement:
    def test_minimal_creation(self):
        elem = UIElement(
            element_id="e1",
            element_type=ElementType.BUTTON,
            label="领取",
            bbox=(0, 0, 100, 50),
            confidence=0.95,
        )
        assert elem.element_id == "e1"
        assert elem.element_type == ElementType.BUTTON
        assert elem.label == "领取"
        assert elem.bbox == (0, 0, 100, 50)
        assert elem.confidence == 0.95
        assert elem.explored is False
        assert elem.leads_to is None

    def test_to_dict_roundtrip(self):
        elem = UIElement(
            element_id="e1",
            element_type=ElementType.ICON,
            label="设置",
            bbox=(10, 20, 30, 40),
            confidence=0.8,
            explored=True,
            leads_to="page_settings",
            extra={"action": "tap"},
        )
        d = elem.to_dict()
        assert d["type"] == "icon"
        assert d["label"] == "设置"
        assert d["bbox"] == [10, 20, 30, 40]
        assert d["explored"] is True
        assert d["leads_to"] == "page_settings"

        elem2 = UIElement.from_dict(d)
        assert elem2.element_id == elem.element_id
        assert elem2.element_type == elem.element_type
        assert elem2.label == elem.label
        assert elem2.bbox == elem.bbox
        assert elem2.explored == elem.explored
        assert elem2.leads_to == elem.leads_to
        assert elem2.extra == {"action": "tap"}

    def test_defaults_from_dict(self):
        d = {
            "element_id": "e1",
            "type": "button",
            "label": "test",
            "bbox": [0, 0, 1, 1],
            "confidence": 0.5,
        }
        elem = UIElement.from_dict(d)
        assert elem.explored is False
        assert elem.leads_to is None
        assert elem.extra == {}

    def test_all_element_types(self):
        for et in ElementType:
            elem = UIElement(
                element_id="e", element_type=et, label="", bbox=(0, 0, 0, 0), confidence=0.0
            )
            assert elem.element_type == et


class TestPageNode:
    def test_minimal_creation(self):
        node = PageNode(page_id="p1", name="主界面", screenshot_hash="hash1")
        assert node.page_id == "p1"
        assert node.name == "主界面"
        assert node.screenshot_hash == "hash1"
        assert node.state == PageState.UNEXPLORED
        assert node.resolution == (1280, 720)
        assert node.elements == []

    def test_unexplored_elements_filters_text(self):
        node = PageNode(
            page_id="p1",
            name="test",
            screenshot_hash="h1",
            elements=[
                UIElement("e1", ElementType.BUTTON, "领取", (0, 0, 10, 10), 0.9),
                UIElement("e2", ElementType.TEXT, "描述文本", (0, 0, 10, 10), 0.9),
                UIElement("e3", ElementType.ICON, "图标", (0, 0, 10, 10), 0.9, explored=True),
                UIElement("e4", ElementType.BUTTON, "探索过的", (0, 0, 10, 10), 0.9, explored=True),
            ],
        )
        unexplored = node.unexplored_elements
        assert len(unexplored) == 1
        assert unexplored[0].element_id == "e1"

    def test_to_dict_roundtrip(self):
        node = PageNode(
            page_id="p1",
            name="战斗准备",
            screenshot_hash="hash_battle",
            elements=[
                UIElement("e1", ElementType.BUTTON, "开始战斗", (0, 0, 100, 50), 0.95),
            ],
            parent_edge="edge_from_menu",
            depth=2,
            state=PageState.EXPLORING,
            resolution=(1920, 1080),
            verification_count=3,
        )
        d = node.to_dict()
        assert d["page_id"] == "p1"
        assert d["name"] == "战斗准备"
        assert d["state"] == "exploring"
        assert d["depth"] == 2
        assert d["resolution"] == [1920, 1080]
        assert d["verification_count"] == 3
        assert len(d["elements"]) == 1

        node2 = PageNode.from_dict(d)
        assert node2.page_id == node.page_id
        assert node2.name == node.name
        assert node2.state == node.state
        assert node2.depth == node.depth
        assert node2.resolution == node.resolution
        assert len(node2.elements) == 1

    def test_icon_name_returns_string(self):
        node = PageNode(page_id="p1", name="test", screenshot_hash="h1")
        icon = node.icon_name
        assert isinstance(icon, str)

    def test_vlm_response_not_in_to_dict(self):
        node = PageNode(
            page_id="p1",
            name="test",
            screenshot_hash="h1",
            vlm_response={"elements": []},
        )
        d = node.to_dict()
        assert "vlm_response" not in d


class TestPageEdge:
    def test_minimal_creation(self):
        edge = PageEdge(
            edge_id="edge1",
            from_page_id="p1",
            to_page_id="p2",
            element_id="e1",
            action_type="tap",
        )
        assert edge.edge_id == "edge1"
        assert edge.action_type == "tap"
        assert edge.action_params == {}

    def test_to_dict(self):
        edge = PageEdge(
            edge_id="edge1",
            from_page_id="p1",
            to_page_id="p2",
            element_id="e1",
            action_type="swipe",
            action_params={"x": 100, "y": 200},
        )
        d = edge.to_dict()
        assert d["from"] == "p1"
        assert d["to"] == "p2"
        assert d["action_type"] == "swipe"
        assert d["params"] == {"x": 100, "y": 200}


class TestPageTree:
    def test_empty_tree(self):
        tree = PageTree()
        assert tree.root is None
        assert tree.nodes == {}
        assert tree.edges == []
        assert tree.stats == {"pages_discovered": 0, "elements_found": 0, "edges_created": 0}

    def test_add_node(self):
        tree = PageTree()
        node = PageNode("p1", "主界面", "hash1")
        tree.add_node(node)
        assert tree.get_node("p1") is node
        assert tree.stats["pages_discovered"] == 1
        assert tree.stats["elements_found"] == 0

    def test_add_node_updates_stats_elements(self):
        tree = PageTree()
        node = PageNode("p1", "test", "h1", elements=[
            UIElement("e1", ElementType.BUTTON, "btn", (0, 0, 1, 1), 0.9),
        ])
        tree.add_node(node)
        assert tree.stats["elements_found"] == 1

    def test_add_node_replacement_does_not_increase_stats(self):
        tree = PageTree()
        node1 = PageNode("p1", "旧名", "h1")
        tree.add_node(node1)
        assert tree.stats["pages_discovered"] == 1
        node2 = PageNode("p1", "新名", "h1")
        tree.add_node(node2)
        assert tree.stats["pages_discovered"] == 1

    def test_root_setter(self):
        tree = PageTree()
        node = PageNode("p1", "主界面", "hash1")
        tree.root = node
        assert tree.root is node
        assert tree._root_page_id == "p1"

    def test_get_node_by_hash(self):
        tree = PageTree()
        node = PageNode("p1", "test", "hash_abc")
        tree.add_node(node)
        found = tree.get_node_by_hash("hash_abc")
        assert found is node
        assert tree.get_node_by_hash("nonexistent") is None

    def test_add_edge_creates_edge(self):
        tree = PageTree()
        node = PageNode("p1", "test", "h1", elements=[
            UIElement("e1", ElementType.BUTTON, "btn", (0, 0, 1, 1), 0.9),
        ])
        tree.add_node(node)
        edge = PageEdge("edge1", "p1", "p2", "e1", "tap")
        tree.add_edge(edge)
        assert len(tree.edges) == 1
        assert tree.stats["edges_created"] == 1

    def test_add_edge_marks_element_explored(self):
        tree = PageTree()
        node = PageNode("p1", "test", "h1", elements=[
            UIElement("e1", ElementType.BUTTON, "btn", (0, 0, 1, 1), 0.9),
        ])
        tree.add_node(node)
        edge = PageEdge("edge1", "p1", "p2", "e1", "tap")
        tree.add_edge(edge)
        assert node.elements[0].explored is True
        assert node.elements[0].leads_to == "p2"

    def test_add_edge_duplicate_ignored(self):
        tree = PageTree()
        node = PageNode("p1", "test", "h1", elements=[
            UIElement("e1", ElementType.BUTTON, "btn", (0, 0, 1, 1), 0.9),
        ])
        tree.add_node(node)
        edge1 = PageEdge("edge1", "p1", "p2", "e1", "tap")
        edge2 = PageEdge("edge2", "p1", "p2", "e1", "tap")
        tree.add_edge(edge1)
        tree.add_edge(edge2)
        assert len(tree.edges) == 1
        assert tree.stats["edges_created"] == 1

    def test_get_edges_from(self):
        tree = PageTree()
        tree.add_node(PageNode("p1", "test", "h1"))
        tree.add_node(PageNode("p2", "test2", "h2"))
        tree.add_node(PageNode("p3", "test3", "h3"))
        tree.add_edge(PageEdge("e1", "p1", "p2", "elem1", "tap"))
        tree.add_edge(PageEdge("e2", "p1", "p3", "elem2", "tap"))
        tree.add_edge(PageEdge("e3", "p2", "p3", "elem3", "tap"))
        from_p1 = tree.get_edges_from("p1")
        assert len(from_p1) == 2
        assert tree.get_edges_from("nonexistent") == []

    def test_to_dict_roundtrip(self, tmp_path):
        tree = PageTree()
        node = PageNode("p1", "主界面", "hash1", elements=[
            UIElement("e1", ElementType.BUTTON, "领取", (0, 0, 100, 50), 0.95),
        ])
        tree.root = node
        tree.add_edge(PageEdge("edge1", "p1", "p2", "e1", "tap"))

        d = tree.to_dict()
        assert d["root_page_id"] == "p1"
        assert "p1" in d["nodes"]
        assert len(d["edges"]) == 1

        path = tmp_path / "test_tree.json"
        tree.save(str(path))
        tree2 = PageTree.load(str(path))
        assert tree2.root is not None
        assert tree2.root.page_id == "p1"
        assert len(tree2.edges) == 1
        assert tree2.stats["edges_created"] >= 1

    def test_save_load_file_roundtrip(self):
        tree = PageTree()
        node = PageNode("p1", "test", "hash1", elements=[
            UIElement("e1", ElementType.BUTTON, "btn", (0, 0, 1, 1), 0.9),
        ])
        tree.root = node
        tree.add_edge(PageEdge("edge1", "p1", "p2", "e1", "tap"))

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
            tree.save(path)

        try:
            tree2 = PageTree.load(path)
            assert tree2.root is not None
            assert tree2.root.name == "test"
            assert len(tree2.edges) == 1
            assert tree2.stats["pages_discovered"] >= 1
        finally:
            Path(path).unlink()

    def test_hash_index_on_load(self, tmp_path):
        tree = PageTree()
        tree.add_node(PageNode("p1", "test", "hash_a"))
        tree.add_node(PageNode("p2", "test2", "hash_b"))
        path = tmp_path / "test_hash.json"
        tree.save(str(path))
        tree2 = PageTree.load(str(path))
        assert tree2.get_node_by_hash("hash_a").page_id == "p1"
        assert tree2.get_node_by_hash("hash_b").page_id == "p2"

    def test_nodes_property_returns_copy(self):
        tree = PageTree()
        tree.add_node(PageNode("p1", "test", "h1"))
        nodes_copy = tree.nodes
        nodes_copy["p2"] = PageNode("p2", "fake", "h2")
        assert "p2" not in tree._nodes

    def test_edges_property_returns_copy(self):
        tree = PageTree()
        tree.add_edge(PageEdge("e1", "p1", "p2", "elem", "tap"))
        edges_copy = tree.edges
        edges_copy.append(PageEdge("e2", "p1", "p3", "elem", "tap"))
        assert len(tree._edges) == 1