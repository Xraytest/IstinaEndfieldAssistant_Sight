from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Annotation:
    """Generic scene annotation item."""

    label: str
    shape_type: str
    points: list[tuple[int, int]]
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnnotationShape:
    """Renderable annotation shape."""

    label: str
    shape_type: str
    pts: list[tuple[int, int]]
    color: tuple[int, int, int]
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnnotationSet:
    """Collection of annotations for one scene analysis result."""

    annotations: list[Annotation] = field(default_factory=list)
    raw_text: str = ""
    raw_tool_calls: list[dict[str, Any]] = field(default_factory=list)
