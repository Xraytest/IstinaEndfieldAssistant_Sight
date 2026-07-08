"""
颜色匹配后端 — 包装 RecognitionEngine._color_match()

将 HSV 颜色匹配结果统一输出为 ElementInfo 列表。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from ..element_info import ElementInfo

logger = logging.getLogger(__name__)


class ColorBackend:
    """HSV color matching backend.

    使用 OpenCV inRange + contour detection 检测特定颜色区域。
    包装 RecognitionEngine._color_match() 并支持独立运行。
    """

    def __init__(
        self,
        recognition_engine=None,
        default_min_area: int = 30,
        default_min_contours: int = 1,
    ):
        self._engine = recognition_engine
        self._default_min_area = default_min_area
        self._default_min_contours = default_min_contours

    def recognize(
        self,
        screen: np.ndarray,
        color_signatures: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ElementInfo]:
        """Match color regions on screen.

        Args:
            screen: BGR image
            color_signatures: list of {lower: [h,s,v], upper: [h,s,v],
                                  min_area, min_contours, roi}

        Returns:
            List[ElementInfo] with source="color"
        """
        results: List[ElementInfo] = []

        if not color_signatures:
            return results

        h_img, w_img = screen.shape[:2]

        for sig in color_signatures:
            elems = self._match_one_signature(screen, sig, w_img, h_img)
            results.extend(elems)

        return results

    def recognize_golden_regions(
        self, screen: np.ndarray, roi: Optional[List[int]] = None
    ) -> List[ElementInfo]:
        """Detect golden/yellow UI elements (buttons, icons, tabs).

        Endfield UI uses distinctive gold/yellow for interactive elements.
        This is a convenience method that uses the standard golden HSV range.
        """
        sig = {
            "lower": [15, 80, 100],
            "upper": [35, 255, 255],
            "min_area": 40,
            "min_contours": 1,
            "roi": roi,
        }
        return self.recognize(screen, [sig])

    def recognize_green_regions(
        self, screen: np.ndarray, roi: Optional[List[int]] = None
    ) -> List[ElementInfo]:
        """Detect green UI elements (resource icons, world indicators).

        Endfield world map has distinctive green resource icons in the top-right.
        """
        sig = {
            "lower": [35, 80, 80],
            "upper": [85, 255, 200],
            "min_area": 50,
            "min_contours": 1,
            "roi": roi,
        }
        return self.recognize(screen, [sig])

    def recognize_gameplay_scene(
        self, screen: np.ndarray, min_blue_ratio: float = 0.6
    ) -> Dict[str, Any]:
        """Detect 3D gameplay scene (blue-dominant screen).

        Endfield gameplay screens are dominated by blue sky/environment.
        This method:
        1. Checks if blue pixels exceed min_blue_ratio
        2. Detects character positions (skin color)
        3. Detects non-blue objects (buildings, items)

        Returns:
            Dict with keys: is_gameplay, blue_ratio, characters, objects
        """
        result = {
            "is_gameplay": False,
            "blue_ratio": 0.0,
            "characters": [],
            "objects": [],
            "ui_elements": [],
        }

        try:
            hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
            gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
            h_img, w_img = screen.shape[:2]

            # Blue pixel ratio (sky/environment)
            blue_mask = cv2.inRange(hsv, np.array([80, 30, 30]), np.array([140, 255, 255]))
            blue_ratio = cv2.countNonZero(blue_mask) / (w_img * h_img)
            result["blue_ratio"] = round(blue_ratio, 3)

            if blue_ratio < min_blue_ratio:
                return result

            result["is_gameplay"] = True

            # Skin color detection (character models)
            skin_mask = cv2.inRange(hsv, np.array([0, 30, 80]), np.array([20, 150, 255]))
            skin_contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in skin_contours:
                area = cv2.contourArea(c)
                if area > 200:
                    x, y, bw, bh = cv2.boundingRect(c)
                    cx, cy = x + bw // 2, y + bh // 2
                    result["characters"].append({
                        "cx": cx, "cy": cy,
                        "w": bw, "h": bh,
                        "area": float(area),
                        "aspect": round(bw / max(bh, 1), 2),
                    })

            # Non-blue objects (buildings, structures)
            non_blue = cv2.bitwise_not(blue_mask)
            nb_contours, _ = cv2.findContours(non_blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in nb_contours:
                area = cv2.contourArea(c)
                if 200 < area < 50000:
                    x, y, bw, bh = cv2.boundingRect(c)
                    cx, cy = x + bw // 2, y + bh // 2
                    aspect = bw / max(bh, 1)
                    result["objects"].append({
                        "cx": cx, "cy": cy,
                        "w": bw, "h": bh,
                        "area": float(area),
                        "aspect": round(aspect, 2),
                    })

            # UI overlay detection (bright regions on edges)
            _, bright = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
            # Left panel
            left_bright = bright[:, :160]
            left_ct, _ = cv2.findContours(left_bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in left_ct:
                if 80 < cv2.contourArea(c) < 5000:
                    x, y, bw, bh = cv2.boundingRect(c)
                    result["ui_elements"].append({
                        "cx": x + bw // 2, "cy": y + bh // 2,
                        "side": "left", "w": bw, "h": bh,
                    })
            # Right panel
            right_bright = bright[:, w_img-200:]
            right_ct, _ = cv2.findContours(right_bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in right_ct:
                if 80 < cv2.contourArea(c) < 5000:
                    x, y, bw, bh = cv2.boundingRect(c)
                    result["ui_elements"].append({
                        "cx": w_img - 200 + x + bw // 2,
                        "cy": y + bh // 2,
                        "side": "right", "w": bw, "h": bh,
                    })

        except Exception as e:
            logger.debug(f"Gameplay scene detection failed: {e}")

        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _match_one_signature(
        self, screen: np.ndarray, sig: Dict[str, Any], w_img: int, h_img: int
    ) -> List[ElementInfo]:
        """Match a single color signature."""
        results = []
        lower = sig.get("lower", [0, 0, 0])
        upper = sig.get("upper", [180, 255, 255])
        min_area = sig.get("min_area", self._default_min_area)
        min_contours = sig.get("min_contours", self._default_min_contours)
        roi = sig.get("roi")

        # Route 1: RecognitionEngine
        if self._engine is not None:
            try:
                ok, detail = self._engine.recognize(screen, {
                    "type": "ColorMatch",
                    "roi": roi or [0, 0, w_img, h_img],
                    "lower": lower,
                    "upper": upper,
                    "min_area": min_area,
                    "min_contours": min_contours,
                })
                if ok and detail:
                    for i, (cx, cy) in enumerate(detail.get("centers", [])):
                        results.append(ElementInfo(
                            element_type="region",
                            label=f"color_region_{i}",
                            bbox=(
                            max(0.0, (cx - 20) / w_img),
                            max(0.0, (cy - 20) / h_img),
                            min(1.0, (cx + 20) / w_img),
                            min(1.0, (cy + 20) / h_img),
                        ),
                            center=(cx / w_img, cy / h_img),
                            confidence=0.7,
                            source="color",
                            action="unknown",
                            metadata={
                                "method": "RecognitionEngine",
                                "contours": detail.get("contours", 0),
                                "lower": lower,
                                "upper": upper,
                                "total_area": detail.get("total_area", 0),
                            },
                        ))
                    return results
            except Exception:
                pass

        # Route 2: Direct OpenCV
        try:
            x_off, y_off = 0, 0
            if roi:
                rx, ry, rw, rh = roi
                img_crop = screen[ry:ry + rh, rx:rx + rw]
                x_off, y_off = rx, ry
            else:
                img_crop = screen

            hsv = cv2.cvtColor(img_crop, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            valid = [c for c in contours if cv2.contourArea(c) >= min_area]
            if len(valid) >= min_contours:
                for c in valid:
                    x, y, bw, bh = cv2.boundingRect(c)
                    cx = x + x_off + bw // 2
                    cy = y + y_off + bh // 2
                    results.append(ElementInfo(
                        element_type="region",
                        label="color_region",
                        bbox=((x + x_off) / w_img, (y + y_off) / h_img,
                              (x + x_off + bw) / w_img, (y + y_off + bh) / h_img),
                        center=(cx / w_img, cy / h_img),
                        confidence=0.7,
                        source="color",
                        action="unknown",
                        metadata={
                            "method": "OpenCV",
                            "lower": lower,
                            "upper": upper,
                            "area": float(cv2.contourArea(c)),
                        },
                    ))
        except Exception as e:
            logger.debug(f"Color matching failed: {e}")

        return results
