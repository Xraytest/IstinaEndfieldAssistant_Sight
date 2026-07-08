from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from .template_registry import TemplateRegistry

logger = logging.getLogger(__name__)


class TemplateMatcher:
    def __init__(self, registry: Optional[TemplateRegistry] = None):
        self._registry = registry or TemplateRegistry()
        self._last_results: Dict[str, List[Dict]] = {}

    def match(
        self,
        screen: np.ndarray,
        template_ref: str,
        threshold: float = 0.8,
        roi: Optional[List[int]] = None,
        max_results: int = 5,
    ) -> List[Dict]:
        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY) if len(screen.shape) == 3 else screen
        h_img, w_img = screen_gray.shape[:2]
        tpl = self._registry.resolve(template_ref)
        if tpl is None:
            return []
        t_h, t_w = tpl.shape[:2]
        if roi:
            rx, ry, rw, rh = roi
            if rx < 0:
                rx = w_img + rx
            if ry < 0:
                ry = h_img + ry
            screen_roi = screen_gray[ry:ry + rh, rx:rx + rw]
        else:
            screen_roi = screen_gray
            rx, ry = 0, 0
        if t_h > screen_roi.shape[0] or t_w > screen_roi.shape[1]:
            return []
        res = cv2.matchTemplate(screen_roi, tpl, cv2.TM_CCOEFF_NORMED)
        locations = np.where(res >= threshold)
        results = []
        for pt in zip(*locations[::-1]):  # noqa: B905
            x, y = pt
            conf = float(res[y, x])
            results.append({
                "x": rx + x,
                "y": ry + y,
                "w": t_w,
                "h": t_h,
                "confidence": conf,
                "center": (rx + x + t_w // 2, ry + y + t_h // 2),
            })
        results.sort(key=lambda r: -r["confidence"])
        seen = set()
        deduped = []
        for r in results:
            key = (r["x"] // 5, r["y"] // 5)
            if key not in seen:
                seen.add(key)
                deduped.append(r)
                if len(deduped) >= max_results:
                    break
        self._last_results[template_ref] = deduped
        return deduped

    def match_first(
        self,
        screen: np.ndarray,
        template_ref: str,
        threshold: float = 0.8,
        roi: Optional[List[int]] = None,
    ) -> Optional[Dict]:
        results = self.match(screen, template_ref, threshold, roi, max_results=1)
        return results[0] if results else None

    def match_any(
        self,
        screen: np.ndarray,
        template_refs: List[str],
        threshold: float = 0.8,
        roi: Optional[List[int]] = None,
    ) -> Optional[Tuple[str, Dict]]:
        for ref in template_refs:
            result = self.match_first(screen, ref, threshold, roi)
            if result:
                return (ref, result)
        return None

    def match_all_instances(
        self,
        screen: np.ndarray,
        template_ref: str,
        threshold: float = 0.8,
        roi: Optional[List[int]] = None,
    ) -> List[Dict]:
        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY) if len(screen.shape) == 3 else screen
        h_img, w_img = screen_gray.shape[:2]
        tpl = self._registry.resolve(template_ref)
        if tpl is None:
            return []
        t_h, t_w = tpl.shape[:2]
        if roi:
            rx, ry, rw, rh = roi
            if rx < 0:
                rx = w_img + rx
            if ry < 0:
                ry = h_img + ry
            screen_roi = screen_gray[ry:ry + rh, rx:rx + rw]
        else:
            screen_roi = screen_gray
            rx, ry = 0, 0
        if t_h > screen_roi.shape[0] or t_w > screen_roi.shape[1]:
            return []
        res = cv2.matchTemplate(screen_roi, tpl, cv2.TM_CCOEFF_NORMED)
        results = []
        h_res, w_res = res.shape
        for y in range(h_res):
            for x in range(w_res):
                conf = float(res[y, x])
                if conf >= threshold:
                    results.append({
                        "x": rx + x,
                        "y": ry + y,
                        "w": t_w,
                        "h": t_h,
                        "confidence": conf,
                        "center": (rx + x + t_w // 2, ry + y + t_h // 2),
                    })
        results.sort(key=lambda r: -r["confidence"])
        nms_results = []
        for r in results:
            overlap = False
            for kept in nms_results:
                ix = max(r["x"], kept["x"])
                iy = max(r["y"], kept["y"])
                ix2 = min(r["x"] + r["w"], kept["x"] + kept["w"])
                iy2 = min(r["y"] + r["h"], kept["y"] + kept["h"])
                if ix < ix2 and iy < iy2:
                    overlap = True
                    break
            if not overlap:
                nms_results.append(r)
        return nms_results
