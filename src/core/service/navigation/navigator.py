from __future__ import annotations

from typing import Any, Dict, Optional

import cv2
import numpy as np

from core.capability.llm import LlmClient
from core.foundation.logger import get_logger
from core.service.maa_end.runtime import MaaEndRuntime

from .entity_db import Entity, EntityDatabase
from .map_data_loader import MapDataLoader
from .minimap_locator import MapPosition, MinimapLocator
from .vlm_walk_navigator import VlmWalkConfig, VlmWalkNavigator


class Navigator:
    """High-level navigation orchestrator.

    Uses scrcpy frames for localization and MaaEnd pipeline for movement execution.
    """

    _maaend: MaaEndRuntime
    _screenshot_fn: Any
    _data: MapDataLoader
    _entities: EntityDatabase
    _locator: MinimapLocator

    def __init__(
        self,
        maaend: MaaEndRuntime,
        screenshot_fn=None,
    ):
        self._maaend = maaend
        self._screenshot_fn = screenshot_fn
        self._logger = get_logger(__name__)
        self._data = MapDataLoader()
        self._entities = EntityDatabase()
        self._locator = MinimapLocator(self._data)
        # NAV-03: 加载实体库失败时记录 warning 并继续使用空库，避免中断构造
        if not self._entities.load():
            self._logger.warning("entity database failed to load; navigation will use an empty entity set")

    def set_screenshot_fn(self, fn) -> None:
        self._screenshot_fn = fn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def to_coords(
        self,
        map_name: str,
        x: float,
        y: float,
        level_id: Optional[str] = None,
        zone_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Navigate to a specific coordinate on a map.

        Args:
            map_name: e.g. "map01", "map02"
            x, y: target map projection coordinates
            level_id: specific level to navigate to (e.g. "lv001")
            zone_override: if provided, use this zone_id instead of auto-detecting

        Returns:
            result dict with status and details
        """
        self._logger.info("nav to coords: map=%s x=%.1f y=%.1f", map_name, x, y)

        if map_name == "unknown":
            return {"status": "error", "message": "cannot navigate to unknown map"}

        frame = self._get_frame()
        if frame is None:
            return {"status": "error", "message": "no screenshot available"}

        current_pos = self._locator.locate(frame)
        current_level = self._resolve_current_level(current_pos, frame)

        level_to_nav = level_id or current_level
        if not level_to_nav:
            return {"status": "error", "message": "cannot determine target level"}

        # NAV-02: 当前地图未知时不做强制传送，避免误传送
        if (
            current_pos
            and current_pos.map_id not in ("unknown", "")
            and current_pos.map_id != map_name
        ):
            self._logger.info("different map, teleporting first")
            teleport_ok = self._teleport_to(map_name, level_to_nav)
            if not teleport_ok:
                return {"status": "error", "message": "failed to teleport to map"}

        zone_id = zone_override or self._data.get_zone_id(map_name)
        result = self._navigate_navmesh(zone_id, map_name, level_to_nav, x, y)
        return result

    def to_entity(self, entity_name: str, limit: int = 10) -> Dict[str, Any]:
        """Navigate to a named entity (resource, POI, etc.).

        Args:
            entity_name: name or partial name of the entity
            limit: max candidates to try

        Returns:
            result dict
        """
        matches = self._entities.find_by_name(entity_name, exact=False, limit=limit)
        if not matches:
            self._logger.warning("entity not found: %s", entity_name)
            return {"status": "error", "message": f"entity '{entity_name}' not found"}

        if len(matches) == 1:
            return self._nav_to_entity(matches[0])

        self._logger.info("multiple matches for '%s': %d", entity_name, len(matches))
        for m in matches[:limit]:
            ok = self._nav_to_entity(m)
            if ok.get("status") == "success":
                return ok
        return {"status": "error", "message": f"failed to navigate to '{entity_name}'"}

    def where_am_i(self) -> Dict[str, Any]:
        """Determine current player location from scrcpy frame."""
        frame = self._get_frame()
        if frame is None:
            return {"status": "error", "message": "no screenshot available"}

        pos = self._locator.locate(frame)
        if pos is None:
            return {"status": "unknown", "message": "cannot determine position"}

        nearby = []
        if pos.map_id != "unknown" and pos.level_id:
            nearby = self._entities.find_nearby(
                pos.map_id, pos.level_id,
                pos.center_x, pos.center_y,
                radius=100.0, limit=10,
            )

        return {
            "status": "success",
            "map_id": pos.map_id,
            "level_id": pos.level_id,
            "tile_class": pos.tile_class,
            "grid_cell": pos.grid_cell,
            "center_x": pos.center_x,
            "center_y": pos.center_y,
            "confidence": pos.confidence,
            "nearby_entities": [
                {
                    "name": e.key_name,
                    "category": e.category,
                    "distance": round(e.distance_to(pos.center_x, pos.center_y), 1),
                    "map_x": round(e.map_location[0], 1),
                    "map_y": round(e.map_location[1], 1),
                }
                for e in nearby
            ],
        }

    def list_entities(
        self,
        category: Optional[str] = None,
        map_name: Optional[str] = None,
        name_filter: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List available entities in the database."""
        self._entities.load()
        if name_filter:
            matches = self._entities.find_by_name(name_filter, limit=limit)
            # XC-2: name_filter 存在时仍保留 category/map_name 过滤，用 and 组合
            if category:
                matches = [e for e in matches if e.category == category]
            if map_name:
                matches = [e for e in matches if e.map_id == map_name]
        elif category and map_name:
            all_in_map = self._entities.find_by_map(map_name, limit=10000)
            matches = [e for e in all_in_map if e.category == category][:limit]
        elif category:
            matches = self._entities.find_by_category(category, limit=limit)
        elif map_name:
            matches = self._entities.find_by_map(map_name, limit=limit)
        else:
            return {
                "status": "success",
                "categories": sorted(self._entities.get_categories()),
                "maps": sorted(self._entities.get_map_ids()),
                "total": self._entities.count(),
                "hint": "use category= or map_name= to filter",
            }

        return {
            "status": "success",
            "count": len(matches),
            "entities": [
                {
                    "id": e.id,
                    "name": e.key_name,
                    "template": e.template_name,
                    "category": e.category,
                    "map_id": e.map_id,
                    "level_id": e.map_level_id,
                    "map_x": round(e.map_location[0], 1),
                    "map_y": round(e.map_location[1], 1),
                }
                for e in matches
            ],
        }

    def list_maps(self) -> Dict[str, Any]:
        """List available maps and their levels."""
        maps = self._data.list_available_maps()
        result = []
        for m in maps:
            levels = self._data.list_levels_for_map(m["name"])
            result.append({**m, "levels": levels})
        return {"status": "success", "maps": result}

    # ------------------------------------------------------------------
    # VLM-driven walk navigation
    # ------------------------------------------------------------------

    def to_coords_vlm(
        self,
        map_name: str,
        x: float,
        y: float,
        level_id: Optional[str] = None,
        zone_override: Optional[str] = None,
        llm_client: Optional[LlmClient] = None,
        max_steps: int = 40,
        keyevent_fn: Optional[callable] = None,
        step_timeout: Optional[float] = None,
        target_radius: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Navigate to (x, y) using VLM-driven walking instead of blind-walk waypoints.

        Falls back to NAVMESH if VLM client is unavailable or stuck detected.

        Args:
            step_timeout: 单次 VLM 推理超时（秒），None 则使用 VlmWalkConfig 默认值。
            target_radius: 到达判定半径，None 则使用 VlmWalkConfig 默认值。
        """
        self._logger.info("nav-vlm to coords: map=%s x=%.1f y=%.1f", map_name, x, y)

        if llm_client is None:
            self._logger.warning("no LLM client supplied, falling back to navmesh")
            zone_id = zone_override or self._data.get_zone_id(map_name)
            return self._navigate_navmesh(zone_id, map_name, level_id or "lv001", x, y)

        frame = self._get_frame()
        if frame is None:
            return {"status": "error", "message": "no screenshot available"}

        # Teleport if on different map
        current_pos = self._locator.locate(frame)
        current_level = self._resolve_current_level(current_pos, frame)
        if current_pos and current_pos.map_id not in (map_name, "unknown") and current_pos.map_id != "":
            self._logger.info("different map (%s), teleporting first", current_pos.map_id)
            target_level = level_id or current_level or "lv001"
            self._teleport_to(map_name, target_level)

        # Build input function from keyevent_fn or default fallback (logging only)
        def default_input(key: str, duration: Optional[float]) -> None:
            self._logger.info("[vlm-input] key=%s duration=%s (no keyevent_fn provided)", key, duration)

        input_fn = keyevent_fn or default_input

        cfg_kwargs: Dict[str, Any] = {"max_steps": max_steps}
        if step_timeout is not None:
            cfg_kwargs["vlm_call_timeout_s"] = float(step_timeout)
            cfg_kwargs["step_timeout_s"] = float(step_timeout)
        if target_radius is not None:
            cfg_kwargs["target_radius"] = float(target_radius)
        walk_cfg = VlmWalkConfig(**cfg_kwargs)
        walker = VlmWalkNavigator(
            llm_client=llm_client,
            screenshot_fn=self._screenshot_fn,
            input_fn=input_fn,
            locator=self._locator,
            data_loader=self._data,
            config=walk_cfg,
        )

        walk_result = walker.walk_to(
            map_name=map_name,
            target_x=x,
            target_y=y,
            level_id=level_id,
        )

        # If VLM walk failed or stuck, fall back to navmesh
        if walk_result.get("status") != "success" and walk_cfg.fallback_to_navmesh:
            self._logger.info("VLM walk did not converge, falling back to navmesh")
            zone_id = zone_override or self._data.get_zone_id(map_name)
            target_level = level_id or current_level or "lv001"
            navmesh_result = self._navigate_navmesh(
                zone_id, map_name, target_level, x, y,
            )
            navmesh_result["vlm_walk"] = walk_result.get("history", [])
            return navmesh_result

        return walk_result

    def to_entity_vlm(
        self,
        entity_name: str,
        llm_client: Optional[LlmClient] = None,
        max_steps: int = 40,
        keyevent_fn: Optional[callable] = None,
        limit: int = 10,
        step_timeout: Optional[float] = None,
        target_radius: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Navigate to a named entity using VLM-driven walking."""
        matches = self._entities.find_by_name(entity_name, exact=False, limit=limit)
        if not matches:
            self._logger.warning("entity not found: %s", entity_name)
            return {"status": "error", "message": f"entity '{entity_name}' not found"}

        for entity in matches[:limit]:
            result = self.to_coords_vlm(
                map_name=entity.map_id,
                x=entity.map_location[0],
                y=entity.map_location[1],
                level_id=entity.map_level_id,
                llm_client=llm_client,
                max_steps=max_steps,
                keyevent_fn=keyevent_fn,
                step_timeout=step_timeout,
                target_radius=target_radius,
            )
            if result.get("status") == "success":
                return result
        return {"status": "error", "message": f"failed to reach '{entity_name}' via VLM"}
    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_frame(self) -> Optional[np.ndarray]:
        if self._screenshot_fn is None:
            return None
        try:
            data = self._screenshot_fn()
            if data is None:
                return None
            arr = np.frombuffer(data, dtype=np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception as exc:
            self._logger.warning("screenshot failed: %s", exc)
            return None

    def _resolve_current_level(
        self, pos: Optional[MapPosition], frame: Optional[np.ndarray],
    ) -> Optional[str]:
        if pos is not None and pos.level_id is not None:
            return pos.level_id
        return None

    def _teleport_to(self, map_name: str, level_id: str) -> bool:
        level_key = f"{map_name}_{level_id}"
        scene_node = self._data.get_scene_node(level_key)
        if scene_node:
            self._logger.info("teleporting via scene node: %s", scene_node)
            return self._maaend.run_task(scene_node)
        self._logger.warning("no scene node for %s, trying map-level teleport", level_key)
        for base_level in ["lv001", "lv002", "lv003"]:
            alt_key = f"{map_name}_{base_level}"
            alt_node = self._data.get_scene_node(alt_key)
            if alt_node:
                self._logger.info("teleporting via alt scene node: %s", alt_node)
                return self._maaend.run_task(alt_node)
        self._logger.warning("no teleport available for %s", level_key)
        return False

    def _navigate_navmesh(
        self, zone_id: str, map_name: str, level_id: str,
        target_x: float, target_y: float,
    ) -> Dict[str, Any]:
        entry = "NavCustomEntry"
        override = {
            entry: {
                "recognition": "DirectHit",
                "action": {
                    "type": "Custom",
                    "param": {
                        "custom_action": "MapNavigateAction",
                        "custom_action_param": {
                            "path": [{
                                "action": "NAVMESH",
                                "target": [target_x, target_y],
                                "zone_id": zone_id,
                            }],
                        },
                    },
                },
                "next": ["NavCustomDone"],
            },
            "NavCustomDone": {
                "recognition": "DirectHit",
                "action": "DoNothing",
                "next": [],
            },
        }
        self._logger.info(
            "executing navmesh navigation: zone=%s target=(%.1f, %.1f)",
            zone_id, target_x, target_y,
        )
        ok = self._maaend.run_pipeline(entry, override)
        return {
            "status": "success" if ok else "error",
            "action": "navmesh",
            "zone_id": zone_id,
            "target_x": target_x,
            "target_y": target_y,
            "map_name": map_name,
            "level_id": level_id,
        }

    def _nav_to_entity(self, entity: Entity) -> Dict[str, Any]:
        return self.to_coords(
            map_name=entity.map_id,
            x=entity.map_location[0],
            y=entity.map_location[1],
            level_id=entity.map_level_id,
        )
