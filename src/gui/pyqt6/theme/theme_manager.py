"""Endfield industrial sci-fi theme for PyQt6.

Dark industrial black + terminal cyan primary color + CRT micro-glow borders.
Design language references ak.hypergryph.com / endfield.hypergryph.com.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# Theme definitions
# ---------------------------------------------------------------------------

THEMES: Dict[str, Dict[str, Any]] = {
    "endfield": {
        "name": "Endfield",
        "description": "工业科幻 - 终端青 + 暗黑底色",
        "colors": {
            "bg_primary": "#0a0a0f",
            "bg_secondary": "#101016",
            "bg_tertiary": "#14141a",
            "bg_card": "rgba(18, 18, 26, 0.92)",
            "bg_elevated": "rgba(26, 26, 38, 0.90)",
            "canvas_bg": "#050508",
            "surface": "#0a0a0f",
            "surface_dim": "#07070b",
            "surface_bright": "rgba(30, 30, 45, 0.85)",
            "surface_container": "rgba(16, 16, 26, 0.88)",
            "surface_container_low": "rgba(12, 12, 20, 0.93)",
            "surface_container_lowest": "#050508",
            "surface_container_high": "rgba(22, 22, 36, 0.85)",
            "surface_container_highest": "rgba(28, 28, 46, 0.82)",
            "log_bg": "rgba(5, 5, 8, 0.95)",
            "text_primary": "#e8e8ee",
            "text_secondary": "#9090a8",
            "text_tertiary": "#606080",
            "text_muted": "#404058",
            "text_disabled": "#282840",
            "on_surface": "#e8e8ee",
            "on_surface_variant": "#9090a8",
            "primary": "#18d1ff",
            "primary_dark": "#06bbff",
            "primary_darker": "#0099cc",
            "primary_light": "#6ae5ff",
            "primary_lighter": "#a3f0ff",
            "primary_hover": "#3ddbff",
            "primary_container": "rgba(24, 209, 255, 0.12)",
            "primary_light_container": "rgba(24, 209, 255, 0.12)",
            "primary_dark_container": "rgba(0, 153, 204, 0.25)",
            "on_primary": "#000000",
            "on_primary_container": "#c0f0ff",
            "info": "#18d1ff",
            "info_dark": "#0099cc",
            "info_light": "#6ae5ff",
            "info_container": "rgba(24, 209, 255, 0.12)",
            "on_info": "#000000",
            "success": "#00ffa2",
            "success_dark": "#00cc81",
            "success_light": "#4dffbc",
            "success_container": "rgba(0, 255, 162, 0.12)",
            "on_success": "#000000",
            "tertiary": "#00ffa2",
            "tertiary_dark": "#00cc81",
            "tertiary_light": "#4dffbc",
            "tertiary_container": "rgba(0, 255, 162, 0.12)",
            "on_tertiary": "#000000",
            "on_tertiary_container": "#ccffee",
            "danger": "#ff3355",
            "danger_dark": "#cc0022",
            "danger_light": "#ff6680",
            "danger_container": "rgba(255, 51, 85, 0.12)",
            "on_danger": "#ffffff",
            "warning": "#fffa00",
            "warning_dark": "#e6de01",
            "warning_light": "#fffb4d",
            "warning_container": "rgba(255, 250, 0, 0.12)",
            "on_warning": "#000000",
            "accent_gold": "#fffa00",
            "accent_gold_dark": "#e6de01",
            "accent_gold_light": "#fffb4d",
            "accent_gold_glow": "rgba(255, 250, 0, 0.2)",
            "secondary": "#ff1aac",
            "secondary_dark": "#cc0088",
            "secondary_light": "#ff4dc0",
            "secondary_container": "rgba(255, 26, 172, 0.12)",
            "on_secondary": "#000000",
            "on_secondary_container": "#ffccee",
            "inverse_surface": "#e0e0e8",
            "inverse_primary": "#0099cc",
            "inverse_on_surface": "#0a0a0f",
            "border_color": "rgba(24, 209, 255, 0.15)",
            "border_light": "rgba(24, 209, 255, 0.08)",
            "border_glow": "rgba(255, 250, 0, 0.08)",
            "outline": "rgba(24, 209, 255, 0.20)",
            "outline_variant": "rgba(24, 209, 255, 0.12)",
            "divider_color": "rgba(24, 209, 255, 0.10)",
            "hover_bg": "rgba(24, 209, 255, 0.08)",
            "selection_bg": "rgba(24, 209, 255, 0.25)",
            "selection_border": "#18d1ff",
            "shadow": "rgba(0, 0, 0, 0.5)",
            "shadow_light": "rgba(0, 0, 0, 0.3)",
            "shadow_cyan": "rgba(24, 209, 255, 0.06)",
        },
    },
    "arknight": {
        "name": "Arknight",
        "description": "经典暗黑 - 低调蓝灰 + 高对比",
        "colors": {
            "bg_primary": "#0b0d10",
            "bg_secondary": "#111318",
            "bg_tertiary": "#16181f",
            "bg_card": "rgba(22, 24, 32, 0.94)",
            "bg_elevated": "rgba(30, 32, 42, 0.92)",
            "canvas_bg": "#06070a",
            "surface": "#0b0d10",
            "surface_dim": "#07080b",
            "surface_bright": "rgba(34, 36, 48, 0.88)",
            "surface_container": "rgba(18, 20, 28, 0.90)",
            "surface_container_low": "rgba(14, 16, 22, 0.94)",
            "surface_container_lowest": "#06070a",
            "surface_container_high": "rgba(24, 26, 36, 0.88)",
            "surface_container_highest": "rgba(32, 34, 46, 0.85)",
            "log_bg": "rgba(6, 7, 10, 0.96)",
            "text_primary": "#e4e6f0",
            "text_secondary": "#8a8ea4",
            "text_tertiary": "#5a5e74",
            "text_muted": "#3a3e54",
            "text_disabled": "#262a40",
            "on_surface": "#e4e6f0",
            "on_surface_variant": "#8a8ea4",
            "primary": "#5c7cfa",
            "primary_dark": "#4c6ef5",
            "primary_darker": "#3b5de7",
            "primary_light": "#82a5ff",
            "primary_lighter": "#a8c0ff",
            "primary_hover": "#7b9bff",
            "primary_container": "rgba(92, 124, 250, 0.12)",
            "primary_light_container": "rgba(92, 124, 250, 0.10)",
            "primary_dark_container": "rgba(59, 93, 231, 0.20)",
            "on_primary": "#ffffff",
            "on_primary_container": "#d0d8ff",
            "info": "#5c7cfa",
            "info_dark": "#4c6ef5",
            "info_light": "#82a5ff",
            "info_container": "rgba(92, 124, 250, 0.10)",
            "on_info": "#ffffff",
            "success": "#2f9e44",
            "success_dark": "#268538",
            "success_light": "#5cb85c",
            "success_container": "rgba(47, 158, 68, 0.10)",
            "on_success": "#ffffff",
            "tertiary": "#5c7cfa",
            "tertiary_dark": "#4c6ef5",
            "tertiary_light": "#82a5ff",
            "tertiary_container": "rgba(92, 124, 250, 0.10)",
            "on_tertiary": "#ffffff",
            "on_tertiary_container": "#d0d8ff",
            "danger": "#e03131",
            "danger_dark": "#c92a2a",
            "danger_light": "#ff6b6b",
            "danger_container": "rgba(224, 49, 49, 0.10)",
            "on_danger": "#ffffff",
            "warning": "#f08c00",
            "warning_dark": "#d97706",
            "warning_light": "#f59f00",
            "warning_container": "rgba(240, 140, 0, 0.10)",
            "on_warning": "#000000",
            "accent_gold": "#f08c00",
            "accent_gold_dark": "#d97706",
            "accent_gold_light": "#f59f00",
            "accent_gold_glow": "rgba(240, 140, 0, 0.15)",
            "secondary": "#be4bdb",
            "secondary_dark": "#9c36b5",
            "secondary_light": "#da77f2",
            "secondary_container": "rgba(190, 75, 219, 0.10)",
            "on_secondary": "#ffffff",
            "on_secondary_container": "#f3d9ff",
            "inverse_surface": "#e4e6f0",
            "inverse_primary": "#4c6ef5",
            "inverse_on_surface": "#0b0d10",
            "border_color": "rgba(92, 124, 250, 0.18)",
            "border_light": "rgba(92, 124, 250, 0.10)",
            "border_glow": "rgba(240, 140, 0, 0.06)",
            "outline": "rgba(92, 124, 250, 0.25)",
            "outline_variant": "rgba(92, 124, 250, 0.15)",
            "divider_color": "rgba(92, 124, 250, 0.12)",
            "hover_bg": "rgba(92, 124, 250, 0.08)",
            "selection_bg": "rgba(92, 124, 250, 0.22)",
            "selection_border": "#5c7cfa",
            "shadow": "rgba(0, 0, 0, 0.55)",
            "shadow_light": "rgba(0, 0, 0, 0.35)",
            "shadow_cyan": "rgba(92, 124, 250, 0.05)",
        },
    },
    "minimal": {
        "name": "Minimal",
        "description": "极简白昼 - 浅色高对比 + 低饱和",
        "colors": {
            "bg_primary": "#f8f9fa",
            "bg_secondary": "#ffffff",
            "bg_tertiary": "#f1f3f5",
            "bg_card": "rgba(255, 255, 255, 0.96)",
            "bg_elevated": "rgba(255, 255, 255, 0.98)",
            "canvas_bg": "#f1f3f5",
            "surface": "#f8f9fa",
            "surface_dim": "#e9ecef",
            "surface_bright": "#ffffff",
            "surface_container": "rgba(255, 255, 255, 0.95)",
            "surface_container_low": "rgba(248, 249, 250, 0.98)",
            "surface_container_lowest": "#f8f9fa",
            "surface_container_high": "rgba(255, 255, 255, 0.92)",
            "surface_container_highest": "rgba(255, 255, 255, 0.88)",
            "log_bg": "rgba(248, 249, 250, 0.98)",
            "text_primary": "#1a1d28",
            "text_secondary": "#5a5f72",
            "text_tertiary": "#8a8fa2",
            "text_muted": "#a8adbe",
            "text_disabled": "#c8ccd8",
            "on_surface": "#1a1d28",
            "on_surface_variant": "#5a5f72",
            "primary": "#228be6",
            "primary_dark": "#1c7ed6",
            "primary_darker": "#1864ab",
            "primary_light": "#4dabf7",
            "primary_lighter": "#74c0fc",
            "primary_hover": "#339af0",
            "primary_container": "rgba(34, 139, 230, 0.08)",
            "primary_light_container": "rgba(34, 139, 230, 0.06)",
            "primary_dark_container": "rgba(24, 100, 171, 0.12)",
            "on_primary": "#ffffff",
            "on_primary_container": "#e7f5ff",
            "info": "#228be6",
            "info_dark": "#1c7ed6",
            "info_light": "#4dabf7",
            "info_container": "rgba(34, 139, 230, 0.08)",
            "on_info": "#ffffff",
            "success": "#2f9e44",
            "success_dark": "#268538",
            "success_light": "#5cb85c",
            "success_container": "rgba(47, 158, 68, 0.08)",
            "on_success": "#ffffff",
            "tertiary": "#5c7cfa",
            "tertiary_dark": "#4c6ef5",
            "tertiary_light": "#82a5ff",
            "tertiary_container": "rgba(92, 124, 250, 0.08)",
            "on_tertiary": "#ffffff",
            "on_tertiary_container": "#e7f5ff",
            "danger": "#e03131",
            "danger_dark": "#c92a2a",
            "danger_light": "#ff6b6b",
            "danger_container": "rgba(224, 49, 49, 0.08)",
            "on_danger": "#ffffff",
            "warning": "#f08c00",
            "warning_dark": "#d97706",
            "warning_light": "#f59f00",
            "warning_container": "rgba(240, 140, 0, 0.08)",
            "on_warning": "#000000",
            "accent_gold": "#f08c00",
            "accent_gold_dark": "#d97706",
            "accent_gold_light": "#f59f00",
            "accent_gold_glow": "rgba(240, 140, 0, 0.12)",
            "secondary": "#be4bdb",
            "secondary_dark": "#9c36b5",
            "secondary_light": "#da77f2",
            "secondary_container": "rgba(190, 75, 219, 0.08)",
            "on_secondary": "#ffffff",
            "on_secondary_container": "#f3d9ff",
            "inverse_surface": "#1a1d28",
            "inverse_primary": "#4dabf7",
            "inverse_on_surface": "#f8f9fa",
            "border_color": "rgba(0, 0, 0, 0.10)",
            "border_light": "rgba(0, 0, 0, 0.06)",
            "border_glow": "rgba(240, 140, 0, 0.04)",
            "outline": "rgba(0, 0, 0, 0.15)",
            "outline_variant": "rgba(0, 0, 0, 0.10)",
            "divider_color": "rgba(0, 0, 0, 0.08)",
            "hover_bg": "rgba(0, 0, 0, 0.04)",
            "selection_bg": "rgba(34, 139, 230, 0.15)",
            "selection_border": "#228be6",
            "shadow": "rgba(0, 0, 0, 0.08)",
            "shadow_light": "rgba(0, 0, 0, 0.04)",
            "shadow_cyan": "rgba(34, 139, 230, 0.04)",
        },
    },
}

# ---------------------------------------------------------------------------
# Color palette (legacy - kept for backward compatibility)
# ---------------------------------------------------------------------------
COLORS: Dict[str, str] = THEMES["endfield"]["colors"]

FONTS: Dict[str, str] = {
    "family": "Microsoft YaHei UI",
    "family_display": "Microsoft YaHei UI",
    "family_fallback": "Segoe UI",
    "family_mono": "Consolas",
}

FONT_SIZES: Dict[str, int] = {
    "size_base": 12, "size_small": 11, "size_large": 13, "size_xlarge": 15,
    "size_header": 20, "size_title": 17,
    "display_large": 42, "display_medium": 34, "display_small": 26,
    "headline_large": 24, "headline_medium": 20, "headline_small": 17,
    "title_large": 15, "title_medium": 13, "title_small": 12,
    "body_large": 13, "body_medium": 12, "body_small": 11,
    "label_large": 12, "label_medium": 11, "label_small": 10,
}

FONT_WEIGHTS: Dict[str, int] = {
    "thin": 100, "extra_light": 200, "light": 300, "regular": 400,
    "medium": 500, "semi_bold": 600, "bold": 700, "extra_bold": 800, "black": 900,
}

SPACING_UNIT: int = 4
SPACING: Dict[str, int] = {
    "xxxs": 2, "xxs": 4, "xs": 6, "sm": 8, "md": 12, "lg": 16, "xl": 20, "xxl": 24, "xxxl": 32,
    "none": 0, "margin_xs": 4, "margin_sm": 8, "margin_md": 12, "margin_lg": 16, "margin_xl": 20,
    "padding_xs": 4, "padding_sm": 8, "padding_md": 12, "padding_lg": 16, "padding_xl": 20,
    "section": 16, "container": 20, "card_padding": 20, "dialog_padding": 24,
    "component": 8, "icon_text": 8, "list_item_padding": 10,
    "button_padding_h": 24, "button_padding_v": 10, "button_padding_h_small": 8, "button_padding_v_small": 2,
    "input_padding_h": 14, "input_padding_v": 10,
}

ELEVATION: Dict[str, int] = {
    "level_0": 0, "level_1": 1, "level_2": 2, "level_3": 3, "level_4": 4, "level_5": 5,
    "card": 1, "card_hover": 2, "button": 0, "button_floating": 3, "menu": 2, "dialog": 3, "drawer": 4, "modal": 5,
}

CORNER_RADIUS: Dict[str, int] = {
    "none": 0, "xs": 2, "sm": 4, "md": 6, "lg": 8, "xl": 12, "xxl": 16, "full": 9999,
    "badge": 9999, "button": 4, "button_sm": 4, "button_lg": 6, "card": 6, "card_lg": 8,
    "chip": 4, "dialog": 8, "fab": 8, "input": 4, "input_filled": 4, "input_outlined": 4,
    "menu": 4, "snackbar": 4, "tooltip": 3,
}

TIER_COLORS: Dict[str, str] = {
    "free": "#404058", "plus": "#fffa00", "prime": "#18d1ff", "pro": "#ff1aac",
}

ANIMATION_CONFIG: Dict[str, Any] = {
    "enabled": True, "fade_enabled": True, "slide_enabled": True,
    "scale_enabled": True, "hover_enabled": True,
    "duration_fast": 120, "duration_normal": 200, "duration_slow": 350,
    "easing_curve": "OutCubic",
}

DURATION: Dict[str, int] = {
    "instant": 0, "fast": 100, "normal": 180, "slow": 300, "slower": 400,
    "hover": 120, "press": 60, "fade": 180, "expand": 200, "slide": 250,
    "dialog": 250, "snackbar": 200,
}

_STYLESHEET: Optional[str] = None
_FONT_RESOURCES_LOADED = False
_CURRENT_THEME: str = "endfield"


# ---------------------------------------------------------------------------
# Stylesheet builder
# ---------------------------------------------------------------------------
def _build_stylesheet(theme_colors: Dict[str, str]) -> str:
    c = theme_colors
    return r"""/* ============================================================================
 * Endfield industrial sci-fi style - PyQt6 QSS
 * ============================================================================ */

