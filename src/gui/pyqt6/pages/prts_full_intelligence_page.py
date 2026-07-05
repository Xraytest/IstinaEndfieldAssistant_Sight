from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
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

        control_row = QHBoxLayout()
        control_row.setSpacing(8)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Full", "Quick", "Deep"])
        control_row.addWidget(self._mode_combo)

        run_btn = QPushButton("Run Analysis")
        run_btn.clicked.connect(self._run_analysis)
        control_row.addWidget(run_btn)

        control_row.addStretch()
        content_root.addLayout(control_row)

        self._result_text = QTextEdit()
        self._result_text.setReadOnly(True)
        content_root.addWidget(self._result_text)

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
