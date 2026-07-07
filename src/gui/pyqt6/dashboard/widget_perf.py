"""Performance monitoring and debugging tools for dashboard widgets."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gui.pyqt6.i18n import get_locale_manager

locale = get_locale_manager()


@dataclass
class WidgetPerfStats:
    """Performance statistics for a single widget."""
    widget_id: str
    refresh_count: int = 0
    error_count: int = 0
    total_refresh_ms: float = 0.0
    last_refresh_ms: float = 0.0
    max_refresh_ms: float = 0.0
    min_refresh_ms: float = float("inf")
    started_at: float = field(default_factory=time.time)
    last_refresh_at: Optional[float] = None

    def record_refresh(self, elapsed_ms: float, error: bool = False) -> None:
        self.refresh_count += 1
        self.last_refresh_ms = elapsed_ms
        self.last_refresh_at = time.time()
        self.total_refresh_ms += elapsed_ms
        self.max_refresh_ms = max(self.max_refresh_ms, elapsed_ms)
        self.min_refresh_ms = min(self.min_refresh_ms, elapsed_ms)
        if error:
            self.error_count += 1

    @property
    def avg_refresh_ms(self) -> float:
        if self.refresh_count == 0:
            return 0.0
        return self.total_refresh_ms / self.refresh_count

    @property
    def uptime_s(self) -> float:
        return time.time() - self.started_at


class WidgetPerfMonitor:
    """Central performance monitor for dashboard widgets."""

    def __init__(self) -> None:
        self._stats: dict[str, WidgetPerfStats] = {}
        self._listeners: list = []

    def stats_for(self, widget_id: str) -> WidgetPerfStats:
        if widget_id not in self._stats:
            self._stats[widget_id] = WidgetPerfStats(widget_id=widget_id)
        return self._stats[widget_id]

    def record(self, widget_id: str, elapsed_ms: float, error: bool = False) -> None:
        stats = self.stats_for(widget_id)
        stats.record_refresh(elapsed_ms, error)
        self._emit("record", widget_id, stats)

    def summary(self) -> dict[str, dict]:
        return {
            widget_id: {
                "refresh_count": s.refresh_count,
                "error_count": s.error_count,
                "avg_ms": round(s.avg_refresh_ms, 2),
                "max_ms": round(s.max_refresh_ms, 2),
                "min_ms": round(s.min_refresh_ms, 2) if s.min_refresh_ms != float("inf") else 0.0,
                "uptime_s": round(s.uptime_s, 1),
            }
            for widget_id, s in self._stats.items()
        }

    def listen(self, callback) -> None:
        self._listeners.append(callback)

    def _emit(self, event: str, widget_id: str, stats: WidgetPerfStats) -> None:
        for cb in self._listeners:
            try:
                cb(event, widget_id, stats)
            except Exception:
                pass


# Global monitor
_monitor: Optional[WidgetPerfMonitor] = None


def get_widget_perf_monitor() -> WidgetPerfMonitor:
    global _monitor
    if _monitor is None:
        _monitor = WidgetPerfMonitor()
    return _monitor


class PerfOverlay(QLabel):
    """Small overlay showing widget performance."""

    def __init__(self, widget_id: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._widget_id = widget_id
        self.setVisible(False)
        self._monitor = get_widget_perf_monitor()
        self._monitor.listen(self._on_stats)
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(1000)
        self._update_timer.timeout.connect(self._refresh_text)
        self._update_timer.start()
        self._refresh_text()

    def _on_stats(self, event: str, widget_id: str, stats) -> None:
        if widget_id != self._widget_id:
            return
        self._refresh_text()

    def _refresh_text(self) -> None:
        stats = self._monitor.stats_for(self._widget_id)
        text = (
            f"avg: {stats.avg_refresh_ms:.0f}ms | "
            f"max: {stats.max_refresh_ms:.0f}ms | "
            f"errors: {stats.error_count}"
        )
        self.setText(text)

    def showEvent(self, event) -> None:
        self._refresh_text()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)


class WidgetPerfMixin:
    """Mixin for dashboard widgets to monitor performance."""

    def _perf_start(self) -> float:
        return time.perf_counter()

    def _perf_record(self, start: float, error: bool = False) -> None:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        monitor = get_widget_perf_monitor()
        monitor.record(getattr(self, "_widget_id", "unknown"), elapsed_ms, error)
