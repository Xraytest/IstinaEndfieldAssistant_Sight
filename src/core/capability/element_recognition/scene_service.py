"""
场景/页面理解服务 — 基于图像模板匹配的终末地页面识别

整合模板匹配、OCR、颜色检测，识别游戏当前所处的画面/场景。
提供场景识别、页面验证、场景追踪等能力。

用法::

    svc = SceneUnderstandingService()
    result = svc.identify(screen)
    print(f"当前页面: {result.page_type} (置信度: {result.confidence:.2f})")
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from core.foundation.paths import get_cache_subdir, get_project_root
from .element_info import ElementInfo, PageInfo, SceneAnalysis3D
from .recognizer import EndfieldElementRecognizer
from .backends.vlm_backend import VlmBackend

logger = logging.getLogger(__name__)


class SceneUnderstandingService:
    """场景/页面理解服务。

    基于模板匹配 + OCR + 颜色检测，识别游戏当前页面。
    维护场景上下文，支持场景追踪与验证。

    Attributes:
        recognizer: 底层统一识别器
        current_page: 当前识别的页面类型
        current_confidence: 当前页面置信度
        page_history: 页面历史记录 [(page_type, confidence, timestamp), ...]
    """

    def __init__(
        self,
        catalog_path: str = "",
        enable_yolo: bool = False,
        template_threshold: float = 0.7,
        maaend_runtime=None,
        vlm_backend: Optional[VlmBackend] = None,
    ):
        if not catalog_path:
            catalog_path = str(get_cache_subdir("analysis") / "page_catalog.json")

        self._catalog_path = catalog_path
        self._threshold = template_threshold
        self.current_page: str = "unknown"
        self.current_confidence: float = 0.0
        self.page_history: List[Dict[str, Any]] = []
        self._last_screen = None
        self._vlm_backend = vlm_backend

        self.recognizer = EndfieldElementRecognizer(
            catalog_path=catalog_path,
            enable_yolo=enable_yolo,
            maaend_runtime=maaend_runtime,
            vlm_backend=vlm_backend,
        )

    def set_vlm_backend(self, vlm_backend: Optional[VlmBackend]) -> None:
        """同步更新 VLM 后端，确保识别器和场景分析保持一致。"""
        self._vlm_backend = vlm_backend
        self.recognizer._vlm_backend = vlm_backend

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def identify(self, screen: np.ndarray) -> PageInfo:
        """识别当前画面属于哪个页面/场景。

        对截图运行模板匹配 + OCR + 颜色检测，综合识别页面类型。
        自动更新当前页面上下文。

        Args:
            screen: BGR 截图 (numpy array)

        Returns:
            PageInfo: 页面分析结果（page_type, confidence, elements, ...）
        """
        if screen is None or screen.size == 0:
            return PageInfo(page_type="unknown", confidence=0.0)

        self._last_screen = screen
        page = self.recognizer.recognize(screen)

        self.current_page = page.page_type
        self.current_confidence = page.confidence

        self.page_history.append({
            "page_type": page.page_type,
            "confidence": page.confidence,
            "timestamp": time.time(),
            "element_count": len(page.elements),
        })
        if len(self.page_history) > 100:
            self.page_history.pop(0)

        return page

    def identify_from_bytes(self, image_bytes: bytes) -> PageInfo:
        """从 PNG 字节数据识别页面。

        Args:
            image_bytes: PNG 编码的截图字节

        Returns:
            PageInfo
        """
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        screen = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if screen is None:
            return PageInfo(page_type="unknown", confidence=0.0)
        return self.identify(screen)

    def verify(self, screen: np.ndarray, expected_page: str) -> Tuple[bool, PageInfo]:
        """验证当前画面是否是指定页面。

        Args:
            screen: BGR 截图
            expected_page: 期望的页面类型（如 "gameplay", "loading"）

        Returns:
            (is_match, page_info): 是否匹配 + 完整页面分析
        """
        page = self.identify(screen)
        is_match = (
            page.page_type == expected_page
            and page.confidence >= 0.5
        )
        return is_match, page

    def verify_by_key_elements(
        self, screen: np.ndarray, expected_templates: List[str]
    ) -> Tuple[bool, List[ElementInfo]]:
        """通过关键模板元素验证页面。

        只运行模板匹配，检查指定的模板是否全部出现在画面中。
        适用于快速验证（无需完整的页面分类流程）。

        Args:
            screen: BGR 截图
            expected_templates: 期望出现的模板名称列表

        Returns:
            (all_found, matched_elements)
        """
        elems = self.recognizer.recognize_templates(screen, names=expected_templates)
        found_names = {e.label for e in elems}
        all_found = all(
            any(t in fn for fn in found_names)
            for t in expected_templates
        )
        return all_found, elems

    def analyze_elements(
        self,
        screen: np.ndarray,
        enable_template: bool = True,
        enable_ocr: bool = True,
        enable_color: bool = True,
    ) -> PageInfo:
        """对画面做详细元素分析，返回所有检测到的元素。

        Args:
            screen: BGR 截图
            enable_template: 是否启用模板匹配
            enable_ocr: 是否启用 OCR
            enable_color: 是否启用颜色检测

        Returns:
            PageInfo: 包含所有检测元素的详细分析
        """
        return self.recognizer.recognize(screen, enable={
            "template": enable_template,
            "ocr": enable_ocr,
            "color": enable_color,
            "yolo": False,
        })

    def get_scene_context(self) -> Dict[str, Any]:
        """获取当前场景上下文。"""
        return {
            "current_page": self.current_page,
            "current_confidence": self.current_confidence,
            "history_count": len(self.page_history),
            "recent_history": self.page_history[-10:] if self.page_history else [],
        }

    def get_dominant_page(self, window: int = 5) -> Tuple[str, float]:
        """获取最近 N 次识别中最常见的页面类型。

        用于消除单次识别抖动。

        Args:
            window: 观察窗口大小（最近几次识别）

        Returns:
            (dominant_page, ratio): 主导页面类型及其占比
        """
        if not self.page_history:
            return ("unknown", 0.0)

        recent = self.page_history[-window:]
        counts: Dict[str, int] = {}
        for entry in recent:
            pt = entry["page_type"]
            counts[pt] = counts.get(pt, 0) + 1

        best_page = max(counts, key=counts.get)
        ratio = counts[best_page] / len(recent)
        return best_page, ratio

    def list_available_templates(self) -> List[str]:
        """列出所有可用的模板名称。"""
        return self.recognizer.get_available_templates()

    def analyze_scene_3d(
        self,
        screen: np.ndarray,
        prompt: str = "",
    ) -> Optional[SceneAnalysis3D]:
        """VLM 3D 场景深度分析。

        通过 VLM 理解当前画面的 3D 场景语义，
        返回结构化标注结果（含渲染后的图像）。

        Args:
            screen: BGR 截图
            prompt: VLM prompt（不传则使用默认 prompt）

        Returns:
            SceneAnalysis3D 或 None（VLM 未就绪时）
        """
        if self._vlm_backend is None:
            return None
        return self._vlm_backend.analyze_scene_3d(screen, prompt)

    def get_page_info(self, page_type: str) -> Optional[Dict[str, Any]]:
        """获取指定页面类型的签名定义。"""
        return self.recognizer.get_page_signature(page_type)

    def reset_context(self) -> None:
        """重置场景上下文。"""
        self.current_page = "unknown"
        self.current_confidence = 0.0
        self.page_history.clear()
        self._last_screen = None
