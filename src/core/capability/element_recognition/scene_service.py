from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from core.foundation.paths import get_cache_subdir

from .backends.scene_geometry import SceneGeometryAnalyzer
from .element_info import ElementInfo, PageInfo, SceneAnalysis3D
from .recognizer import EndfieldElementRecognizer

logger = logging.getLogger(__name__)


class SceneUnderstandingService:
    """High-level scene understanding service.

    The default 3D path uses a local geometry analyzer.
    """

    def __init__(
        self,
        catalog_path: str = "",
        enable_yolo: bool = False,
        template_threshold: float = 0.7,
        maaend_runtime=None,
    ):
        if not catalog_path:
            catalog_path = str(get_cache_subdir("analysis") / "page_catalog.json")

        self._catalog_path = catalog_path
        self._threshold = template_threshold
        self.current_page: str = "unknown"
        self.current_confidence: float = 0.0
        self.page_history: List[Dict[str, Any]] = []
        self._last_screen = None
        self._geometry_analyzer = SceneGeometryAnalyzer()

        self.recognizer = EndfieldElementRecognizer(
            catalog_path=catalog_path,
            enable_yolo=enable_yolo,
            maaend_runtime=maaend_runtime,
        )

    def identify(self, screen: np.ndarray) -> PageInfo:
        if screen is None or screen.size == 0:
            return PageInfo(page_type="unknown", confidence=0.0)

        page = None
        try:
            page = self.recognizer.recognize(screen)
        except Exception as exc:
            logger.warning("场景识别异常: %s", exc)
            return PageInfo(page_type="unknown", confidence=0.0)

        self._last_screen = screen
        self.current_page = page.page_type
        self.current_confidence = page.confidence

        self.page_history.append(
            {
                "page_type": page.page_type,
                "confidence": page.confidence,
                "timestamp": time.time(),
                "element_count": len(page.elements),
            }
        )
        if len(self.page_history) > 100:
            self.page_history.pop(0)

        return page

    def identify_from_bytes(self, image_bytes: bytes) -> PageInfo:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        screen = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if screen is None:
            return PageInfo(page_type="unknown", confidence=0.0)
        return self.identify(screen)

    def verify(self, screen: np.ndarray, expected_page: str) -> Tuple[bool, PageInfo]:
        page = self.identify(screen)
        is_match = page.page_type == expected_page and page.confidence >= 0.5
        return is_match, page

    def verify_by_key_elements(
        self, screen: np.ndarray, expected_templates: List[str]
    ) -> Tuple[bool, List[ElementInfo]]:
        elems = self.recognizer.recognize_templates(screen, names=expected_templates)
        found_names = {e.label for e in elems}
        all_found = all(any(t in fn for fn in found_names) for t in expected_templates)
        return all_found, elems

    def analyze_elements(
        self,
        screen: np.ndarray,
        enable_template: bool = True,
        enable_ocr: bool = True,
        enable_color: bool = True,
    ) -> PageInfo:
        return self.recognizer.recognize(
            screen,
            enable={
                "template": enable_template,
                "ocr": enable_ocr,
                "color": enable_color,
                "yolo": False,
            },
        )

    def get_scene_context(self) -> Dict[str, Any]:
        return {
            "current_page": self.current_page,
            "current_confidence": self.current_confidence,
            "history_count": len(self.page_history),
            "recent_history": self.page_history[-10:] if self.page_history else [],
        }

    def get_dominant_page(self, window: int = 5) -> Tuple[str, float]:
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
        return self.recognizer.get_available_templates()

    def analyze_scene_3d(
        self,
        screen: np.ndarray,
        prompt: str = "",
    ) -> Optional[SceneAnalysis3D]:
        return self._geometry_analyzer.analyze(screen, prompt=prompt)

    def get_page_info(self, page_type: str) -> Optional[Dict[str, Any]]:
        return self.recognizer.get_page_signature(page_type)

    def reset_context(self) -> None:
        self.current_page = "unknown"
        self.current_confidence = 0.0
        self.page_history.clear()
        self._last_screen = None
