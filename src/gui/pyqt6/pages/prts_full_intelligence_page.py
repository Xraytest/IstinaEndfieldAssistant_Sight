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

from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.theme.hero import HeroHeader
from gui.pyqt6.theme.icons import get_action_icon
from gui.pyqt6.theme.widget_styles import BTN_ACTIVE, BTN_DEFAULT, CARD_STYLE, INPUT_STYLE, LOG_STYLE
from gui.pyqt6.responsive import LoadingOverlay


locale = get_locale_manager()


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
        variant = "success" if status == locale.tr("normal_status", "Normal") else "danger"
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

        header = HeroHeader(locale.tr("prts_title", "PRTS Intelligence"), locale.tr("prts_subtitle", "Automated analysis and intelligent decision console."), content)
        content_root.addWidget(header)

        # Skeleton status grid (shown before first data load) -------------
        self._skeleton_grid_widget = QWidget()
        self._skeleton_grid = QGridLayout(self._skeleton_grid_widget)
        self._skeleton_grid.setSpacing(10)
        self._skeleton_grid.setContentsMargins(0, 0, 0, 0)
        for i in range(6):
            self._skeleton_grid.addWidget(SkeletonCard(self._skeleton_grid_widget), i // 3, i % 3)
        content_root.addWidget(self._skeleton_grid_widget)

        # Real status grid (hidden until data arrives) ---------------------
        self._real_grid = QGridLayout()
        self._real_grid.setSpacing(10)
        self._real_grid.setContentsMargins(0, 0, 0, 0)

        self._device_card = StatCard(locale.tr("device_status", "Device"), locale.tr("offline", "Offline"), locale.tr("offline", "Offline"))
        self._device_card.setAccessibleName("设备状态卡片")
        self._device_card.setAccessibleDescription("显示设备连接状态和序列号")
        self._real_grid.addWidget(self._device_card, 0, 0)

        self._connection_card = StatCard(locale.tr("connection_status", "Connection"), locale.tr("offline", "Offline"), locale.tr("offline", "Offline"))
        self._connection_card.setAccessibleName("连接状态卡片")
        self._connection_card.setAccessibleDescription("显示与后端服务的连接状态")
        self._real_grid.addWidget(self._connection_card, 0, 1)

        self._llm_card = StatCard(locale.tr("llm_service", "LLM Service"), locale.tr("disabled_status", "Disabled"), locale.tr("disabled_status", "Disabled"))
        self._llm_card.setAccessibleName("LLM服务卡片")
        self._llm_card.setAccessibleDescription("显示大语言模型服务状态")
        self._real_grid.addWidget(self._llm_card, 0, 2)

        self._task_card = StatCard(locale.tr("today_tasks", "Today's Tasks"), "0/20", locale.tr("normal_status", "Normal"))
        self._task_card.setAccessibleName("今日任务卡片")
        self._task_card.setAccessibleDescription("显示今日任务完成进度")
        self._real_grid.addWidget(self._task_card, 1, 0)

        self._runtime_card = StatCard(locale.tr("runtime_status", "Runtime"), locale.tr("maaend_idle", "Idle"), locale.tr("normal_status", "Normal"))
        self._runtime_card.setAccessibleName("运行时卡片")
        self._runtime_card.setAccessibleDescription("显示当前运行时状态")
        self._real_grid.addWidget(self._runtime_card, 1, 1)

        self._queue_card = StatCard(locale.tr("queue_status", "Queue"), locale.tr("queue_count", "0 items"), locale.tr("normal_status", "Normal"))
        self._queue_card.setAccessibleName("队列状态卡片")
        self._queue_card.setAccessibleDescription("显示任务队列中的项目数量")
        self._real_grid.addWidget(self._queue_card, 1, 2)

        self._real_grid_widget = QWidget()
        self._real_grid_widget.setLayout(self._real_grid)
        self._real_grid_widget.hide()
        content_root.addWidget(self._real_grid_widget)

        # Quick actions -----------------------------------------------------
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self._daily_btn = QPushButton(locale.tr("btn_daily", "Run Daily"))
        self._daily_btn.setStyleSheet(BTN_ACTIVE)
        self._daily_btn.setIcon(get_action_icon("运行"))
        self._daily_btn.setAccessibleName(locale.tr("btn_daily", "Run Daily"))
        self._daily_btn.setAccessibleDescription(locale.tr("btn_daily", "Execute daily task automation flow"))
        self._daily_btn.clicked.connect(lambda: self._run_with_loading("daily", {"options": {"preset": "DailyFull"}}))
        actions_row.addWidget(self._daily_btn)

        self._harvest_btn = QPushButton(locale.tr("btn_harvest", "Run Harvest"))
        self._harvest_btn.setStyleSheet(BTN_DEFAULT)
        self._harvest_btn.setIcon(get_action_icon("运行"))
        self._harvest_btn.setAccessibleName(locale.tr("btn_harvest", "Run Harvest"))
        self._harvest_btn.setAccessibleDescription(locale.tr("btn_harvest", "Execute harvest task automation flow"))
        self._harvest_btn.clicked.connect(lambda: self._run_with_loading("harvest", {}))
        actions_row.addWidget(self._harvest_btn)

        self._analyze_btn = QPushButton(locale.tr("btn_analyze", "Analyze Scene"))
        self._analyze_btn.setStyleSheet(BTN_DEFAULT)
        self._analyze_btn.setIcon(get_action_icon("分析"))
        self._analyze_btn.setAccessibleName(locale.tr("btn_analyze", "Analyze Scene"))
        self._analyze_btn.setAccessibleDescription(locale.tr("btn_analyze", "Run scene analysis task"))
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
        self._mode_combo.setAccessibleName(locale.tr("analysis_mode", "Analysis Mode"))
        self._mode_combo.setAccessibleDescription(locale.tr("analysis_mode", "Analysis Mode") + ": Full, Quick, Deep")
        analysis_row.addWidget(self._mode_combo)

        self._run_analysis_btn = QPushButton(locale.tr("btn_run_analysis", "Run Analysis"))
        self._run_analysis_btn.setStyleSheet(BTN_DEFAULT)
        self._run_analysis_btn.setIcon(get_action_icon("分析"))
        self._run_analysis_btn.setAccessibleName(locale.tr("btn_run_analysis", "Run Analysis"))
        self._run_analysis_btn.setAccessibleDescription(locale.tr("btn_run_analysis", "Run scene analysis with selected mode"))
        self._run_analysis_btn.clicked.connect(self._run_analysis)
        analysis_row.addWidget(self._run_analysis_btn)

        analysis_row.addStretch()
        content_root.addLayout(analysis_row)

        # Result viewer -----------------------------------------------------
        self._result_text = QTextEdit()
        self._result_text.setReadOnly(True)
        self._result_text.setStyleSheet(LOG_STYLE)
        content_root.addWidget(self._result_text, 1)

        # Loading overlay ---------------------------------------------------
        self._loading = LoadingOverlay(self, text=locale.tr("task_running", "Task running..."))
        self._loading.hide()

    def _run_with_loading(self, command: str, params: dict) -> None:
        self._loading.show()
        self._bridge.execute(command, params)

    def _run_analysis(self) -> None:
        mode = self._mode_combo.currentText()
        self._loading.show()
        self._bridge.execute("analyze", {"options": {"mode": mode}})

    def _refresh_status(self) -> None:
        self._bridge.execute("system status", {})

    def _on_command_finished(self, command: str, result: dict) -> None:
        self._loading.hide()
        if command == "system status":
            self._update_status_cards(result)
        elif command == "analyze":
            self._result_text.setText(str(result))

    def _update_status_cards(self, result: dict) -> None:
        if self._skeleton_grid_widget.isVisible():
            self._skeleton_grid_widget.hide()
            self._real_grid_widget.show()
        data = result.get("data", {}) if isinstance(result, dict) else {}
        device = data.get("device", {})
        connection = data.get("connection", {})
        llm = data.get("llm", {})

        self._device_card.set_status(locale.tr("online" if device.get("connected") else "offline", "Online" if device.get("connected") else "Offline"))
        self._device_card.set_value(device.get("serial", locale.tr("offline", "Offline")))

        self._connection_card.set_status(locale.tr("connection_ok" if connection.get("maaend_ready") else "connection_disconnected", "Connected" if connection.get("maaend_ready") else "Disconnected"))
        self._connection_card.set_value(connection.get("address", locale.tr("connection_status", "Connection")))

        llm_status = "normal_status" if llm.get("enabled") else "disabled_status"
        self._llm_card.set_status(locale.tr(llm_status, "Normal" if llm.get("enabled") else "Disabled"))
        self._llm_card.set_value(
            (locale.tr("port", "Port") + f" {llm.get('port', 9998)}") if llm.get("enabled") else locale.tr("disabled_status", "Disabled")
        )
