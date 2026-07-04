from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.foundation.logger import get_logger
from core.foundation.paths import get_project_root


@dataclass
class MapLevel:
    x: int
    y: int
    width: int
    height: int


@dataclass
class MapLayout:
    base_map: str
    canvas_width: int
    canvas_height: int
    tile_w: int
    tile_h: int
    levels: Dict[str, MapLevel]


@dataclass
class GridCell:
    center: Tuple[float, float]
    lb: Tuple[float, float]
    rt: Tuple[float, float]
    items: Dict[str, str]


@dataclass
class MapInfo:
    name: str
    label: str
    scene_node: str
    bbox: Optional[Tuple[int, int, int, int]]


_LAYOUT_FILES = {
    "base01": "base01_layout.json",
    "map01": "map01_layout.json",
    "map02": "map02_layout.json",
}

_MAP_LABELS = {
    "map01": "ValleyIV",
    "map02": "Wuling",
    "base01": "Dijiang",
}

_ZONE_MAP = {
    "map01": "ValleyIV_Base",
    "map02": "Wuling_Base",
    "base01": "Dijiang_Base",
}


class MapDataLoader:
    _maaend_root: Path
    _layouts: Dict[str, MapLayout]
    _grid_tiers: Dict[str, GridCell]
    _bbox_data: Dict[str, Tuple[int, int, int, int]]
    _scene_map: Dict[str, str]

    def __init__(self, maaend_root: Optional[str] = None):
        self._maaend_root = Path(maaend_root) if maaend_root else (get_project_root() / "3rd-part" / "maaend")
        self._logger = get_logger(__name__)
        self._layouts = {}
        self._grid_tiers = {}
        self._bbox_data = {}
        self._scene_map = {}

    # ------------------------------------------------------------------
    # Map Layouts
    # ------------------------------------------------------------------

    def load_layout(self, map_name: str) -> Optional[MapLayout]:
        if map_name in self._layouts:
            return self._layouts[map_name]

        filename = _LAYOUT_FILES.get(map_name)
        if not filename:
            self._logger.warning("unknown map layout: %s", map_name)
            return None

        path = self._maaend_root / "data" / "ZmdMap" / filename
        if not path.exists():
            self._logger.warning("layout file not found: %s", path)
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as exc:
            self._logger.warning("failed to load layout %s: %s", map_name, exc)
            return None

        levels = {}
        for lid, lv in raw.get("levels", {}).items():
            levels[lid] = MapLevel(x=lv["x"], y=lv["y"], width=lv["width"], height=lv["height"])

        layout = MapLayout(
            base_map=raw.get("base_map", map_name),
            canvas_width=raw.get("canvas_width", 0),
            canvas_height=raw.get("canvas_height", 0),
            tile_w=raw.get("tile_w", 600),
            tile_h=raw.get("tile_h", 600),
            levels=levels,
        )
        self._layouts[map_name] = layout
        return layout

    def load_all_layouts(self) -> Dict[str, MapLayout]:
        for name in _LAYOUT_FILES:
            self.load_layout(name)
        return dict(self._layouts)

    def get_layout(self, map_name: str) -> Optional[MapLayout]:
        return self._layouts.get(map_name) or self.load_layout(map_name)

    # ------------------------------------------------------------------
    # Grid Tiers
    # ------------------------------------------------------------------

    def load_grid_tiers(self) -> Dict[str, GridCell]:
        if self._grid_tiers:
            return dict(self._grid_tiers)

        path = self._maaend_root / "data" / "ZmdMap" / "grid_tiers.json"
        if not path.exists():
            self._logger.warning("grid_tiers.json not found: %s", path)
            return {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as exc:
            self._logger.warning("failed to load grid_tiers: %s", exc)
            return {}

        for key, val in raw.items():
            self._grid_tiers[key] = GridCell(
                center=tuple(val["center"]),
                lb=tuple(val["lb"]),
                rt=tuple(val["rt"]),
                items=dict(val.get("items", {})),
            )
        return dict(self._grid_tiers)

    def get_grid_cell(self, key: str) -> Optional[GridCell]:
        if not self._grid_tiers:
            self.load_grid_tiers()
        return self._grid_tiers.get(key)

    # ------------------------------------------------------------------
    # Bounding Box Data (minimap crop regions)
    # ------------------------------------------------------------------

    def load_bbox_data(self) -> Dict[str, Tuple[int, int, int, int]]:
        if self._bbox_data:
            return dict(self._bbox_data)

        path = self._maaend_root / "data" / "MapTracker" / "map_bbox_data.json"
        if not path.exists():
            self._logger.warning("map_bbox_data.json not found: %s", path)
            return {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as exc:
            self._logger.warning("failed to load bbox data: %s", exc)
            return {}

        for key, val in raw.items():
            self._bbox_data[key] = tuple(val)
        return dict(self._bbox_data)

    def get_bbox(self, key: str) -> Optional[Tuple[int, int, int, int]]:
        if not self._bbox_data:
            self.load_bbox_data()
        return self._bbox_data.get(key)

    # ------------------------------------------------------------------
    # Map → Scene Manager Node mapping
    # ------------------------------------------------------------------

    def load_scene_map(self) -> Dict[str, str]:
        if self._scene_map:
            return dict(self._scene_map)

        path = self._maaend_root / "data" / "MapTracker" / "map_external_data.json"
        if not path.exists():
            self._logger.warning("map_external_data.json not found: %s", path)
            return {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as exc:
            self._logger.warning("failed to load scene map: %s", exc)
            return {}

        for key, val in raw.items():
            self._scene_map[key] = val.get("scene_manager_node", "")
        return dict(self._scene_map)

    def get_scene_node(self, level_id: str) -> Optional[str]:
        if not self._scene_map:
            self.load_scene_map()
        return self._scene_map.get(level_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_zone_id(self, map_name: str) -> str:
        return _ZONE_MAP.get(map_name, f"{map_name}_Base")

    def get_map_label(self, map_name: str) -> str:
        return _MAP_LABELS.get(map_name, map_name)

    def list_available_maps(self) -> List[Dict[str, Any]]:
        result = []
        for map_name in _LAYOUT_FILES:
            layout = self.get_layout(map_name)
            label = self.get_map_label(map_name)
            result.append({
                "name": map_name,
                "label": label,
                "zone_id": self.get_zone_id(map_name),
                "levels": list(layout.levels.keys()) if layout else [],
            })
        return result

    def list_levels_for_map(self, map_name: str) -> List[Dict[str, Any]]:
        layout = self.get_layout(map_name)
        if not layout:
            return []
        result = []
        for lid, lv in layout.levels.items():
            scene_node = self.get_scene_node(lid)
            result.append({
                "level_id": lid,
                "x": lv.x,
                "y": lv.y,
                "width": lv.width,
                "height": lv.height,
                "scene_node": scene_node or "",
            })
        return result
