"""Micro-animation helpers for PyQt6 widgets.

Provides subtle hover/press animations to enhance the tactile feel of
buttons and interactive elements, aligned with Hypergryph's polished UI.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QRectF, Qt
from PyQt6.QtGui import QPainter, QColor, QMouseEvent
from PyQt6.QtWidgets import QPushButton, QWidget


class AnimatedButton(QPushButton):
    """QPushButton with smooth background color transition on hover/press.

    Uses QPropertyAnimation on a custom ``_bg_opacity`` property to fade
    between normal, hover, and pressed states over 120-200ms.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bg_opacity = 0.0
        self._target_opacity = 0.0
        self._animation = QPropertyAnimation(self, b"_bg_opacity", self)
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get_bg_opacity(self):
        return self._bg_opacity

    def _set_bg_opacity(self, value):
        self._bg_opacity = value
        self.update()

    _bg_opacity = property(_get_bg_opacity, _set_bg_opacity)

    def enterEvent(self, event):
        self._target_opacity = 1.0
        self._animate_to(self._target_opacity)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._target_opacity = 0.0
        self._animate_to(self._target_opacity)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._bg_opacity = 0.5
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._animate_to(self._target_opacity)
        super().mouseReleaseEvent(event)

    def _animate_to(self, target):
        self._animation.stop()
        self._animation.setStartValue(self._bg_opacity)
        self._animation.setEndValue(target)
        self._animation.start()

    def paintEvent(self, event):
        # Let the base class paint the button first
        super().paintEvent(event)
        # Draw a subtle overlay that fades in/out
        if self._bg_opacity > 0.01:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            alpha = int(self._bg_opacity * 40)
            painter.fillRect(self.rect(), QColor(24, 209, 255, alpha))
            painter.end()