/* Global */
QWidget { font-family: 'Microsoft YaHei UI'; font-size: 12px; color: """ + c["text_primary"] + """; background-color: """ + c["bg_primary"] + """; }
QMainWindow {
    background-color: """ + c["bg_primary"] + """;
    background-image: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(11,15,25,0.98),
        stop:0.45 rgba(7,8,13,1),
        stop:1 rgba(6,8,12,1));
}
QWidget[ui-mode="compact"] QLabel[variant="hero"] { font-size: 22px; }
QWidget[ui-mode="compact"] QLabel[variant="header"] { font-size: 17px; }
QWidget[ui-mode="compact"] QPushButton { min-height: 26px; padding: 2px 6px; }
QWidget[ui-mode="compact"] QLineEdit,
QWidget[ui-mode="compact"] QComboBox,
QWidget[ui-mode="compact"] QSpinBox { min-height: 26px; padding: 4px 8px; }
QWidget[ui-mode="compact"] QGroupBox { font-size: 12px; }
QWidget[ui-mode="compact"] QListWidget::item { padding: 4px 6px; }
QWidget[ui-mode="compact"] QTabBar::tab { padding: 6px 14px; min-width: 64px; }
QWidget[ui-mode="compact"] QTextEdit,
QWidget[ui-mode="compact"] QPlainTextEdit { padding: 6px; }

