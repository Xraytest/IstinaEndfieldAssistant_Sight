"""元素分析与任务知识库 - 数据模型

定义元素知识、验证结果、任务定义、活动信息等持久化存储的数据结构。
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
import time
import json


class ElementType(Enum):
    """UI元素类型"""
    BUTTON = "button"
    TEXT = "text"
    ICON = "icon"
    TAB = "tab"
    TOGGLE = "toggle"
    SLIDER = "slider"
    INPUT = "input"
    LIST_ITEM = "list_item"
    IMAGE = "image"
    UNKNOWN = "unknown"


class VerificationStatus(Enum):
    """元素验证状态"""
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    CONFIRMED_PERSISTENT = "confirmed_persistent"  # 多次验证确认的持久元素
    CHANGED = "changed"        # 元素位置/标签发生变化
    REMOVED = "removed"        # 元素已不存在


@dataclass
class ElementKnowledge:
    """单个UI元素的知识记录（持久化存储）
    
    对比 PageTree.UIElement，增加了持久化字段：
    - verification_count: 验证次数
    - last_seen: 最后出现时间
    - variant_labels: 同一元素可能出现的变体标签
    - semantic_id: 语义ID（如 "daily_task_tab"）用于跨版本匹配
    """
    element_id: str                    # 唯一标识
    semantic_id: str                   # 语义ID（如 "claim_button", "daily_tab"）
    element_type: ElementType
    label: str                         # 精确可见文本
    bbox: Tuple[float, float, float, float]  # [x1, y1, x2, y2]
    confidence: float = 0.0
    page_name: str = ""                # 所属页面
    page_hash: str = ""                # 页面截图hash
    
    # 持久化追踪字段
    verification_count: int = 0
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    first_seen: float = 0.0
    last_seen: float = 0.0
    last_verified: float = 0.0
    
    # 历史变体
    variant_labels: List[str] = field(default_factory=list)
    
    # 动作信息
    action: str = "tap"                # tap / swipe / none
    leads_to_page: str = ""            # 点击后导航到的页面
    
    # 额外属性
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["element_type"] = self.element_type.value
        d["verification_status"] = self.verification_status.value
        d["bbox"] = list(self.bbox)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ElementKnowledge":
        return cls(
            element_id=d["element_id"],
            semantic_id=d.get("semantic_id", d["element_id"]),
            element_type=ElementType(d.get("type", d.get("element_type", "unknown"))),
            label=d["label"],
            bbox=tuple(d["bbox"]),
            confidence=d.get("confidence", 0.0),
            page_name=d.get("page_name", ""),
            page_hash=d.get("page_hash", ""),
            verification_count=d.get("verification_count", 0),
            verification_status=VerificationStatus(d.get("verification_status", "unverified")),
            first_seen=d.get("first_seen", 0.0),
            last_seen=d.get("last_seen", 0.0),
            last_verified=d.get("last_verified", 0.0),
            variant_labels=d.get("variant_labels", []),
            action=d.get("action", "tap"),
            leads_to_page=d.get("leads_to_page", ""),
            extra=d.get("extra", {}),
        )


@dataclass
class ElementVerification:
    """元素验证记录"""
    element_id: str
    verified: bool
    timestamp: float = 0.0
    confidence: float = 0.0
    corrected_label: str = ""
    corrected_bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    model_tag: str = ""
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_id": self.element_id,
            "verified": self.verified,
            "timestamp": self.timestamp or time.time(),
            "confidence": self.confidence,
            "corrected_label": self.corrected_label,
            "corrected_bbox": list(self.corrected_bbox),
            "model_tag": self.model_tag,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ElementVerification":
        return cls(
            element_id=d["element_id"],
            verified=d["verified"],
            timestamp=d.get("timestamp", 0.0),
            confidence=d.get("confidence", 0.0),
            corrected_label=d.get("corrected_label", ""),
            corrected_bbox=tuple(d.get("corrected_bbox", [0, 0, 0, 0])),
            model_tag=d.get("model_tag", ""),
            note=d.get("note", ""),
        )


@dataclass
class PageKnowledge:
    """页面知识（持久化）
    
    相比 PageTree.PageNode，增加持久化统计和跨会话追踪。
    """
    page_id: str
    page_name: str
    page_hash: str
    page_type: str = "other"           # menu/dialog/battle/world_map/shop/etc
    resolution: Tuple[int, int] = (0, 0)
    elements: List[ElementKnowledge] = field(default_factory=list)
    edges: List[Dict[str, str]] = field(default_factory=list)
    
    visit_count: int = 0
    first_visit: float = 0.0
    last_visit: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_id": self.page_id,
            "page_name": self.page_name,
            "page_hash": self.page_hash,
            "page_type": self.page_type,
            "resolution": list(self.resolution),
            "elements": [e.to_dict() for e in self.elements],
            "edges": self.edges,
            "visit_count": self.visit_count,
            "first_visit": self.first_visit,
            "last_visit": self.last_visit,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PageKnowledge":
        return cls(
            page_id=d["page_id"],
            page_name=d["page_name"],
            page_hash=d["page_hash"],
            page_type=d.get("page_type", "other"),
            resolution=tuple(d.get("resolution", [0, 0])),
            elements=[ElementKnowledge.from_dict(e) for e in d.get("elements", [])],
            edges=d.get("edges", []),
            visit_count=d.get("visit_count", 0),
            first_visit=d.get("first_visit", 0.0),
            last_visit=d.get("last_visit", 0.0),
        )

    def get_element_by_semantic(self, semantic_id: str) -> Optional[ElementKnowledge]:
        return next((e for e in self.elements if e.semantic_id == semantic_id), None)


class TaskStatus(Enum):
    """任务状态"""
    UNKNOWN = "unknown"
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CLAIMABLE = "claimable"          # 已完成、可领取奖励
    CLAIMED = "claimed"


class TaskCycle(Enum):
    """任务周期"""
    DAILY = "daily"
    WEEKLY = "weekly"
    EVENT = "event"
    ONCE = "once"
    UNKNOWN = "unknown"


@dataclass
class TaskDefinition:
    """任务定义（活动/每日/每周任务的描述）
    
    从UI分析中提取的结构化任务信息。
    """
    task_id: str                       # 语义ID
    task_name: str                     # 任务名称（如 "击败据点敌人10次"）
    task_cycle: TaskCycle              # 每日/每周/活动
    task_category: str = ""            # 任务分类（如 "作战任务" "收集任务"）
    
    # 进度信息
    current_progress: int = 0
    total_progress: int = 0
    progress_text: str = ""            # 原始进度文本（如 "5/10"）
    
    # 奖励信息
    rewards: List[Dict[str, Any]] = field(default_factory=list)
    
    # 状态
    status: TaskStatus = TaskStatus.UNKNOWN
    
    # UI坐标（领取按钮位置）
    claim_button_bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    
    # 页面位置
    page_name: str = ""
    page_hash: str = ""
    
    # 元数据
    last_seen: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["task_cycle"] = self.task_cycle.value
        d["status"] = self.status.value
        d["claim_button_bbox"] = list(self.claim_button_bbox)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TaskDefinition":
        return cls(
            task_id=d["task_id"],
            task_name=d["task_name"],
            task_cycle=TaskCycle(d.get("task_cycle", "unknown")),
            task_category=d.get("task_category", ""),
            current_progress=d.get("current_progress", 0),
            total_progress=d.get("total_progress", 0),
            progress_text=d.get("progress_text", ""),
            rewards=d.get("rewards", []),
            status=TaskStatus(d.get("status", "unknown")),
            claim_button_bbox=tuple(d.get("claim_button_bbox", [0, 0, 0, 0])),
            page_name=d.get("page_name", ""),
            page_hash=d.get("page_hash", ""),
            last_seen=d.get("last_seen", 0.0),
            extra=d.get("extra", {}),
        )


@dataclass
class TaskInstance:
    """任务实例（一次会话中的任务快照）
    
    记录特定时间点的任务状态，用于追踪任务进度变化。
    """
    task_id: str
    session_id: str
    timestamp: float = 0.0
    status: TaskStatus = TaskStatus.UNKNOWN
    current_progress: int = 0
    total_progress: int = 0
    progress_text: str = ""
    screenshot_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp or time.time(),
            "status": self.status.value,
            "current_progress": self.current_progress,
            "total_progress": self.total_progress,
            "progress_text": self.progress_text,
            "screenshot_hash": self.screenshot_hash,
        }


@dataclass
class EventActivity:
    """活动信息（限时活动、签到活动等）"""
    event_id: str
    event_name: str
    event_type: str = ""               # sign_in / battle_pass / limited / etc
    start_time: float = 0.0
    end_time: float = 0.0
    
    # 入口位置
    entry_element_id: str = ""
    entry_page: str = ""
    
    # 子页面/任务列表
    tasks: List[TaskDefinition] = field(default_factory=list)
    
    # 状态
    is_active: bool = True
    last_seen: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_name": self.event_name,
            "event_type": self.event_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "entry_element_id": self.entry_element_id,
            "entry_page": self.entry_page,
            "tasks": [t.to_dict() for t in self.tasks],
            "is_active": self.is_active,
            "last_seen": self.last_seen,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EventActivity":
        return cls(
            event_id=d["event_id"],
            event_name=d["event_name"],
            event_type=d.get("event_type", ""),
            start_time=d.get("start_time", 0.0),
            end_time=d.get("end_time", 0.0),
            entry_element_id=d.get("entry_element_id", ""),
            entry_page=d.get("entry_page", ""),
            tasks=[TaskDefinition.from_dict(t) for t in d.get("tasks", [])],
            is_active=d.get("is_active", True),
            last_seen=d.get("last_seen", 0.0),
        )


@dataclass
class AnalysisResult:
    """单次VLM分析结果"""
    page_name: str
    page_type: str
    elements: List[Dict[str, Any]] = field(default_factory=list)
    has_daily_tasks: bool = False
    has_weekly_tasks: bool = False
    has_event: bool = False
    description: str = ""
    raw_reply: str = ""               # VLM原始回复
    model_tag: str = ""
    timestamp: float = 0.0
    screenshot_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_name": self.page_name,
            "page_type": self.page_type,
            "elements": self.elements,
            "has_daily_tasks": self.has_daily_tasks,
            "has_weekly_tasks": self.has_weekly_tasks,
            "has_event": self.has_event,
            "description": self.description,
            "raw_reply": self.raw_reply[:500] if len(self.raw_reply) > 500 else self.raw_reply,
            "model_tag": self.model_tag,
            "timestamp": self.timestamp or time.time(),
            "screenshot_hash": self.screenshot_hash,
        }


def make_semantic_id(page_name: str, label: str, element_type: str) -> str:
    """从页面名、标签和类型生成语义ID
    
    用于跨会话匹配同一元素。
    """
    import hashlib
    raw = f"{page_name}:{label}:{element_type}"
    return f"sem_{hashlib.md5(raw.encode()).hexdigest()[:12]}"
