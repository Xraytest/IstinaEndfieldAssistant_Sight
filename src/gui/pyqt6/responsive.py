from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from PyQt6.QtCore import QEvent, QObject, QSize, Qt
from PyQt6.QtGui import QFontMetrics, QGuiApplication
from PyQt6.QtWidgets import QFrame, QScrollArea, QWidget


@dataclass(frozen=True)
class UiBreakpoints:
    normal_width: int = 1280
    compact_width: int = 960
    narrow_width: int = 800
    normal_height: int = 720


BREAKPOINTS = UiBreakpoints()

# DPI scaling thresholds
_DPI_REFERENCE = 96.0  # 100% scaling reference
_DPI_THRESHOLDS = [
    (144.0, 1.5),   # 150%
    (120.0, 1.25),  # 125%
    (96.0, 1.0),    # 100%
]


def get_dpi_scale(widget: QWidget) -> float:
    """Return the DPI scaling factor for the widget's screen.

    Returns 1.0 if the screen or DPI information is unavailable.
    """
    screen = widget.screen()
    if screen is None:
        return 1.0
    dpi = screen.logicalDotsPerInch()
    for threshold, scale in _DPI_THRESHOLDS:
        if dpi >= threshold:
            return scale
    return 1.0


def scale_value(value: int, scale: float) -> int:
    """Scale an integer value by the given factor, rounding to nearest int."""
    return max(1, int(round(value * scale)))


def ui_mode_for_size(size: QSize) -> str:
    width = size.width()
    height = size.height()
    if width < BREAKPOINTS.compact_width or height < BREAKPOINTS.normal_height:
        return "compact"
    return "normal"


def is_narrow_size(size: QSize) -> bool:
    return size.width() < BREAKPOINTS.compact_width or size.height() < BREAKPOINTS.normal_height


def apply_ui_mode(widget: QWidget, mode: str) -> None:
    if widget.property("ui-mode") == mode:
        return
    widget.setProperty("ui-mode", mode)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def apply_dpi_scaling(widget: QWidget, base_font_size: int = 12) -> None:
    """Apply DPI-aware font scaling to a widget and all its children."""
    scale = get_dpi_scale(widget)
    if scale <= 1.0:
        return
    font = widget.font()
    font.setPointSizeF(base_font_size * scale)
    widget.setFont(font)
    # Recursively apply to children
    for child in widget.findChildren(QWidget):
        if child is widget:
            continue
        child_font = child.font()
        child_font.setPointSizeF(base_font_size * scale)
        child.setFont(child_font)


def clamp_window_size(available: QSize, preferred: Tuple[int, int], minimum: Tuple[int, int]) -> QSize:
    max_width = max(minimum[0], int(available.width() * 0.92))
    max_height = max(minimum[1], int(available.height() * 0.92))
    width = min(preferred[0], max_width)
    height = min(preferred[1], max_height)
    width = max(width, minimum[0])
    height = max(height, minimum[1])
    return QSize(width, height)


def elide_text(widget: QWidget, text: str, mode: Qt.TextElideMode = Qt.TextElideMode.ElideMiddle) -> str:
    fm = QFontMetrics(widget.font())
    return fm.elidedText(text, mode, max(0, widget.width() - 8))


def make_scroll_area(widget: QWidget, *, resizable: bool = True) -> QScrollArea:
    area = QScrollArea(widget.parentWidget())
    area.setWidgetResizable(resizable)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(widget)
    return area


class ResizeObserver(QObject):
    def __init__(self, target: QWidget, callback):
        super().__init__(target)
        self._target = target
        self._callback = callback
        target.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._target and event.type() == QEvent.Type.Resize:
            self._callback(self._target.size())
        return super().eventFilter(watched, event)
