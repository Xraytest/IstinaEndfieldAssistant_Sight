"""
YOLO 后端 — 包装 YOLO11n 通用物体检测

将 YOLO 检测结果统一输出为 ElementInfo 列表。
仅在需要时 lazy-load 模型。
"""
from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

from ..element_info import ElementInfo

logger = logging.getLogger(__name__)


class YOLOBackend:
    """YOLO11n general object detection backend.

    Detects generic objects (person, cell phone, etc.) that may be
    relevant for context understanding. Not game-specific.
    """

    def __init__(self, model_path: str = "yolo11n.pt", conf_threshold: float = 0.25):
        self._model_path = model_path
        self._conf_threshold = conf_threshold
        self._model = None

    def recognize(
        self,
        screen: np.ndarray,
        class_filter: Optional[List[str]] = None,
        max_results: int = 30,
    ) -> List[ElementInfo]:
        """Run YOLO detection on screen.

        Args:
            screen: BGR image
            class_filter: only return these class names (None = all)
            max_results: maximum number of results

        Returns:
            List[ElementInfo] with source="yolo"
        """
        if not self._is_available():
            return []

        try:
            results = self._model(screen, verbose=False)
        except Exception as e:
            logger.debug(f"YOLO detection failed: {e}")
            return []

        h_img, w_img = screen.shape[:2]
        elements: List[ElementInfo] = []

        for r in results:
            boxes = getattr(r, "boxes", None)
            if boxes is None:
                continue
            names = getattr(r, "names", {})

            for box in boxes:
                conf = float(box.conf[0])
                if conf < self._conf_threshold:
                    continue

                cls_id = int(box.cls[0])
                cls_name = names.get(cls_id, str(cls_id))

                # 可选过滤
                if class_filter and cls_name not in class_filter:
                    continue

                xyxy = box.xyxy[0].tolist()
                x1, y1, x2, y2 = xyxy
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)

                elements.append(ElementInfo(
                    element_type="yolo_object",
                    label=cls_name,
                    bbox=(x1 / w_img, y1 / h_img, x2 / w_img, y2 / h_img),
                    center=(cx / w_img, cy / h_img),
                    confidence=round(conf, 2),
                    source="yolo",
                    action="unknown",
                    metadata={
                        "class_id": cls_id,
                        "raw_x1": int(x1), "raw_y1": int(y1),
                        "raw_x2": int(x2), "raw_y2": int(y2),
                    },
                ))

        return elements[:max_results]

    def is_loaded(self) -> bool:
        return self._model is not None

    def _is_available(self) -> bool:
        if self._model is not None:
            return True
        try:
            from ultralytics import YOLO
            self._model = YOLO(self._model_path)
            logger.info(f"YOLO model loaded: {self._model_path}")
            return True
        except Exception as e:
            logger.debug(f"YOLO not available: {e}")
            return False