/* Buttons */
QPushButton { background-color: rgba(13,19,28,0.92); color: """ + c["text_primary"] + """; border: 1px solid rgba(64,132,162,0.32); border-radius: 2px; padding: 2px 10px; font-size: 12px; font-weight: 500; min-height: 28px; }
QPushButton:hover { background-color: """ + c["hover_bg"] + """; border-color: """ + c["primary_light"] + """80; }
QPushButton:pressed { background-color: rgba(18,27,38,0.92); border-color: """ + c["primary"] + """80; }
QPushButton:disabled { background-color: """ + c["surface_container"] + """; color: """ + c["text_disabled"] + """; border-color: """ + c["border_light"] + """; }
QPushButton[variant="primary"] { background-color: """ + c["primary_container"] + """; color: """ + c["primary_light"] + """; border: 1px solid """ + c["primary"] + """60; }
QPushButton[variant="primary"]:hover { background-color: """ + c["primary_container"] + """66; }
QPushButton[variant="primary"]:pressed { background-color: """ + c["primary_container"] + """88; }
QPushButton[variant="secondary"] { background-color: rgba(255,255,255,0.02); color: """ + c["text_primary"] + """; border: 1px solid rgba(88,98,121,0.48); }
QPushButton[variant="secondary"]:hover { background-color: """ + c["hover_bg"] + """; border-color: """ + c["primary_light"] + """60; }
QPushButton[variant="text"] { background-color: transparent; color: """ + c["text_secondary"] + """; border: none; }
QPushButton[variant="text"]:hover { background-color: """ + c["hover_bg"] + """; }
QPushButton[variant="danger"] { background-color: transparent; color: """ + c["danger"] + """; border: 1px solid """ + c["danger"] + """66; }
QPushButton[variant="danger"]:hover { background-color: """ + c["danger_container"] + """; border-color: """ + c["danger_light"] + """; }

