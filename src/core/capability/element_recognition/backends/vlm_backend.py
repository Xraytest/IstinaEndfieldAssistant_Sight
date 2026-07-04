from __future__ import annotations

import json
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from core.capability.element_recognition.element_info import SceneAnalysis3D
from core.capability.llm.vlm.client import VlmClient
from core.capability.llm.vlm.annotation.renderer import VlmAnnotationRenderer

_SCENE_DEFAULT_PROMPT = (
    "分析这张图片，识别场景中的所有物体和元素。"
    "像分析真实世界环境一样，描述你看到的内容。"
    "使用像素坐标标注每个物体的位置。"
)

_TOOLS_SCENE = [
    {
        "type": "function",
        "function": {
            "name": "annotate_scene",
            "description": "标注场景中的物体和元素",
            "parameters": {
                "type": "object",
                "properties": {
                    "annotations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "description": "物体或元素的名称，如 'person'、'building'、'tree'、'car' 等"},
                                "shape_type": {"type": "string", "enum": ["rectangle", "polygon", "circle"], "description": "边界形状"},
                                "points": {
                                    "type": "array",
                                    "items": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 2,
                                        "maxItems": 2,
                                    },
                                    "description": "像素坐标 [[x1,y1],[x2,y2],...]",
                                },
                                "confidence": {"type": "number", "description": "检测置信度 0-1"},
                            },
                            "required": ["label", "shape_type", "points"],
                        },
                    }
                },
                "required": ["annotations"],
            },
        }
    },
]


class VlmBackendError(Exception):
    """VLM 后端异常"""


class VlmBackend:
    """VLM 多模态后端。

    通过 VlmClient 调用 llama-server (VLM)，支持：
    - analyze_scene_3d()  深度 3D 场景分析
    - recognize()         传统 element 识别兼容
    """

    def __init__(self, client: VlmClient, prompt: str = ""):
        self._client = client
        self._prompt = prompt or _SCENE_DEFAULT_PROMPT
        self._renderer = VlmAnnotationRenderer()

    def analyze_scene_3d(
        self,
        screen: NDArray[Any],
        prompt: str = "",
    ) -> SceneAnalysis3D:
        """VLM 3D 场景深度分析。"""
        use_prompt = prompt or self._prompt
        _, img_encoded = cv2.imencode(".png", screen)
        image_data = img_encoded.tobytes()

        try:
            result = self._client.analyze_with_tools(image_data, use_prompt, _TOOLS_SCENE)
        except Exception as e:
            raise VlmBackendError(f"VLM analyze failed: {e}") from e

        tool_calls = result.get("tool_calls", [])
        text = result.get("content", "")
        usage = result.get("usage", {})

        annotation_set, rendered = self._renderer.process(
            screen, tool_calls, confidence=0.5
        )

        return SceneAnalysis3D(
            annotations=annotation_set,
            rendered_image=rendered,
            raw_text=text,
            raw_tool_calls=tool_calls,
            usage=usage,
        )

    def recognize(
        self,
        screen: NDArray[Any],
        prompt: str = "",
    ) -> list[dict[str, Any]]:
        """VLM 通用目标识别（兼容后端接口）。"""
        use_prompt = prompt or self._prompt
        _, img_encoded = cv2.imencode(".png", screen)
        image_data = img_encoded.tobytes()

        try:
            result = self._client.analyze_with_tools(image_data, use_prompt, _TOOLS_SCENE)
        except Exception as e:
            raise VlmBackendError(f"VLM recognize failed: {e}") from e

        elements: list[dict[str, Any]] = []
        tool_calls = result.get("tool_calls", [])
        for tc in tool_calls:
            func = tc.get("function", {})
            try:
                args = func.get("arguments", {})
                if isinstance(args, str):
                    args = json.loads(args)
            except (json.JSONDecodeError, TypeError):
                args = {}

            annos = args.get("annotations", [args])
            for anno in annos:
                elements.append(
                    {
                        "label": anno.get("label", "unknown"),
                        "type": "vlm_detection",
                        "bbox": anno.get("points", []),
                        "confidence": anno.get("confidence", 0.5),
                        "source": "vlm",
                        "interaction": anno.get("interaction", ""),
                        "distance": anno.get("distance", ""),
                    }
                )

        return elements

    def health_check(self) -> bool:
        return self._client.health_check()
