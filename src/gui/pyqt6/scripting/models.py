"""Data models for script recording and playback."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ActionRecord:
    """A single recorded action."""
    widget_type: str
    object_name: str
    action_type: str  # "click" | "text_changed" | "combo_changed"
    value: Optional[Dict[str, Any]] = None  # {"x": float, "y": float, "button": int} for click, {"text": str} for text

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionRecord:
        return cls(**data)


@dataclass
class Script:
    """A recorded script containing multiple actions."""
    name: str
    actions: List[ActionRecord] = field(default_factory=list)
    description: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["actions"] = [a.to_dict() for a in self.actions]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Script:
        actions = [ActionRecord.from_dict(a) for a in data.get("actions", [])]
        return cls(
            name=data.get("name", ""),
            actions=actions,
            description=data.get("description", ""),
            created_at=data.get("created_at", ""),
        )

    def save(self, directory: Path) -> Path:
        """Save script to a JSON file in the given directory."""
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.name}.json"
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> Script:
        """Load a script from a JSON file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)