/* Labels */
QLabel { color: """ + c["text_primary"] + """; background-color: transparent; border: none; }
QLabel[variant="header"] { font-size: 20px; font-weight: 600; color: """ + c["text_primary"] + """; }
QLabel[variant="title"] { font-size: 17px; font-weight: 600; color: """ + c["text_primary"] + """; }
QLabel[variant="hero"] { font-size: 28px; font-weight: 700; color: """ + c["on_surface"] + """; letter-spacing: 1px; }
QLabel[variant="secondary"] { color: """ + c["text_secondary"] + """; }
QLabel[variant="muted"] { color: """ + c["text_muted"] + """; }
QLabel[variant="terminal"] { font-family: 'Microsoft YaHei UI'; color: """ + c["primary"] + """; font-size: 12px; }
QLabel[variant="eyebrow"] { color: """ + c["primary_light"] + """; font-size: 11px; font-weight: 600; letter-spacing: 2px; }
QLabel[variant="accent"] { color: """ + c["accent_gold"] + """; }
QLabel[variant="success"] { color: """ + c["success"] + """; }
QLabel[variant="danger"] { color: """ + c["danger"] + """; }

/* Inputs */
QLineEdit { background-color: """ + c["surface_container"] + """; color: """ + c["text_primary"] + """; border: 1px solid """ + c["border_color"] + """; border-radius: 4px; padding: 6px 10px; font-size: 12px; min-height: 28px; }
QLineEdit:hover { border-color: """ + c["primary"] + """40; }
QLineEdit:focus { border-color: """ + c["primary"] + """; }
QLineEdit:disabled { background-color: """ + c["surface_container"] + """; color: """ + c["text_disabled"] + """; }

