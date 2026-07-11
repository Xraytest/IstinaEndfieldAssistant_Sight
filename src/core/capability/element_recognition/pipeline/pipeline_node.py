from __future__ import annotations

import copy
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class RecognitionType(str, Enum):
    DirectHit = "DirectHit"
    TemplateMatch = "TemplateMatch"
    OCR = "OCR"
    ColorMatch = "ColorMatch"
    And = "And"
    Or = "Or"
    Custom = "Custom"


class NodeAction(str, Enum):
    Click = "Click"
    Swipe = "Swipe"
    KeyDown = "KeyDown"
    KeyUp = "KeyUp"
    DoNothing = "DoNothing"
    StopTask = "StopTask"
    Custom = "Custom"
    StartApp = "StartApp"


@dataclass
class PipelineNode:
    name: str
    recognition: RecognitionType = RecognitionType.DirectHit
    template: Optional[Union[str, List[str]]] = None
    roi: Optional[List[int]] = None
    roi_offset: Optional[List[int]] = None
    threshold: float = 0.8
    action: Optional[Union[str, Dict[str, Any]]] = None
    next: List[str] = field(default_factory=list)
    all_of: Optional[List[str]] = None
    any_of: Optional[List[str]] = None
    box_index: int = 0
    pre_delay: int = 200
    post_delay: int = 200
    rate_limit: int = 1000
    enabled: bool = True
    max_hit: int = 0
    pre_wait_freezes: Optional[Union[int, Dict[str, Any]]] = None
    focus: Optional[Dict[str, str]] = None
    desc: str = ""
    expected: Optional[List[str]] = None
    custom_action: Optional[str] = None
    custom_action_param: Optional[Dict[str, Any]] = None
    custom_recognition: Optional[str] = None
    custom_recognition_param: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> PipelineNode:
        raw = data.get("recognition", "DirectHit")
        recognition = raw if isinstance(raw, RecognitionType) else RecognitionType(raw) if isinstance(raw, str) and raw in RecognitionType._value2member_map_ else RecognitionType.DirectHit
        if recognition == RecognitionType.DirectHit and not raw:
            recognition = RecognitionType.DirectHit
        action_raw = data.get("action")
        action = None
        custom_action = None
        custom_action_param = None
        if isinstance(action_raw, str):
            action = action_raw
            if action_raw == "Custom":
                custom_action = data.get("custom_action")
                custom_action_param = data.get("custom_action_param")
        elif isinstance(action_raw, dict):
            action = action_raw.get("type", "DoNothing")
            if action == "Custom":
                custom_action = action_raw.get("param", {}).get("custom_action") if isinstance(action_raw.get("param"), dict) else None
                custom_action_param = action_raw.get("param", {}).get("custom_action_param") if isinstance(action_raw.get("param"), dict) else None
            elif action in ("Swipe",):
                custom_action_param = action_raw.get("param")

        return cls(
            name=name,
            recognition=recognition,
            template=data.get("template"),
            roi=data.get("roi"),
            roi_offset=data.get("roi_offset"),
            threshold=data.get("threshold", 0.8),
            action=action,
            next=data.get("next", []),
            all_of=data.get("all_of"),
            any_of=data.get("any_of"),
            box_index=data.get("box_index", 0),
            pre_delay=data.get("pre_delay", 200),
            post_delay=data.get("post_delay", 200),
            rate_limit=data.get("rate_limit", 1000),
            enabled=data.get("enabled", True),
            max_hit=data.get("max_hit", 0),
            pre_wait_freezes=data.get("pre_wait_freezes"),
            focus=data.get("focus"),
            desc=data.get("desc", ""),
            expected=data.get("expected"),
            custom_action=custom_action,
            custom_action_param=custom_action_param,
            custom_recognition=data.get("custom_recognition"),
            custom_recognition_param=data.get("custom_recognition_param"),
            metadata=data,
        )

    def to_dict(self) -> Dict[str, Any]:
        # PN-5: 返回 metadata 的深拷贝，避免调用方修改返回字典时污染节点原始数据。
        return copy.deepcopy(self.metadata)


@dataclass
class PipelineGraph:
    nodes: Dict[str, PipelineNode] = field(default_factory=dict)
    entry_points: List[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def add_node(self, node: PipelineNode) -> None:
        self.nodes[node.name] = node

    def get_node(self, name: str) -> Optional[PipelineNode]:
        return self.nodes.get(name)

    def get_node_or_entry(self, name: str) -> Optional[PipelineNode]:
        node = self.nodes.get(name)
        if node is None and self.entry_points:
            node = self.nodes.get(self.entry_points[0])
        return node

    def resolve_transitions(self, node: PipelineNode) -> List[PipelineNode]:
        return [self.nodes.get(n) for n in node.next if n in self.nodes]

    def merge(self, other: PipelineGraph) -> None:
        # PN-3: 合并加锁保护，并对 entry_points 去重，避免多线程合并时竞争或重复。
        with self._lock:
            self.nodes.update(other.nodes)
            for ep in other.entry_points:
                if ep not in self.entry_points:
                    self.entry_points.append(ep)
