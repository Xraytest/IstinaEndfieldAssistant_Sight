"""Data visualization chart widget for dashboard."""
from __future__ import annotations

from typing import Any, Optional

import numpy as np

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from gui.pyqt6.dashboard.widget_base import DashboardWidget
from gui.pyqt6.i18n import get_locale_manager

locale = get_locale_manager()


class MiniChartWidget(QWidget):
    """Lightweight line chart drawn with QPainter."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._values: list[float] = []
        self._max_points = 20

    def set_data(self, values: list[float]) -> None:
        self._values = values[-self._max_points:]
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return

        values = self._values
        if len(values) < 2:
            painter.end()
            return

        min_v = min(values)
        max_v = max(values)
        rng = max_v - min_v if max_v != min_v else 1.0

        pad = 4
        x_step = (w - pad * 2) / (len(values) - 1)
        y_scale = (h - pad * 2) / rng

        def tx(i: int, v: float) -> tuple[int, int]:
            x = int(pad + i * x_step)
            y = int(h - pad - (v - min_v) * y_scale)
            return x, y

        # Fill under curve
        path = QPainterPath()
        path.moveTo(*tx(0, values[0]))
        for i in range(1, len(values)):
            path.lineTo(*tx(i, values[i]))
        path.lineTo(tx(len(values) - 1, min_v))
        path.lineTo(*tx(0, min_v))
        path.closeSubpath()
        painter.fillPath(path, QColor(24, 209, 255, 35))

        # Line
        pen = QPen(QColor(24, 209, 255))
        pen.setWidth(2)
        painter.setPen(pen)
        path = QPainterPath()
        path.moveTo(*tx(0, values[0]))
        for i in range(1, len(values)):
            path.lineTo(*tx(i, values[i]))
        painter.drawPath(path)

        # Dots
        painter.setPen(QColor(24, 209, 255))
        painter.setBrush(QColor(24, 209, 255))
        for i, v in enumerate(values):
            x, y = tx(i, v)
            painter.drawEllipse(x - 2, y - 2, 4, 4)


class ChartWidget(DashboardWidget):
    """Dashboard widget showing a line chart."""

    def __init__(self, title: str, bridge, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, "chart", parent)
        self._bridge = bridge
        self._chart = MiniChartWidget(self)
        content = self.content_widget()
        layout = QVBoxLayout(content)
        layout.addWidget(self._chart)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(3000)
        self._poll_timer.timeout.connect(self.refresh)
        self._poll_timer.start()
        self.refresh()

    def update_data(self, data: Any) -> None:
        if isinstance(data, list):
            self._chart.set_data([float(v) for v in data])

    def refresh(self) -> None:
        try:
            result = self._bridge.execute("stats trend")
            if result and result.get("status") == "success":
                values = result.get("values", [])
                self.update_data(values)
        except Exception:
            pass
