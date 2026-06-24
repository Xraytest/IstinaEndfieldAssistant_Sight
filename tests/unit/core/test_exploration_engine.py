"""Tests for core/cloud/exploration_engine.py"""

import json
from typing import Dict, Any, Optional, List
from unittest.mock import MagicMock, patch

import pytest

import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from core.cloud.exploration_engine import (
        ExplorationEngine,
        ExplorationConfig,
        ExplorationState,
        EXPLORATION_SYSTEM_PROMPT,
        ELEMENT_VERIFY_PROMPT,
    )
from core.cloud.page_tree import (
    UIElement,
    ElementType,
    PageNode,
    PageState,
)


class TestParseJsonFromText:
    def test_parse_valid_json_object(self):
        engine = ExplorationEngine()
        text = '{"page_name": "主界面", "elements": []}'
        result = engine._parse_json_from_text(text)
        assert result is not None
        assert result["page_name"] == "主界面"

    def test_parse_json_with_markdown_block(self):
        engine = ExplorationEngine()
        text = 'Some text\n```json\n{"key": "value"}\n```\nmore text'
        result = engine._parse_json_from_text(text)
        assert result is not None
        assert result["key"] == "value"

    def test_parse_json_with_code_fence(self):
        engine = ExplorationEngine()
        text = '```json\n{"elements": [{"id": "e1"}]}\n```'
        result = engine._parse_json_from_text(text)
        assert result is not None
        assert len(result["elements"]) == 1

    def test_parse_invalid_json_returns_none(self):
        engine = ExplorationEngine()
        text = "这不是JSON内容"
        result = engine._parse_json_from_text(text)
        assert result is None

    def test_parse_empty_string(self):
        engine = ExplorationEngine()
        assert engine._parse_json_from_text("") is None

    def test_parse_none(self):
        engine = ExplorationEngine()
        assert engine._parse_json_from_text(None) is None  # type: ignore

    def test_parse_nested_json(self):
        engine = ExplorationEngine()
        text = '{"page": {"name": "test", "elements": [{"id": "e1", "type": "button"}]}}'
        result = engine._parse_json_from_text(text)
        assert result is not None
        assert result["page"]["name"] == "test"

    def test_parse_json_with_extra_text_around(self):
        engine = ExplorationEngine()
        text = "Header\n\n{\"a\": 1}\n\nFooter"
        result = engine._parse_json_from_text(text)
        assert result is not None
        assert result["a"] == 1

    def test_parse_malformed_json_inside_fence(self):
        engine = ExplorationEngine()
        text = '```json\n{invalid json}\n```'
        result = engine._parse_json_from_text(text)
        assert result is None


class TestDictToElement:
    def test_basic_conversion(self):
        engine = ExplorationEngine()
        elem_dict = {
            "id": "e1",
            "type": "button",
            "label": "领取",
            "bbox": [100, 200, 300, 400],
            "confidence": 0.95,
            "action": "tap",
        }
        element = engine._dict_to_element("e1", elem_dict)
        assert element.element_id == "e1"
        assert element.element_type == ElementType.BUTTON
        assert element.label == "领取"
        assert element.bbox == (100.0, 200.0, 300.0, 400.0)
        assert element.confidence == 0.95

    def test_unknown_type_falls_back(self):
        engine = ExplorationEngine()
        elem_dict = {
            "id": "e1",
            "label": "test",
            "bbox": [0, 0, 1, 1],
        }
        element = engine._dict_to_element("e1", elem_dict)
        assert element.element_type == ElementType.UNKNOWN

    def test_invalid_bbox_normalized(self):
        engine = ExplorationEngine()
        elem_dict = {
            "id": "e1",
            "type": "button",
            "label": "test",
            "bbox": [1, 2],
            "confidence": 0.5,
        }
        element = engine._dict_to_element("e1", elem_dict)
        assert element.bbox == (0.0, 0.0, 0.0, 0.0)

    def test_missing_confidence_default(self):
        engine = ExplorationEngine()
        elem_dict = {
            "id": "e1",
            "type": "icon",
            "label": "test",
            "bbox": [0, 0, 10, 10],
        }
        element = engine._dict_to_element("e1", elem_dict)
        assert element.confidence == 0.5

    def test_dict_roundtrip(self):
        engine = ExplorationEngine()
        elem_dict = {
            "id": "e1",
            "type": "tab",
            "label": "每日",
            "bbox": [50, 60, 150, 160],
            "confidence": 0.9,
            "action": "tap",
            "description": "每日任务标签",
        }
        element = engine._dict_to_element("e1", elem_dict)
        assert element.element_type == ElementType.TAB
        assert element.extra["action"] == "tap"
        assert element.extra["description"] == "每日任务标签"


