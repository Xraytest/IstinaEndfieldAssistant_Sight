from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.theme.hero import HeroHeader
from gui.pyqt6.theme.widget_styles import BTN_ACTIVE, BTN_DEFAULT, CARD_STYLE, INPUT_STYLE, LOG_STYLE


class StatCard(QFrame):
    """状态卡片：标题 + 数值 + 状态指示器。"""

    def __init__(self, title: str, value: str, status: str = "normal", parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setProperty("variant", "secondary")
        layout.addWidget(title_label)

        self._value_label = QLabel(value)
        self._value_label.setProperty("variant", "hero")
        self._value_label.setStyleSheet("font-size: 22px;")
        layout.addWidget(self._value_label)

        self._status_label = QLabel(status)
        self._status_label.setProperty("variant", "success" if status == "正常" else "danger")
        layout.addWidget(self._status_label)

    def set_status(self, status: str) -> None:
        self._status_label.setText(status)
        variant = "success" if status == "正常" else "danger"
        self._status_label.setProperty("variant", variant)
        self.style().unpolish(self._status_label)
        self.style().polish(self._status_label)

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)


class PrtsFullIntelligencePage(QWidget):
    def __init__(self, bridge: CLIBridge, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._bridge = bridge
        self._bridge.commandFinished.connect(self._on_command_finished)
        self._setup_ui()
        self._refresh_status()

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

        header = HeroHeader("PRTS全智能", "自动化分析与智能决策控制台。", content)
        content_root.addWidget(header)

        # Status grid -------------------------------------------------------
        status_grid = QGridLayout()
        status_grid.setSpacing(10)
        status_grid.setContentsMargins(0, 0, 0, 0)

        self._device_card = StatCard("设备", "未连接", "离线")
        status_grid.addWidget(self._device_card, 0, 0)

        self._connection_card = StatCard("连接状态", "断开", "离线")
        status_grid.addWidget(self._connection_card, 0, 1)

        self._llm_card = StatCard("LLM 服务", "未知", "未知")
        status_grid.addWidget(self._llm_card, 0, 2)

        self._task_card = StatCard("今日任务", "0/20", "正常")
        status_grid.addWidget(self._task_card, 1, 0)

        self._runtime_card = StatCard("运行时", "空闲", "正常")
        status_grid.addWidget(self._runtime_card, 1, 1)

        self._queue_card = StatCard("队列", "0 项", "正常")
        status_grid.addWidget(self._queue_card, 1, 2)

        content_root.addLayout(status_grid)

        # Quick actions -----------------------------------------------------
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self._daily_btn = QPushButton("运行日常")
        self._daily_btn.setStyleSheet(BTN_ACTIVE)
        self._daily_btn.clicked.connect(lambda: self._bridge.execute("daily", {"options": {"preset": "DailyFull"}}))
        actions_row.addWidget(self._daily_btn)

        self._harvest_btn = QPushButton("运行收获")
        self._harvest_btn.setStyleSheet(BTN_DEFAULT)
        self._harvest_btn.clicked.connect(lambda: self._bridge.execute("harvest", {}))
        actions_row.addWidget(self._harvest_btn)

        self._analyze_btn = QPushButton("分析场景")
        self._analyze_btn.setStyleSheet(BTN_DEFAULT)
        self._analyze_btn.clicked.connect(self._run_analysis)
        actions_row.addWidget(self._analyze_btn)

        actions_row.addStretch()
        content_root.addLayout(actions_row)

        # Analysis controls -------------------------------------------------
        analysis_row = QHBoxLayout()
        analysis_row.setSpacing(8)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Full", "Quick", "Deep"])
        self._mode_combo.setStyleSheet(INPUT_STYLE)
        self._mode_combo.setMinimumWidth(120)
        analysis_row.addWidget(self._mode_combo)

        self._run_analysis_btn = QPushButton("运行分析")
        self._run_analysis_btn.setStyleSheet(BTN_DEFAULT)
        self._run_analysis_btn.clicked.connect(self._run_analysis)
        analysis_row.addWidget(self._run_analysis_btn)

        analysis_row.addStretch()
        content_root.addLayout(analysis_row)

        # Result viewer -----------------------------------------------------
        self._result_text = QTextEdit()
        self._result_text.setReadOnly(True)
        self._result_text.setStyleSheet(LOG_STYLE)
        content_root.addWidget(self._result_text, 1)

    def _run_analysis(self) -> None:
        mode = self._mode_combo.currentText()
        self._bridge.execute("analyze", {"options": {"mode": mode}})

    def _refresh_status(self) -> None:
        self._bridge.execute("system status", {})

    def _on_command_finished(self, command: str, result: dict) -> None:
        if command == "system status":
            self._update_status_cards(result)
        elif command == "analyze":
            self._result_text.setText(str(result))

    def _update_status_cards(self, result: dict) -> None:
        data = result.get("data", {}) if isinstance(result, dict) else {}
        device = data.get("device", {})
        connection = data.get("connection", {})
        llm = data.get("llm", {})

        self._device_card.set_status("在线" if device.get("connected") else "离线")
        self._device_card.set_value(device.get("serial", "未连接"))

        self._connection_card.set_status("已连接" if connection.get("maaend_ready") else "断开")
        self._connection_card.set_value(connection.get("address", "localhost:16512"))

        llm_status = "正常" if llm.get("enabled") else "未启用"
        self._llm_card.set_status(llm_status)
        self._llm_card.set_value(
            f"端口 {llm.get('port', 9998)}" if llm.get("enabled") else "未启用"
        )
