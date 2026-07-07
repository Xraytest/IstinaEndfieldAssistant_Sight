"""System resource dashboard widget."""
from __future__ import annotations

import psutil
from typing import Optional

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gui.pyqt6.dashboard.widget_base import DashboardWidget
from gui.pyqt6.i18n import get_locale_manager

locale = get_locale_manager()


class SystemResourceWidget(DashboardWidget):
    """Shows system resource usage."""

    def __init__(self, title: str, bridge, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, "system_resource", parent)
        self._bridge = bridge
        self._cpu_label = QLabel("CPU: -")
        self._mem_label = QLabel("Memory: -")
        content = self.content_widget()
        layout = QVBoxLayout(content)
        layout.addWidget(self._cpu_label)
        layout.addWidget(self._mem_label)
        self.start_auto_refresh()

    def update_data(self, _: Optional[dict] = None) -> None:
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory().percent
            self._cpu_label.setText(locale.tr("system_cpu", "CPU: {percent}%").format(percent=round(cpu, 1)))
            self._mem_label.setText(locale.tr("system_memory", "Memory: {percent}%").format(percent=round(mem, 1)))
        except Exception:
            pass

    def refresh(self) -> None:
        self.update_data()
