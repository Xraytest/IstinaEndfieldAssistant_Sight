"""Placeholder page for legacy MaaEndPage.

The old MaaEndPage entrypoint has been superseded by MaaEndControlPage.
This file preserves the page slot for MainWindow while routing all
functionality through the unified CLIBridge.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QVBoxLayout, QWidget

from gui.pyqt6.cli_bridge import CLIBridge


class MaaEndPage(QWidget):
    def __init__(self, bridge: CLIBridge, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._bridge = bridge
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
