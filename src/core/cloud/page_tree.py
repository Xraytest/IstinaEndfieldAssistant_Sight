import hashlib
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class ElementType(Enum):
    BUTTON = "button"
    TEXT = "text"
    ICON = "icon"
    SLIDER = "slider"
    INPUT = "input"
    TOGGLE = "toggle"
    TAB = "tab"
    LIST_ITEM = "list_item"
    IMAGE = "image"
    UNKNOWN = "unknown"


class PageState(Enum):
    UNEXPLORED = "unexplored"
    EXPLORING = "exploring"
    EXPLORED = "explored"
    ERROR = "error"


@dataclass
class UIElement:
    element_id: str
    element_type: ElementType
    label: str
    bbox: Tuple[float, float, float, float]
    confidence: float
    explored: bool = False
    leads_to: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_id": self.element_id,
            "type": self.element_type.value,
            "label": self.label,
            "bbox": list(self.bbox),
            "confidence": self.confidence,
            "explored": self.explored,
            "leads_to": self.leads_to,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UIElement":
        return cls(
            element_id=d["element_id"],
            element_type=ElementType(d["type"]),
            label=d["label"],
            bbox=tuple(d["bbox"]),
            confidence=d["confidence"],
            explored=d.get("explored", False),
            leads_to=d.get("leads_to"),
            extra=d.get("extra", {}),
        )


@dataclass
class PageNode:
    page_id: str
    name: str
    screenshot_hash: str
    elements: List[UIElement] = field(default_factory=list)
    parent_edge: Optional[str] = None
    depth: int = 0
    state: PageState = PageState.UNEXPLORED
    resolution: Tuple[int, int] = (1280, 720)
    timestamp: float = field(default_factory=time.time)
    vlm_response: Optional[Dict[str, Any]] = None
    verification_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_id": self.page_id,
            "name": self.name,
            "screenshot_hash": self.screenshot_hash,
            "elements": [e.to_dict() for e in self.elements],
            "parent_edge": self.parent_edge,
            "depth": self.depth,
            "state": self.state.value,
            "resolution": list(self.resolution),
            "timestamp": self.timestamp,
            "verification_count": self.verification_count,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PageNode":
        return cls(
            page_id=d["page_id"],
            name=d["name"],
            screenshot_hash=d["screenshot_hash"],
            elements=[UIElement.from_dict(e) for e in d.get("elements", [])],
            parent_edge=d.get("parent_edge"),
            depth=d.get("depth", 0),
            state=PageState(d.get("state", "unexplored")),
            resolution=tuple(d.get("resolution", [1280, 720])),
            timestamp=d.get("timestamp", time.time()),
            verification_count=d.get("verification_count", 0),
        )

    @property
    def unexplored_elements(self) -> List[UIElement]:
        return [e for e in self.elements if not e.explored and e.element_type != ElementType.TEXT]

    @property
    def icon_name(self) -> str:
        type_icons = {
            PageState.UNEXPLORED: " ",
            PageState.EXPLORING: " ",
            PageState.EXPLORED: " ",
            PageState.ERROR: " ",
        }
        return type_icons.get(self.state, " ")


@dataclass
class PageEdge:
    edge_id: str
    from_page_id: str
    to_page_id: str
    element_id: str
    action_type: str
    action_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "from": self.from_page_id,
            "to": self.to_page_id,
            "element_id": self.element_id,
            "action_type": self.action_type,
            "params": self.action_params,
        }


class PageTree:
    def __init__(self):
        self._nodes: Dict[str, PageNode] = {}
        self._edges: List[PageEdge] = []
        self._root_page_id: Optional[str] = None
        self._hash_index: Dict[str, str] = {}
        self._stats: Dict[str, int] = {"pages_discovered": 0, "elements_found": 0, "edges_created": 0}

    @property
    def root(self) -> Optional[PageNode]:
        if self._root_page_id:
            return self._nodes.get(self._root_page_id)
        return None

    @root.setter
    def root(self, node: PageNode):
        self._root_page_id = node.page_id
        self.add_node(node)

    def add_node(self, node: PageNode) -> None:
        if node.page_id not in self._nodes:
            self._stats["pages_discovered"] += 1
        old = self._nodes.get(node.page_id)
        self._nodes[node.page_id] = node
        self._hash_index[node.screenshot_hash] = node.page_id
        if old is None:
            self._stats["elements_found"] += len(node.elements)

    def add_edge(self, edge: PageEdge) -> None:
        for existing in self._edges:
            if existing.from_page_id == edge.from_page_id and existing.element_id == edge.element_id:
                return
        self._edges.append(edge)
        self._stats["edges_created"] += 1
        if edge.from_page_id in self._nodes:
            for elem in self._nodes[edge.from_page_id].elements:
                if elem.element_id == edge.element_id:
                    elem.explored = True
                    elem.leads_to = edge.to_page_id

    def get_node(self, page_id: str) -> Optional[PageNode]:
        return self._nodes.get(page_id)

    def get_node_by_hash(self, screenshot_hash: str) -> Optional[PageNode]:
        page_id = self._hash_index.get(screenshot_hash)
        if page_id:
            return self._nodes.get(page_id)
        return None

    def get_edges_from(self, page_id: str) -> List[PageEdge]:
        return [e for e in self._edges if e.from_page_id == page_id]

    @property
    def nodes(self) -> Dict[str, PageNode]:
        return dict(self._nodes)

    @property
    def edges(self) -> List[PageEdge]:
        return list(self._edges)

    @property
    def stats(self) -> Dict[str, int]:
        return dict(self._stats)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root_page_id": self._root_page_id,
            "nodes": {k: v.to_dict() for k, v in self._nodes.items()},
            "edges": [e.to_dict() for e in self._edges],
            "stats": self._stats,
        }

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "PageTree":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        tree = cls()
        tree._root_page_id = data.get("root_page_id")
        for pid, nd in data.get("nodes", {}).items():
            tree._nodes[pid] = PageNode.from_dict(nd)
            tree._hash_index[nd["screenshot_hash"]] = pid
        for ed in data.get("edges", []):
            edge = PageEdge(
                edge_id=ed["edge_id"],
                from_page_id=ed["from"],
                to_page_id=ed["to"],
                element_id=ed["element_id"],
                action_type=ed["action_type"],
                action_params=ed.get("params", {}),
            )
            tree._edges.append(edge)
        tree._stats = data.get("stats", {"pages_discovered": 0, "elements_found": 0, "edges_created": 0})
        return tree


def hash_screenshot(screenshot_b64: str) -> str:
    return hashlib.sha256(screenshot_b64.encode()).hexdigest()[:16]


def hash_element(box_str: str) -> str:
    return hashlib.md5(box_str.encode()).hexdigest()[:8]
