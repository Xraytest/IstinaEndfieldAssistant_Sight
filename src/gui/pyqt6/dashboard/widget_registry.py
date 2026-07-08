"""Dashboard widget registry and discovery system."""
from __future__ import annotations

from typing import Any, Dict, Optional


class WidgetRegistry:
    """Registry of available dashboard widgets."""

    def __init__(self) -> None:
        self._widgets: Dict[str, Dict[str, Any]] = {}

    def register(self, widget_id: str, name: str, description: str, widget_class: Any) -> None:
        self._widgets[widget_id] = {
            "id": widget_id,
            "name": name,
            "description": description,
            "class": widget_class,
        }

    def get_available_widgets(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._widgets)

    def get_widget(self, widget_id: str) -> Optional[Dict[str, Any]]:
        return self._widgets.get(widget_id)

    def is_registered(self, widget_id: str) -> bool:
        return widget_id in self._widgets


# Global registry instance
_registry: Optional[WidgetRegistry] = None


def get_widget_registry() -> WidgetRegistry:
    global _registry
    if _registry is None:
        _registry = WidgetRegistry()
    return _registry
