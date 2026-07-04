from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.pyqt6.cli_bridge import CLIBridge


class PrtsFullIntelligencePage(QWidget):
    def __init__(self, bridge: CLIBridge, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._bridge = bridge
        self._bridge.commandFinished.connect(self._on_command_finished)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        control_row = QHBoxLayout()
        control_row.setSpacing(8)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Full", "Quick", "Deep"])
        control_row.addWidget(self._mode_combo)

        run_btn = QPushButton("Run Analysis")
        run_btn.clicked.connect(self._run_analysis)
        control_row.addWidget(run_btn)

        control_row.addStretch()
        root.addLayout(control_row)

        self._result_text = QTextEdit()
        self._result_text.setReadOnly(True)
        root.addWidget(self._result_text)

    def _run_analysis(self) -> None:
        mode = self._mode_combo.currentText()
        self._bridge.execute("analyze", {"options": {"mode": mode}})

    def _on_command_finished(self, command: str, result: dict) -> None:
        if command == "analyze":
            self._result_text.setText(str(result))

    def set_analysis_mode(self, mode: str) -> None:
        index = self._mode_combo.findText(mode)
        if index >= 0:
            self._mode_combo.setCurrentIndex(index)
