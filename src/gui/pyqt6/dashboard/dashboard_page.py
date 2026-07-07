"""Dashboard page with customizable widgets for IstinaEndfieldAssistant Sight."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.pyqt6.dashboard.widget_base import DashboardWidget
from gui.pyqt6.dashboard.widget_registry import get_widget_registry
from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.theme.widget_styles import BTN_ACTIVE, BTN_DEFAULT, CARD_STYLE

locale = get_locale_manager()

# Register built-in widgets
_registry = get_widget_registry()
_registry.register("device", locale.tr("widget_device", "Device Status"), locale.tr("widget_device_desc", "Shows device connection status"), None)
_registry.register("queue", locale.tr("widget_queue", "Queue Progress"), locale.tr("widget_queue_desc", "Shows queue execution progress"), None)
_registry.register("llm", locale.tr("widget_llm", "LLM Status"), locale.tr("widget_llm_desc", "Shows LLM service status"), None)
_registry.register("quick_actions", locale.tr("widget_quick_actions", "Quick Actions"), locale.tr("widget_quick_actions_desc", "Quick action buttons"), None)
_registry.register("recent_tasks", locale.tr("widget_recent_tasks", "Recent Tasks"), locale.tr("widget_recent_tasks_desc", "Shows recent task history"), None)
_registry.register("system_resource", locale.tr("widget_system_resource", "System Resources"), locale.tr("widget_system_resource_desc", "Shows CPU and memory usage"), None)


class DashboardPage(QWidget):
    """Customizable dashboard page with draggable widgets."""

    def __init__(self, bridge, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._grid_widgets: Dict[str, QWidget] = {}
        self._config_path = self._resolve_config_path()
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(2000)
        self._poll_timer.timeout.connect(self._poll_data)
        self._setup_ui()
        self._load_layout()
        self._poll_timer.start()

    def _resolve_config_path(self) -> Path:
        try:
            from core.foundation.paths import get_project_root
            return Path(get_project_root()) / "config" / "dashboard_layout.json"
        except Exception:
            return Path(__file__).resolve().parent.parent.parent.parent / "config" / "dashboard_layout.json"

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        content_root = QVBoxLayout(content)
        content_root.setContentsMargins(16, 16, 16, 16)
        content_root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(locale.tr("dashboard_title", "Dashboard"))
        title.setProperty("variant", "hero")
        header.addWidget(title)
        header.addStretch()

        customize_btn = QPushButton(locale.tr("dashboard_customize", "Customize"))
        customize_btn.setStyleSheet(BTN_DEFAULT)
        customize_btn.clicked.connect(self._save_layout)
        header.addWidget(customize_btn)

        add_widget_btn = QPushButton(locale.tr("dashboard_add_widget", "Add Widget"))
        add_widget_btn.setStyleSheet(BTN_ACTIVE)
        add_widget_btn.clicked.connect(self._open_widget_market)
        header.addWidget(add_widget_btn)
        content_root.addLayout(header)

        self._grid = QGridLayout()
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(0, 0, 0, 0)
        content_root.addLayout(self._grid)

    def _load_layout(self) -> None:
        if not self._config_path.exists():
            self._add_default_widgets()
            return
        try:
            data = json.loads(self._config_path.read_text(encoding="utf-8"))
        except Exception:
            self._add_default_widgets()
            return

        widgets = data.get("widgets", [])
        if not widgets:
            self._add_default_widgets()
            return

        for idx, entry in enumerate(widgets):
            widget_id = entry.get("id", "")
            row = entry.get("row", idx)
            col = entry.get("col", 0)
            title = entry.get("title", widget_id)
            widget = self._create_widget(widget_id, title)
            if widget is not None:
                self._grid.addWidget(widget, row, col)
                self._grid_widgets[widget_id] = widget
                if hasattr(widget, "fade_in"):
                    widget.fade_in(180)

    def _add_default_widgets(self) -> None:
        defaults = [
            ("device", 0, 0),
            ("queue", 0, 1),
            ("llm", 1, 0),
            ("quick_actions", 1, 1),
        ]
        for widget_id, row, col in defaults:
            title = widget_id.replace("_", " ").title()
            widget = self._create_widget(widget_id, title)
            if widget is not None:
                self._grid.addWidget(widget, row, col)
                self._grid_widgets[widget_id] = widget
                if hasattr(widget, "fade_in"):
                    widget.fade_in(180)

    def _create_widget(self, widget_id: str, title: str) -> Optional[QWidget]:
        if widget_id == "device":
            from gui.pyqt6.dashboard.widgets.device_status_widget import DeviceStatusWidget
            return DeviceStatusWidget(title, bridge=self._bridge)
        if widget_id == "queue":
            from gui.pyqt6.dashboard.widgets.queue_progress_widget import QueueProgressWidget
            return QueueProgressWidget(title, bridge=self._bridge)
        if widget_id == "llm":
            from gui.pyqt6.dashboard.widgets.llm_status_widget import LLMStatusWidget
            return LLMStatusWidget(title, bridge=self._bridge)
        if widget_id == "quick_actions":
            from gui.pyqt6.dashboard.widgets.quick_actions_widget import QuickActionsWidget
            return QuickActionsWidget(title, bridge=self._bridge)
        if widget_id == "recent_tasks":
            from gui.pyqt6.dashboard.widgets.recent_tasks_widget import RecentTasksWidget
            return RecentTasksWidget(title, bridge=self._bridge)
        if widget_id == "system_resource":
            from gui.pyqt6.dashboard.widgets.system_resource_widget import SystemResourceWidget
            return SystemResourceWidget(title, bridge=self._bridge)
        return None

    def _poll_data(self) -> None:
        """Poll bridge for data and update widgets."""
        # Poll device status
        device_widget = self._grid_widgets.get("device")
        if device_widget is not None:
            try:
                result = self._bridge.execute("device info")
                if result and result.get("status") == "success":
                    devices = result.get("devices") or []
                    device_widget.update_data(devices)
            except Exception:
                pass

        # Poll queue status
        queue_widget = self._grid_widgets.get("queue")
        if queue_widget is not None:
            try:
                result = self._bridge.execute("queue status")
                if result and result.get("status") == "success":
                    queue_widget.update_data(result)
            except Exception:
                pass

        # Poll LLM status
        llm_widget = self._grid_widgets.get("llm")
        if llm_widget is not None:
            try:
                result = self._bridge.execute("llm status")
                if result and result.get("status") == "success":
                    llm_widget.update_data(result)
            except Exception:
                pass

    def _save_layout(self) -> None:
        widgets = []
        for widget_id, widget in self._grid_widgets.items():
            index = self._grid.indexOf(widget)
            if index == -1:
                continue
            row, col, _, _ = self._grid.getItemPosition(index)
            widgets.append({
                "id": widget_id,
                "title": widget_id.replace("_", " ").title(),
                "row": row,
                "col": col,
            })
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(json.dumps({"widgets": widgets}, ensure_ascii=False, indent=2), encoding="utf-8")

    def _open_widget_market(self) -> None:
        from gui.pyqt6.dashboard.widget_market_dialog import WidgetMarketDialog
        dialog = WidgetMarketDialog(self._bridge, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            widget_id = dialog.selected_widget_id()
            if widget_id and widget_id not in self._grid_widgets:
                self._add_widget(widget_id)

    def _add_widget(self, widget_id: str) -> None:
        registry = get_widget_registry()
        info = registry.get_widget(widget_id)
        if info is None:
            return
        title = info["name"]
        widget = self._create_widget(widget_id, title)
        if widget is not None:
            # Find next available position
            row = self._grid.rowCount()
            col = 0
            self._grid.addWidget(widget, row, col)
            self._grid_widgets[widget_id] = widget
            self._save_layout()
            if hasattr(widget, "fade_in"):
                widget.fade_in()

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-dashboard-widget"):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-dashboard-widget"):
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasFormat("application/x-dashboard-widget"):
            event.ignore()
            return
        widget_id = event.mimeData().data("application/x-dashboard-widget").data().decode()
        widget = self._grid_widgets.get(widget_id)
        if widget is None:
            event.ignore()
            return

        # Find drop position
        pos = event.pos()
        drop_row = -1
        drop_col = -1
        for i in range(self._grid.count()):
            row, col, _, _ = self._grid.getItemPosition(i)
            item = self._grid.itemAt(i)
            if item and item.widget():
                rect = item.widget().geometry()
                if rect.contains(pos):
                    drop_row = row
                    drop_col = col
                    break

        if drop_row >= 0 and drop_col >= 0:
            # Remove from current position
            self._grid.removeWidget(widget)
            # Add at new position
            self._grid.addWidget(widget, drop_row, drop_col)
            self._save_layout()

        event.accept()
