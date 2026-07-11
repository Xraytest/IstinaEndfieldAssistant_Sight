from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from .template_registry import TemplateRegistry

logger = logging.getLogger(__name__)


def _to_gray(screen: np.ndarray) -> np.ndarray:
    """转为灰度图；M3: 4 通道 BGRA 先转 BGR 再转灰度，避免 cvtColor 报错。"""
    if len(screen.shape) == 2:
        return screen
    if screen.shape[2] == 4:
        screen = cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR)
    return cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)


def _apply_roi(screen_gray: np.ndarray, roi: Optional[List[int]]):
    """M2: 计算 ROI 区域并裁剪到图像边界内，避免负坐标/越界切片产生错误区域。"""
    h_img, w_img = screen_gray.shape[:2]
    if roi:
        rx, ry, rw, rh = roi
        if rx < 0:
            rx = w_img + rx
        if ry < 0:
            ry = h_img + ry
        rx = max(0, min(rx, w_img))
        ry = max(0, min(ry, h_img))
        rw = max(0, min(rw, w_img - rx))
        rh = max(0, min(rh, h_img - ry))
        screen_roi = screen_gray[ry:ry + rh, rx:rx + rw]
    else:
        screen_roi = screen_gray
        rx, ry = 0, 0
    return screen_roi, rx, ry


def _iou_nms(results: List[Dict], max_results: int = 5, iou_thresh: float = 0.5) -> List[Dict]:
    """M1: 按 IoU 做非极大值抑制，与 match_all_instances 统一去重口径。"""
    kept: List[Dict] = []
    for r in results:
        overlap = False
        for k in kept:
            ix = max(r["x"], k["x"])
            iy = max(r["y"], k["y"])
            ix2 = min(r["x"] + r["w"], k["x"] + k["w"])
            iy2 = min(r["y"] + r["h"], k["y"] + k["h"])
            iw = max(0, ix2 - ix)
            ih = max(0, iy2 - iy)
            inter = iw * ih
            union = r["w"] * r["h"] + k["w"] * k["h"] - inter
            if union > 0 and inter / union > iou_thresh:
                overlap = True
                break
        if not overlap:
            kept.append(r)
            if len(kept) >= max_results:
                break
    return kept


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
        screen_gray = _to_gray(screen)
        tpl = self._registry.resolve(template_ref)
        if tpl is None:
            return []
        t_h, t_w = tpl.shape[:2]
        screen_roi, rx, ry = _apply_roi(screen_gray, roi)
        if screen_roi.shape[0] < t_h or screen_roi.shape[1] < t_w:
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
        # M1: 使用 IoU-NMS 去重，与 match_all_instances 口径一致
        deduped = _iou_nms(results, max_results)
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
        screen_gray = _to_gray(screen)
        tpl = self._registry.resolve(template_ref)
        if tpl is None:
            return []
        t_h, t_w = tpl.shape[:2]
        screen_roi, rx, ry = _apply_roi(screen_gray, roi)
        if screen_roi.shape[0] < t_h or screen_roi.shape[1] < t_w:
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
        return _iou_nms(results, max_results=len(results))
