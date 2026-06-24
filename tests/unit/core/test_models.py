"""Tests for core/element_analysis/models.py"""

import json
import time
from typing import Dict, Any

import pytest

from core.element_analysis.models import (
    ElementType,
    VerificationStatus,
    TaskStatus,
    TaskCycle,
    ElementKnowledge,
    ElementVerification,
    PageKnowledge,
    TaskDefinition,
    TaskInstance,
    EventActivity,
    AnalysisResult,
    make_semantic_id,
)


class TestEnums:
    def test_element_type_values(self):
        assert ElementType.BUTTON.value == "button"
        assert ElementType.TEXT.value == "text"
        assert ElementType.ICON.value == "icon"
        assert ElementType.TAB.value == "tab"
        assert ElementType.TOGGLE.value == "toggle"
        assert ElementType.SLIDER.value == "slider"
        assert ElementType.INPUT.value == "input"
        assert ElementType.LIST_ITEM.value == "list_item"
        assert ElementType.IMAGE.value == "image"
        assert ElementType.UNKNOWN.value == "unknown"

    def test_verification_status_values(self):
        assert VerificationStatus.UNVERIFIED.value == "unverified"
        assert VerificationStatus.VERIFIED.value == "verified"
        assert VerificationStatus.CONFIRMED_PERSISTENT.value == "confirmed_persistent"
        assert VerificationStatus.CHANGED.value == "changed"
        assert VerificationStatus.REMOVED.value == "removed"

    def test_task_status_values(self):
        assert TaskStatus.UNKNOWN.value == "unknown"
        assert TaskStatus.NOT_STARTED.value == "not_started"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.CLAIMABLE.value == "claimable"
        assert TaskStatus.CLAIMED.value == "claimed"

    def test_task_cycle_values(self):
        assert TaskCycle.DAILY.value == "daily"
        assert TaskCycle.WEEKLY.value == "weekly"
        assert TaskCycle.EVENT.value == "event"
        assert TaskCycle.ONCE.value == "once"
        assert TaskCycle.UNKNOWN.value == "unknown"

    def test_all_enum_members_present(self):
        assert len(ElementType) == 10
        assert len(VerificationStatus) == 5
        assert len(TaskStatus) == 6
        assert len(TaskCycle) == 5


class TestMakeSemanticId:
    def test_returns_string(self):
        sid = make_semantic_id("主界面", "领取", "button")
        assert isinstance(sid, str)
        assert sid.startswith("sem_")

    def test_deterministic_same_input(self):
        sid1 = make_semantic_id("page", "label", "type")
        sid2 = make_semantic_id("page", "label", "type")
        assert sid1 == sid2

    def test_different_input_different_output(self):
        sid1 = make_semantic_id("page_a", "label", "type")
        sid2 = make_semantic_id("page_b", "label", "type")
        assert sid1 != sid2

    def test_consistent_length(self):
        sid = make_semantic_id("a", "b", "c")
        expected_prefix = "sem_"
        assert len(sid) == len(expected_prefix) + 12


class TestElementKnowledge:
    def test_minimal_creation(self):
        ek = ElementKnowledge(
            element_id="e1",
            semantic_id="test_btn",
            element_type=ElementType.BUTTON,
            label="测试",
            bbox=(0, 0, 100, 100),
        )
        assert ek.element_id == "e1"
        assert ek.semantic_id == "test_btn"
        assert ek.element_type == ElementType.BUTTON
        assert ek.label == "测试"
        assert ek.bbox == (0, 0, 100, 100)
        assert ek.confidence == 0.0
        assert ek.verification_count == 0
        assert ek.verification_status == VerificationStatus.UNVERIFIED
        assert ek.variant_labels == []
        assert ek.action == "tap"
        assert ek.extra == {}

    def test_to_dict_roundtrip(self, sample_element_dict: Dict[str, Any]):
        ek = ElementKnowledge.from_dict(sample_element_dict)
        d = ek.to_dict()
        assert d["element_id"] == "elem_001"
        assert d["semantic_id"] == "daily_claim_button"
        assert d["element_type"] == "button"
        assert d["label"] == "领取"
        assert d["bbox"] == [100, 200, 300, 400]
        assert d["confidence"] == 0.95
        assert d["verification_status"] == "verified"
        assert d["action"] == "tap"
        assert d["leads_to_page"] == "奖励页面"

        ek2 = ElementKnowledge.from_dict(d)
        assert ek2.element_id == ek.element_id
        assert ek2.semantic_id == ek.semantic_id
        assert ek2.element_type == ek.element_type
        assert ek2.label == ek.label
        assert ek2.bbox == ek.bbox
        assert ek2.verification_status == ek.verification_status

    def test_from_dict_with_type_alias(self):
        d = {
            "element_id": "e2",
            "type": "icon",
            "label": "图标",
            "bbox": [0, 0, 50, 50],
        }
        ek = ElementKnowledge.from_dict(d)
        assert ek.element_type == ElementType.ICON

    def test_to_dict_json_serializable(self, sample_element_dict: Dict[str, Any]):
        ek = ElementKnowledge.from_dict(sample_element_dict)
        json_str = json.dumps(ek.to_dict(), ensure_ascii=False)
        assert isinstance(json_str, str)
        assert "领取" in json_str

    def test_defaults_for_missing_fields(self):
        d = {"element_id": "e3", "label": "test", "bbox": [0, 0, 10, 10]}
        ek = ElementKnowledge.from_dict(d)
        assert ek.semantic_id == "e3"
        assert ek.element_type == ElementType.UNKNOWN
        assert ek.confidence == 0.0
        assert ek.verification_status == VerificationStatus.UNVERIFIED
        assert ek.variant_labels == []
        assert ek.action == "tap"
        assert ek.extra == {}

    def test_with_variant_labels(self):
        ek = ElementKnowledge(
            element_id="e4",
            semantic_id="btn_var",
            element_type=ElementType.BUTTON,
            label="领取",
            bbox=(0, 0, 10, 10),
            variant_labels=["收取", "获得"],
        )
        assert len(ek.variant_labels) == 2
        d = ek.to_dict()
        assert d["variant_labels"] == ["收取", "获得"]