class TestEnqueueElements:
    def test_enqueue_unexplored_elements(self):
        engine = ExplorationEngine()
        node = PageNode(
            page_id="p1",
            name="test",
            screenshot_hash="h1",
            elements=[
                UIElement("e1", ElementType.BUTTON, "btn1", (0, 0, 10, 10), 0.9),
                UIElement("e2", ElementType.TEXT, "text1", (0, 0, 10, 10), 0.9),
                UIElement("e3", ElementType.ICON, "icon1", (0, 0, 10, 10), 0.9, explored=True),
            ],
        )
        engine._enqueue_elements(node)
        assert len(engine._explore_queue) == 1
        assert engine._explore_queue[0][0] == "p1"
        assert engine._explore_queue[0][1] == "e1"

    def test_empty_elements_no_enqueue(self):
        engine = ExplorationEngine()
        node = PageNode("p1", "test", "h1")
        engine._enqueue_elements(node)
        assert engine._explore_queue == []


class TestFindNextUnvisited:
    def test_returns_sorted_by_confidence(self):
        engine = ExplorationEngine()
        engine._visited_pages.add("p1")
        node = PageNode("p1", "test", "h1", elements=[
            UIElement("e1", ElementType.BUTTON, "btn1", (0, 0, 10, 10), 0.5),
            UIElement("e2", ElementType.BUTTON, "btn2", (0, 0, 10, 10), 0.9),
            UIElement("e3", ElementType.BUTTON, "btn3", (0, 0, 10, 10), 0.7),
        ])
        engine._page_tree.add_node(node)
        result = engine._find_next_unvisited()
        assert len(result) == 3
        assert result[0][2].element_id == "e2"  # highest confidence first

    def test_filters_low_confidence(self):
        engine = ExplorationEngine()
        engine._visited_pages.add("p1")
        node = PageNode("p1", "test", "h1", elements=[
            UIElement("e1", ElementType.BUTTON, "btn1", (0, 0, 10, 10), 0.3),
            UIElement("e2", ElementType.BUTTON, "btn2", (0, 0, 10, 10), 0.8),
        ])
        engine._page_tree.add_node(node)
        result = engine._find_next_unvisited()
        assert len(result) == 1
        assert result[0][2].element_id == "e2"

    def test_no_visited_pages(self):
        engine = ExplorationEngine()
        result = engine._find_next_unvisited()
        assert result == []

    def test_limits_to_five(self):
        engine = ExplorationEngine()
        engine._visited_pages.add("p1")
        elements = [
            UIElement(f"e{i}", ElementType.BUTTON, f"btn{i}", (0, 0, 10, 10), 0.9)
            for i in range(10)
        ]
        node = PageNode("p1", "test", "h1", elements=elements)
        engine._page_tree.add_node(node)
        result = engine._find_next_unvisited()
        assert len(result) <= 5

    def test_all_explored_returns_empty(self):
        engine = ExplorationEngine()
        engine._visited_pages.add("p1")
        node = PageNode("p1", "test", "h1", elements=[
            UIElement("e1", ElementType.BUTTON, "btn1", (0, 0, 10, 10), 0.9, explored=True),
        ])
        engine._page_tree.add_node(node)
        result = engine._find_next_unvisited()
        assert result == []


class TestCallbacks:
    def test_on_and_emit(self):
        engine = ExplorationEngine()
        collected: list = []

        def on_page_discovered(**kwargs):
            collected.append(("page_discovered", kwargs))

        engine.on("page_discovered", on_page_discovered)
        engine._emit("page_discovered", page_id="p1")
        assert len(collected) == 1
        assert collected[0][1]["page_id"] == "p1"

    def test_unknown_event_does_not_crash(self):
        engine = ExplorationEngine()
        engine._emit("nonexistent", data="test")


