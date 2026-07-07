"""Widget-specific style strings derived from the central ThemeManager.

Pages should import from here instead of defining local style constants.
This ensures all colors, fonts, and spacing stay in sync with the project theme.
"""

from __future__ import annotations

from gui.pyqt6.theme.theme_manager import COLORS, FONTS, FONT_SIZES, SPACING

# ---------------------------------------------------------------------------
# Color shortcuts
# ---------------------------------------------------------------------------
_PRIMARY = COLORS["primary"]
_SUCCESS = COLORS["success"]
_DANGER = COLORS["danger"]
_WARNING = COLORS["warning"]
_ACCENT_GOLD = COLORS["accent_gold"]
_TEXT_PRIMARY = COLORS["text_primary"]
_TEXT_SECONDARY = COLORS["text_secondary"]
_BG_CARD = COLORS["bg_card"]
_BORDER = COLORS["border_color"]
_BORDER_LIGHT = COLORS["border_light"]
_FONT = FONTS["family"]
_SIZE_BASE = FONT_SIZES["size_base"]


# ---------------------------------------------------------------------------
# Label inline styles
# ---------------------------------------------------------------------------
INFO_STYLE = (
    f"color: {_TEXT_SECONDARY}; font-size: {_SIZE_BASE}px;"
    f" font-family: '{_FONT}'; padding: 3px 0;"
)
VAL_STYLE = (
    f"color: {_TEXT_PRIMARY}; font-size: {_SIZE_BASE}px;"
    f" font-family: '{_FONT}'; padding: 3px 0;"
)
GREEN_STYLE = (
    f"color: {_SUCCESS}; font-size: {_SIZE_BASE}px;"
    f" font-family: '{_FONT}'; padding: 3px 0;"
)
RED_STYLE = (
    f"color: {_DANGER}; font-size: {_SIZE_BASE}px;"
    f" font-family: '{_FONT}'; padding: 3px 0;"
)
BLUE_STYLE = (
    f"color: {_PRIMARY}; font-size: {_SIZE_BASE}px;"
    f" font-family: '{_FONT}'; padding: 3px 0;"
)
YELLOW_STYLE = (
    f"color: {_WARNING}; font-size: {_SIZE_BASE}px;"
    f" font-family: '{_FONT}'; padding: 3px 0;"
)
HEADER_STYLE = (
    f"color: {_PRIMARY}; font-size: 14px; font-family: '{_FONT}';"
    f" font-weight: bold; letter-spacing: 1px; padding: 4px 0;"
)
METRIC_VALUE_STYLE = (
    f"font-size: 22px; font-family: '{_FONT}';"
    f" color: {_TEXT_PRIMARY}; font-weight: bold;"
)

# ---------------------------------------------------------------------------
# Card / container QSS blocks
# ---------------------------------------------------------------------------
CARD_STYLE = f"""
    QGroupBox {{
        background-color: {_BG_CARD};
        border: 1px solid {_BORDER_LIGHT};
        border-radius: 6px;
        font-size: 13px; font-family: '{_FONT}';
        color: {_TEXT_PRIMARY}; font-weight: bold; letter-spacing: 1px;
        margin-top: 12px;
        padding-top: 18px;
    }}
    QGroupBox:hover {{
        border: 1px solid rgba(24, 209, 255, 0.35);
        background-color: {_BG_CARD};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        top: -1px;
        padding: 0 4px;
    }}
"""

PANEL_STYLE = f"""
    QFrame {{
        background-color: {_BG_CARD};
        border: 1px solid {_BORDER_LIGHT};
        border-radius: 8px;
    }}
"""

LIST_STYLE = f"""
    QListWidget {{
        background-color: rgba(10, 10, 15, 0.90);
        border: 1px solid {_BORDER_LIGHT};
        color: {_TEXT_PRIMARY}; font-family: '{_FONT}'; font-size: {_SIZE_BASE}px;
    }}
    QListWidget::item {{ padding: 3px 6px; }}
    QListWidget::item:hover {{ background-color: rgba(24, 209, 255, 0.08); border-left: 2px solid rgba(24, 209, 255, 0.35); }}
    QListWidget::item:selected {{ background-color: {_PRIMARY}33; color: {_PRIMARY}; border-left: 2px solid {_PRIMARY}; }}
"""

LOG_STYLE = f"""
    QTextEdit {{
        background-color: rgba(10, 10, 15, 0.90);
        color: #e0e0e8;
        border: 1px solid {_BORDER_LIGHT};
        border-radius: 4px;
        font-size: 11px; font-family: '{_FONT}'; padding: 2px 4px;
    }}
"""

INPUT_STYLE = f"""
    QLineEdit, QSpinBox, QComboBox {{
        background-color: rgba(16, 16, 26, 0.85);
        color: {_TEXT_PRIMARY}; border: 1px solid {_BORDER};
        border-radius: 2px; font-size: {_SIZE_BASE}px; font-family: '{_FONT}'; padding: 6px 10px; min-height: 32px;
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {_PRIMARY}; }}
"""

