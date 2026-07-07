"""Standard Reasoning control panel: task list, preset list, task queue, option editor, preview, log viewer."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QScrollArea,
    QTextEdit, QMessageBox, QSplitter, QCheckBox, QComboBox, QSpinBox, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QApplication, QDialog, QFormLayout, QDialogButtonBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer, QEventLoop, QObject
from PyQt6.QtGui import QColor, QBrush, QIcon, QPixmap, QImage, QFont

from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.responsive import is_narrow_size

INFO_STYLE = "color: #9090a8; font-size: 12px; font-family: 'Microsoft YaHei UI'; padding: 3px 0;"
VAL_STYLE = "color: #e8e8ee; font-size: 12px; font-family: 'Microsoft YaHei UI'; padding: 3px 0;"
GREEN_STYLE = "color: #00ffa2; font-size: 12px; font-family: 'Microsoft YaHei UI'; padding: 3px 0;"
RED_STYLE = "color: #ff3355; font-size: 12px; font-family: 'Microsoft YaHei UI'; padding: 3px 0;"
BLUE_STYLE = "color: #18d1ff; font-size: 12px; font-family: 'Microsoft YaHei UI'; padding: 3px 0;"
YELLOW_STYLE = "color: #ffcc33; font-size: 12px; font-family: 'Microsoft YaHei UI'; padding: 3px 0;"
HEADER_STYLE = "color: #18d1ff; font-size: 14px; font-family: 'Microsoft YaHei UI'; font-weight: bold; letter-spacing: 1px; padding: 4px 0;"

CARD_STYLE = """
    QGroupBox {
        background-color: rgba(16, 16, 26, 0.85);
        border: 1px solid rgba(24, 209, 255, 0.10);
        border-radius: 3px;
        font-size: 13px; font-family: 'Microsoft YaHei UI';
        color: #e8e8ee; font-weight: bold; letter-spacing: 1px;
        margin-top: 12px;
        padding-top: 18px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        top: -1px;
        padding: 0 4px;
    }
