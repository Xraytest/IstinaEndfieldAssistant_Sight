from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.foundation.logger import get_logger
from core.foundation.paths import get_project_root


@dataclass
class Entity:
    id: int
    template_name: str
    key_name: str
    raw_location: Tuple[float, float, float]
    pixel_location: Tuple[float, float]
    map_location: Tuple[float, float]
    category: str
    map_id: str
    map_level_id: str

    @classmethod
    def from_raw(cls, raw: Dict[str, Any], category: str, map_id: str, map_level_id: str) -> Entity:
        rl = raw.get("raw_location", [0, 0, 0])
        pl = raw.get("pixel_location", [0, 0])
        ml = raw.get("map_location", [0, 0])
        return cls(
            id=raw.get("id", 0),
            template_name=raw.get("template_name", ""),
            key_name=raw.get("key_name", ""),
            raw_location=(float(rl[0]), float(rl[1]), float(rl[2])) if len(rl) >= 3 else (0.0, 0.0, 0.0),
            pixel_location=(float(pl[0]), float(pl[1])) if len(pl) >= 2 else (0.0, 0.0),
            map_location=(float(ml[0]), float(ml[1])) if len(ml) >= 2 else (0.0, 0.0),
            category=category,
            map_id=map_id,
            map_level_id=map_level_id,
        )

    def distance_to(self, x: float, y: float) -> float:
        dx = self.map_location[0] - x
        dy = self.map_location[1] - y
        return (dx * dx + dy * dy) ** 0.5


class EntityDatabase:
    _maaend_root: Path
    _entities: List[Entity]
    _by_id: Dict[int, Entity]
    _by_name: Dict[str, List[Entity]]
    _by_category: Dict[str, List[Entity]]
    _by_map: Dict[str, List[Entity]]
    _by_level: Dict[str, List[Entity]]
    _loaded: bool

    def __init__(self, maaend_root: Optional[str] = None):
        self._maaend_root = Path(maaend_root) if maaend_root else (get_project_root() / "3rd-part" / "maaend")
        self._logger = get_logger(__name__)
        self._entities = []
        self._by_id = {}
        self._by_name = {}
        self._by_category = {}
        self._by_map = {}
        self._by_level = {}
        self._loaded = False

    def load(self) -> bool:
        if self._loaded:
            return True

        path = self._maaend_root / "data" / "ZmdMap" / "maaend_entities.json"
        if not path.exists():
            self._logger.warning("maaend_entities.json not found: %s", path)
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw_maps = json.load(f)
        except Exception as exc:
            self._logger.warning("failed to load maaend_entities.json: %s", exc)
            return False

        for map_entry in raw_maps:
            map_id = map_entry.get("map_id", "")
            for level_entry in map_entry.get("levels", []):
                level_id = level_entry.get("map_level_id", "")
                for cat_entry in level_entry.get("categories", []):
                    category = cat_entry.get("category", "unknown")
                    for raw_entity in cat_entry.get("data", []):
                        entity = Entity.from_raw(raw_entity, category, map_id, level_id)
                        self._entities.append(entity)
                        self._by_id[entity.id] = entity
                        self._by_name.setdefault(entity.key_name, []).append(entity)
                        self._by_category.setdefault(entity.category, []).append(entity)
                        self._by_map.setdefault(entity.map_id, []).append(entity)
                        level_key = f"{map_id}_{level_id}"
                        self._by_level.setdefault(level_key, []).append(entity)

        self._loaded = True
        self._logger.info(
            "entity db loaded: %d entities across %d maps",
            len(self._entities),
            len(raw_maps),
        )
        return True

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    @property
    def loaded(self) -> bool:
        return self._loaded

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def find_by_id(self, entity_id: int) -> Optional[Entity]:
        self._ensure_loaded()
        return self._by_id.get(entity_id)

    def find_by_name(self, name: str, exact: bool = False, limit: int = 50) -> List[Entity]:
        self._ensure_loaded()
        if exact:
            return list(self._by_name.get(name, []))[:limit]
        pattern = re.compile(re.escape(name), re.IGNORECASE)
        results = []
        for key, entities in self._by_name.items():
            if pattern.search(key):
                results.extend(entities)
                if len(results) >= limit:
                    break
        return results[:limit]

    def find_by_category(self, category: str, limit: int = 100) -> List[Entity]:
        self._ensure_loaded()
        return list(self._by_category.get(category, []))[:limit]

    def find_by_map(self, map_id: str, limit: int = 100) -> List[Entity]:
        self._ensure_loaded()
        return list(self._by_map.get(map_id, []))[:limit]

    def find_by_level(self, map_id: str, level_id: str, limit: int = 100) -> List[Entity]:
        self._ensure_loaded()
        key = f"{map_id}_{level_id}"
        return list(self._by_level.get(key, []))[:limit]

    def find_nearby(
        self, map_id: str, level_id: str, x: float, y: float,
        radius: float = 50.0, category: Optional[str] = None, limit: int = 20,
    ) -> List[Entity]:
        self._ensure_loaded()
        level_key = f"{map_id}_{level_id}"
        candidates = self._by_level.get(level_key, [])
        if category:
            candidates = [e for e in candidates if e.category == category]

        scored = [(e.distance_to(x, y), e) for e in candidates if e.distance_to(x, y) <= radius]
        scored.sort(key=lambda p: p[0])
        return [e for _, e in scored[:limit]]

    # ------------------------------------------------------------------
    # Info methods
    # ------------------------------------------------------------------

    def get_categories(self) -> Set[str]:
        self._ensure_loaded()
        return set(self._by_category.keys())

    def get_map_ids(self) -> Set[str]:
        self._ensure_loaded()
        return set(self._by_map.keys())

    def count(self) -> int:
        self._ensure_loaded()
        return len(self._entities)

    def stats(self) -> Dict[str, Any]:
        self._ensure_loaded()
        return {
            "total_entities": len(self._entities),
            "categories": sorted(self.get_categories()),
            "maps": sorted(self.get_map_ids()),
            "by_category": {k: len(v) for k, v in sorted(self._by_category.items())},
            "by_map": {k: len(v) for k, v in sorted(self._by_map.items())},
        }