CHECK_STYLE = f"""
    QCheckBox {{ color: {_TEXT_PRIMARY}; font-size: {_SIZE_BASE}px; font-family: '{_FONT}'; spacing: 8px; }}
    QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 2px; border: 1px solid {_BORDER}; background-color: transparent; }}
    QCheckBox::indicator:checked {{ background-color: {_PRIMARY}; border-color: {_PRIMARY}; }}
"""

COMBO_STYLE = f"""
    QComboBox {{
        background-color: rgba(10, 10, 15, 0.80); color: {_TEXT_PRIMARY}; border: 1px solid {_BORDER};
        border-radius: 4px; padding: 8px 12px; font-size: {_SIZE_BASE}px; font-family: '{_FONT}'; min-height: 36px;
    }}
    QComboBox::drop-down {{ border: none; width: 28px; }}
    QComboBox::down-arrow {{ image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid {_PRIMARY}80; width: 0; height: 0; }}
    QComboBox QAbstractItemView {{ background-color: rgba(12, 12, 20, 0.95); color: {_TEXT_PRIMARY}; border: 1px solid {_BORDER}; selection-background-color: {_PRIMARY}26; }}
"""

TABLE_STYLE = f"""
    QTableWidget {{ background-color: rgba(16, 16, 26, 0.85); border: 1px solid {_BORDER_LIGHT}; border-radius: 2px; color: {_TEXT_PRIMARY}; font-size: {_SIZE_BASE}px; font-family: '{_FONT}'; gridline-color: {_BORDER_LIGHT}; }}
    QTableWidget::item {{ padding: 6px; }}
    QTableWidget::item:hover {{ background-color: rgba(24, 209, 255, 0.08); }}
    QTableWidget::item:selected {{ background-color: rgba(24, 209, 255, 0.25); color: #000000; border-left: 3px solid {_PRIMARY}; }}
    QHeaderView::section {{ background-color: {_PRIMARY}14; color: {_PRIMARY}; font-size: 11px; font-weight: bold; padding: 6px; border: none; }}
"""

PREVIEW_STYLE = f"""
    QLabel {{
        background-color: rgba(8, 8, 12, 0.95);
        border: 1px solid {_BORDER_LIGHT};
        border-radius: 4px;
        padding: 2px;
    }}
"""

SKELETON_STYLE = f"""
    QFrame {{
        background-color: {_BORDER_LIGHT};
        border: none;
        border-radius: 4px;
    }}
"""

LOADING_OVERLAY_STYLE = f"""
    QFrame {{
        background-color: rgba(10, 10, 15, 0.85);
        border: none;
    }}
    QLabel {{
        color: {_PRIMARY};
        font-size: 14px;
        font-family: '{_FONT}';
        letter-spacing: 2px;
    }}
"""

SPLITTER_HANDLE_STYLE = "QSplitter::handle { width: 1px; background: rgba(24, 209, 255, 0.12); }"
SCROLL_AREA_TRANSPARENT_STYLE = "QScrollArea { border: none; background: transparent; }"
PROGRESS_BAR_STYLE = f"""
    QProgressBar {{
        background-color: rgba(16, 16, 26, 0.85);
        border: 1px solid rgba(24, 209, 255, 0.15);
        border-radius: 8px;
        height: 16px;
        text-align: center;
        color: #9090a8;
        font-size: 10px;
        font-family: '{_FONT}';
    }}
    QProgressBar::chunk {{
        background-color: {_PRIMARY};
        border-radius: 8px;
    }}
"""

# ---------------------------------------------------------------------------
# Button QSS blocks
# ---------------------------------------------------------------------------
BTN_ACTIVE = f"""
    QPushButton {{
        background-color: {_SUCCESS}1a;
        color: {_SUCCESS};
        border: 1px solid {_SUCCESS}4d;
        border-radius: 2px;
        padding: 8px 16px;
        font-size: 11px; font-family: '{_FONT}'; font-weight: bold; letter-spacing: 1px;
        min-height: 36px;
    }}
    QPushButton:hover {{ background-color: {_SUCCESS}33; }}
"""

BTN_DEFAULT = f"""
    QPushButton {{
        background-color: {_PRIMARY}1a;
        color: {_PRIMARY};
        border: 1px solid {_PRIMARY}4d;
        border-radius: 2px;
        padding: 8px 16px;
        font-size: 11px; font-family: '{_FONT}'; font-weight: bold; letter-spacing: 1px;
        min-height: 36px;
    }}
    QPushButton:hover {{ background-color: {_PRIMARY}33; }}
"""

BTN_STOP = f"""
    QPushButton {{
        background-color: {_DANGER}1f;
        color: {_DANGER};
        border: 1px solid {_DANGER}66;
        border-radius: 2px;
        padding: 8px 16px;
        font-size: 11px; font-family: '{_FONT}'; font-weight: bold; letter-spacing: 1px;
        min-height: 36px;
    }}
    QPushButton:hover {{ background-color: {_DANGER}40; }}
"""
