"""Reusable hero header widget for consistent page titles."""

from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from gui.pyqt6.theme.theme_manager import COLORS


def _rgba(hex_color: str, alpha: float) -> str:
    """Convert #RRGGBB hex color to rgba() string."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


class HeroHeader(QFrame):
    """统一页面标题区域。

    使用 ``settingsHero`` 作为 objectName，复用 ``theme_manager.py``
    中已定义的 ``QFrame#settingsHero`` QSS 规则。
    """

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("settingsHero")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setProperty("variant", "hero")
        layout.addWidget(title_label)

        # Accent divider: a thin rule fading rightward for a polished
        # section-header hierarchy. Decorative only, no behavior change.
        accent = QFrame()
        accent.setFixedHeight(2)
        accent.setMaximumWidth(220)
        accent.setStyleSheet(
            f"background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f" stop:0 {COLORS['primary']}, stop:0.35 {_rgba(COLORS['primary'], 0.55)},"
            f" stop:1 {_rgba(COLORS['primary'], 0)}); border: none; border-radius: 1px;"
        )
        layout.addWidget(accent)

        if subtitle:
            summary = QLabel(subtitle)
            summary.setProperty("variant", "secondary")
            layout.addWidget(summary)


def create_scrolled_page(
    parent: QWidget,
    title: str,
    subtitle: str = "",
    *,
    spacing: int = 14,
) -> tuple:
    """创建标准滚动页面框架：QVBoxLayout(root) → QScrollArea → content QVBoxLayout + HeroHeader。

    供 SettingsPage / DeviceSettingsPage / PrtsFullIntelligencePage / LogPage /
    ScheduledTasksPage 等 ``_setup_ui`` 复用，消除重复的滚动区域 + HeroHeader 模板代码。

    Args:
        parent: 页面 widget（通常是 ``self``）。
        title: HeroHeader 标题（已本地化的字符串）。
        subtitle: HeroHeader 副标题（已本地化的字符串）。
        spacing: content_layout 的 ``setSpacing`` 值，默认 14。

    Returns:
        ``(root_layout, content_layout)`` 元组。调用方继续向 ``content_layout``
        添加页面专属控件。
    """
    root = QVBoxLayout(parent)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    scroll = QScrollArea(parent)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    root.addWidget(scroll)

    content = QWidget()
    scroll.setWidget(content)
    content_root = QVBoxLayout(content)
    content_root.setContentsMargins(16, 16, 16, 16)
    content_root.setSpacing(spacing)

    header = HeroHeader(title, subtitle, content)
    content_root.addWidget(header)

    return root, content_root
