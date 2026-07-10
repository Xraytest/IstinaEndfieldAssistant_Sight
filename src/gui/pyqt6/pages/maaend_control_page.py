"""Standard Reasoning control panel: task list, preset list, task queue, option editor, preview, log viewer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QEventLoop,
    QPropertyAnimation,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QShowEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.foundation.logger import LogCategory, get_logger
from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.queue_state import QueueState
from gui.pyqt6.theme.widget_styles import (
    BLUE_STYLE,
    BTN_ACTIVE,
    BTN_DEFAULT,
    BTN_STOP,
    CARD_STYLE,
    CHECK_STYLE,
    COMBO_STYLE,
    HEADER_STYLE,
    INFO_STYLE,
    INPUT_STYLE,
    LIST_STYLE,
    LOG_STYLE,
    PROGRESS_BAR_STYLE,
    RED_STYLE,
    SCROLL_AREA_TRANSPARENT_STYLE,
    SPLITTER_HANDLE_STYLE,
    TABLE_STYLE,
    VAL_STYLE,
)

locale = get_locale_manager()

NAME_ZH = {
    # presets
    "DailyFull": "全套日常",
    "QuickDaily": "快速日常",
    "RealtimeAssist": "实时辅助",
    # tasks from interface.json imports
    "SellProduct": "🛒售卖产品",
    "SeizeDeliveryJobs": "🏍️抢委托送货",
    "DeliveryJobs": "🚚转交委托",
    "AutoStockpile": "📦自动囤货",
    "AutoStockStaple": "🏪购买稳定物资",
    "AutoSell": "💰售卖弹性物资",
    "EnvironmentMonitoring": "🌿环境监测",
    "GearAssembly": "🔧装备制造",
    "Weapon": "🔫升级武器",
    "BatchUseDetector": "🧭批量探测器",
    "EssenceFilter": "🔒基质筛选锁定",
    "ResourceRecycleStation": "🦉资源回收站",
    "AutoCollect": "🧺自动采集",
    "AutoEcoFarm": "🌾生态农场",
    "PuzzleSolver": "🧩解拼图",
    "ImportBluePrints": "📐一键导入蓝图",
    "AutoUseSpMedication": "💊应急理智加强剂",
    "AutoEssence": "🎱基质刷取",
    "ProtocolSpace": "⚔️协议空间",
    "DijiangRewards": "🎁基建任务",
    "VisitFriends": "🤝拜访好友",
    "GiftOperator": "🎁赠送干员礼物",
    "BatchAddFriends": "👥批量添加好友",
    "PullCountCalculator": "🧮抽数计算",
    "BakerEntry": "💬会话消息嘴替",
    "ReadAllWiki": "📖百科已读",
    "DailyRewards": "📅日常奖励领取",
    "ClaimSimulationRewards": "📦领取模拟空间奖励",
    "TrialOfSwordmancy": "🗡️选剑演武",
    "CreditShopping": "🛍️信用点购物",
    "AccountSwitch": "自动切换账号",
    "WebEvent202605": "🎁自动共贺庆典网页活动",
    "AndroidOpenGame": "🎮打开游戏",
    "CloseGame": "❌关闭游戏",
    "RealTimeTask": "🤖实时开荒辅助",
    "ItemTransfer": "🐌库存转移",
    "Crafting": "🧪简易制作",
    "SimpleProductionBatchStart": "🔨批量简易制作",
    "ReceiveProdManual": "🌾简制手册领取",
    "StashBackpack": "🎒存放背包",
}


def _zh(name: str) -> str:
    if not name:
        return name
    return NAME_ZH.get(name, name)


_OPTION_LOCALE_PATH = Path(__file__).resolve().parent.parent.parent.parent.parent / "3rd-part" / "maaend" / "locales" / "interface" / "zh_cn.json"
OPTION_LOCALE: Dict[str, str] = {}
try:
    if _OPTION_LOCALE_PATH.exists():
        OPTION_LOCALE = json.loads(_OPTION_LOCALE_PATH.read_text(encoding="utf-8"))
except Exception:
    OPTION_LOCALE = {}


def _resolve_label(raw: Any) -> str:
    if not isinstance(raw, str):
        return str(raw)
    if raw.startswith("$"):
        return OPTION_LOCALE.get(raw.lstrip("$"), raw)
    return raw


class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, cases: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        if not cases:
            cases = [{"name": "Yes"}, {"name": "No"}]
        self._cases = cases
        self._on_name = str(cases[0].get("name", ""))
        self._off_name = str(cases[-1].get("name", ""))
        self._checked = False
        self._hover = False
        self.setFixedSize(40, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        if self._checked != checked:
            self._checked = checked
            self.update()
            self.toggled.emit(checked)

    def value(self) -> str:
        return self._on_name if self._checked else self._off_name

    def setValue(self, name: str) -> None:
        self.setChecked(str(name) == self._on_name)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QPainter, QPainterPath

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        corner_radius = 4

        # Outer border: fixed gray-white, no state change
        outer_path = QPainterPath()
        outer_path.addRoundedRect(QRectF(0, 0, w, h), corner_radius, corner_radius)
        painter.fillPath(outer_path, QColor("#d8d8d8"))

        # Inner gap: background color shows through, creating a ring effect
        gap = 2
        inner_gap_path = QPainterPath()
        inner_gap_path.addRoundedRect(QRectF(gap, gap, w - gap * 2, h - gap * 2), corner_radius - gap, corner_radius - gap)
        painter.fillPath(inner_gap_path, QColor("#1a1a2e"))

        # Inner track: translucent color based on state
        inner_gap = 1
        inner_path = QPainterPath()
        inner_path.addRoundedRect(QRectF(gap + inner_gap, gap + inner_gap, w - (gap + inner_gap) * 2, h - (gap + inner_gap) * 2), corner_radius - gap - inner_gap, corner_radius - gap - inner_gap)

        if self._checked:
            track_color = QColor(25, 209, 255, 45)
            if self._hover:
                track_color = QColor(25, 209, 255, 70)
        else:
            track_color = QColor(255, 255, 255, 10)
            if self._hover:
                track_color = QColor(255, 255, 255, 18)

        painter.fillPath(inner_path, track_color)

        # Slider: rounded square with subtle corners
        slider_margin = 3
        slider_size = h - (slider_margin * 2)
        slider_radius = 3
        slider_x = w - slider_size - slider_margin if self._checked else slider_margin
        slider_rect = QRectF(slider_x, slider_margin, slider_size, slider_size)
        slider_path = QPainterPath()
        slider_path.addRoundedRect(slider_rect, slider_radius, slider_radius)

        if self._checked:
            slider_color = QColor(25, 209, 255, 245)
            if self._hover:
                slider_color = QColor(25, 209, 255, 255)
        else:
            slider_color = QColor(220, 225, 235, 240)
            if self._hover:
                slider_color = QColor(240, 245, 250, 255)

        painter.fillPath(slider_path, slider_color)


class MaaEndControlPage(QWidget):
    execution_state_changed = pyqtSignal(bool)
    log_message = pyqtSignal(str, str)
    queue_item_status_changed = pyqtSignal(int, str)
    progress_changed = pyqtSignal(int, str)

    def __init__(self, bridge: CLIBridge, parent=None):
        super().__init__(parent)
        self._bridge = bridge
        self._logger = get_logger(__name__)
        self._selected_task: Optional[str] = None
        self._selected_preset: Optional[str] = None
        self._focused_queue_index: Optional[int] = None
        self._option_widgets: Dict[str, QWidget] = {}
        self._is_executing = False
        self._worker: Optional[TaskRunWorker] = None
        self._connected = False
        self._tasks_cache: Dict[str, Dict[str, Any]] = {}
        self._presets_cache: Dict[str, Dict[str, Any]] = {}
        self._task_option_defs: Dict[str, Dict[str, Any]] = {}
        self._queue_state = QueueState()
        self._state_path = self._queue_state.state_path
        self._auto_retry_enabled = True
        self._max_retries = 3
        self._retry_delay_ms = 2000
        self._metadata_cache_path = self._resolve_metadata_cache_path()
        self._load_metadata_cache()
        self._setup_ui()
        font = QFont("Microsoft YaHei UI")
        self.setFont(font)
        for widget_name in ("_status_label", "_apply_preset_to_queue_btn", "_log_text"):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.setFont(font)
        self._auto_connect_attempted = False
        # 延迟初始化：先尝试自动连接，再刷新列表，避免在 __init__ 中启动嵌套 QEventLoop
        QTimer.singleShot(0, self._delayed_init)
        self._queue_state.load()
        self._selected_task = self._queue_state.selected_task
        self._selected_preset = self._queue_state.selected_preset
        self._restore_queue_ui()
        self.log_message.connect(self._append_log)
        self._bridge.logMessage.connect(self._append_log)
        self.queue_item_status_changed.connect(self._on_queue_item_status_changed)
        self.progress_changed.connect(self._on_progress_changed)


    def _refresh_queue_list(self) -> None:
        for row in range(self._queue_list.rowCount()):
            item = self._queue_list.item(row, 0)
            if not item:
                continue
            entry = self._queue_state.get_queue_item(row)
            if not entry:
                continue
            item.setText(self._format_queue_label(entry.get("name", ""), entry.get("type", "task"), entry.get("options") or {}))

    def _restore_queue_ui(self) -> None:
        self._focused_queue_index = None
        self._queue_list.setRowCount(0)
        for entry in self._queue_state.queue_items:
            row = self._queue_list.rowCount()
            self._queue_list.insertRow(row)
            self._queue_list.setItem(row, 0, QTableWidgetItem(self._format_queue_label(entry.get("name", ""), entry.get("type", "task"), entry.get("options") or {})))

    # ------------------------------------------------------------------
    # bridge compatibility
    # ------------------------------------------------------------------
    def set_bridge(self, bridge: CLIBridge) -> None:
        self._bridge = bridge
        self.refresh()

    def _sync_execute(self, command: str, params: Optional[Dict[str, Any]] = None, timeout_ms: int = 300000) -> Optional[dict]:
        self._logger.debug(LogCategory.GUI, "_sync_execute 开始", command=command, timeout_ms=timeout_ms)
        loop = QEventLoop()
        result = None
        expected = command.split()
        timed_out = False

        def _on_finished(cmd: str, res: dict):
            nonlocal result
            if cmd.split()[: len(expected)] == expected:
                result = res
                loop.quit()

        self._bridge.commandFinished.connect(_on_finished)
        self._bridge.execute(command, params or {})
        QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec()
        timed_out = result is None
        self._bridge.commandFinished.disconnect(_on_finished)
        self._logger.debug(LogCategory.GUI, "_sync_execute 结束", command=command, timed_out=timed_out, result_type=type(result).__name__)
        return result

    def _resolve_connect_params(self) -> Dict[str, Any]:
        try:
            from core.foundation.paths import get_project_root

            config_path = Path(get_project_root()) / "config" / "client_config.json"
            if config_path.is_file():
                data = json.loads(config_path.read_text(encoding="utf-8"))
                serial = (((data.get("device") or {}).get("last_connected")) or ((data.get("device") or {}).get("serial")))
                if serial:
                    return {"serial": serial}
        except Exception:
            pass
        return {}

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel(locale.tr("maaend_console", "// Standard Inference Console"))
        title.setStyleSheet(HEADER_STYLE)
        header.addWidget(title)
        header.addStretch()
        self._status_label = QLabel(locale.tr("maaend_idle", "Idle"))
        self._status_label.setStyleSheet(BLUE_STYLE)
        header.addWidget(self._status_label)
        root.addLayout(header)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter = main_splitter
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setStyleSheet(SPLITTER_HANDLE_STYLE)

        # Column 1: Tasks -----------------------------------------------
        tasks_col = QWidget()
        self._tasks_col = tasks_col
        tasks_layout = QVBoxLayout(tasks_col)
        tasks_layout.setContentsMargins(0, 0, 0, 0)
        tasks_layout.setSpacing(10)

        task_card = QGroupBox(locale.tr("task_card", "Task"))
        task_card.setStyleSheet(CARD_STYLE)
        task_layout = QVBoxLayout(task_card)
        task_layout.setContentsMargins(2, 2, 2, 2)
        task_layout.setSpacing(2)
        self._task_list = QListWidget()
        self._task_list.setStyleSheet(LIST_STYLE)
        self._task_list.setMinimumHeight(80)
        self._task_list.itemSelectionChanged.connect(self._on_task_selected)
        self._task_list.itemDoubleClicked.connect(lambda item: self._add_to_queue())
        self._task_list.setDragEnabled(True)
        self._task_list.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        task_layout.addWidget(self._task_list, 1)

        tasks_layout.addWidget(task_card)
        tasks_col.setMinimumWidth(220)

        # Column 2: Options ---------------------------------------------
        options_col = QWidget()
        self._options_col = options_col
        options_layout = QVBoxLayout(options_col)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(10)

        option_card = QGroupBox(locale.tr("option_card", "Options"))
        option_card.setStyleSheet(CARD_STYLE)
        option_layout = QVBoxLayout(option_card)
        option_layout.setContentsMargins(2, 2, 2, 2)
        option_layout.setSpacing(2)
        self._option_scroll = QScrollArea()
        self._option_scroll.setWidgetResizable(True)
        self._option_scroll.setStyleSheet(SCROLL_AREA_TRANSPARENT_STYLE)
        self._option_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._option_container = QWidget()
        self._option_form = QVBoxLayout(self._option_container)
        self._option_form.setContentsMargins(0, 0, 0, 0)
        self._option_form.setSpacing(4)
        self._option_scroll.setWidget(self._option_container)
        option_layout.addWidget(self._option_scroll)
        option_btn_row = QHBoxLayout()
        option_btn_row.setContentsMargins(0, 0, 0, 0)
        option_btn_row.setSpacing(6)
        option_btn_row.addStretch()
        option_layout.addLayout(option_btn_row)
        options_layout.addWidget(option_card)
        options_col.setMinimumWidth(240)

        # Column 3: Right (Presets | Queue | Preview | SimpleLog) -------
        right_col = QWidget()
        self._right_col = right_col
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        right_vsplitter = QSplitter(Qt.Orientation.Vertical)
        self._right_vsplitter = right_vsplitter
        right_vsplitter.setChildrenCollapsible(False)
        right_vsplitter.setStyleSheet(SPLITTER_HANDLE_STYLE)

        # Presets
        preset_card = QGroupBox(locale.tr("preset_card", "Presets"))
        preset_card.setStyleSheet(CARD_STYLE)
        preset_layout = QVBoxLayout(preset_card)
        preset_layout.setContentsMargins(2, 2, 2, 2)
        preset_layout.setSpacing(2)
        self._preset_list = QListWidget()
        self._preset_list.setStyleSheet(LIST_STYLE)
        self._preset_list.setMinimumHeight(60)
        self._preset_list.itemSelectionChanged.connect(self._on_preset_selected)
        preset_layout.addWidget(self._preset_list)
        preset_btn_row = QHBoxLayout()
        preset_btn_row.setContentsMargins(0, 0, 0, 0)
        preset_btn_row.setSpacing(6)
        self._apply_preset_to_queue_btn = QPushButton(locale.tr("btn_apply_preset", "Apply Preset"))
        self._apply_preset_to_queue_btn.setStyleSheet(BTN_ACTIVE)
        self._apply_preset_to_queue_btn.clicked.connect(self._apply_preset_to_queue)
        preset_btn_row.addWidget(self._apply_preset_to_queue_btn)
        preset_btn_row.addStretch()
        preset_layout.addLayout(preset_btn_row)
        right_vsplitter.addWidget(preset_card)

        # Queue
        queue_card = QGroupBox(locale.tr("queue_card", "Queue"))
        queue_card.setStyleSheet(CARD_STYLE)
        queue_layout = QVBoxLayout(queue_card)
        queue_layout.setContentsMargins(2, 2, 2, 2)
        queue_layout.setSpacing(2)
        self._queue_list = QTableWidget()
        self._queue_list.setColumnCount(1)
        self._queue_list.horizontalHeader().setVisible(False)
        self._queue_list.horizontalHeader().setStretchLastSection(True)
        self._queue_list.verticalHeader().setVisible(False)
        self._queue_list.setStyleSheet(TABLE_STYLE)
        self._queue_list.setMinimumHeight(60)
        self._queue_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._queue_list.setAcceptDrops(True)
        self._queue_list.setDropIndicatorShown(True)
        self._queue_list.installEventFilter(self)
        self._queue_list.selectionModel().currentChanged.connect(lambda current, previous: self._on_queue_focus_changed(current.row()))
        queue_layout.addWidget(self._queue_list)
        queue_btn_row = QHBoxLayout()
        queue_btn_row.setContentsMargins(0, 0, 0, 0)
        queue_btn_row.setSpacing(6)
        self._add_queue_btn = QPushButton(locale.tr("btn_add", "Add"))
        self._add_queue_btn.setStyleSheet(BTN_DEFAULT)
        self._add_queue_btn.clicked.connect(self._add_to_queue)
        queue_btn_row.addWidget(self._add_queue_btn)
        self._run_queue_btn = QPushButton(locale.tr("btn_run", "Run"))
        self._run_queue_btn.setStyleSheet(BTN_ACTIVE)
        self._run_queue_btn.clicked.connect(self._run_queue)
        queue_btn_row.addWidget(self._run_queue_btn)
        queue_btn_row.addStretch()
        queue_layout.addLayout(queue_btn_row)
        queue_move_row = QHBoxLayout()
        queue_move_row.setContentsMargins(0, 0, 0, 0)
        queue_move_row.setSpacing(6)
        self._queue_up_btn = QPushButton(locale.tr("btn_up", "Move Up"))
        self._queue_up_btn.setStyleSheet(BTN_DEFAULT)
        self._queue_up_btn.clicked.connect(self._queue_move_up)
        queue_move_row.addWidget(self._queue_up_btn)
        self._queue_down_btn = QPushButton(locale.tr("btn_down", "Move Down"))
        self._queue_down_btn.setStyleSheet(BTN_DEFAULT)
        self._queue_down_btn.clicked.connect(self._queue_move_down)
        queue_move_row.addWidget(self._queue_down_btn)
        self._queue_clear_btn = QPushButton(locale.tr("btn_clear", "Clear"))
        self._queue_clear_btn.setStyleSheet(BTN_DEFAULT)
        self._queue_clear_btn.clicked.connect(self._queue_clear)
        queue_move_row.addWidget(self._queue_clear_btn)
        self._export_queue_btn = QPushButton(locale.tr("btn_export", "Export"))
        self._export_queue_btn.setStyleSheet(BTN_DEFAULT)
        self._export_queue_btn.clicked.connect(self._export_queue)
        queue_move_row.addWidget(self._export_queue_btn)
        self._import_queue_btn = QPushButton(locale.tr("btn_import", "Import"))
        self._import_queue_btn.setStyleSheet(BTN_DEFAULT)
        self._import_queue_btn.clicked.connect(self._import_queue)
        queue_move_row.addWidget(self._import_queue_btn)
        queue_move_row.addStretch()
        queue_layout.addLayout(queue_move_row)
        right_vsplitter.addWidget(queue_card)

        # SimpleLog
        log_card = QGroupBox(locale.tr("log_card", "Execution Log"))
        log_card.setStyleSheet(CARD_STYLE)
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(2, 2, 2, 2)
        log_layout.setSpacing(2)
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setStyleSheet(LOG_STYLE)
        log_layout.addWidget(self._log_text)
        log_btn_row = QHBoxLayout()
        log_btn_row.setContentsMargins(0, 0, 0, 0)
        log_btn_row.setSpacing(4)
        self._clear_log_btn = QPushButton(locale.tr("btn_clear", "Clear"))
        self._clear_log_btn.setStyleSheet(BTN_DEFAULT)
        self._clear_log_btn.clicked.connect(self._log_text.clear)
        log_btn_row.addWidget(self._clear_log_btn)
        self._log_filter_combo = QComboBox()
        self._log_filter_combo.addItems([locale.tr("log_filter_all", "All"), locale.tr("log_filter_info", "Info"), locale.tr("log_filter_warning", "Warning"), locale.tr("log_filter_error", "Error")])
        self._log_filter_combo.setStyleSheet(COMBO_STYLE)
        self._log_filter_combo.currentIndexChanged.connect(self._apply_log_filter)
        log_btn_row.addWidget(self._log_filter_combo)
        log_btn_row.addStretch()
        log_layout.addLayout(log_btn_row)
        right_vsplitter.addWidget(log_card)

        right_layout.addWidget(right_vsplitter)

        main_splitter.addWidget(tasks_col)
        main_splitter.addWidget(options_col)
        main_splitter.addWidget(right_col)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 3)
        main_splitter.setStretchFactor(2, 5)
        root.addWidget(main_splitter, 1)

        # BOTTOM -------------------------------------------------------
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.addSpacing(4)
        self._stop_btn = QPushButton(locale.tr("btn_stop", "Stop"))
        self._stop_btn.setStyleSheet(BTN_STOP)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_execution)
        bottom.addWidget(self._stop_btn)
        self._retry_btn = QPushButton(locale.tr("btn_retry", "Retry"))
        self._retry_btn.setStyleSheet(BTN_DEFAULT)
        self._retry_btn.setEnabled(False)
        self._retry_btn.clicked.connect(self._retry_failed)
        bottom.addWidget(self._retry_btn)
        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setMinimumHeight(16)
        self._progress_bar.setMaximumWidth(200)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setStyleSheet(PROGRESS_BAR_STYLE)
        self._progress_bar.setVisible(False)
        bottom.addWidget(self._progress_bar, 1)
        root.addLayout(bottom)

        font = QFont("Microsoft YaHei UI")
        for widget in (
            title,
            self._status_label,
            self._apply_preset_to_queue_btn,
            self._add_queue_btn,
            self._run_queue_btn,
            self._queue_up_btn,
            self._queue_down_btn,
            self._queue_clear_btn,
            self._clear_log_btn,
            self._log_text,
        ):
            widget.setFont(font)

        self._sync_layout_geometry()

    # ------------------------------------------------------------------
    # task / preset list helpers
    # ------------------------------------------------------------------
    def _refresh_task_list(self):
        selected_before = self._selected_task
        loaded = False
        if not self._tasks_cache:
            result = self._sync_execute("metadata list", timeout_ms=10000)
            if result and result.get("status") == "success":
                self._tasks_cache = result.get("tasks") or {}
                self._task_option_defs = result.get("task_option_defs") or {}
                self._presets_cache = result.get("presets") or {}
                self._persist_metadata_cache()
                loaded = True
        else:
            loaded = True

        if loaded:
            self._task_list.clear()
            for name in sorted(self._tasks_cache.keys()):
                item = QListWidgetItem(_zh(name))
                item.setData(Qt.ItemDataRole.UserRole, name)
                self._task_list.addItem(item)
            if selected_before and selected_before in self._tasks_cache:
                matches = self._task_list.findItems(_zh(selected_before), Qt.MatchFlag.MatchExactly)
                if matches:
                    self._task_list.setCurrentItem(matches[0])
            if selected_before and not self._task_list.currentItem():
                self._selected_task = selected_before

    def _refresh_preset_list(self):
        selected_before = self._selected_preset
        loaded = False
        if not self._presets_cache:
            result = self._sync_execute("metadata list", timeout_ms=10000)
            if result and result.get("status") == "success":
                self._tasks_cache = result.get("tasks") or {}
                self._task_option_defs = result.get("task_option_defs") or {}
                self._presets_cache = result.get("presets") or {}
                self._persist_metadata_cache()
                loaded = True
        else:
            loaded = True

        if loaded:
            self._preset_list.clear()
            for name in sorted(self._presets_cache.keys()):
                item = QListWidgetItem(_zh(name))
                item.setData(Qt.ItemDataRole.UserRole, name)
                self._preset_list.addItem(item)
            if selected_before and selected_before in self._presets_cache:
                matches = self._preset_list.findItems(_zh(selected_before), Qt.MatchFlag.MatchExactly)
                if matches:
                    self._preset_list.setCurrentItem(matches[0])
            if selected_before and not self._preset_list.currentItem():
                self._selected_preset = selected_before

    def _on_task_selected(self):
        items = self._task_list.selectedItems()
        self._selected_task = items[0].data(Qt.ItemDataRole.UserRole) if items else None
        self._focused_queue_index = None
        self._build_option_editor()
        self._persist_state()

    def _on_preset_selected(self):
        items = self._preset_list.selectedItems()
        self._selected_preset = items[0].data(Qt.ItemDataRole.UserRole) if items else None
        self._focused_queue_index = None
        self._persist_state()

    # ------------------------------------------------------------------
    # queue helpers
    # ------------------------------------------------------------------
    def _add_to_queue(self):
        if self._selected_preset:
            preset = self._presets_cache.get(self._selected_preset)
            if not preset:
                QMessageBox.warning(self, locale.tr("preset_not_found", "Preset Not Found"), locale.tr("preset_not_found_msg", "Preset '{preset}' not found.").format(preset=self._selected_preset))
                return
            task_list = preset.get("task", [])
            if not task_list:
                QMessageBox.information(self, locale.tr("preset_empty", "Preset Is Empty"), locale.tr("preset_empty_msg", "Preset '{preset}' has no tasks.").format(preset=self._selected_preset))
                return
            # 添加预设到队列 = 覆盖现有队列（清空再填充），不是追加；与 runtime.apply_preset 共享同一覆盖语义。
            for entry in list(self._queue_state.queue_items):
                name = entry.get("name")
                if name:
                    self._queue_state.clear_saved_options(name)
            items = []
            for task_entry in task_list:
                name, inline_options = self._normalize_task_entry(task_entry)
                options = task_entry.get("option") or {}
                if inline_options:
                    options = {**dict(options), **inline_options}
                saved = self._queue_state.load_options(name)
                if saved:
                    current_options = dict(options)
                    options = dict(saved)
                    options.update(current_options)
                self._queue_state.save_options(name, options)
                items.append({"name": name, "display_name": name, "type": "task", "options": dict(options)})
            self._queue_state.set_queue_items(items)
            self._restore_queue_ui()
            self._append_log("预设", locale.tr("btn_apply_preset", "Applied preset '{name}' ({count} tasks)").format(name=_zh(self._selected_preset), count=len(task_list)))
            self._queue_state.persist()
        elif self._selected_task:
            name = self._selected_task
            item_type = "task"
            # 以当前编辑器值为准生成新实例，不再继承/合并被污染的共享 task_options 快照
            options = self._collect_options()
            entry = {"name": name, "display_name": name, "type": item_type, "options": dict(options)}
            items = self._queue_state.queue_items + [entry]
            self._queue_state.set_queue_items(items)
            self._restore_queue_ui()
            self._queue_state.persist()
        else:
            QMessageBox.information(self, locale.tr("select_task_or_preset", "Please select a task or preset first."), locale.tr("select_task_or_preset", "Please select a task or preset first."))

    def _queue_move_up(self):
        row = self._queue_list.currentRow()
        if row <= 0:
            return
        items = self._queue_state.queue_items
        items[row], items[row - 1] = items[row - 1], items[row]
        self._queue_state.set_queue_items(items)
        self._restore_queue_ui()
        self._queue_list.setCurrentCell(row - 1, 0)
        self._queue_state.persist()

    def _queue_move_down(self):
        row = self._queue_list.currentRow()
        if row < 0 or row >= self._queue_list.rowCount() - 1:
            return
        items = self._queue_state.queue_items
        items[row], items[row + 1] = items[row + 1], items[row]
        self._queue_state.set_queue_items(items)
        self._restore_queue_ui()
        self._queue_list.setCurrentCell(row + 1, 0)
        self._queue_state.persist()

    def _queue_clear(self):
        for entry in list(self._queue_state.queue_items):
            name = entry.get("name")
            if name:
                self._queue_state.clear_saved_options(name)
        self._queue_state.clear_queue()
        self._restore_queue_ui()
        self._queue_state.persist()

    def _export_queue(self) -> None:
        if not self._queue_state.queue_items:
            QMessageBox.information(self, locale.tr("queue_empty", "Queue Empty"), locale.tr("queue_empty_msg", "The queue is empty."))
            return
        path, _ = QFileDialog.getSaveFileName(self, locale.tr("export_queue", "Export Queue"), "queue_preset.json", "JSON (*.json)")
        if not path:
            return
        try:
            data = {
                "version": 1,
                "queue_items": self._queue_state.queue_items,
                "task_options": self._queue_state.saved_task_options,
            }
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            QMessageBox.information(self, locale.tr("export_success", "Export Successful"), locale.tr("export_success_msg", "Queue exported to {path}").format(path=path))
        except Exception as exc:
            QMessageBox.warning(self, locale.tr("export_failed", "Export Failed"), str(exc))

    def _import_queue(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, locale.tr("import_queue", "Import Queue"), "", "JSON (*.json)")
        if not path:
            return
        try:
            raw = Path(path).read_text(encoding="utf-8")
            data = json.loads(raw)
            items = data.get("queue_items") if isinstance(data.get("queue_items"), list) else None
            if not items:
                raise ValueError("Invalid queue preset file: missing queue_items")
            reply = QMessageBox.question(self, locale.tr("import_confirm", "Import Confirm"), locale.tr("import_confirm_msg", "Replace current queue with {count} items?").format(count=len(items)))
            if reply != QMessageBox.StandardButton.Yes:
                return
            for entry in list(self._queue_state.queue_items):
                name = entry.get("name")
                if name:
                    self._queue_state.clear_saved_options(name)
            self._queue_state.set_queue_items(items)
            saved = data.get("task_options")
            if isinstance(saved, dict):
                for k, v in saved.items():
                    if isinstance(v, dict):
                        self._queue_state.save_options(k, v)
            self._restore_queue_ui()
            self._queue_state.persist()
            QMessageBox.information(self, locale.tr("import_success", "Import Successful"), locale.tr("import_success_msg", "Imported {count} queue items.").format(count=len(items)))
        except Exception as exc:
            QMessageBox.warning(self, locale.tr("import_failed", "Import Failed"), str(exc))

    def _runtime_queue_runner(self, retry_indices: Optional[list[int]] = None) -> bool:
        items = list(self._queue_state.queue_items)
        if not items:
            return True
        total = len(items)
        failed: list[int] = []
        indices = range(total) if retry_indices is None else retry_indices
        for idx in indices:
            if idx < 0 or idx >= total:
                continue
            if self._worker and getattr(self._worker, '_stopped', False):
                break
            entry = items[idx]
            # 通过 QueueState 加锁更新状态，再通过信号让主线程刷新 UI
            self._queue_state.update_queue_item_status(idx, "running")
            self.queue_item_status_changed.emit(idx, "running")
            self.progress_changed.emit(int((idx) / total * 100), locale.tr("task_progress", "Running {idx}/{total}").format(idx=idx + 1, total=total))
            name, inline_options = self._normalize_runtime_entry(entry)
            # 仅使用该队列条目的实例 options（权威），不再合并共享 task_options 快照，避免其他实例选项泄漏
            options = dict(entry.get("options") or {})
            if inline_options:
                options = {**options, **inline_options}
            self.log_message.emit("队列", locale.tr("executing_task", "Executing {name} ({idx}/{total})").format(name=_zh(name), idx=idx + 1, total=total))
            clean_name, inline_options = self._parse_inline_task_name(name)
            merged_options = dict(inline_options)
            merged_options.update(options)
            # name 是 argparse 位置参数，嵌入命令字符串；options 通过 params 传递
            result = self._sync_execute(f"task run {clean_name}", {"options": merged_options}, timeout_ms=300000)

            ok = bool(result and result.get("status") == "success")
            self._queue_state.update_queue_item_status(idx, "success" if ok else "failed")
            self.queue_item_status_changed.emit(idx, "success" if ok else "failed")
            self.log_message.emit("队列", f"{_zh(name)} -> {locale.tr('queue_success' if ok else 'queue_failed', 'Success' if ok else 'Failed')} ({idx + 1}/{total})")
            if not ok:
                failed.append(idx)
        self._failed_indices = failed
        if failed:
            self.progress_changed.emit(100, locale.tr("execution_failed", "Failed"))
            return False
        self.progress_changed.emit(100, locale.tr("execution_completed", "Completed"))
        return True


    # ------------------------------------------------------------------
    # option editor
    # ------------------------------------------------------------------
    def _build_option_editor(self, queue_index: Optional[int] = None) -> None:
        while self._option_form.count():
            item = self._option_form.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._option_widgets.clear()
        if not self._selected_task:
            hint = QLabel(locale.tr("select_task_first", "Please select a task first to edit options."))
            hint.setStyleSheet(INFO_STYLE)
            self._option_form.addWidget(hint)
            return
        task = self._tasks_cache.get(self._selected_task)
        if not task:
            return
        option_names = task.get("option", [])
        if not option_names:
            hint = QLabel(locale.tr("no_editable_options", "This task has no editable options."))
            hint.setStyleSheet(INFO_STYLE)
            self._option_form.addWidget(hint)
            return
        option_defs = self._task_option_defs or {}
        local_defs = task.get("_option_defs")
        if isinstance(local_defs, dict) and local_defs:
            option_defs = local_defs
        if not isinstance(option_defs, dict):
            option_defs = {}
        for name in option_names:
            opt_def = option_defs.get(name, {})
            container = QWidget()
            row = QHBoxLayout(container)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            label = QLabel(_resolve_label(opt_def.get("label", name)))
            label.setStyleSheet(INFO_STYLE)
            label.setMaximumWidth(220)
            label.setWordWrap(True)
            row.addWidget(label)
            widget = self._create_option_widget(name, opt_def)
            self._option_widgets[name] = widget
            row.addWidget(widget, 1)
            self._option_form.addWidget(container)
        self._option_form.addStretch()
        self._option_form.setEnabled(False)
        # 信号防护由 _apply_saved_option_values 内部对每个 widget 调用 blockSignals 实现；
        # 布局对象本身不发射信号，外层 _option_form.blockSignals 无效，故移除。
        self._apply_saved_option_values(self._selected_task, queue_index=queue_index)
        self._option_form.setEnabled(True)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_layout_geometry()

    def eventFilter(self, obj, event):
        if obj is self._queue_list:
            if event.type() == QEvent.Type.DragEnter:
                if event.source() is self._task_list:
                    event.accept()
                    return True
            elif event.type() == QEvent.Type.Drop:
                if event.source() is self._task_list:
                    selected = self._task_list.currentItem()
                    if selected:
                        self._selected_task = selected.data(Qt.ItemDataRole.UserRole)
                        if not self._is_executing:
                            self._add_to_queue()
                    event.accept()
                    return True
        return super().eventFilter(obj, event)

    def _sync_layout_geometry(self) -> None:
        splitter = getattr(self, "_splitter", None)
        if splitter is None:
            return
        required = ("_preset_list", "_task_list", "_queue_list", "_log_text")
        if not all(hasattr(self, name) for name in required):
            return
        tasks_col = getattr(self, "_tasks_col", None)
        options_col = getattr(self, "_options_col", None)
        right_col = getattr(self, "_right_col", None)
        if tasks_col is not None:
            tasks_col.setMinimumWidth(220)
        if options_col is not None:
            options_col.setMinimumWidth(240)
        if right_col is not None:
            right_col.setMinimumWidth(400)
        total = max(self.width(), 1)
        tasks_width = max(220, int(total * 0.20))
        options_width = max(240, int(total * 0.30))
        right_width = max(400, total - tasks_width - options_width - 12)
        splitter.setSizes([tasks_width, options_width, right_width])
        self._preset_list.setMinimumHeight(60)
        self._task_list.setMinimumHeight(80)
        self._queue_list.setMinimumHeight(60)
        self._log_text.setMinimumHeight(60)
        self._option_scroll.setMinimumHeight(120)
        # Queue list row height optimization
        if hasattr(self, "_queue_list"):
            self._queue_list.verticalHeader().setDefaultSectionSize(32)

    def _create_option_widget(self, name: str, opt_def: Dict[str, Any]) -> QWidget:
        opt_type = opt_def.get("type", "switch")
        cases = opt_def.get("cases", [])
        default_case = opt_def.get("default_case")
        if opt_type == "switch":
            toggle = ToggleSwitch(cases)
            if default_case is not None:
                toggle.setValue(str(default_case))
            toggle.toggled.connect(self._save_options)
            return toggle
        if opt_type == "checkbox":
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            default_items = set(default_case) if isinstance(default_case, list) else set()
            checkboxes: Dict[str, QCheckBox] = {}
            for case in cases:
                cb = QCheckBox(_resolve_label(case.get("label", case.get("name", ""))))
                cb.setStyleSheet(CHECK_STYLE)
                cb.setChecked(case.get("name", "") in default_items)
                cb.toggled.connect(self._save_options)
                layout.addWidget(cb)
                checkboxes[case.get("name", "")] = cb
            container.checkboxes = checkboxes  # type: ignore[attr-defined]
            return container
        if opt_type == "select":
            combo = QComboBox()
            combo.setStyleSheet(COMBO_STYLE)
            for case in cases:
                combo.addItem(_resolve_label(case.get("label", case.get("name", ""))), case.get("name"))
            if default_case is not None:
                idx = combo.findData(str(default_case))
                if idx < 0:
                    idx = combo.findText(str(default_case))
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.currentIndexChanged.connect(self._save_options)
            return combo
        if opt_type == "input":
            container = QWidget()
            form = QFormLayout(container)
            form.setContentsMargins(0, 0, 0, 0)
            form.setSpacing(6)
            inputs = opt_def.get("inputs", [])
            line_edits: Dict[str, QLineEdit] = {}
            for input_def in inputs:
                input_name = input_def.get("name", "")
                le = QLineEdit(str(input_def.get("default", "")))
                le.setStyleSheet(INPUT_STYLE)
                le.textChanged.connect(self._save_options)
                form.addRow(QLabel(_resolve_label(input_def.get("label", input_name))), le)
                line_edits[input_name] = le
            container.line_edits = line_edits  # type: ignore[attr-defined]
            return container
        return QLabel("Unsupported option type")

    def _collect_options(self) -> Dict[str, Any]:
        options: Dict[str, Any] = {}
        if not self._selected_task:
            return options
        task = self._tasks_cache.get(self._selected_task)
        if not task:
            return options
        option_names = task.get("option", [])
        option_defs = self._task_option_defs or {}
        local_defs = task.get("_option_defs")
        if isinstance(local_defs, dict) and local_defs:
            option_defs = local_defs
        if not isinstance(option_defs, dict):
            option_defs = {}
        for name in option_names:
            widget = self._option_widgets.get(name)
            if widget is None:
                continue
            opt_def = option_defs.get(name, {})
            opt_type = opt_def.get("type", "switch")
            if opt_type == "switch":
                toggle = widget
                options[name] = toggle.value()
            elif opt_type == "checkbox":
                checkboxes = getattr(widget, "checkboxes", {})
                options[name] = [n for n, cb in checkboxes.items() if cb.isChecked()]
            elif opt_type == "select":
                combo = widget
                options[name] = combo.currentData() or combo.currentText()
            elif opt_type == "input":
                line_edits = getattr(widget, "line_edits", {})
                options[name] = {n: le.text() for n, le in line_edits.items()}
        return options

    def _format_queue_label(self, name: str, item_type: str, options: Dict[str, Any]) -> str:
        return f"[{item_type.upper()}] {_zh(name)}"

    def _summarize_options(self, options: Dict[str, Any]) -> str:
        if not options:
            return ""
        parts: List[str] = []
        for key in sorted(options.keys()):
            if key == "settings":
                continue
            value = options[key]
            if isinstance(value, dict):
                inner = ", ".join(f"{k}={v}" for k, v in value.items())
                parts.append(f"{key}={{{inner}}}")
            elif isinstance(value, list):
                parts.append(f"{key}=[{', '.join(map(str, value))}]")
            else:
                parts.append(f"{key}={value}")
        return "; ".join(parts)

    def _save_options(self):
        if not self._selected_task:
            return
        options = self._collect_options()
        row = self._focused_queue_index
        if row is not None and 0 <= row < len(self._queue_state.queue_items):
            entry = self._queue_state.queue_items[row]
            if entry.get("name") == self._selected_task:
                # 聚焦队列条目时，仅写入该条目的实例 options，不污染共享 task_options 快照
                self._queue_state.update_queue_item_options(row, options)
            else:
                # 行名不匹配（极端竞态），回退为写入共享默认
                self._queue_state.save_options(self._selected_task, options)
        else:
            # 仅任务列表选中、未聚焦任何队列条目：写入共享默认（任务默认/新建种子）
            self._queue_state.save_options(self._selected_task, options)
        # 持久化优先且独立：即便后续 UI 刷新异常（如 item 为空），也必须保证本次编辑已落盘
        try:
            self._persist_state()
        except Exception as e:
            self.log_message.emit(locale.tr("persist", "Persist"), f"{locale.tr('save_failed', 'Save Failed')}: {e}")
        # UI 刷新独立于持久化，避免 UI 异常（如 item(row,0) 为 None）吞掉写盘
        try:
            if row is not None and 0 <= row < len(self._queue_state.queue_items):
                item = self._queue_list.item(row, 0)
                if item is not None:
                    entry = self._queue_state.queue_items[row]
                    item.setText(self._format_queue_label(self._selected_task, entry.get("type", "task"), options))
            self._refresh_queue_list()
        except Exception:
            pass

    def _refresh_queue_list(self) -> None:
        for row in range(self._queue_list.rowCount()):
            item = self._queue_list.item(row, 0)
            if not item:
                continue
            entry = self._queue_state.get_queue_item(row)
            if not entry:
                continue
            item.setText(self._format_queue_label(entry.get("name", ""), entry.get("type", "task"), entry.get("options") or {}))

    def _load_options(self, task_name: str) -> Dict[str, Any]:
        return self._queue_state.load_options(task_name)

    def _clear_saved_options(self, task_name: str) -> None:
        self._queue_state.clear_saved_options(task_name)

    def _apply_saved_option_values(self, task_name: str, queue_index: Optional[int] = None) -> None:
        if queue_index is not None and 0 <= queue_index < len(self._queue_state.queue_items):
            # 队列实例权威：只读取该条目的实例 options，不回退共享快照（避免被其他实例污染）
            entry = self._queue_state.queue_items[queue_index]
            saved = dict(entry.get("options") or {})
        else:
            # 非队列聚焦（任务列表选中）：读取共享默认
            saved = self._load_options(task_name)
            if not saved:
                return
        task = self._tasks_cache.get(task_name)
        if not task:
            return
        option_names = task.get("option", [])
        option_defs = self._task_option_defs or {}
        local_defs = task.get("_option_defs")
        if isinstance(local_defs, dict) and local_defs:
            option_defs = local_defs
        if not isinstance(option_defs, dict):
            option_defs = {}
        for name in option_names:
            if name not in saved:
                continue
            widget = self._option_widgets.get(name)
            if widget is None:
                continue
            value = saved[name]
            opt_def = option_defs.get(name, {})
            opt_type = opt_def.get("type", "switch")
            if opt_type == "switch":
                widget.blockSignals(True)
                widget.setValue(str(value))
                widget.blockSignals(False)
            elif opt_type == "checkbox":
                checkboxes = getattr(widget, "checkboxes", {})
                if isinstance(value, list):
                    for n, cb in checkboxes.items():
                        cb.blockSignals(True)
                        cb.setChecked(n in value)
                        cb.blockSignals(False)
            elif opt_type == "select":
                widget.blockSignals(True)
                idx = widget.findData(str(value))
                if idx < 0:
                    idx = widget.findText(str(value))
                if idx >= 0:
                    widget.setCurrentIndex(idx)
                widget.blockSignals(False)
            elif opt_type == "input":
                line_edits = getattr(widget, "line_edits", {})
                if isinstance(value, dict):
                    for n, le in line_edits.items():
                        if n in value:
                            le.blockSignals(True)
                            le.setText(str(value[n]))
                            le.blockSignals(False)

    def _resolve_state_path(self) -> Path:
        try:
            from core.foundation.paths import get_project_root

            base = Path(get_project_root()) / "config"
        except Exception:
            base = Path(__file__).resolve().parent.parent.parent.parent / "config"
        base.mkdir(parents=True, exist_ok=True)
        return base / "maaend_task_state.json"

    def _persist_state(self) -> None:
        try:
            self._queue_state.set_state_path(self._state_path)
            self._queue_state.set_selected_task(self._selected_task)
            self._queue_state.set_selected_preset(self._selected_preset)
            self._queue_state.persist()
        except Exception as e:
            self.log_message.emit(locale.tr("persist", "Persist"), f"{locale.tr("save_failed", "Save Failed")}: {e}")

    def _resolve_metadata_cache_path(self) -> Path:
        try:
            from core.foundation.paths import get_project_root
            base = Path(get_project_root()) / "cache"
        except Exception:
            base = Path(__file__).resolve().parent.parent.parent.parent.parent / "cache"
        base.mkdir(parents=True, exist_ok=True)
        return base / "metadata_cache.json"

    def _load_metadata_cache(self) -> None:
        path = self._metadata_cache_path
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._tasks_cache = data.get("tasks") or {}
            self._presets_cache = data.get("presets") or {}
            self._task_option_defs = data.get("task_option_defs") or {}
        except Exception:
            pass

    def _persist_metadata_cache(self) -> None:
        try:
            data = {
                "tasks": self._tasks_cache,
                "presets": self._presets_cache,
                "task_option_defs": self._task_option_defs,
            }
            self._metadata_cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _open_task_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(locale.tr("task_settings_title", "Task Settings"))
        dialog.setMinimumWidth(620)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        info = QLabel(
            locale.tr("task_settings_desc", "Task options and queue state are persisted to local config.\nCurrent path: {path}").format(path=self._state_path)
        )
        info.setWordWrap(True)
        info.setStyleSheet(INFO_STYLE)
        layout.addWidget(info)
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setPlainText(self._state_path.read_text(encoding="utf-8") if self._state_path.exists() else "{}")
        layout.addWidget(preview, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def _on_queue_focus_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._queue_state.queue_items):
            return
        # 切换前：把编辑器里仍是旧条目的已编辑值 flush 到旧实例（仅聚焦队列条目时）
        if self._focused_queue_index is not None and self._selected_task and 0 <= self._focused_queue_index < len(self._queue_state.queue_items):
            old_row = self._focused_queue_index
            old_entry = self._queue_state.queue_items[old_row]
            if old_entry.get("name") == self._selected_task:
                self._queue_state.update_queue_item_options(old_row, self._collect_options())
        entry = self._queue_state.queue_items[row]
        name = entry.get("name")
        if not name:
            return
        self._selected_task = name
        self._focused_queue_index = row
        self._build_option_editor(queue_index=row)

    def _normalize_task_entry(self, task_entry: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        name = str(task_entry.get("name") or "").strip()
        options = task_entry.get("option")
        inline_options: Dict[str, Any] = {}
        if isinstance(name, str) and name:
            parsed_name, parsed_options = self._parse_inline_task_name(name)
            name = parsed_name
            inline_options = parsed_options
        if isinstance(options, dict):
            inline_options = {**inline_options, **options}
        return name, inline_options

    def _normalize_runtime_entry(self, entry: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        name = str(entry.get("name") or entry.get("display_name") or "").strip()
        options = entry.get("options")
        inline_options: Dict[str, Any] = {}
        if isinstance(name, str) and name:
            parsed_name, parsed_options = self._parse_inline_task_name(name)
            name = parsed_name
            inline_options = parsed_options
        if isinstance(options, dict):
            inline_options = {**inline_options, **options}
        return name, inline_options

    def _parse_inline_task_name(self, name: str) -> tuple[str, Dict[str, Any]]:
        if "|" not in name:
            return name, {}
        base, payload = name.split("|", 1)
        base = base.strip()
        payload = payload.strip()
        if not base or not payload:
            return name, {}
        if payload.startswith("{") and payload.endswith("}"):
            try:
                parsed = json.loads(payload)
                if isinstance(parsed, dict):
                    return base, parsed
            except Exception:
                return base, {"_inline": payload}
        return base, {"_inline": payload}

    # ------------------------------------------------------------------
    # execution
    # ------------------------------------------------------------------
    def _delayed_init(self) -> None:
        """延迟初始化：立即渲染缓存列表，主线程顺序执行重连和元数据加载。"""
        # 初始化期间停止预览定时器，避免与系统连接的嵌套事件循环冲突
        main_window = self.window()
        preview_timer = getattr(main_window, "_preview_timer", None)
        if preview_timer is not None:
            preview_timer.stop()

        # 立即渲染列表，保证启动时任务/预设列表可见。
        self.refresh()

        # 主线程延迟执行，避免在 __init__ 中启动嵌套 QEventLoop
        QTimer.singleShot(50, self._do_auto_connect)

    def _do_auto_connect(self) -> None:
        params = self._resolve_connect_params()
        result = self._sync_execute("system connect", params, timeout_ms=15000)
        self._on_auto_connect_finished(bool(result and result.get("status") == "success"))
        QTimer.singleShot(0, self._do_metadata_load)

    def _on_auto_connect_finished(self, success: bool) -> None:
        if success:
            self._connected = True
            self._auto_connect_attempted = False
            self._append_log("系统", locale.tr("auto_connect_success", "Auto-connect succeeded at startup"))
        else:
            self._auto_connect_attempted = True
            self._append_log("系统", locale.tr("auto_connect_failed", "Auto-connect failed at startup, will not retry."))

        preview_timer = getattr(self.window(), "_preview_timer", None)
        if preview_timer is not None and self._connected:
            preview_timer.start()

    def _do_metadata_load(self) -> None:
        result = self._sync_execute("metadata list", timeout_ms=10000)
        self._on_metadata_loaded(result or {})

    def _on_metadata_loaded(self, result: dict) -> None:
        if result and result.get("status") == "success":
            new_tasks = result.get("tasks") or {}
            new_presets = result.get("presets") or {}
            new_defs = result.get("task_option_defs") or {}
            if new_tasks != self._tasks_cache or new_presets != self._presets_cache:
                self._tasks_cache = new_tasks
                self._presets_cache = new_presets
                self._task_option_defs = new_defs
                self._persist_metadata_cache()
                self.refresh()
        # 即使加载失败或结果未变化，只要缓存仍为空就尝试刷新，
        # 防止列表因之前的失败 _sync_execute 被 clear() 后永远空白。
        if not self._tasks_cache or not self._presets_cache:
            self.refresh()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        # 页面切回时，若任一缓存为空则触发刷新，避免列表因切换操作丢失内容
        if not self._tasks_cache or not self._presets_cache:
            QTimer.singleShot(50, self.refresh)

    def closeEvent(self, event: QCloseEvent) -> None:
        super().closeEvent(event)

    def set_connected(self, connected: bool) -> None:
        """由 MainWindow 同步设备连接状态。"""
        self._connected = connected

    def set_auto_connect_attempted(self) -> None:
        """标记启动自动连接已尝试过，后续不再重试。"""
        self._auto_connect_attempted = True

    def _ensure_connected(self) -> bool:
        """Auto-connect runtime if not already connected. Returns True on success."""
        if self._connected:
            return True
        if self._auto_connect_attempted:
            return False
        self._append_log("系统", locale.tr("connecting_maaend", "Connecting to MaaEnd runtime..."))
        result = self._sync_execute("system connect", timeout_ms=15000)
        if not result or result.get("status") != "success":
            self._auto_connect_attempted = True
            QMessageBox.warning(self, locale.tr("connection_failed", "Connection Failed"), locale.tr("connect_failed_msg", "Cannot connect to MaaEnd runtime. Please check the device."))
            return False
        self._connected = True
        self._auto_connect_attempted = False
        self._append_log("系统", locale.tr("maaend_connected", "MaaEnd runtime connected"))
        return True

    def _add_task_to_queue(self):
        if not self._selected_task or self._is_executing:
            return
        name = self._selected_task
        current_options = self._collect_options()
        saved = self._load_options(name)
        options = dict(saved) if saved else {}
        options.update(current_options)
        self._queue_state.save_options(name, options)
        entry = {"name": name, "display_name": name, "type": "task", "options": dict(options)}
        items = self._queue_state.queue_items + [entry]
        self._queue_state.set_queue_items(items)
        self._restore_queue_ui()
        self._queue_state.persist()
        self._append_log("队列", locale.tr("btn_add", "Added {name}").format(name=_zh(name)))

    def _bridge_task_run(self, name: str, options: Dict[str, Any]) -> bool:
        clean_name, inline_options = self._parse_inline_task_name(name)
        merged_options = dict(inline_options)
        merged_options.update(options)
        # name 是 argparse 位置参数，嵌入命令字符串；options 通过 params 传递
        result = self._sync_execute(f"task run {clean_name}", {"options": merged_options})
        return bool(result and result.get("status") == "success")

    def _apply_preset_to_queue(self):
        if not self._selected_preset or self._is_executing:
            return
        preset = self._presets_cache.get(self._selected_preset)
        if not preset:
            QMessageBox.warning(self, locale.tr("preset_not_found", "Preset Not Found"), locale.tr("preset_not_found_msg", "Preset '{preset}' not found.").format(preset=self._selected_preset))
            return
        task_list = preset.get("task", [])
        if not task_list:
            QMessageBox.information(self, locale.tr("preset_empty", "Preset Is Empty"), locale.tr("preset_empty_msg", "Preset '{preset}' has no tasks.").format(preset=self._selected_preset))
            return
        # 应用预设 = 用预设中的任务列表覆盖现有队列（清空再填充），不是追加。
        for entry in list(self._queue_state.queue_items):
            name = entry.get("name")
            if name:
                self._queue_state.clear_saved_options(name)
        items = []
        for task_entry in task_list:
            name, inline_options = self._normalize_task_entry(task_entry)
            options = task_entry.get("option") or {}
            if inline_options:
                options = {**dict(options), **inline_options}
            saved = self._queue_state.load_options(name)
            if saved:
                current_options = dict(options)
                options = dict(saved)
                options.update(current_options)
            self._queue_state.save_options(name, options)
            items.append({"name": name, "type": "task", "options": dict(options)})
        self._queue_state.set_queue_items(items)
        self._restore_queue_ui()
        self._append_log("预设", locale.tr("btn_apply_preset", "Applied preset '{name}' ({count} tasks)").format(name=_zh(self._selected_preset), count=len(task_list)))
        self._persist_state()
        return

    def _run_queue(self):
        if not self._queue_state.queue_items or self._is_executing:
            return
        if not self._ensure_connected():
            return
        self._failed_indices: list[int] = []
        self._retry_count = 0
        self._start_execution(lambda: self._runtime_queue_runner())

    def _retry_failed(self) -> None:
        if self._is_executing or not self._failed_indices:
            return
        if not self._ensure_connected():
            return
        self._retry_count += 1
        self._append_log("系统", locale.tr("retry_started", "Retry {count}/{max} for {n} failed items").format(count=self._retry_count, max=self._max_retries, n=len(self._failed_indices)))
        self._start_execution(lambda: self._runtime_queue_runner(retry_indices=self._failed_indices))

    def _start_execution(self, target):
        self._is_executing = True
        self._update_execution_ui()
        self._append_log("系统", locale.tr("execution_started", "Start execution"))
        self._worker = TaskRunWorker(target)
        self._worker.log.connect(self._append_log)
        self._worker.finished.connect(self._on_execution_finished)
        self._worker.start()

    def _stop_execution(self):
        if self._worker:
            self._worker.stop()
        self._append_log("系统", locale.tr("execution_stop_requested", "Stop requested"))

    def _on_execution_finished(self, success: bool):
        self._is_executing = False
        if hasattr(self, '_status_pulse_animation'):
            self._status_pulse_animation.stop()
            del self._status_pulse_animation
        self._update_execution_ui()
        self._append_log("系统", locale.tr("execution_finished", "Execution finished: {success}").format(success=success))
        if not success and self._failed_indices and self._auto_retry_enabled and self._retry_count < self._max_retries:
            self._append_log("系统", locale.tr("auto_retry_scheduled", "Auto-retry in {delay}s...").format(delay=self._retry_delay_ms / 1000))
            QTimer.singleShot(self._retry_delay_ms, self._retry_failed)
        self.execution_state_changed.emit(False)

    def _update_execution_ui(self):
        self._apply_preset_to_queue_btn.setEnabled(not self._is_executing)
        self._run_queue_btn.setEnabled(not self._is_executing)
        self._add_queue_btn.setEnabled(not self._is_executing)
        self._queue_up_btn.setEnabled(not self._is_executing)
        self._queue_down_btn.setEnabled(not self._is_executing)
        self._queue_clear_btn.setEnabled(not self._is_executing)
        self._stop_btn.setEnabled(self._is_executing)
        self._retry_btn.setEnabled(not self._is_executing and bool(getattr(self, '_failed_indices', [])))
        self._progress_bar.setVisible(self._is_executing)
        if not self._is_executing:
            self._progress_bar.setValue(0)
        self._status_label.setText(locale.tr("maaend_running" if self._is_executing else "maaend_idle", "Running" if self._is_executing else "Idle"))
        self._status_label.setStyleSheet(RED_STYLE if self._is_executing else BLUE_STYLE)
        if self._is_executing:
            self._pulse_status_label()
        self.execution_state_changed.emit(self._is_executing)

    def _pulse_status_label(self):
        """Pulse the status label to draw attention during execution."""
        animation = QPropertyAnimation(self._status_label, b"windowOpacity", self)
        animation.setDuration(1000)
        animation.setLoopCount(-1)  # Infinite loop
        animation.setKeyValueAt(0.0, 1.0)
        animation.setKeyValueAt(0.5, 0.5)
        animation.setKeyValueAt(1.0, 1.0)
        animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        animation.start()
        # Store reference to prevent garbage collection
        self._status_pulse_animation = animation

    def _on_queue_item_status_changed(self, row: int, status: str) -> None:
        """主线程槽：更新队列列表中指定行的状态显示。"""
        self._queue_state.update_queue_item_status(row, status)
        item = self._queue_list.item(row, 0)
        if item is None:
            return
        entry = self._queue_state.get_queue_item(row)
        if entry is None:
            return
        item.setText(self._format_queue_label(entry.get("name", ""), entry.get("type", "task"), entry.get("options") or {}))

    def _on_progress_changed(self, value: int, fmt: str) -> None:
        """主线程槽：更新进度条。"""
        self._progress_bar.setValue(value)
        self._progress_bar.setFormat(fmt)

    def _append_log(self, source: str, text: str):
        color = BLUE_STYLE if source == "系统" else VAL_STYLE
        self._log_text.append(f"<span style='{color}'>[{source}] {text}</span>")
        # Auto-scroll to bottom for real-time log streaming
        cursor = self._log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._log_text.setTextCursor(cursor)


    def _apply_log_filter(self, index: int) -> None:
        # Simple filter: hide/show log lines by checking source tags
        # For a full implementation, we'd need to store line data; here we just
        # clear and re-emit filtered logs from a buffer.
        # This is a lightweight placeholder that future-proofs the UI.
        pass

    def refresh(self):
        self._refresh_task_list()
        self._refresh_preset_list()
        # 延迟构建 option editor，避免阻塞列表显示
        QTimer.singleShot(0, self._build_option_editor)

class TaskRunWorker(QThread):
    log = pyqtSignal(str, str)
    finished = pyqtSignal(bool)

    def __init__(self, target):
        super().__init__()
        self._target = target
        self._stopped = False

    def run(self):
        try:
            result = bool(self._target())
            if self._stopped:
                self.finished.emit(False)
                return
            self.finished.emit(result)
        except Exception as e:
            self.log.emit("ERROR", str(e))
            self.finished.emit(False)

    def stop(self):
        self._stopped = True
        # 不再调用 QThread.terminate()，避免在子线程持有资源时强制终止导致崩溃或数据损坏。
        # 目标方法会通过定期检查 _stopped 标志安全退出。

