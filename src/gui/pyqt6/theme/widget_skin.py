"""Dashboard widget skin definitions and helpers.

Skins are themed style sheets applied on top of the base widget frame.
Each skin keeps a consistent visual language (colors, borders, shadows,
typography) inspired by Hypergryph / Arknights visual identity.
"""
from __future__ import annotations

from gui.pyqt6.theme.widget_styles import (
    _ACCENT_GOLD,
    _BG_CARD,
    _BORDER,
    _BORDER_LIGHT,
    _FONT,
    _PRIMARY,
    _SIZE_BASE,
    _TEXT_PRIMARY,
    _TEXT_SECONDARY,
    _WARNING,
)

# ---------------------------------------------------------------------------
# Color palettes per skin
# ---------------------------------------------------------------------------
_SKINS = {
    "default": {
        "name": "Default",
        "card_bg": _BG_CARD,
        "title_color": _TEXT_PRIMARY,
        "border_color": _BORDER_LIGHT,
        "accent_color": _PRIMARY,
        "subtext_color": _TEXT_SECONDARY,
        "shadow": "0 2px 8px rgba(0,0,0,0.25)",
        "radius": "6px",
        "header_bg": "transparent",
        "header_separator": _BORDER_LIGHT,
    },
    "arknight": {
        "name": "Arknights",
        "card_bg": "rgba(18, 20, 26, 0.95)",
        "title_color": "#d0d4de",
        "border_color": "rgba(120, 126, 147, 0.35)",
        "accent_color": "#7a8aa0",
        "subtext_color": "#8b919e",
        "shadow": "0 4px 14px rgba(0,0,0,0.45)",
        "radius": "4px",
        "header_bg": "rgba(90, 100, 120, 0.18)",
        "header_separator": "rgba(120, 126, 147, 0.35)",
    },
    "endfield": {
        "name": "Endfield",
        "card_bg": "rgba(10, 14, 20, 0.96)",
        "title_color": "#cfefff",
        "border_color": "rgba(24, 209, 255, 0.25)",
        "accent_color": "#18d1ff",
        "subtext_color": "#8fb8c8",
        "shadow": "0 6px 18px rgba(24, 209, 255, 0.12)",
        "radius": "8px",
        "header_bg": "rgba(24, 209, 255, 0.08)",
        "header_separator": "rgba(24, 209, 255, 0.25)",
    },
    "rhodes_island": {
        "name": "Rhodes Island",
        "card_bg": "rgba(22, 24, 30, 0.97)",
        "title_color": "#f2f3f5",
        "border_color": "rgba(255, 255, 255, 0.08)",
        "accent_color": "#ffffff",
        "subtext_color": "#a6a9b0",
        "shadow": "0 2px 10px rgba(0,0,0,0.55)",
        "radius": "0px",
        "header_bg": "rgba(255, 255, 255, 0.04)",
        "header_separator": "rgba(255, 255, 255, 0.08)",
    },
    "operator": {
        "name": "Operator",
        "card_bg": "rgba(28, 24, 20, 0.96)",
        "title_color": "#e6dfd3",
        "border_color": "rgba(180, 150, 100, 0.30)",
        "accent_color": _ACCENT_GOLD,
        "subtext_color": "#b0a594",
        "shadow": "0 6px 20px rgba(0,0,0,0.50)",
        "radius": "10px",
        "header_bg": "rgba(180, 150, 100, 0.12)",
        "header_separator": "rgba(180, 150, 100, 0.30)",
    },
}

# Active skin for the whole dashboard. Updated by DashboardPage when the
# user changes skin preference.
ACTIVE_SKIN: str = "default"


def set_skin(skin_id: str) -> None:
    global ACTIVE_SKIN
    ACTIVE_SKIN = skin_id if skin_id in _SKINS else "default"


def current_skin() -> dict:
    return _SKINS.get(ACTIVE_SKIN, _SKINS["default"])


def skin_ids() -> list[str]:
    return list(_SKINS.keys())


def skin_options() -> dict[str, str]:
    return {k: v["name"] for k, v in _SKINS.items()}


def widget_skin_stylesheet() -> str:
    skin = current_skin()
    return (
        f"#metricCard {{"
        f" background-color: {skin['card_bg']};"
        f" border: 1px solid {skin['border_color']};"
        f" border-radius: {skin['radius']};"
        f" box-shadow: {skin['shadow']};"
        f"}}"
        f"#metricCard:hover {{"
        f" border-color: {skin['accent_color']};"
        f"}}"
    )


def widget_header_stylesheet() -> str:
    skin = current_skin()
    return (
        f"QLabel[property=\"title\"] {{"
        f" color: {skin['title_color']};"
        f" font-size: 13px; font-family: '{_FONT}';"
        f" font-weight: bold; letter-spacing: 1px;"
        f" background-color: {skin['header_bg']};"
        f" padding: 6px 8px;"
        f" border-bottom: 1px solid {skin['header_separator']};"
        f"}}"
    )


def apply_skin_to(widget) -> None:
    """Apply current dashboard skin to a DashboardWidget instance."""
    try:
        widget.setStyleSheet(widget_skin_stylesheet())
        for child in widget.findChildren(type(widget).__bases__[0]):
            pass
    except Exception:
        pass
