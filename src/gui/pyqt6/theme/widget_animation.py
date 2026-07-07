"""Lightweight animation and micro-feedback helpers for dashboard widgets."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QWidget


def _set_opacity(widget: QWidget, opacity: float) -> None:
    widget.setGraphicsEffect(None)
    if opacity < 1.0:
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(opacity)
        widget.setGraphicsEffect(effect)
    else:
        widget.setGraphicsEffect(None)


def fade(widget: QWidget, duration: int = 180, start: float = 0.6, end: float = 1.0) -> QPropertyAnimation:
    animation = QPropertyAnimation(widget, b"windowOpacity")
    animation.setDuration(duration)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.start()
    return animation


def pulse(widget: QWidget, duration: int = 360) -> QPropertyAnimation:
    animation = QPropertyAnimation(widget, b"windowOpacity")
    animation.setDuration(duration)
    animation.setStartValue(1.0)
    animation.setKeyValueAt(0.5, 0.65)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.InOutSine)
    animation.setLoopCount(-1)
    animation.start()
    return animation


def stop_pulse(widget: QWidget) -> None:
    widget.setGraphicsEffect(None)
    _set_opacity(widget, 1.0)


def success_pulse(widget: QWidget) -> None:
    animation = QPropertyAnimation(widget, b"windowOpacity")
    animation.setDuration(240)
    animation.setStartValue(1.0)
    animation.setKeyValueAt(0.5, 0.75)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.start()


def bounce(widget: QWidget) -> None:
    geometry = widget.geometry()
    animation = QPropertyAnimation(widget, b"geometry")
    animation.setDuration(200)
    animation.setStartValue(geometry)
    start_rect = geometry.adjusted(0, -2, 0, 0)
    animation.setKeyValueAt(0.5, start_rect)
    animation.setEndValue(geometry)
    animation.setEasingCurve(QEasingCurve.Type.OutBack)
    animation.start()


class MicroFeedback:
    """Container for hover/press micro-feedback on a widget."""

    def __init__(self, widget: QWidget) -> None:
        self._widget = widget
        self._hovered = False

    def install(self) -> None:
        self._widget.enterEvent = self._enter
        self._widget.leaveEvent = self._leave
        self._widget.mousePressEvent = self._press
        self._widget.mouseReleaseEvent = self._release

    def _enter(self, event) -> None:
        self._hovered = True
        success_pulse(self._widget)
        super(self._widget.__class__, self._widget).enterEvent(event)

    def _leave(self, event) -> None:
        self._hovered = False
        stop_pulse(self._widget)
        super(self._widget.__class__, self._widget).leaveEvent(event)

    def _press(self, event) -> None:
        bounce(self._widget)
        super(self._widget.__class__, self._widget).mousePressEvent(event)

    def _release(self, event) -> None:
        if self._hovered:
            success_pulse(self._widget)
        super(self._widget.__class__, self._widget).mouseReleaseEvent(event)
