"""
OCR 后端 — 优先使用 maafw 内置 OCR，回退到 MaaEndOCR / OCRManager

将 OCR 识别结果统一输出为 ElementInfo 列表（每个 text block 作为一个 text 元素）。
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

import numpy as np

from ..element_info import ElementInfo

logger = logging.getLogger(__name__)

MAAFW_OCR_AVAILABLE = False
try:
    from maa.pipeline import JOCR, JRecognitionType
    from maa.tasker import Tasker
    MAAFW_OCR_AVAILABLE = True
except ImportError:
    JRecognitionType = None
    JOCR = None
    Tasker = None


class OCRBackend:
    """OCR text recognition backend.

    识别路径优先级:
    1. maafw Tasker.post_recognition(JRecognitionType.OCR, ...) — 内置 OCR 引擎
    2. MaaEndOCR — MaaFramework JOCR + EasyOCR fallback
    3. OCRManager — MaaFw executor.ocr() + ScreenDecider

    优先使用 maafw 内置 OCR（功能最完整，与 MaaEnd pipeline 一致）。
    """

    def __init__(
        self,
        maaend_ocr=None,
        ocr_manager=None,
        default_roi: Optional[List[int]] = None,
        confidence_threshold: float = 0.3,
        maa_tasker: Optional[Any] = None,
    ):
        self._maaend_ocr = maaend_ocr
        self._ocr_manager = ocr_manager
        self._default_roi = default_roi
        self._confidence_threshold = confidence_threshold
        self._maa_tasker = maa_tasker

    def set_maa_tasker(self, tasker: Any) -> None:
        self._maa_tasker = tasker

    def recognize(
        self,
        screen: np.ndarray,
        roi: Optional[List[int]] = None,
        expected: Optional[List[str]] = None,
    ) -> List[ElementInfo]:
        """Run OCR and return text elements.

        Args:
            screen: BGR image
            roi: [x, y, w, h] region of interest
            expected: expected text allow-list for filtering

        Returns:
            List[ElementInfo] with source="ocr"
        """
        results: List[ElementInfo] = []
        roi = roi or self._default_roi

        # Route 1: maafw 内置 OCR（优先）
        if self._maa_tasker is not None and MAAFW_OCR_AVAILABLE:
            try:
                results.extend(self._run_maafw_ocr(screen, roi, expected))
            except Exception as e:
                logger.debug(f"maafw OCR failed: {e}")

        # Route 2: MaaEndOCR
        if not results and self._maaend_ocr is not None:
            results.extend(self._run_maaend_ocr(screen, roi, expected))

        # Route 3: OCRManager
        if not results and self._ocr_manager is not None:
            results.extend(self._run_ocr_manager(screen, roi, expected))

        results = [r for r in results if r.confidence >= self._confidence_threshold]

        if expected:
            filtered = []
            for r in results:
                if any(kw in r.label for kw in expected):
                    filtered.append(r)
            results = filtered

        return results

    def recognize_text_regions(
        self,
        screen: np.ndarray,
        keywords: Optional[List[str]] = None,
    ) -> List[ElementInfo]:
        results = self.recognize(screen)
        if keywords:
            return [r for r in results
                    if any(kw.lower() in r.label.lower() for kw in keywords)]
        return results

    def _run_maafw_ocr(
        self, screen: np.ndarray, roi: Optional[List[int]], expected: Optional[List[str]]
    ) -> List[ElementInfo]:
        """使用 maafw 内置 OCR 引擎识别文字。"""
        results = []
        h, w = screen.shape[:2]

        if roi:
            rx, ry, rw, rh = roi
        else:
            rx, ry, rw, rh = 0, 0, w, h

        ocr_param = JOCR(
            expected=expected or [],
            roi=(rx, ry, rw, rh),
            threshold=self._confidence_threshold,
        )

        job = self._maa_tasker.post_recognition(
            JRecognitionType.OCR,
            ocr_param,
            screen,
        )
        detail = job.get()

        if not detail or not detail.hit:
            return results

        best = detail.best_result
        if best is not None:
            bx1, by1, bw, bh = best.box
            results.append(ElementInfo(
                element_type="text",
                label=best.text.strip(),
                bbox=(bx1 / w, by1 / h, (bx1 + bw) / w, (by1 + bh) / h),
                center=((bx1 + bw / 2) / w, (by1 + bh / 2) / h),
                confidence=best.score,
                source="ocr",
                action="none",
                metadata={"ocr_engine": "maafw", "algorithm": str(detail.algorithm)},
            ))

        if detail.all_results:
            seen = {best.text} if best is not None else set()
            for item in detail.all_results:
                text = getattr(item, "text", "").strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                ibox = getattr(item, "box", (0, 0, 0, 0))
                results.append(ElementInfo(
                    element_type="text",
                    label=text,
                    bbox=(ibox[0] / w, ibox[1] / h, (ibox[0] + ibox[2]) / w, (ibox[1] + ibox[3]) / h),
                    center=((ibox[0] + ibox[2] / 2) / w, (ibox[1] + ibox[3] / 2) / h),
                    confidence=getattr(item, "score", best.score if best else 0.5),
                    source="ocr",
                    action="none",
                    metadata={"ocr_engine": "maafw"},
                ))

        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_maaend_ocr(
        self, screen: np.ndarray, roi: Optional[List[int]], expected: Optional[List[str]]
    ) -> List[ElementInfo]:
        """Run MaaEndOCR and convert to ElementInfo list."""
        results = []
        try:
            ocr_result = self._maaend_ocr.recognize(screen, roi=roi, expected=expected)
        except Exception as e:
            logger.debug(f"MaaEndOCR failed: {e}")
            return results

        if not ocr_result or not ocr_result.get("best_text"):
            return results

        h, w = screen.shape[:2]
        all_results = ocr_result.get("all_results", [])
        best_text = ocr_result.get("best_text", "")
        confidence = ocr_result.get("confidence", 0.0)

        # 主文本块
        x1, y1, rw, rh = ocr_result.get("roi", [0, 0, w, h])
        results.append(ElementInfo(
            element_type="text",
            label=best_text,
            bbox=(x1 / w, y1 / h, (x1 + rw) / w, (y1 + rh) / h),
            center=((x1 + rw / 2) / w, (y1 + rh / 2) / h),
            confidence=confidence,
            source="ocr",
            action="none",
            metadata={
                "roi": [x1, y1, rw, rh],
                "all_results_count": len(all_results),
                "ocr_engine": "MaaEndOCR",
            },
        ))

        # 子文本块
        for sub in all_results[:10]:
            sub_text = sub.get("text", "")
            if not sub_text or sub_text == best_text:
                continue

            # Robust box parsing (handle multiple formats)
            sx, sy, sw, sh = self._parse_ocr_box(sub, x1, y1, rw, rh, w, h)

            results.append(ElementInfo(
                element_type="text",
                label=sub_text,
                bbox=(sx / w, sy / h, (sx + sw) / w, (sy + sh) / h),
                center=((sx + sw / 2) / w, (sy + sh / 2) / h),
                confidence=sub.get("confidence", confidence),
                source="ocr",
                action="none",
                metadata={"parent": best_text, "ocr_engine": "MaaEndOCR"},
            ))

        return results

    @staticmethod
    def _parse_ocr_box(sub: dict, roi_x: int, roi_y: int, roi_w: int, roi_h: int,
                       screen_w: int, screen_h: int) -> Tuple[int, int, int, int]:
        """Parse OCR bounding box from various possible formats.

        Handles:
        - [x, y, w, h] (standard)
        - [x1, y1, x2, y2] (corner format)
        - [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] (4-point polygon)
        - None → fallback to roi
        """
        box = sub.get("box")
        if not box:
            # Fallback: use roi with small random offset to avoid stacking at (0,0)
            return (roi_x, roi_y, roi_w, roi_h)

        try:
            if isinstance(box, (list, tuple)) and len(box) >= 4:
                # Check if it's a 4-point polygon [[x1,y1],[x2,y2],...]
                if isinstance(box[0], (list, tuple)) and len(box) == 4:
                    xs = [p[0] for p in box]
                    ys = [p[1] for p in box]
                    sx, sy = min(xs), min(ys)
                    ex, ey = max(xs), max(ys)
                    return (int(sx), int(sy), int(ex - sx), int(ey - sy))
                # Standard [x, y, w, h] or [x1, y1, x2, y2]
                vals = [int(v) for v in box[:4]]
                if vals[2] > vals[0] and vals[3] > vals[1]:
                    # Looks like [x1, y1, x2, y2]
                    return (vals[0], vals[1], vals[2] - vals[0], vals[3] - vals[1])
                # [x, y, w, h]
                return (vals[0], vals[1], vals[2], vals[3])
        except (TypeError, ValueError, IndexError):
            pass

        # Ultimate fallback: roi center
        return (roi_x + roi_w // 4, roi_y + roi_h // 4, roi_w // 2, roi_h // 2)

    def _run_ocr_manager(
        self, screen: np.ndarray, roi: Optional[List[int]], expected: Optional[List[str]]
    ) -> List[ElementInfo]:
        """Run OCRManager and convert to ElementInfo list."""
        results = []
        try:
            ocr_results = self._ocr_manager.run_ocr(roi=roi, expected=expected)
        except Exception as e:
            logger.debug(f"OCRManager failed: {e}")
            return results

        h, w = screen.shape[:2]
        for item in ocr_results:
            text = item.get("text", "").strip()
            if not text:
                continue
            box = item.get("box", [0, 0, 0, 0])
            x, y, bw, bh = box
            results.append(ElementInfo(
                element_type="text",
                label=text,
                bbox=(x / w, y / h, (x + bw) / w, (y + bh) / h),
                center=(item.get("cx", x + bw // 2) / w,
                        item.get("cy", y + bh // 2) / h),
                confidence=item.get("score", 0.5),
                source="ocr",
                action="none",
                metadata={"ocr_engine": "OCRManager"},
            ))

        return results
