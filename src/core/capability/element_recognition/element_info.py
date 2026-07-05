"""
Unified element recognition data models.

Provides ElementInfo, PageInfo, and SceneAnalysis3D as the shared output
format for all recognition and scene analysis backends.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray


ELEMENT_TYPES = (
    "button",
    "text",
    "icon",
    "tab",
    "toggle",
    "slider",
    "input",
    "list_item",
    "region",
    "yolo_object",
    "unknown",
)

PAGE_TYPES = (
    "world_map",
    "base_hub",
    "quest_panel",
    "event_panel",
    "main_menu",
    "base_industry",
    "character",
    "inventory",
    "settings",
    "credit_shop",
    "delivery",
    "dungeon",
    "signin",
    "loading",
    "title_screen",
    "exit_dialog",
    "logout_dialog",
    "gameplay",
    "unknown",
)


@dataclass
class ElementInfo:
    """Single detected UI/game element."""

    element_type: str
    label: str
    bbox: Tuple[float, float, float, float]
    center: Tuple[float, float]
    confidence: float
    source: str
    action: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.element_type not in ELEMENT_TYPES:
            self.element_type = "unknown"
        if self.action not in ("tap", "swipe", "none", "unknown"):
            self.action = "unknown"
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        x1, y1, x2, y2 = self.bbox
        self.bbox = (float(x1), float(y1), float(x2), float(y2))
        cx, cy = self.center
        self.center = (float(cx), float(cy))


@dataclass
class PageInfo:
    """Page-level recognition result."""

    page_type: str
    confidence: float
    elements: List[ElementInfo] = field(default_factory=list)
    features: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.page_type not in PAGE_TYPES:
            self.page_type = "unknown"
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    def get_elements_by_type(self, element_type: str) -> List[ElementInfo]:
        return [e for e in self.elements if e.element_type == element_type]

    def get_elements_by_source(self, source: str) -> List[ElementInfo]:
        return [e for e in self.elements if e.source == source]

    def find_element(self, label: str, fuzzy: bool = False) -> Optional[ElementInfo]:
        if fuzzy:
            for e in self.elements:
                if label.lower() in e.label.lower():
                    return e
        for e in self.elements:
            if e.label == label:
                return e
        return None


@dataclass
class SceneAnalysis3D:
    """3D scene analysis result."""

    annotations: Any = None
    rendered_image: Optional[NDArray[Any]] = None
    raw_text: str = ""
    raw_tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    usage: Dict[str, Any] = field(default_factory=dict)
    ground: Dict[str, Any] = field(default_factory=dict)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    camera: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