QComboBox { background-color: """ + c["surface_container"] + """; color: """ + c["text_primary"] + """; border: 1px solid """ + c["border_color"] + """; border-radius: 4px; padding: 6px 10px; font-size: 12px; min-height: 28px; }
QComboBox:hover { border-color: """ + c["primary"] + """40; }
QComboBox:focus { border-color: """ + c["primary"] + """; }
QComboBox::drop-down { border: none; width: 28px; padding-right: 8px; }
QComboBox::down-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid """ + c["text_secondary"] + """; width: 0; height: 0; }
QComboBox QAbstractItemView { background-color: """ + c["surface_container"] + """; color: """ + c["text_primary"] + """; border: 1px solid """ + c["border_color"] + """; border-radius: 4px; selection-background-color: """ + c["selection_bg"] + """; selection-color: """ + c["on_primary"] + """; padding: 2px; }

QSpinBox { background-color: """ + c["surface_container"] + """; color: """ + c["text_primary"] + """; border: 1px solid """ + c["border_color"] + """; border-radius: 4px; padding: 4px 8px; font-size: 12px; min-height: 24px; }
QSpinBox:hover { border-color: """ + c["primary"] + """40; }
QSpinBox:focus { border-color: """ + c["primary"] + """; }
QSpinBox::up-button, QSpinBox::down-button { background-color: """ + c["surface_container_lowest"] + """; border: none; width: 24px; subcontrol-position: right; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background-color: """ + c["hover_bg"] + """; }
QSpinBox::up-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-bottom: 6px solid """ + c["text_primary"] + """; width: 0; height: 0; }
QSpinBox::down-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid """ + c["text_primary"] + """; width: 0; height: 0; }

