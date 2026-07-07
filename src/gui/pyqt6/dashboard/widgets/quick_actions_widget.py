"""Quick actions dashboard widget."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from gui.pyqt6.dashboard.widget_base import DashboardWidget
from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.theme.icons import get_action_icon
from gui.pyqt6.theme.widget_styles import BTN_ACTIVE, BTN_DEFAULT

locale = get_locale_manager()


class QuickActionsWidget(DashboardWidget):
    """Quick action buttons."""

    def __init__(self, title: str, bridge, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, "quick_actions", parent)
        self._bridge = bridge
        content = self.content_widget()
        layout = QHBoxLayout(content)
        layout.setSpacing(6)

        daily_btn = QPushButton(locale.tr("btn_daily", "Run Daily"))
        daily_btn.setStyleSheet(BTN_ACTIVE)
        daily_btn.setIcon(get_action_icon("运行"))
        daily_btn.clicked.connect(lambda: bridge.execute("daily"))
        layout.addWidget(daily_btn)

        harvest_btn = QPushButton(locale.tr("btn_harvest", "Run Harvest"))
        harvest_btn.setStyleSheet(BTN_DEFAULT)
        harvest_btn.setIcon(get_action_icon("运行"))
        harvest_btn.clicked.connect(lambda: bridge.execute("harvest"))
        layout.addWidget(harvest_btn)

        analyze_btn = QPushButton(locale.tr("btn_analyze", "Analyze Scene"))
        analyze_btn.setStyleSheet(BTN_DEFAULT)
        analyze_btn.setIcon(get_action_icon("分析"))
        analyze_btn.clicked.connect(lambda: bridge.execute("analyze"))
        layout.addWidget(analyze_btn)