class TestElementVerification:
    def test_minimal_creation(self):
        ev = ElementVerification(element_id="e1", verified=True)
        assert ev.element_id == "e1"
        assert ev.verified is True
        assert ev.timestamp == 0.0
        assert ev.corrected_bbox == (0.0, 0.0, 0.0, 0.0)

    def test_to_dict_roundtrip(self):
        ev = ElementVerification(
            element_id="e1",
            verified=True,
            timestamp=1234.0,
            confidence=0.9,
            corrected_label="修正标签",
            corrected_bbox=(10, 20, 30, 40),
            model_tag="test_model",
            note="测试备注",
        )
        d = ev.to_dict()
        assert d["element_id"] == "e1"
        assert d["verified"] is True
        assert d["corrected_label"] == "修正标签"
        assert d["corrected_bbox"] == [10, 20, 30, 40]

        ev2 = ElementVerification.from_dict(d)
        assert ev2.element_id == ev.element_id
        assert ev2.verified == ev.verified
        assert ev2.corrected_bbox == ev.corrected_bbox

    def test_auto_timestamp(self):
        ev = ElementVerification(element_id="e1", verified=True)
        d = ev.to_dict()
        assert isinstance(d["timestamp"], float)
        assert d["timestamp"] > 0

    def test_missing_bbox_defaults(self):
        d = {"element_id": "e1", "verified": False}
        ev = ElementVerification.from_dict(d)
        assert ev.corrected_bbox == (0.0, 0.0, 0.0, 0.0)


class TestPageKnowledge:
    def test_minimal_creation(self):
        pk = PageKnowledge(page_id="p1", page_name="主界面", page_hash="hash1")
        assert pk.page_id == "p1"
        assert pk.page_name == "主界面"
        assert pk.page_type == "other"
        assert pk.resolution == (0, 0)
        assert pk.elements == []
        assert pk.visit_count == 0

    def test_to_dict_roundtrip(self):
        pk = PageKnowledge(
            page_id="p1",
            page_name="主界面",
            page_hash="hash1",
            page_type="menu",
            resolution=(1280, 720),
            elements=[
                ElementKnowledge(
                    element_id="e1",
                    semantic_id="btn",
                    element_type=ElementType.BUTTON,
                    label="领取",
                    bbox=(0, 0, 100, 50),
                )
            ],
            visit_count=5,
            first_visit=100.0,
            last_visit=500.0,
        )
        d = pk.to_dict()
        assert d["page_id"] == "p1"
        assert d["page_type"] == "menu"
        assert d["resolution"] == [1280, 720]
        assert len(d["elements"]) == 1
        assert d["visit_count"] == 5

        pk2 = PageKnowledge.from_dict(d)
        assert pk2.page_id == pk.page_id
        assert pk2.page_type == pk.page_type
        assert pk2.resolution == pk.resolution
        assert len(pk2.elements) == 1
        assert pk2.elements[0].label == "领取"

    def test_get_element_by_semantic_found(self):
        pk = PageKnowledge(
            page_id="p1",
            page_name="test",
            page_hash="h1",
            elements=[
                ElementKnowledge(
                    element_id="e1",
                    semantic_id="claim_btn",
                    element_type=ElementType.BUTTON,
                    label="领取",
                    bbox=(0, 0, 10, 10),
                ),
                ElementKnowledge(
                    element_id="e2",
                    semantic_id="close_btn",
                    element_type=ElementType.BUTTON,
                    label="关闭",
                    bbox=(0, 0, 10, 10),
                ),
            ],
        )
        found = pk.get_element_by_semantic("claim_btn")
        assert found is not None
        assert found.element_id == "e1"
        assert found.label == "领取"

    def test_get_element_by_semantic_not_found(self):
        pk = PageKnowledge(
            page_id="p1", page_name="test", page_hash="h1"
        )
        assert pk.get_element_by_semantic("nonexistent") is None

    def test_json_serializable(self):
        pk = PageKnowledge(
            page_id="p1",
            page_name="测试页面",
            page_hash="hash1",
            page_type="menu",
        )
        json_str = json.dumps(pk.to_dict(), ensure_ascii=False)
        assert "测试页面" in json_str

    def test_edges_roundtrip(self):
        edges = [{"from": "p1", "to": "p2", "action": "tap"}]
        pk = PageKnowledge(
            page_id="p1",
            page_name="test",
            page_hash="h1",
            edges=edges,
        )
        d = pk.to_dict()
        assert d["edges"] == edges
        pk2 = PageKnowledge.from_dict(d)
        assert pk2.edges == edges