"""
LIST_STYLE = """
    QListWidget {
        background-color: rgba(10, 10, 15, 0.90);
        border: 1px solid rgba(24, 209, 255, 0.10);
        color: #e8e8ee; font-family: 'Microsoft YaHei UI'; font-size: 12px;
    }
    QListWidget::item { padding: 3px 6px; }
    QListWidget::item:selected { background-color: rgba(24, 209, 255, 0.18); color: #18d1ff; }
"""
LOG_STYLE = """
    QTextEdit {
        background-color: rgba(10, 10, 15, 0.90);
        color: #e0e0e8;
        border: 1px solid rgba(24, 209, 255, 0.10);
        border-radius: 4px;
        font-size: 11px; font-family: 'Microsoft YaHei UI'; padding: 2px 4px;
    }
"""
INPUT_STYLE = """
    QLineEdit, QSpinBox, QComboBox {
        background-color: rgba(16, 16, 26, 0.85);
        color: #e8e8ee; border: 1px solid rgba(24, 209, 255, 0.15);
        border-radius: 2px; font-size: 12px; font-family: 'Microsoft YaHei UI'; padding: 6px 10px; min-height: 32px;
    }
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: rgba(24, 209, 255, 0.40); }
"""
CHECK_STYLE = """
    QCheckBox { color: #e8e8ee; font-size: 12px; font-family: 'Microsoft YaHei UI'; spacing: 8px; }
    QCheckBox::indicator { width: 16px; height: 16px; border-radius: 2px; border: 1px solid rgba(24, 209, 255, 0.30); background-color: transparent; }
    QCheckBox::indicator:checked { background-color: #18d1ff; border-color: #18d1ff; }
"""
COMBO_STYLE = """
    QComboBox {
        background-color: rgba(10, 10, 15, 0.80); color: #e8e8ee; border: 1px solid rgba(24, 209, 255, 0.15);
        border-radius: 4px; padding: 8px 12px; font-size: 12px; font-family: 'Microsoft YaHei UI'; min-height: 36px;
    }
    QComboBox::drop-down { border: none; width: 28px; }
    QComboBox::down-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid rgba(24, 209, 255, 0.50); width: 0; height: 0; }
    QComboBox QAbstractItemView { background-color: rgba(12, 12, 20, 0.95); color: #e8e8ee; border: 1px solid rgba(24, 209, 255, 0.15); selection-background-color: rgba(24, 209, 255, 0.15); }
"""
TABLE_STYLE = """
    QTableWidget { background-color: rgba(16, 16, 26, 0.85); border: 1px solid rgba(24, 209, 255, 0.08); border-radius: 2px; color: #e8e8ee; font-size: 12px; font-family: 'Microsoft YaHei UI'; gridline-color: rgba(24, 209, 255, 0.06); }
    QTableWidget::item { padding: 6px; }
    QTableWidget::item:selected { background-color: rgba(24, 209, 255, 0.12); color: #18d1ff; }
    QHeaderView::section { background-color: rgba(24, 209, 255, 0.08); color: #18d1ff; font-size: 11px; font-weight: bold; padding: 6px; border: none; }
"""
PREVIEW_STYLE = """
    QLabel {
        background-color: rgba(8, 8, 12, 0.95);
        border: 1px solid rgba(24, 209, 255, 0.10);
        border-radius: 4px;
        padding: 2px;
    }
"""

BTN_ACTIVE = """
    QPushButton {
        background-color: rgba(0, 255, 162, 0.10);
        color: #00ffa2;
        border: 1px solid rgba(0, 255, 162, 0.30);
        border-radius: 2px;
        padding: 0px 2px;
        font-size: 11px; font-family: 'Microsoft YaHei UI'; font-weight: bold; letter-spacing: 1px;
    }
    QPushButton:hover { background-color: rgba(0, 255, 162, 0.20); }
"""
BTN_DEFAULT = """
    QPushButton {
        background-color: rgba(24, 209, 255, 0.10);
        color: #18d1ff;
        border: 1px solid rgba(24, 209, 255, 0.30);
        border-radius: 2px;
        padding: 0px 2px;
        font-size: 11px; font-family: 'Microsoft YaHei UI'; font-weight: bold; letter-spacing: 1px;
    }
    QPushButton:hover { background-color: rgba(24, 209, 255, 0.20); }
"""
BTN_STOP = """
    QPushButton {
        background-color: rgba(255, 51, 85, 0.12);
        color: #ff3355;
        border: 1px solid rgba(255, 51, 85, 0.40);
        border-radius: 2px;
        padding: 0px 2px;
        font-size: 11px; font-family: 'Microsoft YaHei UI'; font-weight: bold; letter-spacing: 1px;
    }
    QPushButton:hover { background-color: rgba(255, 51, 85, 0.25); }
"""

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


class MaaEndControlPage(QWidget):
    execution_state_changed = pyqtSignal(bool)
    log_message = pyqtSignal(str, str)

    def __init__(self, bridge: CLIBridge, parent=None):
        super().__init__(parent)
        self._bridge = bridge
        self._selected_task: Optional[str] = None
        self._selected_preset: Optional[str] = None
        self._option_widgets: Dict[str, QWidget] = {}
        self._is_executing = False
        self._worker: Optional[TaskRunWorker] = None
        self._queue_items: List[Dict[str, Any]] = []
        self._connected = False
        self._tasks_cache: Dict[str, Dict[str, Any]] = {}
        self._presets_cache: Dict[str, Dict[str, Any]] = {}
        self._task_option_defs: Dict[str, Dict[str, Any]] = {}
        self._saved_task_options: Dict[str, Dict[str, Any]] = {}
        self._state_path = self._resolve_state_path()
        self._setup_ui()
        font = QFont("Microsoft YaHei UI")
        self.setFont(font)
        for widget_name in ("_status_label", "_run_preset_btn", "_log_text"):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.setFont(font)
        self._refresh_task_list()
        self._refresh_preset_list()
        self._load_state()
        self.log_message.connect(self._append_log)
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(1500)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self._preview_label = None

    # ------------------------------------------------------------------
    # bridge compatibility
    # ------------------------------------------------------------------
    def set_bridge(self, bridge: CLIBridge) -> None:
        self._bridge = bridge
        self.refresh()

    def _sync_execute(self, command: str, params: Optional[Dict[str, Any]] = None, timeout_ms: int = 1200) -> Optional[dict]:
        if isinstance(params, int):
            timeout_ms = params
            params = None
        loop = QEventLoop()
        result = None
        expected = command

        def _on_finished(cmd: str, res: dict):
            nonlocal result
            if cmd == expected:
                result = res
                loop.quit()

        self._bridge.commandFinished.connect(_on_finished)
        self._bridge.execute(expected, params or {})
        QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec()
        self._bridge.commandFinished.disconnect(_on_finished)
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
    # public API for MainWindow preview integration
    # ------------------------------------------------------------------
    def update_preview(self, image_data: bytes) -> None:
        if self._preview_label is None:
            return
        if not image_data:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(image_data):
            scaled = pixmap.scaled(self._preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self._preview_label.setPixmap(scaled)

    def start_preview_timer(self) -> None:
        if self._preview_timer.isActive():
            return
        self._refresh_preview()
        self._preview_timer.start()

    def stop_preview_timer(self) -> None:
        self._preview_timer.stop()

    # ------------------------------------------------------------------
    # show / hide events -> timer lifecycle
    # ------------------------------------------------------------------
    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.start_preview_timer()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self.stop_preview_timer()

    def _refresh_preview(self) -> None:
        if self._preview_label is None:
            return
        result = self._sync_execute("screenshot")
        if not result or result.get("status") != "success":
            return
        data = result.get("base64")
        if not data:
            path = result.get("path")
            if path:
                try:
                    data = Path(path).read_bytes()
                except Exception:
                    return
            else:
                return
        try:
            import base64
            image_data = base64.b64decode(data)
        except Exception:
            return
        self.update_preview(image_data)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel("// 标准推理控制台")
        title.setStyleSheet(HEADER_STYLE)
        header.addWidget(title)
        header.addStretch()
        self._status_label = QLabel("空闲")
        self._status_label.setStyleSheet(GREEN_STYLE)
        header.addWidget(self._status_label)
        root.addLayout(header)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter = splitter
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet("QSplitter::handle { width: 1px; background: rgba(24,209,255,0.12); }")
        left = QWidget()
        self._splitter_left = left
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # 预设 -------------------------------------------------------
        preset_card = QGroupBox("预设")
        preset_card.setStyleSheet(CARD_STYLE)
        preset_layout = QVBoxLayout(preset_card)
        preset_layout.setContentsMargins(2, 2, 2, 2)
        preset_layout.setSpacing(2)
        self._preset_list = QListWidget()
        self._preset_list.setStyleSheet(LIST_STYLE)
        self._preset_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._preset_list.setMinimumHeight(92)
        self._preset_list.setMaximumHeight(126)
        self._preset_list.itemSelectionChanged.connect(self._on_preset_selected)
        preset_layout.addWidget(self._preset_list)
        preset_btn_row = QHBoxLayout()
        preset_btn_row.setContentsMargins(0, 0, 0, 0)
        preset_btn_row.setSpacing(6)
        self._run_preset_btn = QPushButton("应用预设")
        self._run_preset_btn.setMinimumHeight(24)
        self._run_preset_btn.setStyleSheet(BTN_ACTIVE)
        self._run_preset_btn.clicked.connect(self._run_preset)
        preset_btn_row.addWidget(self._run_preset_btn)
        preset_btn_row.addStretch()
        preset_layout.addLayout(preset_btn_row)
        left_layout.addWidget(preset_card)

        # 任务 --------------------------------------------------------
        task_card = QGroupBox("任务")
        task_card.setStyleSheet(CARD_STYLE)
        task_layout = QVBoxLayout(task_card)
        task_layout.setContentsMargins(2, 2, 2, 2)
        task_layout.setSpacing(2)
        self._task_list = QListWidget()
        self._task_list.setStyleSheet(LIST_STYLE)
        self._task_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._task_list.setMinimumHeight(110)
        self._task_list.setMaximumHeight(160)
        self._task_list.itemSelectionChanged.connect(self._on_task_selected)
        task_layout.addWidget(self._task_list)
        task_btn_row = QHBoxLayout()
        task_btn_row.setContentsMargins(0, 0, 0, 0)
        task_btn_row.setSpacing(6)
        self._run_task_btn = QPushButton("添加任务")
        self._run_task_btn.setMinimumHeight(24)
        self._run_task_btn.setStyleSheet(BTN_ACTIVE)
        self._run_task_btn.clicked.connect(self._run_task)
        task_btn_row.addWidget(self._run_task_btn)
        self._task_settings_btn = QPushButton("应用队列设置")
        self._task_settings_btn.setMinimumHeight(24)
        self._task_settings_btn.setStyleSheet(BTN_DEFAULT)
        self._task_settings_btn.clicked.connect(self._apply_queue_focus_task_settings)
        task_btn_row.addWidget(self._task_settings_btn)
        task_btn_row.addStretch()
        task_layout.addLayout(task_btn_row)
        left_layout.addWidget(task_card)

        # 队列 --------------------------------------------------------
        queue_card = QGroupBox("队列")
        queue_card.setStyleSheet(CARD_STYLE)
        queue_layout = QVBoxLayout(queue_card)
        queue_layout.setContentsMargins(2, 2, 2, 2)
        queue_layout.setSpacing(2)
        self._queue_list = QListWidget()
        self._queue_list.setStyleSheet(LIST_STYLE)
        self._queue_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._queue_list.setMinimumHeight(96)
        self._queue_list.setMaximumHeight(140)
        self._queue_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._queue_list.currentRowChanged.connect(self._on_queue_focus_changed)
        queue_layout.addWidget(self._queue_list)
        queue_btn_row = QHBoxLayout()
        queue_btn_row.setContentsMargins(0, 0, 0, 0)
        queue_btn_row.setSpacing(6)
        self._add_queue_btn = QPushButton("添加")
        self._add_queue_btn.setMinimumHeight(24)
        self._add_queue_btn.setStyleSheet(BTN_DEFAULT)
        self._add_queue_btn.clicked.connect(self._add_to_queue)
        queue_btn_row.addWidget(self._add_queue_btn)
        self._run_queue_btn = QPushButton("运行")
        self._run_queue_btn.setMinimumHeight(24)
        self._run_queue_btn.setStyleSheet(BTN_ACTIVE)
        self._run_queue_btn.clicked.connect(self._run_queue)
        queue_btn_row.addWidget(self._run_queue_btn)
        queue_btn_row.addStretch()
        queue_layout.addLayout(queue_btn_row)
        queue_move_row = QHBoxLayout()
        queue_move_row.setContentsMargins(0, 0, 0, 0)
        queue_move_row.setSpacing(6)
        self._queue_up_btn = QPushButton("上移")
        self._queue_up_btn.setMinimumHeight(24)
        self._queue_up_btn.setStyleSheet(BTN_DEFAULT)
        self._queue_up_btn.clicked.connect(self._queue_move_up)
        queue_move_row.addWidget(self._queue_up_btn)
        self._queue_down_btn = QPushButton("下移")
        self._queue_down_btn.setMinimumHeight(24)
        self._queue_down_btn.setStyleSheet(BTN_DEFAULT)
        self._queue_down_btn.clicked.connect(self._queue_move_down)
        queue_move_row.addWidget(self._queue_down_btn)
        self._queue_clear_btn = QPushButton("清空")
        self._queue_clear_btn.setMinimumHeight(24)
        self._queue_clear_btn.setStyleSheet(BTN_DEFAULT)
        self._queue_clear_btn.clicked.connect(self._queue_clear)
        queue_move_row.addWidget(self._queue_clear_btn)
        queue_move_row.addStretch()
        queue_layout.addLayout(queue_move_row)
        left_layout.addWidget(queue_card)
        left_layout.addStretch()
        left.setMinimumWidth(280)
        splitter.addWidget(left)

        # RIGHT --------------------------------------------------------
        right = QWidget()
        self._splitter_right = right
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 选项 ------------------------------------------------------
        option_card = QGroupBox("选项")
        option_card.setStyleSheet(CARD_STYLE)
        option_layout = QVBoxLayout(option_card)
        option_layout.setContentsMargins(2, 2, 2, 2)
        option_layout.setSpacing(2)
        self._option_scroll = QScrollArea()
        self._option_scroll.setWidgetResizable(True)
        self._option_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
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
        right_layout.addWidget(option_card, 2)

        # 预览 ------------------------------------------------------
        preview_card = QGroupBox("预览")
        preview_card.setStyleSheet(CARD_STYLE)
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(2, 2, 2, 2)
        preview_layout.setSpacing(2)
        self._preview_label = QLabel("暂无预览")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet(PREVIEW_STYLE)
        self._preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._preview_label.setMinimumHeight(180)
        preview_layout.addWidget(self._preview_label)
        right_layout.addWidget(preview_card, 3)

        # 日志 ----------------------------------------------------------
        log_card = QGroupBox("日志")
        log_card.setStyleSheet(CARD_STYLE)
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(2, 2, 2, 2)
        log_layout.setSpacing(2)
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._log_text.setMinimumHeight(100)
        self._log_text.setMaximumHeight(140)
        self._log_text.setStyleSheet(LOG_STYLE)
        log_layout.addWidget(self._log_text)
        log_btn_row = QHBoxLayout()
        log_btn_row.setContentsMargins(0, 0, 0, 0)
        log_btn_row.setSpacing(4)
        self._clear_log_btn = QPushButton("清空")
        self._clear_log_btn.setMinimumHeight(24)
        self._clear_log_btn.setStyleSheet(BTN_DEFAULT)
        self._clear_log_btn.clicked.connect(self._log_text.clear)
        log_btn_row.addWidget(self._clear_log_btn)
        log_btn_row.addStretch()
        log_layout.addLayout(log_btn_row)
        right_layout.addWidget(log_card, 1)

        font = QFont("Microsoft YaHei UI")
        for widget in (
            title,
            self._status_label,
            self._run_preset_btn,
            self._run_task_btn,
            self._add_queue_btn,
            self._run_queue_btn,
            self._queue_up_btn,
            self._queue_down_btn,
            self._queue_clear_btn,
            self._clear_log_btn,
            self._log_text,
        ):
            widget.setFont(font)

        right.setMinimumWidth(360)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 4)
        root.addWidget(splitter, 1)

        # BOTTOM -------------------------------------------------------
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.addSpacing(4)
        self._stop_btn = QPushButton("停止")
        self._stop_btn.setStyleSheet(BTN_STOP)
        self._stop_btn.setMinimumHeight(24)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_execution)
        bottom.addWidget(self._stop_btn)
        root.addLayout(bottom)
        self._sync_layout_geometry()

    # ------------------------------------------------------------------
    # task / preset list helpers
    # ------------------------------------------------------------------
    def _refresh_task_list(self):
        if not self._tasks_cache:
            result = self._sync_execute("task list")
            if result and result.get("status") == "success":
                self._tasks_cache = result.get("tasks") or {}
                self._task_option_defs = result.get("task_option_defs") or {}
        self._task_list.clear()
        for name in sorted(self._tasks_cache.keys()):
            item = QListWidgetItem(_zh(name))
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._task_list.addItem(item)
        if self._selected_task in self._tasks_cache:
            matches = self._task_list.findItems(_zh(self._selected_task), Qt.MatchFlag.MatchExactly)
            if matches:
                self._task_list.setCurrentItem(matches[0])

    def _refresh_preset_list(self):
        if not self._presets_cache:
            result = self._sync_execute("preset list")
            if result and result.get("status") == "success":
                self._presets_cache = result.get("presets") or {}
        self._preset_list.clear()
        for name in sorted(self._presets_cache.keys()):
            item = QListWidgetItem(_zh(name))
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._preset_list.addItem(item)
        if self._selected_preset in self._presets_cache:
            matches = self._preset_list.findItems(_zh(self._selected_preset), Qt.MatchFlag.MatchExactly)
            if matches:
                self._preset_list.setCurrentItem(matches[0])

    def _on_task_selected(self):
        items = self._task_list.selectedItems()
        self._selected_task = items[0].data(Qt.ItemDataRole.UserRole) if items else None
        self._build_option_editor()

    def _on_preset_selected(self):
        items = self._preset_list.selectedItems()
        self._selected_preset = items[0].data(Qt.ItemDataRole.UserRole) if items else None

    # ------------------------------------------------------------------
    # queue helpers
    # ------------------------------------------------------------------
    def _add_to_queue(self):
        if self._selected_preset:
            preset = self._presets_cache.get(self._selected_preset)
            if not preset:
                QMessageBox.warning(self, "预设不存在", f"预设 '{self._selected_preset}' 未找到。")
                return
            task_list = preset.get("task", [])
            if not task_list:
                QMessageBox.information(self, "预设为空", f"预设 '{self._selected_preset}' 中没有任务。")
            # 添加预设到队列 = 覆盖现有队列（清空再填充），不是追加；与 _run_preset 共享同一覆盖语义。
            for entry in list(self._queue_items):
                name = entry.get("name")
                if name:
                    self._clear_saved_options(name)
            self._queue_items.clear()
            self._queue_list.clear()
            for task_entry in task_list:
                name, inline_options = self._normalize_task_entry(task_entry)
                options = task_entry.get("option") or {}
                if inline_options:
                    options = {**dict(options), **inline_options}
                saved = self._load_options(name)
                if saved:
                    options = dict(options)
                    options.update(saved)
                entry = {"name": name, "display_name": name, "type": "task", "options": dict(options)}
                self._queue_items.append(entry)
                label = self._format_queue_label(name, "task", options)
                self._queue_list.addItem(label)
            self._append_log("预设", f"已应用预设 '{_zh(self._selected_preset)}' ({len(task_list)} 个任务)")
            self._persist_state()
        elif self._selected_task:
            name = self._selected_task
            item_type = "task"
            options = self._collect_options()
            saved = self._load_options(name)
            if saved:
                options.update(saved)
            entry = {"name": name, "display_name": name, "type": item_type, "options": dict(options)}
            self._queue_items.append(entry)
            label = self._format_queue_label(name, item_type, options)
            self._queue_list.addItem(label)
            self._persist_state()
        else:
            QMessageBox.information(self, "未选择", "请先选择一个任务或预设。")

    def _queue_move_up(self):
        row = self._queue_list.currentRow()
        if row <= 0:
            return
        self._queue_items[row], self._queue_items[row - 1] = self._queue_items[row - 1], self._queue_items[row]
        self._queue_list.insertItem(row - 1, self._queue_list.takeItem(row))
        self._queue_list.setCurrentRow(row - 1)
        self._persist_state()

    def _queue_move_down(self):
        row = self._queue_list.currentRow()
        if row < 0 or row >= self._queue_list.count() - 1:
            return
        self._queue_items[row], self._queue_items[row + 1] = self._queue_items[row + 1], self._queue_items[row]
        self._queue_list.insertItem(row + 1, self._queue_list.takeItem(row))
        self._queue_list.setCurrentRow(row + 1)
        self._persist_state()

    def _queue_clear(self):
        for entry in list(self._queue_items):
            name = entry.get("name")
            if name:
                self._clear_saved_options(name)
        self._queue_items.clear()
        self._queue_list.clear()
        self._persist_state()

    def _runtime_queue_runner(self) -> bool:
        items = list(self._queue_items)
        if not items:
            return True
        for entry in items:
            if self._worker and getattr(self._worker, '_stopped', False):
                break
            name, inline_options = self._normalize_runtime_entry(entry)
            item_type = entry.get("type", "task")
            options = entry.get("options") or {}
            if inline_options:
                options = {**dict(options), **inline_options}
            saved = self._load_options(name)
            if saved:
                tmp = dict(options)
                tmp.update(saved)
                options = tmp
            self._append_log("队列", f"执行 {_zh(name)}")
            if item_type == "preset":
                result = self._sync_execute(f"preset run {name}")
                ok = bool(result and result.get("status") == "success")
            else:
                clean_name, inline_options = self._parse_inline_task_name(name)
                merged_options = dict(inline_options)
                merged_options.update(options)
                payload = json.dumps({"name": clean_name, "options": merged_options}, ensure_ascii=False)
                result = self._sync_execute(f"task run {clean_name} --options {payload}")
                ok = bool(result and result.get("status") == "success")
            self._append_log("队列", f"{_zh(name)} -> {'成功' if ok else '失败'}")
            if not ok:
                return False
        return True

    # ------------------------------------------------------------------
    # option editor
    # ------------------------------------------------------------------
    def _build_option_editor(self):
        while self._option_form.count():
            item = self._option_form.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._option_widgets.clear()
        if not self._selected_task:
            hint = QLabel("请先选择一个任务以编辑选项。")
            hint.setStyleSheet(INFO_STYLE)
            self._option_form.addWidget(hint)
            return
        task = self._tasks_cache.get(self._selected_task)
        if not task:
            return
        option_names = task.get("option", [])
        if not option_names:
            hint = QLabel("该任务无可编辑选项。")
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
        self._apply_saved_option_values(self._selected_task)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_layout_geometry()

    def _sync_layout_geometry(self) -> None:
        splitter = getattr(self, "_splitter", None)
        if splitter is None:
            return
        preview_label = getattr(self, "_preview_label", None)
        required = ("_preset_list", "_task_list", "_queue_list", "_log_text")
        if preview_label is None or not all(hasattr(self, name) for name in required):
            return
        left = getattr(self, "_splitter_left", None)
        right = getattr(self, "_splitter_right", None)
        if left is not None and right is not None:
            left.setMinimumWidth(280)
            right.setMinimumWidth(360)
        total = max(self.width(), 1)
        left_width = max(320, int(total * 0.34))
        right_width = max(540, total - left_width - 12)
        splitter.setSizes([left_width, right_width])
        self._preset_list.setMinimumHeight(92)
        self._preset_list.setMaximumHeight(132)
        self._task_list.setMinimumHeight(110)
        self._task_list.setMaximumHeight(168)
        self._queue_list.setMinimumHeight(96)
        self._queue_list.setMaximumHeight(144)
        self._log_text.setMinimumHeight(100)
        self._log_text.setMaximumHeight(144)
        self._option_scroll.setMinimumHeight(180)
        preview_label.setMinimumHeight(180)

    def _create_option_widget(self, name: str, opt_def: Dict[str, Any]) -> QWidget:
        opt_type = opt_def.get("type", "switch")
        cases = opt_def.get("cases", [])
        default_case = opt_def.get("default_case")
        if opt_type == "switch":
            combo = QComboBox()
            combo.setStyleSheet(COMBO_STYLE)
            for case in cases:
                combo.addItem(_resolve_label(case.get("label", case.get("name", ""))))
            if default_case is not None:
                idx = combo.findText(str(default_case))
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            return combo
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
                combo = widget
                options[name] = combo.currentText()
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
                parts.append(f"{key}={{ {inner} }}")
            elif isinstance(value, list):
                parts.append(f"{key}=[{', '.join(map(str, value))}]")
            else:
                parts.append(f"{key}={value}")
        return "; ".join(parts)

    def _save_options(self):
        if not self._selected_task:
            return
        options = self._collect_options()
        self._saved_task_options[self._selected_task] = dict(options)
        try:
            self._persist_state()
            QApplication.beep()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))

    def _load_options(self, task_name: str) -> Dict[str, Any]:
        saved = self._saved_task_options.get(task_name)
        if isinstance(saved, dict):
            return dict(saved)
        return {}

    def _clear_saved_options(self, task_name: str) -> None:
        self._saved_task_options.pop(task_name, None)

    def _apply_saved_option_values(self, task_name: str) -> None:
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
                idx = widget.findText(str(value))
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif opt_type == "checkbox":
                checkboxes = getattr(widget, "checkboxes", {})
                if isinstance(value, list):
                    for n, cb in checkboxes.items():
                        cb.setChecked(n in value)
            elif opt_type == "select":
                idx = widget.findData(str(value))
                if idx < 0:
                    idx = widget.findText(str(value))
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif opt_type == "input":
                line_edits = getattr(widget, "line_edits", {})
                if isinstance(value, dict):
                    for n, le in line_edits.items():
                        if n in value:
                            le.setText(str(value[n]))

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
            state = {
                "selected_task": self._selected_task,
                "selected_preset": self._selected_preset,
                "queue_items": self._queue_items,
                "task_options": self._saved_task_options,
            }
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            self.log_message.emit("持久化", f"保存失败: {e}")

    def _load_state(self) -> None:
        if not self._state_path.exists():
            return
        try:
            state = json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception as e:
            self.log_message.emit("持久化", f"加载失败: {e}")
            return
        self._selected_task = state.get("selected_task") or self._selected_task
        self._selected_preset = state.get("selected_preset") or self._selected_preset
        task_options = state.get("task_options")
        if isinstance(task_options, dict):
            self._saved_task_options = {str(k): dict(v) for k, v in task_options.items() if isinstance(v, dict)}
        queue_items = state.get("queue_items")
        if isinstance(queue_items, list):
            self._queue_items = []
            self._queue_list.clear()
            for entry in queue_items:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name") or "").strip()
                if not name:
                    continue
                name, inline_options = self._parse_inline_task_name(name)
                item_type = entry.get("type", "task")
                options = entry.get("options") or {}
                if inline_options:
                    options = {**inline_options, **dict(options)}
                self._queue_items.append({"name": name, "display_name": str(entry.get("display_name") or name), "type": item_type, "options": dict(options)})
                self._queue_list.addItem(self._format_queue_label(name, item_type, dict(options)))
        if self._selected_task:
            matches = self._task_list.findItems(_zh(self._selected_task), Qt.MatchFlag.MatchExactly)
            if matches:
                self._task_list.setCurrentItem(matches[0])
        if self._selected_preset:
            matches = self._preset_list.findItems(_zh(self._selected_preset), Qt.MatchFlag.MatchExactly)
            if matches:
                self._preset_list.setCurrentItem(matches[0])
        self._persist_state()

    def _open_task_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("任务设置")
        dialog.setMinimumWidth(620)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        info = QLabel(
            "任务选项与队列状态会持久化到本地配置文件。\n"
            f"当前路径：{self._state_path}"
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
        if row < 0 or row >= len(self._queue_items):
            return
        entry = self._queue_items[row]
        name = entry.get("name")
        if not name:
            return
        self._selected_task = name
        self._build_option_editor()

    def _apply_queue_focus_task_settings(self) -> None:
        row = self._queue_list.currentRow()
        if row < 0 or row >= len(self._queue_items):
            QMessageBox.information(self, "未选择", "请先在队列中选择一个任务。")
            return
        entry = self._queue_items[row]
        name = entry.get("name")
        if not name:
            QMessageBox.information(self, "未选择", "请先在队列中选择一个任务。")
            return
        self._selected_task = name
        self._build_option_editor()
        options = self._collect_options()
        entry["options"] = dict(options)
        self._queue_list.item(row).setText(self._format_queue_label(name, entry.get("type", "task"), options))
        self._persist_state()

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
    def _ensure_connected(self) -> bool:
        """Auto-connect runtime if not already connected. Returns True on success."""
        if self._connected:
            return True
        self._append_log("系统", "正在连接 MaaEnd runtime...")
        result = self._sync_execute("system connect", timeout_ms=15000)
        if not result or result.get("status") != "success":
            QMessageBox.warning(self, "连接失败", "无法连接 MaaEnd runtime，请检查设备。")
            return False
        self._connected = True
        self._append_log("系统", "MaaEnd runtime 已连接")
        return True

    def _run_task(self):
        if not self._selected_task or self._is_executing:
            return
        if not self._ensure_connected():
            return
        saved = self._load_options(self._selected_task)
        options = self._collect_options()
        options.update(saved)
        self._start_execution(lambda: self._bridge_task_run(self._selected_task, options))

    def _bridge_task_run(self, name: str, options: Dict[str, Any]) -> bool:
        clean_name, inline_options = self._parse_inline_task_name(name)
        merged_options = dict(inline_options)
        merged_options.update(options)
        payload = json.dumps({"name": clean_name, "options": merged_options}, ensure_ascii=False)
        result = self._sync_execute(f"task run {clean_name} --options {payload}")
        return bool(result and result.get("status") == "success")

    def _run_preset(self):
        if not self._selected_preset or self._is_executing:
            return
        preset = self._presets_cache.get(self._selected_preset)
        if not preset:
            QMessageBox.warning(self, "预设不存在", f"预设 '{self._selected_preset}' 未找到。")
            return
        task_list = preset.get("task", [])
        if not task_list:
            QMessageBox.information(self, "预设为空", f"预设 '{self._selected_preset}' 中没有任务。")
            return
        # 应用预设 = 用预设中的任务列表覆盖现有队列（清空再填充），不是追加。
        for entry in list(self._queue_items):
            name = entry.get("name")
            if name:
                self._clear_saved_options(name)
        self._queue_items.clear()
        self._queue_list.clear()
        for task_entry in task_list:
            name, inline_options = self._normalize_task_entry(task_entry)
            options = task_entry.get("option") or {}
            if inline_options:
                options = {**dict(options), **inline_options}
            saved = self._load_options(name)
            if saved:
                options = dict(options)
                options.update(saved)
            entry = {"name": name, "type": "task", "options": dict(options)}
            self._queue_items.append(entry)
            label = self._format_queue_label(name, "task", options)
            self._queue_list.addItem(label)
        self._append_log("预设", f"已应用预设 '{_zh(self._selected_preset)}' ({len(task_list)} 个任务)")
        self._persist_state()
        return

    def _run_queue(self):
        if not self._queue_items or self._is_executing:
            return
        if not self._ensure_connected():
            return
        self._start_execution(lambda: self._runtime_queue_runner())

    def _start_execution(self, target):
        self._is_executing = True
        self._update_execution_ui()
        self._append_log("系统", "开始执行")
        self._worker = TaskRunWorker(target)
        self._worker.log.connect(self._append_log)
        self._worker.finished.connect(self._on_execution_finished)
        self._worker.start()

    def _stop_execution(self):
        if self._worker:
            self._worker.stop()
        self._append_log("系统", "已请求停止")

    def _on_execution_finished(self, success: bool):
        self._is_executing = False
        self._update_execution_ui()
        self._append_log("系统", f"执行结束: {success}")
        self.execution_state_changed.emit(False)

    def _update_execution_ui(self):
        self._run_task_btn.setEnabled(not self._is_executing)
        self._run_preset_btn.setEnabled(not self._is_executing)
        self._run_queue_btn.setEnabled(not self._is_executing)
        self._add_queue_btn.setEnabled(not self._is_executing)
        self._queue_up_btn.setEnabled(not self._is_executing)
        self._queue_down_btn.setEnabled(not self._is_executing)
        self._queue_clear_btn.setEnabled(not self._is_executing)
        self._stop_btn.setEnabled(self._is_executing)
        self._status_label.setText("运行中" if self._is_executing else "空闲")
        self._status_label.setStyleSheet(RED_STYLE if self._is_executing else GREEN_STYLE)
        self.execution_state_changed.emit(self._is_executing)

    def _append_log(self, source: str, text: str):
        color = BLUE_STYLE if source == "系统" else VAL_STYLE
        self._log_text.append(f"<span style='{color}'>[{source}] {text}</span>")

    def refresh(self):
        self._refresh_task_list()
        self._refresh_preset_list()
        self._build_option_editor()


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
        self.terminate()
