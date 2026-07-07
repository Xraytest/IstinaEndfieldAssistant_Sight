"""Dashboard page with customizable widgets for IstinaEndfieldAssistant Sight."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
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
from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.theme.widget_styles import BTN_ACTIVE, BTN_DEFAULT, CARD_STYLE

locale = get_locale_manager()


class DashboardPage(QWidget):
    """Customizable dashboard page with draggable widgets."""

    def __init__(self, bridge, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._grid_widgets: Dict[str, QWidget] = {}
        self._config_path = self._resolve_config_path()
        self._setup_ui()
        self._load_layout()

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
        return None

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
