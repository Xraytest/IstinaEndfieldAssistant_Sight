"""Icon registry for the GUI.

Provides QIcon instances for navigation items and action buttons.
Icons are generated from Unicode symbols rendered as pixmaps to avoid
external asset dependencies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import QSize, Qt


def _pixmap_from_text(text: str, size: int = 16, color: str = "#18d1ff") -> QPixmap:
    """Render a Unicode symbol into a pixmap for use as an icon."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor("transparent"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor(color))
    font = QFont("Segoe UI Emoji", int(size * 0.7))
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
    painter.end()
    return pixmap


# Navigation icons
_NAV_ICONS: Dict[str, str] = {
    "PRTS全智能": "🤖",
    "标准推理": "⚙️",
    "设备": "📱",
    "设置": "🔧",
    "日志": "📄",
}

# Action button icons
_ACTION_ICONS: Dict[str, str] = {
    "运行": "▶",
    "停止": "⏹",
    "添加": "＋",
    "删除": "✕",
    "上移": "↑",
    "下移": "↓",
    "清空": "🗑",
    "刷新": "🔄",
    "连接": "🔗",
    "断开": "⛔",
    "保存": "💾",
    "分析": "🔍",
}

# Queue status icons
_STATUS_ICONS: Dict[str, str] = {
    "pending": "○",
    "running": "◉",
    "success": "✓",
    "failed": "✗",
}

_cache: Dict[str, QIcon] = {}


def get_nav_icon(label: str, size: int = 18) -> QIcon:
    """Return an icon for a navigation label."""
    text = _NAV_ICONS.get(label, "")
    if not text:
        return QIcon()
    key = f"nav:{label}:{size}"
    if key not in _cache:
        _cache[key] = QIcon(_pixmap_from_text(text, size=size))
    return _cache[key]


def get_action_icon(name: str, size: int = 14) -> QIcon:
    """Return an icon for an action button."""
    text = _ACTION_ICONS.get(name, "")
    if not text:
        return QIcon()
    key = f"action:{name}:{size}"
    if key not in _cache:
        _cache[key] = QIcon(_pixmap_from_text(text, size=size, color="#e8e8ee"))
    return _cache[key]


def get_status_icon(status: str, size: int = 14) -> QIcon:
    """Return an icon for a queue item status."""
    text = _STATUS_ICONS.get(status, "")
    if not text:
        return QIcon()
    key = f"status:{status}:{size}"
    if key not in _cache:
        color = {
            "pending": "#9090a8",
            "running": "#18d1ff",
            "success": "#00ffa2",
            "failed": "#ff3355",
        }.get(status, "#9090a8")
        _cache[key] = QIcon(_pixmap_from_text(text, size=size, color=color))
    return _cache[key]


def apply_nav_icons(list_widget) -> None:
    """Apply icons to all items in a QListWidget used for navigation."""
    for i in range(list_widget.count()):
        item = list_widget.item(i)
        if item is None:
            continue
        icon = get_nav_icon(item.text())
        if not icon.isNull():
            item.setIcon(icon)