/* Checkbox */
QCheckBox { color: """ + c["text_primary"] + """; spacing: 8px; font-size: 12px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 3px; border: 1px solid """ + c["border_color"] + """; background-color: transparent; }
QCheckBox::indicator:hover { border-color: """ + c["primary"] + """; }
QCheckBox::indicator:checked { background-color: """ + c["primary"] + """; border-color: """ + c["primary"] + """; }
QCheckBox::indicator:disabled { border-color: """ + c["text_disabled"] + """; background-color: """ + c["surface_container"] + """; }

/* Tabs */
QTabWidget::pane { background-color: """ + c["bg_primary"] + """; border: 1px solid """ + c["border_color"] + """; border-radius: 4px; top: -1px; }
QTabBar::tab { background-color: transparent; color: """ + c["text_secondary"] + """; border: none; border-bottom: 2px solid transparent; padding: 8px 20px; font-size: 12px; min-width: 80px; }
QTabBar::tab:hover { background-color: """ + c["hover_bg"] + """; }
QTabBar::tab:selected { color: """ + c["primary"] + """; border-bottom: 2px solid """ + c["primary"] + """; }

/* Splitter */
QSplitter::handle { background-color: """ + c["border_light"] + """; }
QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical { height: 1px; }

/* Scrollbar */
QScrollBar:vertical { background-color: transparent; width: 4px; border-radius: 2px; margin: 0; }
QScrollBar::handle:vertical { background-color: """ + c["primary"] + """18; border-radius: 2px; min-height: 20px; margin: 0px; }
QScrollBar::handle:vertical:hover { background-color: """ + c["primary"] + """38; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; background-color: transparent; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background-color: transparent; }
QScrollBar:horizontal { background-color: transparent; height: 4px; border-radius: 2px; margin: 0; }
QScrollBar::handle:horizontal { background-color: """ + c["primary"] + """18; border-radius: 2px; min-width: 20px; margin: 0px; }
QScrollBar::handle:horizontal:hover { background-color: """ + c["primary"] + """38; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; background-color: transparent; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background-color: transparent; }

/* List */
QListWidget { background-color: """ + c["surface_container"] + """; color: """ + c["text_primary"] + """; border: 1px solid """ + c["border_color"] + """; border-radius: 2px; padding: 4px 6px; font-size: 12px; outline: none; }
QListWidget::item { background-color: transparent; padding: 4px 6px; border-left: 2px solid transparent; border-radius: 0; }
QListWidget::item:hover { background-color: """ + c["hover_bg"] + """; border-left: 2px solid """ + c["primary"] + """45; }
QListWidget::item:selected { background-color: """ + c["primary_container"] + """; color: """ + c["primary_light"] + """; border: 1px solid """ + c["primary"] + """50; border-left: 2px solid """ + c["primary"] + """; }
QListWidget::item:selected:!active { background-color: """ + c["primary_container"] + """cc; }

