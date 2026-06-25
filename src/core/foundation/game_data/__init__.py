"""游戏数据模块"""

from ..game_coords import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    ADB_WIDTH,
    ADB_HEIGHT,
    TOP_BAR_Y_RANGE,
    OVERLAY_ROI,
    OVERLAY_ROI_TUPLE,
    Coords,
    TOP_BAR,
    TOP_BAR_BUTTONS,
    OVERLAY_KEYWORDS,
    KNOWN_COORDS,
    MODE_SWITCH_BUTTON,
    NAVIGATION_MAP,
    PAGE_TYPE_KEYWORDS,
    EXIT_DIALOG,
    SIGNIN_PAGE,
    EVENT_CENTER,
    CLAIM_KEYWORDS,
    xy_str,
    lookup_button,
    coords_for_model,
)

__all__ = [
    "SCREEN_WIDTH", "SCREEN_HEIGHT", "ADB_WIDTH", "ADB_HEIGHT",
    "TOP_BAR_Y_RANGE", "OVERLAY_ROI", "OVERLAY_ROI_TUPLE",
    "Coords", "TOP_BAR", "TOP_BAR_BUTTONS",
    "OVERLAY_KEYWORDS", "KNOWN_COORDS", "MODE_SWITCH_BUTTON",
    "NAVIGATION_MAP", "PAGE_TYPE_KEYWORDS",
    "EXIT_DIALOG", "SIGNIN_PAGE", "EVENT_CENTER", "CLAIM_KEYWORDS",
    "xy_str", "lookup_button", "coords_for_model",
]