class TestTaskDefinition:
    def test_minimal_creation(self):
        td = TaskDefinition(task_id="t1", task_name="击败敌人", task_cycle=TaskCycle.DAILY)
        assert td.task_id == "t1"
        assert td.task_cycle == TaskCycle.DAILY
        assert td.status == TaskStatus.UNKNOWN
        assert td.rewards == []
        assert td.claim_button_bbox == (0.0, 0.0, 0.0, 0.0)

    def test_to_dict_roundtrip(self):
        td = TaskDefinition(
            task_id="t1",
            task_name="击败敌人10次",
            task_cycle=TaskCycle.WEEKLY,
            task_category="作战任务",
            current_progress=5,
            total_progress=10,
            progress_text="5/10",
            rewards=[{"type": "currency", "amount": 100}],
            status=TaskStatus.IN_PROGRESS,
            claim_button_bbox=(100, 200, 300, 400),
            page_name="任务页面",
            page_hash="hash123",
        )
        d = td.to_dict()
        assert d["task_cycle"] == "weekly"
        assert d["status"] == "in_progress"
        assert d["claim_button_bbox"] == [100, 200, 300, 400]
        assert len(d["rewards"]) == 1

        td2 = TaskDefinition.from_dict(d)
        assert td2.task_id == td.task_id
        assert td2.task_cycle == td.task_cycle
        assert td2.status == td.status
        assert td2.claim_button_bbox == td.claim_button_bbox


class TestTaskInstance:
    def test_minimal_creation(self):
        ti = TaskInstance(task_id="t1", session_id="s1")
        assert ti.task_id == "t1"
        assert ti.session_id == "s1"
        assert ti.status == TaskStatus.UNKNOWN
        assert ti.current_progress == 0

    def test_to_dict(self):
        ti = TaskInstance(
            task_id="t1",
            session_id="s1",
            timestamp=2000.0,
            status=TaskStatus.COMPLETED,
            current_progress=10,
            total_progress=10,
            progress_text="10/10",
            screenshot_hash="hash_img",
        )
        d = ti.to_dict()
        assert d["status"] == "completed"
        assert d["timestamp"] == 2000.0
        assert d["screenshot_hash"] == "hash_img"


class TestEventActivity:
    def test_minimal_creation(self):
        ea = EventActivity(event_id="evt1", event_name="签到活动")
        assert ea.event_id == "evt1"
        assert ea.is_active is True
        assert ea.tasks == []

    def test_to_dict_roundtrip(self):
        ea = EventActivity(
            event_id="evt1",
            event_name="限时签到",
            event_type="sign_in",
            start_time=1000.0,
            end_time=10000.0,
            entry_element_id="elem_entry",
            entry_page="主界面",
            tasks=[
                TaskDefinition(
                    task_id="t1",
                    task_name="签到1天",
                    task_cycle=TaskCycle.EVENT,
                )
            ],
            is_active=True,
            last_seen=5000.0,
        )
        d = ea.to_dict()
        assert d["event_type"] == "sign_in"
        assert len(d["tasks"]) == 1

        ea2 = EventActivity.from_dict(d)
        assert ea2.event_id == ea.event_id
        assert ea2.event_name == ea.event_name
        assert len(ea2.tasks) == 1


class TestAnalysisResult:
    def test_minimal_creation(self):
        ar = AnalysisResult(page_name="主界面", page_type="menu")
        assert ar.has_daily_tasks is False
        assert ar.elements == []
        assert ar.raw_reply == ""

    def test_to_dict_truncates_raw_reply(self):
        ar = AnalysisResult(
            page_name="test",
            page_type="other",
            raw_reply="x" * 1000,
        )
        d = ar.to_dict()
        assert len(d["raw_reply"]) == 500

    def test_to_dict_without_truncation(self):
        ar = AnalysisResult(
            page_name="test",
            page_type="other",
            raw_reply="short reply",
        )
        d = ar.to_dict()
        assert d["raw_reply"] == "short reply"

    def test_auto_timestamp(self):
        ar = AnalysisResult(page_name="test", page_type="other")
        d = ar.to_dict()
        assert isinstance(d["timestamp"], float)
        assert d["timestamp"] > 0