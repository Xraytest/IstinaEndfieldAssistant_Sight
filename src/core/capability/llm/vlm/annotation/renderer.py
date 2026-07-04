from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from core.capability.llm.vlm.annotation.types import (
    Annotation,
    AnnotationSet,
    AnnotationShape,
)

_COLOR_MAP: dict[str, tuple[int, int, int]] = {
    "person": (0, 128, 255),
    "people": (0, 128, 255),
    "man": (0, 128, 255),
    "woman": (0, 128, 255),
    "building": (128, 128, 128),
    "house": (128, 128, 128),
    "tree": (0, 255, 0),
    "plant": (0, 255, 0),
    "car": (255, 0, 0),
    "vehicle": (255, 0, 0),
    "animal": (128, 0, 128),
    "furniture": (0, 165, 255),
    "object": (200, 200, 200),
    "default": (200, 200, 200),
}

_FONT = cv2.FONT_HERSHEY_SIMPLEX
_FONT_SCALE = 0.4
_FONT_THICKNESS = 1
_BOX_PADDING = 2
_ALPHA = 0.25


def _infer_color(label: str) -> tuple[int, int, int]:
    label_lower = label.lower()
    for key, color in _COLOR_MAP.items():
        if key in label_lower:
            return color
    return _COLOR_MAP["default"]


def _denormalize(
    points: list[list[float]], width: int, height: int
) -> list[tuple[int, int]]:
    return [(round(x * width), round(y * height)) for x, y in points]


def _render_rectangle(
    img: NDArray[Any],
    shape: AnnotationShape,
) -> None:
    if len(shape.pts) < 2:
        return
    x1, y1 = shape.pts[0]
    x2, y2 = shape.pts[1]
    overlay = img.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), shape.color, -1)
    cv2.addWeighted(overlay, _ALPHA, img, 1 - _ALPHA, 0, img)
    cv2.rectangle(img, (x1, y1), (x2, y2), shape.color, 2)

    label_size = cv2.getTextSize(shape.label, _FONT, _FONT_SCALE, _FONT_THICKNESS)[0]
    label_w, label_h = label_size
    label_y = max(y1 - label_h - _BOX_PADDING * 2, 0)
    cv2.rectangle(
        img,
        (x1, label_y),
        (x1 + label_w + _BOX_PADDING * 2, label_y + label_h + _BOX_PADDING * 2),
        shape.color,
        -1,
    )
    cv2.putText(
        img,
        shape.label,
        (x1 + _BOX_PADDING, label_y + label_h + _BOX_PADDING),
        _FONT,
        _FONT_SCALE,
        (255, 255, 255),
        _FONT_THICKNESS,
        lineType=cv2.LINE_AA,
    )


def _render_polygon(
    img: NDArray[Any],
    shape: AnnotationShape,
) -> None:
    if len(shape.pts) < 3:
        return
    pts_array = np.array([shape.pts], dtype=np.int32)
    overlay = img.copy()
    cv2.fillPoly(overlay, pts_array, shape.color)
    cv2.addWeighted(overlay, _ALPHA, img, 1 - _ALPHA, 0, img)
    cv2.polylines(img, pts_array, isClosed=True, color=shape.color, thickness=2)

    cx = int(np.mean([p[0] for p in shape.pts]))
    cy = int(np.min([p[1] for p in shape.pts]))
    label_size = cv2.getTextSize(shape.label, _FONT, _FONT_SCALE, _FONT_THICKNESS)[0]
    label_w, label_h = label_size
    label_y = max(cy - label_h - _BOX_PADDING * 2, 0)
    cv2.rectangle(
        img,
        (cx, label_y),
        (cx + label_w + _BOX_PADDING * 2, label_y + label_h + _BOX_PADDING * 2),
        shape.color,
        -1,
    )
    cv2.putText(
        img,
        shape.label,
        (cx + _BOX_PADDING, label_y + label_h + _BOX_PADDING),
        _FONT,
        _FONT_SCALE,
        (255, 255, 255),
        _FONT_THICKNESS,
        lineType=cv2.LINE_AA,
    )