/* Tables */
QTableWidget, QTableView { background-color: """ + c["bg_primary"] + """; color: """ + c["text_primary"] + """; border: 1px solid """ + c["border_color"] + """; border-radius: 4px; gridline-color: """ + c["border_light"] + """; font-size: 12px; }
QTableWidget::item, QTableView::item { padding: 4px 6px; border: none; }
QTableWidget::item:hover, QTableView::item:hover { background-color: """ + c["hover_bg"] + """; }
QTableWidget::item:selected, QTableView::item:selected { background-color: """ + c["selection_bg"] + """; color: """ + c["on_primary"] + """; }
QHeaderView::section { background-color: """ + c["surface_container"] + """; color: """ + c["text_primary"] + """; border: none; border-bottom: 1px solid """ + c["border_color"] + """; padding: 8px; font-size: 12px; font-weight: 500; }

/* Tree */
QTreeWidget, QTreeView { background-color: """ + c["bg_primary"] + """; color: """ + c["text_primary"] + """; border: 1px solid """ + c["border_color"] + """; border-radius: 4px; font-size: 12px; }
QTreeWidget::item, QTreeView::item { padding: 10px; border-radius: 2px; }
QTreeWidget::item:hover, QTreeView::item:hover { background-color: """ + c["hover_bg"] + """; }
QTreeWidget::item:selected, QTreeView::item:selected { background-color: """ + c["selection_bg"] + """; color: """ + c["on_primary"] + """; }

/* GroupBox */
QGroupBox { background-color: """ + c["bg_card"] + """; color: """ + c["text_primary"] + """; border: 1px solid """ + c["border_color"] + """; border-radius: 6px; font-size: 12px; padding-top: 4px; margin-top: 6px; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 4px; color: """ + c["primary_light"] + """; font-weight: 600; letter-spacing: 1px; }

/* ProgressBar */
QProgressBar { background-color: """ + c["surface_container"] + """; border: none; border-radius: 9999px; height: 4px; text-align: center; color: """ + c["text_primary"] + """; }
QProgressBar::chunk { background-color: """ + c["primary"] + """; border-radius: 9999px; }

/* TextEdit */
QTextEdit, QPlainTextEdit { background-color: """ + c["log_bg"] + """; color: """ + c["text_primary"] + """; border: 1px solid """ + c["border_color"] + """; border-radius: 4px; padding: 4px 6px; font-size: 12px; font-family: 'Microsoft YaHei UI'; }
QTextEdit:focus, QPlainTextEdit:focus { border-color: """ + c["primary"] + """; }

/* Menu */
QMenu { background-color: """ + c["surface_container"] + """; color: """ + c["text_primary"] + """; border: 1px solid """ + c["border_color"] + """; border-radius: 4px; padding: 4px; }
QMenu::item { padding: 8px 20px; border-radius: 2px; }
QMenu::item:selected { background-color: """ + c["hover_bg"] + """; }
QMenu::separator { height: 1px; background-color: """ + c["divider_color"] + """; margin: 4px 8px; }

/* Tooltip */
QToolTip { background-color: """ + c["surface_bright"] + """; color: """ + c["text_primary"] + """; border: 1px solid """ + c["border_color"] + """; border-radius: 3px; padding: 8px 12px; font-size: 11px; }

/* Dialog */
QDialog { background-color: """ + c["bg_primary"] + """; border: 1px solid """ + c["border_color"] + """; }

/* StatusBar */
QStatusBar { background-color: """ + c["surface_dim"] + """; color: """ + c["text_secondary"] + """; border-top: 1px solid """ + c["border_color"] + """; font-size: 11px; }
QStatusBar::item { border: none; }

/* StackedWidget */
QStackedWidget { background-color: """ + c["bg_primary"] + """; }
QStackedWidget > QWidget { background-color: """ + c["bg_primary"] + """; }

QFrame#heroPanel, QFrame#pageHero, QFrame#settingsHero {
    background-color: """ + c["bg_elevated"] + """;
    border: 1px solid """ + c["border_color"] + """;
    border-radius: 6px;
}
QFrame#navPanel, QFrame#contentPanel, QFrame#metricCard, QFrame#controlBar {
    background-color: """ + c["bg_card"] + """;
    border: 1px solid """ + c["border_light"] + """;
    border-radius: 8px;
}
QListWidget#mainNavigation {
    background-color: transparent;
    border: none;
    padding: 0;
}
QStatusBar {
    background-color: """ + c["surface_dim"] + """;
    color: """ + c["text_secondary"] + """;
    border-top: 1px solid """ + c["border_color"] + """;
    font-size: 11px;
}

/* ScrollArea */
QScrollArea { background-color: """ + c["bg_primary"] + """; border: none; }
QScrollArea > QWidget > QWidget { background-color: """ + c["bg_primary"] + """; }