class TestParseElementsFromVlm:
    def test_normalized_elements(self):
        engine = ExplorationEngine()
        vlm_result = {
            "elements": [
                {"id": "e1", "type": "button", "label": "领取", "bbox": [0, 0, 10, 10], "confidence": 0.9},
            ]
        }
        result = engine._parse_elements_from_vlm(vlm_result)
        assert len(result) == 1
        assert result[0]["label"] == "领取"
        assert result[0]["action"] == "tap"

    def test_missing_fields_filled(self):
        engine = ExplorationEngine()
        vlm_result = {
            "elements": [
                {"id": "e1", "type": "button", "bbox": [0, 0, 10, 10]},
            ]
        }
        result = engine._parse_elements_from_vlm(vlm_result)
        assert result[0]["confidence"] == 0.7
        assert result[0]["action"] == "tap"

    def test_normalizes_bbox_2d(self):
        engine = ExplorationEngine()
        vlm_result = {
            "elements": [
                {"bbox_2d": [100, 200, 300, 400], "label": "test", "confidence": 0.8},
            ]
        }
        result = engine._parse_elements_from_vlm(vlm_result)
        assert result[0]["bbox"] == [100, 200, 300, 400]

    def test_normalizes_text_content(self):
        engine = ExplorationEngine()
        vlm_result = {
            "elements": [
                {"text_content": "确认", "bbox": [0, 0, 10, 10], "confidence": 0.8},
            ]
        }
        result = engine._parse_elements_from_vlm(vlm_result)
        assert result[0]["label"] == "确认"

    def test_non_dict_elems_skipped(self):
        engine = ExplorationEngine()
        vlm_result = {
            "elements": ["string_elem", 123, None],
        }
        result = engine._parse_elements_from_vlm(vlm_result)
        assert result == []

    def test_reply_fallback(self):
        engine = ExplorationEngine()
        vlm_result = {
            "reply": '{"elements": [{"id": "e1", "type": "button", "label": "fallback", "bbox": [0, 0, 10, 10], "confidence": 0.5}]}',
        }
        result = engine._parse_elements_from_vlm(vlm_result)
        assert len(result) == 1
        assert result[0]["label"] == "fallback"

    def test_generated_id_when_missing(self):
        engine = ExplorationEngine()
        vlm_result = {
            "elements": [
                {"bbox": [0, 0, 10, 10], "confidence": 0.8},
            ]
        }
        result = engine._parse_elements_from_vlm(vlm_result)
        assert result[0]["id"].startswith("elem_")


class TestProperties:
    def test_initial_state(self):
        engine = ExplorationEngine()
        assert engine.state == ExplorationState.IDLE
        assert engine.running is False
        assert engine.stats == {"vlm_calls": 0, "pages_found": 0, "elements_found": 0, "taps": 0, "errors": 0}
        assert engine.page_tree is not None

    def test_config_defaults(self):
        config = ExplorationConfig()
        assert config.device_serial == ""
        assert config.server_host == "127.0.0.1"
        assert config.server_port == 9999
        assert config.tap_wait_time == 2.0
        assert config.max_depth == 20
        assert config.max_pages == 200

    def test_pause_resume(self):
        engine = ExplorationEngine()
        engine.pause()
        assert engine._pause_event.is_set() is False
        engine.resume()
        assert engine._pause_event.is_set() is True

    def test_stop(self):
        engine = ExplorationEngine()
        engine._running = True
        engine.stop()
        assert engine.running is False
        assert engine._pause_event.is_set() is True


class TestMultiPassVerify:
    def test_empty_elements_returns_empty(self):
        engine = ExplorationEngine()
        result = engine._multi_pass_verify("b64data", [])
        assert result == []

    def test_single_pass_without_communicator(self):
        engine = ExplorationEngine()
        elements = [
            {"id": "e1", "type": "button", "label": "btn", "bbox": [0, 0, 10, 10], "confidence": 0.9},
        ]
        result = engine._multi_pass_verify("b64data", elements)
        assert len(result) == 1
        assert result[0].element_id == "e1"