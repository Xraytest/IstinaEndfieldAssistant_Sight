"""
模板匹配后端 — 整合 Pipeline 模块化框架

使用 TemplateRegistry 统一管理模板生命周期，
PipelineRunner + TemplateMatcher 执行匹配，
同时保留对外部 TemplateMatcher / RecognitionEngine SIFT 的兼容。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from ..element_info import ElementInfo
from ..pipeline import (
    PipelineRunner,
    TemplateRegistry,
)
from ..pipeline import (
    TemplateMatcher as PipelineTemplateMatcher,
)

logger = logging.getLogger(__name__)


class TemplateBackend:
    """Template matching backend.

    基于 Pipeline 模块化框架，通过 TemplateRegistry 管理模板：
    1. TemplateRegistry — 单例，多模块按需加载
    2. PipelineTemplateMatcher — OpenCV matchTemplate（快速，像素级）
    3. 兼容旧版 RecognitionEngine SIFT（鲁棒，缩放/旋转 tolerant）

    模板来源优先级：
    - assets/templates/ 下的模块化模板
    - 3rd-part/maaend/resource/image/ 的 MaaEnd 模板
    """

    def __init__(
        self,
        template_matcher=None,
        recognition_engine=None,
        catalog_path: str = "",
        default_threshold: float = 0.7,
        auto_load_modules: bool = True,
    ):
        self._legacy_matcher = template_matcher
        self._engine = recognition_engine
        self._default_threshold = default_threshold

        # Pipeline 模块化组件
        self._registry = TemplateRegistry()
        self._pipeline_matcher = PipelineTemplateMatcher(self._registry)
        self._runner = PipelineRunner(self._registry, self._pipeline_matcher)

        # 元素目录（可选）
        self._catalog: Dict[str, Any] = {}
        if catalog_path and Path(catalog_path).exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._catalog = data.get("elements", {})
            except Exception:
                pass

        # 自动加载模板模块
        if auto_load_modules:
            self._load_available_modules()

    def load_module(self, module_name: str) -> int:
        count = self._registry.load_module(module_name)
        return count

    def load_modules(self, module_names: List[str]) -> int:
        total = 0
        for name in module_names:
            total += self.load_module(name)
        return total

    def _load_available_modules(self) -> None:
        total = self._registry.load_all()
        if total == 0:
            total = self._load_maaend_modules()
        if total:
            logger.info(f"[TemplateBackend] loaded {total} templates via registry")
        else:
            logger.debug("[TemplateBackend] no templates found in registry, trying MaaEnd...")

    def _load_maaend_modules(self) -> int:
        total = 0
        # 主动加载常用模块
        common_modules = [
            "Common", "SceneManager", "DailyRewards", "AutoSell",
            "AutoEssence", "AutoCollect", "AutoEcoFarm", "OpenGame",
            "CloseInfo", "CreditShopping", "DeliveryJobs",
            "RealTimeTask", "EnvironmentMonitoring",
        ]
        for name in common_modules:
            total += self._registry.load_maaend_module(name)
        return total

    def recognize(
        self,
        screen: np.ndarray,
        template_names: Optional[List[str]] = None,
        threshold: float = None,
        roi: Optional[List[int]] = None,
    ) -> List[ElementInfo]:
        """Match templates against screen.

        Args:
            screen: BGR image
            template_names: 指定模板名列表，None 则匹配目录中所有
            threshold: 匹配阈值 (default: self._default_threshold)
            roi: 搜索区域 [x, y, w, h]

        Returns:
            List[ElementInfo] with source="template"
        """
        if threshold is None:
            threshold = self._default_threshold
        results: List[ElementInfo] = []

        # 确定要匹配的模板列表
        if template_names is None:
            if self._catalog:
                template_names = []
                for elem_key, entry in self._catalog.items():
                    tpl_list = entry.get("templates", [])
                    if tpl_list:
                        template_names.extend(tpl_list)
                    elif elem_key not in template_names:
                        template_names.append(elem_key)
            else:
                template_names = self._registry.available_templates()

        if not template_names:
            return results

        for name in template_names:
            catalog_entry = self._catalog.get(name, {})
            template_list = catalog_entry.get("templates", [name])

            for tmpl_name in template_list:
                elem = self._match_single(screen, tmpl_name, threshold, roi)
                if elem is not None:
                    elem.metadata["catalog_key"] = name
                    elem.metadata.setdefault("element_type",
                                             catalog_entry.get("type", "icon"))
                    elem.metadata.setdefault("action",
                                             catalog_entry.get("action", "unknown"))
                    results.append(elem)

        return results

    def match_page_templates(
        self,
        screen: np.ndarray,
        page_templates: Dict[str, List[str]],
        threshold: float = 0.6,
    ) -> List[ElementInfo]:
        results: List[ElementInfo] = []
        for page_type, tpl_names in page_templates.items():
            for tpl_name in tpl_names:
                elem = self._match_single(screen, tpl_name, threshold)
                if elem is not None:
                    elem.metadata["page_type"] = page_type
                    results.append(elem)
        return results

    def get_available_templates(self) -> List[str]:
        names = set()
        names.update(self._catalog.keys())
        names.update(self._registry.available_templates())
        if self._legacy_matcher:
            names.update(getattr(self._legacy_matcher, '_cache', {}).keys())
        return sorted(names)

    def get_registry(self) -> TemplateRegistry:
        return self._registry

    def get_runner(self) -> PipelineRunner:
        return self._runner

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _match_single(
        self,
        screen: np.ndarray,
        template_name: str,
        threshold: float,
        roi: Optional[List[int]] = None,
    ) -> Optional[ElementInfo]:
        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY) if len(screen.shape) == 3 else screen
        h_img, w_img = screen.shape[:2]

        # Route 0: Pipeline 模块化匹配
        match = self._pipeline_matcher.match_first(screen, template_name, threshold, roi)
        if match is not None:
            x, y, tw, th = match["x"], match["y"], match["w"], match["h"]
            conf = match["confidence"]
            adj_cx, adj_cy = self._adjust_tap_center(screen_gray, x, y, tw, th)
            return ElementInfo(
                element_type="icon",
                label=template_name,
                bbox=(x / w_img, y / h_img, (x + tw) / w_img, (y + th) / h_img),
                center=(adj_cx / w_img, adj_cy / h_img),
                confidence=conf,
                source="template",
                action="tap",
                metadata={
                    "template_name": template_name,
                    "match_method": "pipeline",
                    "raw_x": x, "raw_y": y, "raw_w": tw, "raw_h": th,
                    "adjusted_cx": adj_cx, "adjusted_cy": adj_cy,
                },
            )

        # Route 1: Legacy TemplateMatcher
        if self._legacy_matcher is not None:
            try:
                result = self._legacy_matcher.match(screen, template_name, threshold=threshold, roi=roi)
                if result.get("found"):
                    x, y = result.get("x", 0), result.get("y", 0)
                    tw, th = result.get("w", 0), result.get("h", 0)
                    adj_cx, adj_cy = self._adjust_tap_center(screen_gray, x, y, tw, th)
                    return ElementInfo(
                        element_type="icon",
                        label=template_name,
                        bbox=(x / w_img, y / h_img, (x + tw) / w_img, (y + th) / h_img),
                        center=(adj_cx / w_img, adj_cy / h_img),
                        confidence=result.get("confidence", threshold),
                        source="template",
                        action="tap",
                        metadata={
                            "template_name": template_name,
                            "match_method": "legacy_matcher",
                            "raw_x": x, "raw_y": y, "raw_w": tw, "raw_h": th,
                            "adjusted_cx": adj_cx, "adjusted_cy": adj_cy,
                        },
                    )
            except Exception:
                pass

        # Route 2: RecognitionEngine SIFT
        if self._engine is not None:
            try:
                ok, detail = self._engine.recognize(screen, {
                    "type": "TemplateMatch",
                    "template": template_name,
                    "roi": roi or [0, 0, w_img, h_img],
                    "threshold": threshold * 20,
                })
                if ok and detail:
                    bbox = detail.get("bbox", [0, 0, 0, 0])
                    raw_cx = int((bbox[0] + bbox[2]) / 2)
                    raw_cy = int((bbox[1] + bbox[3]) / 2)
                    adj_cx, adj_cy = self._adjust_tap_center(
                        screen_gray, raw_cx - 10, raw_cy - 10, 20, 20
                    )
                    return ElementInfo(
                        element_type="icon",
                        label=template_name,
                        bbox=(bbox[0] / w_img, bbox[1] / h_img,
                              bbox[2] / w_img, bbox[3] / h_img),
                        center=(adj_cx / w_img, adj_cy / h_img),
                        confidence=min(1.0, detail.get("confidence", 0.5)),
                        source="template",
                        action="tap",
                        metadata={
                            "template_name": template_name,
                            "match_method": "SIFT",
                            "matches": detail.get("matches", 0),
                            "adjusted_cx": adj_cx, "adjusted_cy": adj_cy,
                        },
                    )
            except Exception:
                pass

        return None

    def _adjust_tap_center(
        self,
        screen_gray: np.ndarray,
        tpl_x: int, tpl_y: int, tpl_w: int, tpl_h: int,
    ) -> Tuple[int, int]:
        h_img, w_img = screen_gray.shape[:2]

        search_x1 = max(0, tpl_x - 30)
        search_y1 = max(0, tpl_y - 20)
        search_x2 = min(w_img, tpl_x + tpl_w + 30)
        search_y2 = min(h_img, tpl_y + tpl_h + 40)

        roi = screen_gray[search_y1:search_y2, search_x1:search_x2]
        if roi.size == 0:
            return (tpl_x + tpl_w // 2, tpl_y + tpl_h // 2)

        _, bright = cv2.threshold(roi, 120, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        tpl_cx = tpl_x + tpl_w // 2 - search_x1
        tpl_cy = tpl_y + tpl_h // 2 - search_y1

        best_contour = None
        best_area = 0
        for c in contours:
            if cv2.pointPolygonTest(c, np.array([tpl_cx, tpl_cy], dtype=np.float32), False) >= 0:
                area = cv2.contourArea(c)
                if area > best_area:
                    best_area = area
                    best_contour = c

        if best_contour is not None and best_area > 50:
            x, y, bw, bh = cv2.boundingRect(best_contour)
            adj_cx = search_x1 + x + bw // 2
            adj_cy = search_y1 + y + bh // 2
            return (adj_cx, adj_cy)

        return (tpl_x + tpl_w // 2, tpl_y + tpl_h // 2 + tpl_h // 4)
