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
# Color palette
# ---------------------------------------------------------------------------
COLORS: Dict[str, str] = {
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
}

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


def _build_stylesheet() -> str:
    return r"""/* ============================================================================
 * Endfield industrial sci-fi style - PyQt6 QSS
 * ============================================================================ */

/* Global */
QWidget { font-family: 'Microsoft YaHei UI'; font-size: 12px; color: #e8e8ee; background-color: #07080d; }
QMainWindow {
    background-color: #07080d;
    background-image: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(11,15,25,0.98),
        stop:0.45 rgba(7,8,13,1),
        stop:1 rgba(6,8,12,1));
}
QWidget[ui-mode="compact"] QLabel[variant="hero"] { font-size: 22px; }
QWidget[ui-mode="compact"] QLabel[variant="header"] { font-size: 17px; }
QWidget[ui-mode="compact"] QPushButton { min-height: 30px; padding: 2px 8px; }
QWidget[ui-mode="compact"] QLineEdit,
QWidget[ui-mode="compact"] QComboBox,
QWidget[ui-mode="compact"] QSpinBox { min-height: 30px; padding: 6px 10px; }
QWidget[ui-mode="compact"] QGroupBox { font-size: 12px; }
QWidget[ui-mode="compact"] QListWidget::item { padding: 8px 8px; }
QWidget[ui-mode="compact"] QTabBar::tab { padding: 6px 14px; min-width: 64px; }
QWidget[ui-mode="compact"] QTextEdit,
QWidget[ui-mode="compact"] QPlainTextEdit { padding: 6px; }

/* Buttons */
QPushButton { background-color: rgba(13,19,28,0.92); color: #e8e8ee; border: 1px solid rgba(64,132,162,0.32); border-radius: 2px; padding: 2px 10px; font-size: 12px; font-weight: 500; min-height: 36px; }
QPushButton:hover { background-color: rgba(24,209,255,0.08); border-color: rgba(104,217,244,0.52); }
QPushButton:pressed { background-color: rgba(18,27,38,0.92); border-color: rgba(104,217,244,0.60); }
QPushButton:disabled { background-color: rgba(22,22,36,0.85); color: #282840; border-color: rgba(24,209,255,0.12); }
QPushButton[variant="primary"] { background-color: rgba(22,188,214,0.14); color: #c8f7ff; border: 1px solid rgba(81,219,244,0.64); }
QPushButton[variant="primary"]:hover { background-color: rgba(22,188,214,0.22); }
QPushButton[variant="primary"]:pressed { background-color: rgba(22,188,214,0.30); }
QPushButton[variant="secondary"] { background-color: rgba(255,255,255,0.02); color: #d6dde8; border: 1px solid rgba(88,98,121,0.48); }
QPushButton[variant="secondary"]:hover { background-color: rgba(24,209,255,0.06); border-color: rgba(120,214,236,0.50); }
QPushButton[variant="text"] { background-color: transparent; color: #9090a8; border: none; }
QPushButton[variant="text"]:hover { background-color: rgba(24,209,255,0.08); }
QPushButton[variant="danger"] { background-color: transparent; color: #ff3355; border: 1px solid #ff3355; }
QPushButton[variant="danger"]:hover { background-color: rgba(255,51,85,0.12); border-color: #ff6680; }

/* Labels */
QLabel { color: #e8e8ee; background-color: transparent; border: none; }
QLabel[variant="header"] { font-size: 20px; font-weight: 600; color: #e8e8ee; }
QLabel[variant="title"] { font-size: 17px; font-weight: 600; color: #e8e8ee; }
QLabel[variant="hero"] { font-size: 28px; font-weight: 700; color: #edf2f7; letter-spacing: 1px; }
QLabel[variant="secondary"] { color: #9090a8; }
QLabel[variant="muted"] { color: #404058; }
QLabel[variant="terminal"] { font-family: 'Microsoft YaHei UI'; color: #18d1ff; font-size: 12px; }
QLabel[variant="eyebrow"] { color: #6fd7ef; font-size: 11px; font-weight: 600; letter-spacing: 2px; }
QLabel[variant="accent"] { color: #fffa00; }
QLabel[variant="success"] { color: #00ffa2; }
QLabel[variant="danger"] { color: #ff3355; }

/* Inputs */
QLineEdit { background-color: rgba(16,16,26,0.88); color: #e8e8ee; border: 1px solid rgba(24,209,255,0.12); border-radius: 4px; padding: 10px 14px; font-size: 12px; min-height: 36px; }
QLineEdit:hover { border-color: rgba(24,209,255,0.20); }
QLineEdit:focus { border-color: #18d1ff; }
QLineEdit:disabled { background-color: rgba(22,22,36,0.85); color: #282840; }

QComboBox { background-color: rgba(16,16,26,0.88); color: #e8e8ee; border: 1px solid rgba(24,209,255,0.12); border-radius: 4px; padding: 10px 14px; font-size: 12px; min-height: 36px; }
QComboBox:hover { border-color: rgba(24,209,255,0.20); }
QComboBox:focus { border-color: #18d1ff; }
QComboBox::drop-down { border: none; width: 28px; padding-right: 8px; }
QComboBox::down-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #9090a8; width: 0; height: 0; }
QComboBox QAbstractItemView { background-color: rgba(16,16,26,0.88); color: #e8e8ee; border: 1px solid rgba(24,209,255,0.12); border-radius: 4px; selection-background-color: rgba(24,209,255,0.25); selection-color: #000000; padding: 2px; }

QSpinBox { background-color: rgba(16,16,26,0.88); color: #e8e8ee; border: 1px solid rgba(24,209,255,0.12); border-radius: 4px; padding: 10px 14px; font-size: 12px; min-height: 26px; }
QSpinBox:hover { border-color: rgba(24,209,255,0.20); }
QSpinBox:focus { border-color: #18d1ff; }
QSpinBox::up-button, QSpinBox::down-button { background-color: #050508; border: none; width: 24px; subcontrol-position: right; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background-color: rgba(24,209,255,0.08); }
QSpinBox::up-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-bottom: 6px solid #e8e8ee; width: 0; height: 0; }
QSpinBox::down-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #e8e8ee; width: 0; height: 0; }

/* Checkbox */
QCheckBox { color: #e8e8ee; spacing: 8px; font-size: 12px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 3px; border: 1px solid rgba(24,209,255,0.20); background-color: transparent; }
QCheckBox::indicator:hover { border-color: #18d1ff; }
QCheckBox::indicator:checked { background-color: #18d1ff; border-color: #18d1ff; }
QCheckBox::indicator:disabled { border-color: #282840; background-color: rgba(16,16,26,0.88); }

/* Tabs */
QTabWidget::pane { background-color: #0a0a0f; border: 1px solid rgba(24,209,255,0.12); border-radius: 4px; top: -1px; }
QTabBar::tab { background-color: transparent; color: #9090a8; border: none; border-bottom: 2px solid transparent; padding: 8px 20px; font-size: 12px; min-width: 80px; }
QTabBar::tab:hover { background-color: rgba(24,209,255,0.08); }
QTabBar::tab:selected { color: #18d1ff; border-bottom: 2px solid #18d1ff; }

/* Splitter */
QSplitter::handle { background-color: rgba(24,209,255,0.10); }
QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical { height: 1px; }

/* Scrollbar */
QScrollBar:vertical { background-color: transparent; width: 6px; border-radius: 3px; margin: 0; }
QScrollBar::handle:vertical { background-color: rgba(24,209,255,0.12); border-radius: 3px; min-height: 32px; margin: 2px; }
QScrollBar::handle:vertical:hover { background-color: rgba(24,209,255,0.20); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; background-color: transparent; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background-color: transparent; }
QScrollBar:horizontal { background-color: transparent; height: 6px; border-radius: 3px; margin: 0; }
QScrollBar::handle:horizontal { background-color: rgba(24,209,255,0.12); border-radius: 3px; min-width: 32px; margin: 2px; }
QScrollBar::handle:horizontal:hover { background-color: rgba(24,209,255,0.20); }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; background-color: transparent; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background-color: transparent; }

/* List */
QListWidget { background-color: rgba(10,14,20,0.88); color: #e8e8ee; border: 1px solid rgba(65,110,140,0.34); border-radius: 2px; padding: 8px; font-size: 12px; outline: none; }
QListWidget::item { background-color: transparent; padding: 12px 10px; border-left: 2px solid transparent; border-radius: 0; }
QListWidget::item:hover { background-color: rgba(24,209,255,0.06); border-left: 2px solid rgba(24,209,255,0.28); }
QListWidget::item:selected { background-color: rgba(22,188,214,0.16); color: #eafaff; border: 1px solid rgba(94,210,236,0.45); border-left: 2px solid #71e8ff; }
QListWidget::item:selected:!active { background-color: rgba(22,188,214,0.12); }

/* Tables */
QTableWidget, QTableView { background-color: #0a0a0f; color: #e8e8ee; border: 1px solid rgba(24,209,255,0.12); border-radius: 4px; gridline-color: rgba(24,209,255,0.10); font-size: 12px; }
QTableWidget::item, QTableView::item { padding: 8px; border: none; }
QTableWidget::item:hover, QTableView::item:hover { background-color: rgba(24,209,255,0.08); }
QTableWidget::item:selected, QTableView::item:selected { background-color: rgba(24,209,255,0.25); color: #000000; }
QHeaderView::section { background-color: rgba(16,16,26,0.88); color: #e8e8ee; border: none; border-bottom: 1px solid rgba(24,209,255,0.12); padding: 8px; font-size: 12px; font-weight: 500; }

/* Tree */
QTreeWidget, QTreeView { background-color: #0a0a0f; color: #e8e8ee; border: 1px solid rgba(24,209,255,0.12); border-radius: 4px; font-size: 12px; }
QTreeWidget::item, QTreeView::item { padding: 10px; border-radius: 2px; }
QTreeWidget::item:hover, QTreeView::item:hover { background-color: rgba(24,209,255,0.08); }
QTreeWidget::item:selected, QTreeView::item:selected { background-color: rgba(24,209,255,0.25); color: #000000; }

/* GroupBox */
QGroupBox { background-color: rgba(11,15,22,0.88); color: #e8e8ee; border: 1px solid rgba(66,105,132,0.35); border-radius: 2px; font-size: 12px; padding-top: 6px; margin-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 14px; padding: 0 6px; color: #7ec9da; font-weight: 600; letter-spacing: 1px; }

/* ProgressBar */
QProgressBar { background-color: rgba(16,16,26,0.88); border: none; border-radius: 9999px; height: 4px; text-align: center; color: #e8e8ee; }
QProgressBar::chunk { background-color: #18d1ff; border-radius: 9999px; }

/* TextEdit */
QTextEdit, QPlainTextEdit { background-color: rgba(5,5,8,0.95); color: #e8e8ee; border: 1px solid rgba(24,209,255,0.12); border-radius: 4px; padding: 8px; font-size: 12px; font-family: 'Microsoft YaHei UI'; }
QTextEdit:focus, QPlainTextEdit:focus { border-color: #18d1ff; }

/* Menu */
QMenu { background-color: rgba(16,16,26,0.88); color: #e8e8ee; border: 1px solid rgba(24,209,255,0.12); border-radius: 4px; padding: 4px; }
QMenu::item { padding: 8px 20px; border-radius: 2px; }
QMenu::item:selected { background-color: rgba(24,209,255,0.08); }
QMenu::separator { height: 1px; background-color: rgba(24,209,255,0.10); margin: 4px 8px; }

/* Tooltip */
QToolTip { background-color: rgba(30,30,45,0.85); color: #e8e8ee; border: 1px solid rgba(24,209,255,0.12); border-radius: 3px; padding: 8px 12px; font-size: 11px; }

/* Dialog */
QDialog { background-color: #0a0a0f; border: 1px solid rgba(24,209,255,0.12); }

/* StatusBar */
QStatusBar { background-color: #07070b; color: #9090a8; border-top: 1px solid rgba(24,209,255,0.12); font-size: 11px; }
QStatusBar::item { border: none; }

/* StackedWidget */
QStackedWidget { background-color: #0a0a0f; }
QStackedWidget > QWidget { background-color: #0a0a0f; }

QFrame#heroPanel, QFrame#pageHero, QFrame#settingsHero {
    background-color: rgba(10,14,22,0.92);
    border: 1px solid rgba(72,118,147,0.38);
    border-radius: 2px;
}
QFrame#navPanel, QFrame#contentPanel, QFrame#metricCard, QFrame#controlBar {
    background-color: rgba(9,12,18,0.88);
    border: 1px solid rgba(59,94,119,0.34);
    border-radius: 2px;
}
QListWidget#mainNavigation {
    background-color: transparent;
    border: none;
    padding: 0;
}
QStatusBar {
    background-color: rgba(7,8,12,0.98);
    color: #6f7e95;
    border-top: 1px solid rgba(57,92,120,0.32);
    font-size: 11px;
}

/* ScrollArea */
QScrollArea { background-color: #0a0a0f; border: none; }
QScrollArea > QWidget > QWidget { background-color: #0a0a0f; }

/* Separator */
QFrame[frameShape="4"] { background-color: rgba(24,209,255,0.10); max-height: 1px; border: none; }
QFrame[frameShape="5"] { background-color: rgba(24,209,255,0.10); max-width: 1px; border: none; }
"""


def get_stylesheet() -> str:
    global _STYLESHEET
    if _STYLESHEET is None:
        _STYLESHEET = _build_stylesheet()
    return _STYLESHEET


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
    def get_stylesheet(self) -> str:
        return get_stylesheet()
    def apply_theme(self, app: QApplication) -> None:
        app.setStyleSheet(get_stylesheet())


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


def apply_theme(app: Optional[QApplication] = None) -> None:
    if app is None:
        app = _get_qt_app()
    if app is None:
        return
    font_family = ensure_app_fonts()
    app.setFont(QFont(font_family, FONT_SIZES["size_base"]))
    app.setStyleSheet(get_stylesheet())