/* Separator */
QFrame[frameShape="4"] { background-color: """ + c["divider_color"] + """; max-height: 1px; border: none; }
QFrame[frameShape="5"] { background-color: """ + c["divider_color"] + """; max-width: 1px; border: none; }
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_stylesheet(theme_name: str = "endfield") -> str:
    return _build_stylesheet(THEMES.get(theme_name, THEMES["endfield"])["colors"])


class ThemeManager:
    _instance: Optional["ThemeManager"] = None

    def __new__(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def colors(self) -> Dict[str, str]: return COLORS
    @property
    def fonts(self) -> Dict[str, str]: return FONTS
    @property
    def font_sizes(self) -> Dict[str, int]: return FONT_SIZES
    @property
    def font_weights(self) -> Dict[str, int]: return FONT_WEIGHTS
    @property
    def spacing(self) -> Dict[str, int]: return SPACING
    @property
    def elevation(self) -> Dict[str, int]: return ELEVATION
    @property
    def corner_radius(self) -> Dict[str, int]: return CORNER_RADIUS
    @property
    def animation_config(self) -> Dict[str, Any]: return ANIMATION_CONFIG
    @property
    def duration(self) -> Dict[str, int]: return DURATION

    def get_color(self, name: str, default: str = "#000000") -> str:
        return COLORS.get(name, default)
    def get_font_size(self, name: str, default: int = 12) -> int:
        return FONT_SIZES.get(name, default)
    def get_font_family(self, name: str = "family") -> str:
        return FONTS.get(name, "Microsoft YaHei UI")
    def get_mono_font_family(self) -> str:
        return FONTS.get("family_mono", "Consolas")
    def get_spacing(self, name: str, default: int = 8) -> int:
        return SPACING.get(name, default)
    def get_corner_radius(self, name: str, default: int = 4) -> int:
        return CORNER_RADIUS.get(name, default)
    def get_animation_duration(self, name: str, default: int = 200) -> int:
        return DURATION.get(name, default)
    def is_animation_enabled(self) -> bool:
        return bool(ANIMATION_CONFIG.get("enabled", True))
    def set_animation_enabled(self, enabled: bool) -> None:
        ANIMATION_CONFIG["enabled"] = enabled
    def set_animation_duration(self, name: str, value: int) -> None:
        DURATION[name] = value
    def get_available_themes(self) -> list[dict]:
        return [{"id": k, **v} for k, v in THEMES.items()]
    def set_current_theme(self, theme_name: str) -> None:
        global _CURRENT_THEME, COLORS
        if theme_name in THEMES:
            _CURRENT_THEME = theme_name
            COLORS.clear()
            COLORS.update(THEMES[theme_name]["colors"])
    def get_current_theme(self) -> str:
        return _CURRENT_THEME
    def get_stylesheet(self, theme_name: Optional[str] = None) -> str:
        if theme_name is None:
            theme_name = _CURRENT_THEME
        return get_stylesheet(theme_name)
    def apply_theme(self, app: QApplication, theme_name: Optional[str] = None) -> None:
        self.set_current_theme(theme_name or _CURRENT_THEME)
        app.setStyleSheet(self.get_stylesheet())


def _get_qt_app() -> Optional[QApplication]:
    app = QApplication.instance()
    return app if isinstance(app, QApplication) else None


def ensure_app_fonts() -> str:
    global _FONT_RESOURCES_LOADED
    if _FONT_RESOURCES_LOADED:
        return FONTS["family"]

    candidate_paths = (
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
    )
    desired_family = FONTS["family"]
    fallback_family = desired_family

    for path in candidate_paths:
        if not path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if desired_family in families:
            fallback_family = desired_family
            break
        if families and fallback_family == desired_family:
            fallback_family = families[0]

    FONTS["family"] = fallback_family
    FONTS["family_display"] = fallback_family
    _FONT_RESOURCES_LOADED = True
    return fallback_family


def get_theme() -> ThemeManager:
    return ThemeManager.get_instance()


def apply_theme(app: Optional[QApplication] = None, theme_name: Optional[str] = None) -> None:
    if app is None:
        app = _get_qt_app()
    if app is None:
        return
    font_family = ensure_app_fonts()
    base_size = FONT_SIZES["size_base"]
    # DPI-aware scaling
    screen = app.primaryScreen()
    if screen is not None:
        dpi = screen.logicalDotsPerInch()
        if dpi > 110:
            base_size = max(base_size, int(round(base_size * (dpi / 96.0))))
    app.setFont(QFont(font_family, base_size))
    app.setStyleSheet(get_stylesheet(theme_name or _CURRENT_THEME))
