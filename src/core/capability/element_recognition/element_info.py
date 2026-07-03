"""
终末地画面元素识别模块 — 统一数据类

提供 ElementInfo（单个元素）和 PageInfo（页面分析结果）作为
所有识别后端的统一输出格式。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# 元素类型枚举
ELEMENT_TYPES = (
    "button",       # 可点击按钮
    "text",         # 纯文本标签
    "icon",         # 图标（任务、活动、菜单等）
    "tab",          # 标签页
    "toggle",       # 开关
    "slider",       # 滑块
    "input",        # 输入框
    "list_item",    # 列表项
    "region",       # 区域（颜色匹配得到的色块区域）
    "yolo_object",  # YOLO 检测到的通用物体
    "unknown",      # 未知类型
)

# 页面类型枚举（终末地特定）
PAGE_TYPES = (
    "world_map",           # 主世界地图
    "base_hub",            # 基地主界面（多面板叠加）
    "quest_panel",         # 任务面板
    "event_panel",         # 活动面板
    "main_menu",           # 系统主菜单
    "base_industry",       # 基建/工业界面
    "character",           # 角色界面
    "inventory",           # 背包界面
    "settings",            # 设置界面
    "credit_shop",         # 信用商店
    "delivery",            # 配送任务界面
    "dungeon",             # 副本/关卡
    "signin",              # 签到界面
    "loading",             # 加载画面
    "title_screen",        # 标题/登录画面
    "exit_dialog",         # 退出对话框
    "logout_dialog",       # 登出对话框
    "gameplay",            # 游戏战斗/探索场景
    "unknown",             # 未知页面
)


@dataclass
class ElementInfo:
    """单个画面元素的统一描述。

    Attributes:
        element_type: 元素类型（button/text/icon/tab/region/yolo_object/unknown）
        label: 可见文本、模板名或 YOLO class 名
        bbox: 边界框 [x1, y1, x2, y2]，归一化到 0-1
        center: 中心点 (cx, cy)，归一化到 0-1
        confidence: 检测置信度 0-1
        source: 检测来源（template/ocr/color/yolo）
        action: 建议动作（tap/swipe/none/unknown）
        metadata: 扩展字段（模板匹配的 threshold、OCR 的 score 等）
    """
    element_type: str
    label: str
    bbox: Tuple[float, float, float, float]
    center: Tuple[float, float]
    confidence: float
    source: str
    action: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # 校验并规范化
        if self.element_type not in ELEMENT_TYPES:
            self.element_type = "unknown"
        if self.action not in ("tap", "swipe", "none", "unknown"):
            self.action = "unknown"
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        # 规范化 bbox
        x1, y1, x2, y2 = self.bbox
        self.bbox = (float(x1), float(y1), float(x2), float(y2))
        cx, cy = self.center
        self.center = (float(cx), float(cy))


@dataclass
class PageInfo:
    """页面分析结果。

    Attributes:
        page_type: 页面类型（world_map/quest_panel/...）
        confidence: 分类置信度 0-1
        elements: 页面上检测到的元素列表
        features: 页面特征（亮度、绿色像素数等）
        metadata: 扩展字段
    """
    page_type: str
    confidence: float
    elements: List[ElementInfo] = field(default_factory=list)
    features: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.page_type not in PAGE_TYPES:
            self.page_type = "unknown"
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    def get_elements_by_type(self, element_type: str) -> List[ElementInfo]:
        """按类型筛选元素"""
        return [e for e in self.elements if e.element_type == element_type]

    def get_elements_by_source(self, source: str) -> List[ElementInfo]:
        """按来源筛选元素"""
        return [e for e in self.elements if e.source == source]

    def find_element(self, label: str, fuzzy: bool = False) -> Optional[ElementInfo]:
        """按标签查找元素"""
        if fuzzy:
            for e in self.elements:
                if label.lower() in e.label.lower():
                    return e
        for e in self.elements:
            if e.label == label:
                return e
        return None
