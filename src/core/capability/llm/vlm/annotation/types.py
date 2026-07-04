from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Annotation:
    """VLM Function Call 标注单元。"""

    label: str
    shape_type: str
    points: list[tuple[int, int]]
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnnotationShape:
    """可视化渲染用的形状容器（像素坐标，已归一化 → 原始分辨率）。"""

    label: str
    shape_type: str
    pts: list[tuple[int, int]]
    color: tuple[int, int, int]
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnnotationSet:
    """单帧的完整标注结果。"""

    annotations: list[Annotation] = field(default_factory=list)
    raw_text: str = ""
    raw_tool_calls: list[dict[str, Any]] = field(default_factory=list)
