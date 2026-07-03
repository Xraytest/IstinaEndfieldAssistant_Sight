from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget, QStatusBar, QTabWidget

from core.foundation.paths import ensure_src_path
from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.pages.agent_page import AgentPage
from gui.pyqt6.pages.device_settings_page import DeviceSettingsPage
from gui.pyqt6.pages.maaend_control_page import MaaEndControlPage
from gui.pyqt6.pages.maaend_page import MaaEndPage
from gui.pyqt6.pages.prts_full_intelligence_page import PrtsFullIntelligencePage

ensure_src_path(__file__)


class MainWindow(QMainWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("IstinaEndfieldAssistant Sight")
        self._bridge = CLIBridge(self)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("IstinaEndfieldAssistant Sight - GUI ready")

        self._init_pages()
        self.resize(1280, 800)

    def _init_pages(self) -> None:
        tabs = QTabWidget()
        self.centralWidget().layout().addWidget(tabs)

        tabs.addTab(AgentPage(bridge=self._bridge), "Agent")
        tabs.addTab(DeviceSettingsPage(bridge=self._bridge), "Device")
        tabs.addTab(MaaEndPage(bridge=self._bridge), "MaaEnd")
        tabs.addTab(MaaEndControlPage(bridge=self._bridge), "控制台")
        tabs.addTab(PrtsFullIntelligencePage(bridge=self._bridge), "PRTS")

    def bridge(self) -> CLIBridge:
        return self._bridge