def _render_circle(
    img: NDArray[Any],
    shape: AnnotationShape,
) -> None:
    if len(shape.pts) < 1:
        return
    cx, cy = shape.pts[0]
    radius = int(shape.metadata.get("radius", 10))
    overlay = img.copy()
    cv2.circle(overlay, (cx, cy), radius, shape.color, -1)
    cv2.addWeighted(overlay, _ALPHA, img, 1 - _ALPHA, 0, img)
    cv2.circle(img, (cx, cy), radius, shape.color, 2)

    label_y = max(cy - radius - 20, 0)
    label_size = cv2.getTextSize(shape.label, _FONT, _FONT_SCALE, _FONT_THICKNESS)[0]
    label_w, label_h = label_size
    cv2.rectangle(
        img,
        (cx - label_w // 2 - _BOX_PADDING, label_y),
        (cx + label_w // 2 + _BOX_PADDING, label_y + label_h + _BOX_PADDING * 2),
        shape.color,
        -1,
    )
    cv2.putText(
        img,
        shape.label,
        (cx - label_w // 2 + _BOX_PADDING, label_y + label_h + _BOX_PADDING),
        _FONT,
        _FONT_SCALE,
        (255, 255, 255),
        _FONT_THICKNESS,
        lineType=cv2.LINE_AA,
    )


class VlmAnnotationRenderer:
    """VLM Function Call 标注渲染器。

    将 VLM 返回的 tool_calls 解析为 Annotation 列表，
    并在 OpenCV 图像上绘制矩形/多边形/圆形 + 半透明填充 + 标签。
    """

    def parse_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
        width: int,
        height: int,
        confidence: float = 1.0,
    ) -> list[Annotation]:
        annotations: list[Annotation] = []
        for tc in tool_calls:
            func = tc.get("function", {})
            try:
                args = func.get("arguments", {})
                if isinstance(args, str):
                    import json
                    args = json.loads(args)
            except (json.JSONDecodeError, TypeError):
                args = {}

            items = args.get("annotations", [])
            for item in items:
                shape_type = item.get("shape_type", "rectangle")
                raw_points = item.get("points", [])
                label = item.get("label", "unknown")

                if shape_type == "normalized" and raw_points:
                    pts = _denormalize(raw_points, width, height)
                elif raw_points:
                    pts = [(round(x), round(y)) for x, y in raw_points]
                else:
                    pts = []

                metadata = {k: v for k, v in item.items() if k not in ("points", "shape_type", "label")}
                annotations.append(
                    Annotation(
                        label=label,
                        shape_type=shape_type,
                        points=pts,
                        confidence=confidence,
                        metadata=metadata,
                    )
                )

        return annotations

    def render(
        self,
        image: NDArray[Any],
        annotations: list[Annotation],
    ) -> NDArray[Any]:
        """在图像上绘制所有标注，返回副本。"""
        img = image.copy()

        shapes: list[AnnotationShape] = []
        for ann in annotations:
            color = _infer_color(ann.label)

            shapes.append(
                AnnotationShape(
                    label=ann.label,
                    shape_type=ann.shape_type,
                    pts=ann.points,
                    color=color,
                    confidence=ann.confidence,
                    metadata=ann.metadata,
                )
            )

        for shape in shapes:
            if shape.shape_type == "rectangle":
                _render_rectangle(img, shape)
            elif shape.shape_type == "polygon":
                _render_polygon(img, shape)
            elif shape.shape_type == "circle":
                _render_circle(img, shape)

        return img

    def process(
        self,
        image: NDArray[Any],
        tool_calls: list[dict[str, Any]],
        confidence: float = 1.0,
    ) -> tuple[AnnotationSet, NDArray[Any]]:
        """从 tool_calls 到渲染的完整流水线。"""
        height, width = image.shape[:2]
        annotations = self.parse_tool_calls(tool_calls, width, height, confidence)
        rendered = self.render(image, annotations)
        result_set = AnnotationSet(annotations=annotations, raw_tool_calls=tool_calls)
        return result_set, rendered
