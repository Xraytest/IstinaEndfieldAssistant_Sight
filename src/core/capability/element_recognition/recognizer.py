"""
终末地画面元素统一识别器

整合 5 种识别技术到一个统一入口：
- 模板匹配（TemplateMatcher + SIFT）
- OCR 文字识别（MaaEndOCR + OCRManager）
- 颜色匹配（HSV + contours）
- YOLO 物体检测
- 页面分类（基于元素 + OCR 关键词）

输出统一的 ElementInfo 列表 + PageInfo 页面分析结果。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from .element_info import ElementInfo, PageInfo, ELEMENT_TYPES, PAGE_TYPES
from .backends.template_backend import TemplateBackend
from .backends.ocr_backend import OCRBackend
from .backends.color_backend import ColorBackend
from .backends.yolo_backend import YOLOBackend
from .backends.vlm_backend import VlmBackend

logger = logging.getLogger(__name__)


class EndfieldElementRecognizer:
    """Unified Endfield screen element recognizer.

    整合模板匹配、OCR、颜色匹配、YOLO 检测到一个统一接口。
    所有后端通过依赖注入接入（无硬依赖），缺失的后端自动跳过。

    Example::

        recognizer = EndfieldElementRecognizer()
        page = recognizer.recognize(screen)
        for elem in page.elements:
            print(f"{elem.source}: {elem.label} at {elem.center}")
        print(f"Page: {page.page_type} ({page.confidence:.2f})")
    """

    def __init__(
        self,
        template_matcher=None,
        recognition_engine=None,
        maaend_ocr=None,
        ocr_manager=None,
        catalog_path: str = "",
        enable_yolo: bool = True,
        yolo_model_path: str = "yolo11n.pt",
        yolo_conf: float = 0.25,
        maaend_runtime=None,
        vlm_backend: Optional[VlmBackend] = None,
    ):
        self._maaend_runtime = maaend_runtime
        self._catalog: Dict[str, Any] = {}
        self._page_signatures: Dict[str, Any] = {}
        self._load_catalog(catalog_path)

        self._template_backend = TemplateBackend(
            template_matcher=template_matcher,
            recognition_engine=recognition_engine,
            catalog_path=catalog_path,
        )
        if self._catalog:
            self._template_backend._catalog = self._catalog

        resolved_maaend_ocr = maaend_ocr
        resolved_ocr_manager = ocr_manager
        maa_tasker = getattr(maaend_runtime, "_tasker", None) if maaend_runtime is not None else None

        self._ocr_backend = OCRBackend(
            maaend_ocr=resolved_maaend_ocr,
            ocr_manager=resolved_ocr_manager,
            maa_tasker=maa_tasker,
        )
        self._color_backend = ColorBackend(
            recognition_engine=recognition_engine,
        )
        self._yolo_backend = YOLOBackend(
            model_path=yolo_model_path,
            conf_threshold=yolo_conf,
        ) if enable_yolo else None
        self._vlm_backend = vlm_backend

        # 传递 maa_tasker 到 template backend 的 pipeline runner
        if maa_tasker is not None:
            tpl_runner = self._template_backend.get_runner()
            if tpl_runner:
                tpl_runner.set_maa_tasker(maa_tasker)

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def recognize(
        self,
        screen: np.ndarray,
        page_hint: str = "",
        enable: Dict[str, bool] = None,
    ) -> PageInfo:
        """统一识别入口：运行所有启用的后端，合并去重，分类页面。

        Args:
            screen: BGR 截图
            page_hint: 页面类型提示（跳过已确认的页面检测）
            enable: 控制各后端开关 {"template": True, "ocr": True, ...}

        Returns:
            PageInfo with detected elements and page classification
        """
        if screen is None or screen.size == 0:
            return PageInfo(page_type="unknown", confidence=0.0)

        enable = enable or {}
        h_img, w_img = screen.shape[:2]
        all_elements: List[ElementInfo] = []

        # Phase 1: 并行检测
        if enable.get("template", True):
            elems = self._template_backend.recognize(screen)
            all_elements.extend(elems)

        if enable.get("ocr", True):
            elems = self._ocr_backend.recognize(screen)
            all_elements.extend(elems)

        if enable.get("color", True):
            elems = self._color_backend.recognize(screen, self._get_color_signatures(page_hint))
            all_elements.extend(elems)

        if enable.get("yolo", True) and self._yolo_backend is not None:
            elems = self._yolo_backend.recognize(screen)
            all_elements.extend(elems)

        if enable.get("vlm", False) and self._vlm_backend is not None:
            elems = self._vlm_backend.recognize(screen)
            all_elements.extend(elems)

        # Phase 2: 去重（相同位置 + 相同标签）
        deduped = self._deduplicate(all_elements)

        # Phase 2.5: 3D 游戏场景检测（蓝色主导的画面）
        gameplay_info = self._color_backend.recognize_gameplay_scene(screen)
        if gameplay_info.get("is_gameplay"):
            # 3D 场景：添加角色/对象元素到列表
            for char in gameplay_info.get("characters", []):
                deduped.append(ElementInfo(
                    element_type="character",
                    label="character",
                    bbox=(char["cx"] / w_img, char["cy"] / h_img,
                          (char["cx"] + char["w"]) / w_img, (char["cy"] + char["h"]) / h_img),
                    center=(char["cx"] / w_img, char["cy"] / h_img),
                    confidence=0.7,
                    source="color",
                    action="unknown",
                    metadata={"method": "skin_color", "area": char["area"],
                              "aspect": char["aspect"]},
                ))
            for obj in gameplay_info.get("objects", [])[:5]:
                deduped.append(ElementInfo(
                    element_type="region",
                    label="scene_object",
                    bbox=(obj["cx"] / w_img, obj["cy"] / h_img,
                          (obj["cx"] + obj["w"]) / w_img, (obj["cy"] + obj["h"]) / h_img),
                    center=(obj["cx"] / w_img, obj["cy"] / h_img),
                    confidence=0.5,
                    source="color",
                    action="unknown",
                    metadata={"method": "non_blue", "area": obj["area"],
                              "aspect": obj["aspect"]},
                ))

        # Phase 3: 页面分类
        page_info = self._classify_page(screen, deduped, page_hint)

        # Override: if gameplay scene detected with high blue ratio, prefer gameplay page
        if (gameplay_info.get("is_gameplay") and
                gameplay_info.get("blue_ratio", 0) > 0.75 and
                page_info.page_type not in ("exit_dialog", "loading", "title_screen")):
            page_info.page_type = "gameplay"
            page_info.confidence = max(page_info.confidence, 0.7)

        page_info.elements = deduped
        page_info.features = self._extract_features(screen)
        page_info.metadata["gameplay_info"] = gameplay_info

        return page_info

    def recognize_templates(
        self, screen: np.ndarray, names: Optional[List[str]] = None
    ) -> List[ElementInfo]:
        """仅模板匹配"""
        return self._template_backend.recognize(screen, template_names=names)

    def recognize_text(
        self,
        screen: np.ndarray,
        roi: Optional[List[int]] = None,
        expected: Optional[List[str]] = None,
    ) -> List[ElementInfo]:
        """仅 OCR 文字识别"""
        return self._ocr_backend.recognize(screen, roi=roi, expected=expected)

    def recognize_colors(
        self,
        screen: np.ndarray,
        signatures: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ElementInfo]:
        """仅颜色匹配"""
        return self._color_backend.recognize(screen, signatures)

    def recognize_yolo(
        self,
        screen: np.ndarray,
        class_filter: Optional[List[str]] = None,
    ) -> List[ElementInfo]:
        """仅 YOLO 物体检测"""
        if self._yolo_backend is None:
            return []
        return self._yolo_backend.recognize(screen, class_filter=class_filter)

    def get_catalog_element(self, name: str) -> Optional[Dict[str, Any]]:
        """获取元素目录中某个元素的定义"""
        return self._catalog.get(name)

    def get_page_signature(self, page_type: str) -> Optional[Dict[str, Any]]:
        """获取页面签名（用于分类的特征组合）"""
        return self._page_signatures.get(page_type)

    def get_available_templates(self) -> List[str]:
        """列出所有已知模板名"""
        return self._template_backend.get_available_templates()

    # ------------------------------------------------------------------
    # 页面分类
    # ------------------------------------------------------------------

    def _classify_page(
        self, screen: np.ndarray, elements: List[ElementInfo], hint: str = ""
    ) -> PageInfo:
        """Classify page type from detected elements."""
        if hint and hint in PAGE_TYPES:
            return PageInfo(page_type=hint, confidence=0.9, elements=elements)

        scores: Dict[str, float] = {}
        for page_type, sig in self._page_signatures.items():
            score = self._score_page(screen, elements, sig)
            if score > 0:
                scores[page_type] = score

        if not scores:
            return PageInfo(page_type="unknown", confidence=0.3, elements=elements)

        best_page = max(scores, key=scores.get)
        best_score = scores[best_page]
        # Normalize confidence: score >= 3.0 -> high confidence
        confidence = min(1.0, best_score / 3.0)

        return PageInfo(page_type=best_page, confidence=confidence, elements=elements)

    def _score_page(
        self, screen: np.ndarray, elements: List[ElementInfo], sig: Dict[str, Any]
    ) -> float:
        """Score how well elements match a page signature.

        Scoring tiers:
        - Required element matched (template/OCR/YOLO): +2.0 each
        - Color signature present: +1.0
        - OCR keyword match: +0.5 each
        - Fallback: count of catalog templates present / total catalog templates * 2.0
        """
        score = 0.0
        # 统一 lowercase 做匹配，避免大小写不一致
        element_labels = {e.label.lower() for e in elements}
        element_types = {e.element_type for e in elements}
        element_sources = {e.source for e in elements}

        # Tier 1: Required elements
        required = sig.get("required_elements", [])
        required_matched = 0
        for req in required:
            catalog_entry = self._catalog.get(req, {})
            # Template match
            tpl_names = catalog_entry.get("templates", [])
            if any(t.lower() in element_labels for t in tpl_names):
                score += 2.0
                required_matched += 1
                continue
            # OCR keyword
            ocr_kws = catalog_entry.get("ocr_keywords", [])
            if any(kw.lower() in element_labels for kw in ocr_kws):
                score += 1.5
                required_matched += 1
                continue
            # YOLO class
            yolo_cls = catalog_entry.get("yolo_classes", [])
            if any(c in element_types for c in yolo_cls):
                score += 1.5
                required_matched += 1

        # Tier 2: Color signatures
        color_sigs = sig.get("color_signatures", [])
        if color_sigs:
            color_elems = self._color_backend.recognize(screen, color_sigs)
            if color_elems:
                score += 1.0

        # Tier 3: OCR keywords (any element, not just required)
        ocr_keywords = sig.get("ocr_keywords", [])
        if ocr_keywords and "ocr" in element_sources:
            for elem in elements:
                if elem.source == "ocr":
                    if any(kw.lower() in elem.label.lower() for kw in ocr_keywords):
                        score += 0.5
                        break  # one keyword match is enough

        # Tier 4: Fallback — ratio of catalog templates present
        # Only used when no required elements matched (prevents false positives)
        if required and required_matched == 0 and element_labels:
            all_catalog_templates = set()
            for entry in self._catalog.values():
                all_catalog_templates.update(t.lower() for t in entry.get("templates", []))
            matched = element_labels & all_catalog_templates
            if matched:
                ratio = len(matched) / max(len(all_catalog_templates), 1)
                score += ratio * 1.0  # max +1.0 from fallback

        # Excluded keywords (penalty)
        excluded = sig.get("excluded_keywords", [])
        if excluded:
            for elem in elements:
                if elem.source == "ocr":
                    if any(kw.lower() in elem.label.lower() for kw in excluded):
                        score -= 2.0

        return max(0.0, score)

    # ------------------------------------------------------------------
    # 去重
    # ------------------------------------------------------------------

    def _deduplicate(self, elements: List[ElementInfo]) -> List[ElementInfo]:
        """Remove duplicate elements (same position within threshold + same/similar label).

        Uses spatial proximity (0.05 normalized distance) instead of exact match.
        """
        if len(elements) <= 1:
            return elements

        # Sort by confidence descending — keep highest confidence
        sorted_elems = sorted(elements, key=lambda e: -e.confidence)

        result: List[ElementInfo] = []
        for elem in sorted_elems:
            is_dup = False
            for existing in result:
                if self._is_nearby(elem, existing, threshold=0.05):
                    # Same location — keep the one with higher confidence
                    is_dup = True
                    break
            if not is_dup:
                result.append(elem)

        return result

    def _is_nearby(self, a: ElementInfo, b: ElementInfo, threshold: float = 0.05) -> bool:
        """Check if two elements are at nearby positions with similar labels."""
        # Label similarity
        label_a = a.label.lower().strip()
        label_b = b.label.lower().strip()
        label_match = (
            label_a == label_b
            or label_a in label_b
            or label_b in label_a
        )

        # Spatial proximity (center distance)
        dx = abs(a.center[0] - b.center[0])
        dy = abs(a.center[1] - b.center[1])
        nearby = (dx + dy) < threshold

        return label_match and nearby

    # ------------------------------------------------------------------
    # 特征提取
    # ------------------------------------------------------------------

    def _extract_features(self, screen: np.ndarray) -> Dict[str, Any]:
        """Extract screen features for downstream classification."""
        try:
            h, w = screen.shape[:2]
            gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)

            # Left sidebar brightness
            left_bar = gray[:, max(0, w // 20):w // 6]
            left_bar_brightness = float(np.mean(left_bar)) if left_bar.size > 0 else 0

            # Top-right green pixels
            green_lower = np.array([35, 50, 50])
            green_upper = np.array([85, 255, 255])
            green_mask = cv2.inRange(hsv, green_lower, green_upper)
            top_right_green = green_mask[0:h // 5, max(0, w * 3 // 4):w]
            green_pixels_top_right = int(cv2.countNonZero(top_right_green))

            return {
                "left_bar_brightness": round(left_bar_brightness, 1),
                "green_pixels_top_right": green_pixels_top_right,
                "full_brightness": round(float(np.mean(gray)), 1),
                "resolution": [w, h],
            }
        except Exception:
            return {}

    def _get_color_signatures(self, page_hint: str) -> List[Dict[str, Any]]:
        """Get relevant color signatures for a page type."""
        sigs = []
        if page_hint in ("quest_panel", "exit_dialog"):
            sigs.append({
                "lower": [15, 80, 100], "upper": [35, 255, 255],
                "min_area": 40, "min_contours": 1,
            })
        if page_hint in ("world_map",):
            sigs.append({
                "lower": [35, 80, 80], "upper": [85, 255, 200],
                "min_area": 50, "min_contours": 1,
            })
        return sigs

    # ------------------------------------------------------------------
    # Catalog loading
    # ------------------------------------------------------------------

    def _load_catalog(self, catalog_path: str) -> None:
        """Load element catalog from JSON."""
        if not catalog_path:
            return

        try:
            path = Path(catalog_path)
            if not path.exists():
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._catalog = data.get("elements", {})
            self._page_signatures = data.get("page_signatures", {})
            logger.info(f"Element catalog loaded: {len(self._catalog)} elements, "
                       f"{len(self._page_signatures)} page signatures")
        except Exception as e:
            logger.debug(f"Catalog load failed: {e}")
