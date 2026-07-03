from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.pyqt6.cli_bridge import CLIBridge


class AgentPage(QWidget):
    def __init__(self, bridge: CLIBridge, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._bridge = bridge
        self._bridge.commandFinished.connect(self._on_command_finished)
        self._bridge.logMessage.connect(self._on_log_message)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        root.addWidget(self._log_text)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        analyze_btn = QPushButton("Analyze")
        analyze_btn.clicked.connect(lambda: self._bridge.execute("analyze"))
        button_row.addWidget(analyze_btn)

        explore_btn = QPushButton("Explore")
        explore_btn.clicked.connect(lambda: self._bridge.execute("explore"))
        button_row.addWidget(explore_btn)

        daily_quest_btn = QPushButton("Daily Quest")
        daily_quest_btn.clicked.connect(lambda: self._bridge.execute("daily"))
        button_row.addWidget(daily_quest_btn)

        button_row.addStretch()
        root.addLayout(button_row)

    def _on_command_finished(self, command: str, result: dict) -> None:
        self.append_log(f"[{command}] {result}")

    def _on_log_message(self, source: str, message: str) -> None:
        self.append_log(f"[{source}] {message}")

    def append_log(self, message: str) -> None:
        self._log_text.append(message)
