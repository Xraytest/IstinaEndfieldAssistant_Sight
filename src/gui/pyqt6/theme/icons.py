"""Icon registry for the GUI.

Provides QIcon instances for navigation items and action buttons.
Icons are drawn as vector paths using QPainterPath for crisp scaling
and a consistent Endfield industrial sci-fi aesthetic.
"""

from __future__ import annotations

from typing import Dict, Optional

from PyQt6.QtGui import QIcon, QPainter, QColor, QPainterPath, QPen
from PyQt6.QtCore import QSize, Qt, QPointF


def _pixmap_from_path(path: QPainterPath, size: int = 16, color: str = "#18d1ff", stroke_width: float = 1.5) -> QPixmap:
    """Render a QPainterPath into a pixmap for use as an icon."""
    from PyQt6.QtGui import QPixmap
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor("transparent"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(color), stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setWindow(0, 0, 16, 16)
    painter.drawPath(path)
    painter.end()
    return pixmap





# ---------------------------------------------------------------------------
# Vector icon paths (16x16 coordinate space)
# ---------------------------------------------------------------------------

def _icon_robot() -> QPainterPath:
    p = QPainterPath()
    # Head
    p.addRoundedRect(4, 2, 8, 6, 1.5, 1.5)
    # Eyes
    p.addEllipse(5.5, 4.5, 1.5, 1.5)
    p.addEllipse(9, 4.5, 1.5, 1.5)
    # Body
    p.addRoundedRect(5, 9, 6, 4, 1, 1)
    return p


def _icon_gear() -> QPainterPath:
    p = QPainterPath()
    # Outer gear shape (simplified as circle with notches)
    p.addEllipse(3, 3, 10, 10)
    p.addEllipse(5.5, 5.5, 5, 5)
    # Center dot
    p.addEllipse(7, 7, 2, 2)
    return p


def _icon_device() -> QPainterPath:
    p = QPainterPath()
    # Phone body
    p.addRoundedRect(4, 1.5, 8, 13, 1.5, 1.5)
    # Screen
    p.addRoundedRect(5, 3, 6, 9, 0.5, 0.5)
    # Home button
    p.addEllipse(7, 12, 2, 1.5)
    return p


def _icon_settings() -> QPainterPath:
    p = QPainterPath()
    # Gear shape using arc approximations
    from PyQt6.QtCore import QRectF
    p.arcMoveTo(3, 3, 10, 10, 0)
    p.arcTo(3, 3, 10, 10, 0, 360)
    p.addEllipse(5.5, 5.5, 5, 5)
    p.addEllipse(7, 7, 2, 2)
    return p


def _icon_doc() -> QPainterPath:
    p = QPainterPath()
    p.moveTo(4, 1)
    p.lineTo(12, 1)
    p.lineTo(12, 15)
    p.lineTo(4, 15)
    p.closeSubpath()
    # Fold corner
    p.moveTo(8, 1)
    p.lineTo(8, 5)
    p.lineTo(12, 5)
    p.closeSubpath()
    # Text lines
    p.moveTo(5.5, 7.5)
    p.lineTo(10.5, 7.5)
    p.moveTo(5.5, 10)
    p.lineTo(10.5, 10)
    p.moveTo(5.5, 12.5)
    p.lineTo(9, 12.5)
    return p


def _icon_play() -> QPainterPath:
    p = QPainterPath()
    p.moveTo(3, 2)
    p.lineTo(14, 8)
    p.lineTo(3, 14)
    p.closeSubpath()
    return p


def _icon_stop() -> QPainterPath:
    p = QPainterPath()
    p.addRoundedRect(3, 3, 10, 10, 1.5, 1.5)
    return p


def _icon_plus() -> QPainterPath:
    p = QPainterPath()
    p.moveTo(8, 3)
    p.lineTo(8, 13)
    p.moveTo(3, 8)
    p.lineTo(13, 8)
    return p


def _icon_cross() -> QPainterPath:
    p = QPainterPath()
    p.moveTo(4, 4)
    p.lineTo(12, 12)
    p.moveTo(12, 4)
    p.lineTo(4, 12)
    return p


def _icon_up() -> QPainterPath:
    p = QPainterPath()
    p.moveTo(8, 2)
    p.lineTo(14, 10)
    p.lineTo(8, 8)
    p.lineTo(2, 10)
    p.closeSubpath()
    return p


def _icon_down() -> QPainterPath:
    p = QPainterPath()
    p.moveTo(8, 14)
    p.lineTo(14, 6)
    p.lineTo(8, 8)
    p.lineTo(2, 6)
    p.closeSubpath()
    return p


def _icon_trash() -> QPainterPath:
    p = QPainterPath()
    p.moveTo(4, 3)
    p.lineTo(12, 3)
    p.lineTo(12, 4.5)
    p.lineTo(4, 4.5)
    p.closeSubpath()
    p.moveTo(5.5, 4.5)
    p.lineTo(5.5, 6)
    p.lineTo(10.5, 6)
    p.lineTo(10.5, 4.5)
    p.moveTo(6, 7)
    p.lineTo(6, 13.5)
    p.lineTo(10, 13.5)
    p.lineTo(10, 7)
    return p


def _icon_refresh() -> QPainterPath:
    p = QPainterPath()
    from PyQt6.QtCore import QRectF
    p.arcMoveTo(2, 2, 12, 12, 0)
    p.arcTo(2, 2, 12, 12, 0, 270)
    p.moveTo(8, 2)
    p.lineTo(11, 5)
    p.lineTo(8, 3)
    return p


def _icon_link() -> QPainterPath:
    p = QPainterPath()
    # Left chain
    p.addEllipse(2, 5, 5, 5)
    # Right chain
    p.addEllipse(9, 5, 5, 5)
    # Connecting lines
    p.moveTo(4.5, 7.5)
    p.lineTo(6, 7.5)
    p.moveTo(10, 7.5)
    p.lineTo(11.5, 7.5)
    return p


def _icon_break_link() -> QPainterPath:
    p = QPainterPath()
    p.addEllipse(2, 5, 5, 5)
    p.addEllipse(9, 5, 5, 5)
    p.moveTo(4.5, 7.5)
    p.lineTo(6, 7.5)
    p.moveTo(10, 7.5)
    p.lineTo(11.5, 7.5)
    p.moveTo(6, 6)
    p.lineTo(10, 9)
    p.moveTo(6, 9)
    p.lineTo(10, 6)
    return p


def _icon_save() -> QPainterPath:
    p = QPainterPath()
    p.addRoundedRect(3, 4, 10, 9, 1, 1)
    p.moveTo(2, 4)
    p.lineTo(7, 1)
    p.lineTo(12, 4)
    p.closeSubpath()
    return p


def _icon_search() -> QPainterPath:
    p = QPainterPath()
    p.addEllipse(2, 2, 8, 8)
    p.moveTo(9, 9)
    p.lineTo(14, 14)
    return p


# Navigation icon registry
_NAV_ICONS: Dict[str, callable] = {
    "PRTS全智能": _icon_robot,
    "标准推理": _icon_gear,
    "设备": _icon_device,
    "设置": _icon_settings,
    "日志": _icon_doc,
}

# Action button icon registry
_ACTION_ICONS: Dict[str, callable] = {
    "运行": _icon_play,
    "停止": _icon_stop,
    "添加": _icon_plus,
    "删除": _icon_cross,
    "上移": _icon_up,
    "下移": _icon_down,
    "清空": _icon_trash,
    "刷新": _icon_refresh,
    "连接": _icon_link,
    "断开": _icon_break_link,
    "保存": _icon_save,
    "分析": _icon_search,
}

# Queue status icon registry
_STATUS_ICONS: Dict[str, callable] = {
    "pending": lambda: _icon_dot(4, "#9090a8"),
    "running": lambda: _icon_dot(4, "#18d1ff"),
    "success": lambda: _icon_check(4, "#00ffa2"),
    "failed": lambda: _icon_cross_small(4, "#ff3355"),
}

_cache: Dict[str, QIcon] = {}


def _icon_dot(size: int, color: str) -> QPainterPath:
    p = QPainterPath()
    p.addEllipse(2, 2, size - 4, size - 4)
    return p


def _icon_check(size: int, color: str) -> QPainterPath:
    p = QPainterPath()
    p.moveTo(2, size / 2)
    p.lineTo(size / 3, size - 3)
    p.lineTo(size - 2, 2)
    return p


def _icon_cross_small(size: int, color: str) -> QPainterPath:
    p = QPainterPath()
    margin = 3
    p.moveTo(margin, margin)
    p.lineTo(size - margin, size - margin)
    p.moveTo(size - margin, margin)
    p.lineTo(margin, size - margin)
    return p


def get_nav_icon(label: str, size: int = 18) -> QIcon:
    """Return a vector icon for a navigation label."""
    factory = _NAV_ICONS.get(label)
    if not factory:
        return QIcon()
    key = f"nav:{label}:{size}"
    if key not in _cache:
        path = factory()
        pixmap = _pixmap_from_path(path, size=16, color="#18d1ff", stroke_width=1.8)
        _cache[key] = QIcon(pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    return _cache[key]


def get_action_icon(name: str, size: int = 14) -> QIcon:
    """Return a vector icon for an action button."""
    factory = _ACTION_ICONS.get(name)
    if not factory:
        return QIcon()
    key = f"action:{name}:{size}"
    if key not in _cache:
        path = factory()
        pixmap = _pixmap_from_path(path, size=16, color="#e8e8ee", stroke_width=1.6)
        _cache[key] = QIcon(pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    return _cache[key]


def get_status_icon(status: str, size: int = 14) -> QIcon:
    """Return a vector icon for a queue item status."""
    factory = _STATUS_ICONS.get(status)
    if not factory:
        return QIcon()
    key = f"status:{status}:{size}"
    if key not in _cache:
        path = factory()
        color = {
            "pending": "#9090a8",
            "running": "#18d1ff",
            "success": "#00ffa2",
            "failed": "#ff3355",
        }.get(status, "#9090a8")
        pixmap = _pixmap_from_path(path, size=16, color=color, stroke_width=1.6)
        _cache[key] = QIcon(pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
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
