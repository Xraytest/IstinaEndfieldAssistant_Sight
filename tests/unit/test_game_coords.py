"""Tests for game_coords.py — pure data module, fully offline-testable."""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pytest
from core.game_coords import (
    Coords, SCREEN_WIDTH, SCREEN_HEIGHT, ADB_WIDTH, ADB_HEIGHT,
    TOP_BAR_Y_RANGE, OVERLAY_ROI, TOP_BAR_BUTTONS,
    NAVIGATION_MAP, OVERLAY_KEYWORDS, PAGE_TYPE_KEYWORDS,
    xy_str, lookup_button, coords_for_model,
)


class TestCoords:
    """Coordinate constants validation."""

    def test_all_coords_are_valid_tuples(self):
        """Every Coords attribute should be a tuple of 2 ints within screen bounds."""
        coord_items = {
            k: v for k, v in vars(Coords).items()
            if not k.startswith("_") and not callable(v)
        }
        assert len(coord_items) >= 15, f"Expected >=15 coords, got {len(coord_items)}"

        for name, value in coord_items.items():
            if not isinstance(value, tuple):
                continue
            assert len(value) == 2, f"{name}: expected 2 elements, got {len(value)}"
            x, y = value
            assert isinstance(x, int) and isinstance(y, int), f"{name}: coords must be ints"
            assert 0 <= x <= SCREEN_WIDTH, f"{name}: x={x} out of [0, {SCREEN_WIDTH}]"
            assert 0 <= y <= SCREEN_HEIGHT, f"{name}: y={y} out of [0, {SCREEN_HEIGHT}]"

    def test_known_coordinates(self):
        """Verify specific known coordinate values."""
        assert Coords.tasks_button == (570, 22)
        assert Coords.claim_all == (1035, 323)
        assert Coords.mode_switch == (75, 21)
        assert Coords.exit_confirm == (793, 478)
        assert Coords.exit_cancel == (556, 478)
        assert Coords.title_click == (640, 360)

    def test_claim_alternatives(self):
        """claim_alternatives should be a list of valid coordinate tuples."""
        assert isinstance(Coords.claim_alternatives, list)
        assert len(Coords.claim_alternatives) >= 2
        for coord in Coords.claim_alternatives:
            assert isinstance(coord, tuple)
            assert len(coord) == 2


class TestConstants:
    """Screen and layout constants."""

    def test_screen_dimensions(self):
        assert SCREEN_WIDTH == 1280
        assert SCREEN_HEIGHT == 720
        assert ADB_WIDTH == 1080
        assert ADB_HEIGHT == 1920

    def test_top_bar_y_range(self):
        assert len(TOP_BAR_Y_RANGE) == 2
        assert TOP_BAR_Y_RANGE[0] == 10
        assert TOP_BAR_Y_RANGE[1] == 80

    def test_overlay_roi(self):
        assert OVERLAY_ROI["x_start"] == 950
        assert OVERLAY_ROI["x_end"] == 1280
        assert OVERLAY_ROI["y_start"] == 60
        assert OVERLAY_ROI["y_end"] == 700

    def test_top_bar_buttons(self):
        """TOP_BAR_BUTTONS must have at least the essential entries."""
        essential = ["tasks", "event", "back", "shop", "signin", "settings"]
        for key in essential:
            assert key in TOP_BAR_BUTTONS, f"Missing top-bar button: {key}"
            entry = TOP_BAR_BUTTONS[key]
            assert "x_range" in entry
            assert "y_range" in entry

    def test_navigation_map(self):
        """NAVIGATION_MAP must have essential nav targets."""
        essential = ["title", "loading", "exit_dialog", "mode_exploration", "mode_industry"]
        for key in essential:
            assert key in NAVIGATION_MAP, f"Missing nav target: {key}"
            entry = NAVIGATION_MAP[key]
            assert "action" in entry
            assert entry["action"] in ("click", "swipe", "keyevent", "wait", "claim", "switch_mode", "switch_mode_or_back")

    def test_overlay_keywords(self):
        assert len(OVERLAY_KEYWORDS) >= 10

    def test_page_type_keywords(self):
        assert isinstance(PAGE_TYPE_KEYWORDS, dict)
        assert len(PAGE_TYPE_KEYWORDS) >= 3


class TestHelpers:
    """Helper functions."""

    def test_xy_str(self):
        assert xy_str((570, 22)) == "(570, 22)"
        assert xy_str((0, 0)) == "(0, 0)"
        assert xy_str((1280, 720)) == "(1280, 720)"

    def test_lookup_button_exact(self):
        result = lookup_button("任务")
        assert result is not None

    def test_lookup_button_fuzzy(self):
        result = lookup_button("shop")
        assert result is not None

    def test_lookup_button_missing(self):
        """lookup_button falls back to tasks_button for unknown labels."""
        result = lookup_button("nonexistent_button_xyz")
        assert result == Coords.tasks_button  # default fallback

    def test_coords_for_model_exploration(self):
        coords = coords_for_model("exploration_deep")
        assert isinstance(coords, dict)
        assert "tasks_button" in coords

    def test_coords_for_model_unknown(self):
        coords = coords_for_model("nonexistent_model")
        assert isinstance(coords, dict)
        # Should fall back to defaults
        assert "tasks_button" in coords
