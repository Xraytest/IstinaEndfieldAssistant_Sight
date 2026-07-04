from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from core.foundation.logger import get_logger
from core.foundation.paths import get_project_root
from .map_data_loader import MapDataLoader


@dataclass
class MapPosition:
    map_id: str
    level_id: str
    tile_class: str
    grid_cell: Optional[str]
    center_x: float
    center_y: float
    confidence: float
    raw_class_id: int


# Known minimap regions in scrcpy 1280x720 coordinate space
# These are approximate: top-left of the minimap in the game UI
_FALLBACK_MINIMAP_BBOX = (925, 15, 1250, 340)


class MinimapLocator:
    ONNX_AVAILABLE: bool
    _data: MapDataLoader
    _session = None
    _classes: List[str]
    _input_name: str
    _output_name: str

    def __init__(self, data_loader: MapDataLoader):
        self._data = data_loader
        self._logger = get_logger(__name__)
        self._session = None
        self._classes = []
        self._input_name = "images"
        self._output_name = "output0"

    def _load_onnx(self) -> bool:
        if self._session is not None:
            return True

        try:
            import onnxruntime as ort
        except ImportError:
            self._logger.warning("onnxruntime not available, minimap classification disabled")
            return False

        model_path = (
            Path(self._data._maaend_root)
            / "resource" / "model" / "map" / "cls.onnx"
        )
        if not model_path.exists():
            self._logger.warning("cls.onnx not found: %s", model_path)
            return False

        cls_path = model_path.with_name("cls.json")
        if cls_path.exists():
            try:
                import json
                with open(cls_path, "r", encoding="utf-8") as f:
                    cls_data = json.load(f)
                self._classes = cls_data.get("classes", [])
                self._input_name = cls_data.get("input_name", "images")
                self._output_name = cls_data.get("output_name", "output0")
            except Exception as exc:
                self._logger.warning("failed to load cls.json: %s", exc)

        try:
            self._session = ort.InferenceSession(
                str(model_path),
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            self._logger.info("minimap ONNX model loaded: %s", model_path.name)
            return True
        except Exception as exc:
            self._logger.warning("failed to load ONNX model: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Crop minimap from frame
    # ------------------------------------------------------------------

    def crop_minimap(self, frame: np.ndarray) -> Optional[np.ndarray]:
        h, w = frame.shape[:2]
        bbox = self._find_minimap_bbox(frame, w, h)
        if bbox is None:
            return None
        x1, y1, x2, y2 = bbox
        x1 = max(0, min(x1, w))
        y1 = max(0, min(y1, h))
        x2 = max(x1 + 10, min(x2, w))
        y2 = max(y1 + 10, min(y2, h))
        return frame[y1:y2, x1:x2]

    def _find_minimap_bbox(
        self, frame: np.ndarray, fw: int, fh: int,
    ) -> Optional[Tuple[int, int, int, int]]:
        scale_x = fw / 1280.0
        scale_y = fh / 720.0
        fx1 = int(_FALLBACK_MINIMAP_BBOX[0] * scale_x)
        fy1 = int(_FALLBACK_MINIMAP_BBOX[1] * scale_y)
        fx2 = int(_FALLBACK_MINIMAP_BBOX[2] * scale_x)
        fy2 = int(_FALLBACK_MINIMAP_BBOX[3] * scale_y)
        return (fx1, fy1, fx2, fy2)

    # ------------------------------------------------------------------
    # Classify minimap tile
    # ------------------------------------------------------------------

    def classify(self, minimap: np.ndarray) -> Optional[MapPosition]:
        if self._session is None:
            if not self._load_onnx():
                return None

        if minimap is None or minimap.size == 0:
            return None

        try:
            resized = cv2.resize(minimap, (128, 128))
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            normalized = rgb.astype(np.float32) / 255.0
            input_tensor = np.expand_dims(np.transpose(normalized, (2, 0, 1)), axis=0)
            outputs = self._session.run([self._output_name], {self._input_name: input_tensor})
            probs = outputs[0][0]
            class_id = int(np.argmax(probs))
            confidence = float(probs[class_id])
        except Exception as exc:
            self._logger.warning("ONNX inference failed: %s", exc)
            return None

        tile_class = self._classes[class_id] if class_id < len(self._classes) else f"class_{class_id}"
        return self._parse_tile(tile_class, class_id, confidence)

    def _parse_tile(
        self, tile_class: str, class_id: int, confidence: float,
    ) -> Optional[MapPosition]:
        if tile_class == "None" or confidence < 0.3:
            return None

        map_id = "unknown"
        level_id = ""
        grid_cell = None
        cx = 0.0
        cy = 0.0

        if tile_class.startswith("Map01"):
            map_id = "map01"
        elif tile_class.startswith("Map02"):
            map_id = "map02"
        elif tile_class.startswith("Dung01"):
            map_id = "dung01"
        elif tile_class.startswith("Base01"):
            map_id = "base01"
        elif tile_class.startswith("OMV"):
            map_id = "map01"

        if "Tier" in tile_class:
            parts = tile_class.split("Tier")
            if len(parts) == 2:
                tier_str = parts[1]
                grid_data = self._data.load_grid_tiers()
                for gk, gc in grid_data.items():
                    for item_hash, tier_id in gc.items.items():
                        if tier_id.endswith(f"tier_{tier_str}"):
                            grid_cell = gk
                            cx, cy = gc.center
                            break
                    if grid_cell:
                        break
                if tile_class.startswith("Map01Lv"):
                    level_id = tile_class[5:11].lower()
                elif tile_class.startswith("Map02Lv"):
                    level_id = tile_class[5:11].lower()
        elif "Base" in tile_class and "__r" in tile_class:
            import re
            m = re.search(r"__r(\d+)_c(\d+)", tile_class)
            if m:
                row, col = int(m.group(1)), int(m.group(2))
                layout = self._data.get_layout(map_id)
                if layout:
                    cx = col * layout.tile_w + layout.tile_w / 2
                    cy = row * layout.tile_h + layout.tile_h / 2

        return MapPosition(
            map_id=map_id,
            level_id=level_id,
            tile_class=tile_class,
            grid_cell=grid_cell,
            center_x=cx,
            center_y=cy,
            confidence=confidence,
            raw_class_id=class_id,
        )

    def locate(self, frame: np.ndarray) -> Optional[MapPosition]:
        minimap = self.crop_minimap(frame)
        if minimap is None:
            return None
        return self.classify(minimap)
