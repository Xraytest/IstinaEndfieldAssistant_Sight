"""Device settings page - Endfield terminal style with device management"""
from typing import Optional, Dict, Any, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QTimeEdit, QCheckBox, QGroupBox, QMessageBox,
    QLineEdit, QFileDialog
)
from PyQt6.QtCore import pyqtSignal, Qt, QTime, QTimer
import json
import os

HEADER_STYLE = "color: #18d1ff; font-size: 14px; font-family: Consolas; font-weight: bold; letter-spacing: 1px; padding: 4px 0;"
INFO_STYLE = "color: #9090a8; font-size: 12px; font-family: Consolas; padding: 3px 0;"
VAL_STYLE = "color: #e8e8ee; font-size: 12px; font-family: Consolas; padding: 3px 0;"
GREEN_STYLE = "color: #00ffa2; font-size: 12px; font-family: Consolas; padding: 3px 0;"
RED_STYLE = "color: #ff3355; font-size: 12px; font-family: Consolas; padding: 3px 0;"
YELLOW_STYLE = "color: #ffcc00; font-size: 12px; font-family: Consolas; padding: 3px 0;"

BTN_ACTIVE = """
    QPushButton {
        background-color: rgba(0, 255, 162, 0.10);
        color: #00ffa2;
        border: 1px solid rgba(0, 255, 162, 0.30);
        border-radius: 2px;
        padding: 6px 12px;
        font-size: 11px; font-family: Consolas; font-weight: bold; letter-spacing: 1px;
    }
    QPushButton:hover { background-color: rgba(0, 255, 162, 0.20); }
"""
BTN_DEFAULT = """
    QPushButton {
        background-color: rgba(24, 209, 255, 0.08);
        color: #18d1ff;
        border: 1px solid rgba(24, 209, 255, 0.22);
        border-radius: 2px;
        padding: 6px 12px;
        font-size: 11px; font-family: Consolas; font-weight: bold; letter-spacing: 1px;
    }
    QPushButton:hover { background-color: rgba(24, 209, 255, 0.16); }
"""
BTN_DANGER = """
    QPushButton {
        background-color: rgba(255, 51, 85, 0.10);
        color: #ff3355;
        border: 1px solid rgba(255, 51, 85, 0.30);
        border-radius: 2px;
        padding: 6px 12px;
        font-size: 11px; font-family: Consolas; font-weight: bold; letter-spacing: 1px;
    }
    QPushButton:hover { background-color: rgba(255, 51, 85, 0.20); }
"""
INPUT_STYLE = """
    QLineEdit, QSpinBox {
        background-color: rgba(16, 16, 26, 0.85);
        color: #e8e8ee;
        border: 1px solid rgba(24, 209, 255, 0.15);
        border-radius: 2px;
        font-size: 12px; font-family: Consolas;
        padding: 6px 10px;
    }
    QLineEdit:focus, QSpinBox:focus {
        border-color: rgba(24, 209, 255, 0.40);
    }
"""


class DeviceSettingsPage(QWidget):
    """Device settings page with device management and MaaFw touch config"""

    settings_changed = pyqtSignal(dict)
    schedule_changed = pyqtSignal(list)
    device_connected = pyqtSignal(str)
    device_disconnected = pyqtSignal()

    def __init__(self, device_manager=None, config: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self._config = config or {}
        self._scheduled_tasks: List[Dict[str, Any]] = []
        self._scanned_devices: List[Dict[str, str]] = []
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._poll_device_status)

        self._setup_ui()
        self._load_config_state()
        self._load_scheduled_tasks()

    def _get_cache_dir(self) -> str:
        current = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current))))
        cache = os.path.join(root, "cache")
        os.makedirs(cache, exist_ok=True)
        return cache

    def _load_scheduled_tasks(self):
        path = os.path.join(self._get_cache_dir(), "scheduled_tasks.json")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self._scheduled_tasks = json.load(f)
            self._update_schedule_table()
        except Exception:
            self._scheduled_tasks = []

    def _save_scheduled_tasks(self):
        path = os.path.join(self._get_cache_dir(), "scheduled_tasks.json")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self._scheduled_tasks, f, indent=2, ensure_ascii=False)
            self.schedule_changed.emit(self._scheduled_tasks)
        except Exception as e:
            print(f"Failed to save scheduled tasks: {e}")

    def _load_config_state(self):
        """Load initial state from config"""
        auto_connect = self._config.get('device', {}).get('auto_connect', False)
        self._auto_connect_cb.setChecked(auto_connect)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("// 设备设置")
        title.setStyleSheet(HEADER_STYLE)
        layout.addWidget(title)

        # ── 设备连接 ──
        device_group = self._make_card("设备连接")
        device_layout = QVBoxLayout()
        device_layout.setContentsMargins(24, 20, 24, 20)
        device_layout.setSpacing(14)

        # 连接状态行
        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("连接状态:"))
        status_row.itemAt(0).widget().setStyleSheet(INFO_STYLE)
        self._status_indicator = QLabel("\u25cf 未连接")
        self._status_indicator.setStyleSheet(RED_STYLE)
        status_row.addWidget(self._status_indicator)
        status_row.addStretch()
        device_layout.addLayout(status_row)

        # 上次连接设备
        last_device_row = QHBoxLayout()
        last_device_row.addWidget(QLabel("上次连接:"))
        last_device_row.itemAt(0).widget().setStyleSheet(INFO_STYLE)
        self._last_device_label = QLabel("无")
        self._last_device_label.setStyleSheet(VAL_STYLE)
        last_device_row.addWidget(self._last_device_label)
        last_device_row.addStretch()
        device_layout.addLayout(last_device_row)

        # 间隔
        device_layout.addSpacing(4)

        # 设备序列号输入 + 连接/断开
        serial_row = QHBoxLayout()
        serial_label = QLabel("序列号:")
        serial_label.setStyleSheet(INFO_STYLE)
        serial_row.addWidget(serial_label)

        self._serial_input = QLineEdit()
        self._serial_input.setPlaceholderText("emulator-5554 或 127.0.0.1:5555")
        self._serial_input.setStyleSheet(INPUT_STYLE)
        serial_row.addWidget(self._serial_input)

        self._connect_btn = QPushButton("连接")
        self._connect_btn.setStyleSheet(BTN_ACTIVE)
        self._connect_btn.clicked.connect(self._connect_device)
        self._connect_btn.setFixedWidth(80)
        serial_row.addWidget(self._connect_btn)

        self._disconnect_btn = QPushButton("断开")
        self._disconnect_btn.setStyleSheet(BTN_DANGER)
        self._disconnect_btn.clicked.connect(self._disconnect_device)
        self._disconnect_btn.setFixedWidth(80)
        self._disconnect_btn.setEnabled(False)
        serial_row.addWidget(self._disconnect_btn)

        device_layout.addLayout(serial_row)

        # 间隔
        device_layout.addSpacing(4)

        # 扫描按钮
        scan_row = QHBoxLayout()
        self._scan_btn = QPushButton("扫描设备")
        self._scan_btn.setStyleSheet(BTN_DEFAULT)
        self._scan_btn.clicked.connect(self._scan_devices)
        scan_row.addWidget(self._scan_btn)
        scan_row.addStretch()
        device_layout.addLayout(scan_row)

        # 扫描结果
        self._scan_status_label = QLabel("")
        self._scan_status_label.setStyleSheet("color: #9090a8; font-size: 11px; font-family: Consolas; padding: 2px 0;")
        device_layout.addWidget(self._scan_status_label)

        # 设备列表表格
        self._device_table = QTableWidget()
        self._device_table.setColumnCount(3)
        self._device_table.setHorizontalHeaderLabels(["序列号", "状态", "型号"])
        self._device_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._device_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._device_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._device_table.setColumnWidth(1, 100)
        self._device_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._device_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._device_table.setStyleSheet("""
            QTableWidget {
                background-color: rgba(16, 16, 26, 0.85);
                border: 1px solid rgba(24, 209, 255, 0.08);
                border-radius: 2px;
                color: #e8e8ee; font-size: 12px; font-family: Consolas;
                gridline-color: rgba(24, 209, 255, 0.06);
            }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:selected {
                background-color: rgba(24, 209, 255, 0.12);
                color: #18d1ff;
            }
            QHeaderView::section {
                background-color: rgba(24, 209, 255, 0.08);
                color: #18d1ff; font-size: 11px; font-weight: bold;
                padding: 6px; border: none;
            }
        """)
        self._device_table.itemSelectionChanged.connect(self._on_device_selected)
        self._device_table.setMinimumHeight(120)
        self._device_table.setMaximumHeight(200)
        device_layout.addWidget(self._device_table)

        # 自动连接复选框
        self._auto_connect_cb = QCheckBox("启动时自动连接")
        self._auto_connect_cb.setStyleSheet(self._checkbox_style())
        self._auto_connect_cb.setToolTip("启动时自动连接上次使用的设备")
        self._auto_connect_cb.stateChanged.connect(self._on_auto_connect_changed)
        device_layout.addWidget(self._auto_connect_cb)

        # 上次连接设备
        last_device_row = QHBoxLayout()
        last_device_row.addWidget(QLabel("上次连接:"))
        last_device_row.itemAt(0).widget().setStyleSheet(INFO_STYLE)
        self._last_device_label = QLabel("无")
        self._last_device_label.setStyleSheet(VAL_STYLE)
        last_device_row.addWidget(self._last_device_label)
        last_device_row.addStretch()
        device_layout.addLayout(last_device_row)

        # 自动连接
        self._auto_connect_cb = QCheckBox("启动时自动连接")
        self._auto_connect_cb.setStyleSheet(self._checkbox_style())
        self._auto_connect_cb.setToolTip("启动时自动连接上次使用的设备")
        self._auto_connect_cb.stateChanged.connect(self._on_auto_connect_changed)
        device_layout.addWidget(self._auto_connect_cb)

        device_group.setLayout(device_layout)
        layout.addWidget(device_group)

        # ── 定时标准流启动 ──
        schedule_group = self._make_card("定时标准流启动")
        schedule_layout = QVBoxLayout()
        schedule_layout.setContentsMargins(20, 16, 20, 16)
        schedule_layout.setSpacing(6)

        # 定时任务表格
        self._schedule_table = QTableWidget()
        self._schedule_table.setColumnCount(4)
        self._schedule_table.setHorizontalHeaderLabels(["时间", "流程名称", "启用", "操作"])
        self._schedule_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._schedule_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._schedule_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._schedule_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._schedule_table.setColumnWidth(0, 100)
        self._schedule_table.setColumnWidth(2, 80)
        self._schedule_table.setColumnWidth(3, 100)
        self._schedule_table.setStyleSheet("""
            QTableWidget {
                background-color: rgba(16, 16, 26, 0.85);
                border: 1px solid rgba(24, 209, 255, 0.08);
                border-radius: 2px;
                color: #e8e8ee; font-size: 12px; font-family: Consolas;
                gridline-color: rgba(24, 209, 255, 0.06);
            }
            QTableWidget::item { padding: 8px; }
            QHeaderView::section {
                background-color: rgba(24, 209, 255, 0.08);
                color: #18d1ff; font-size: 11px; font-weight: bold;
                padding: 8px; border: none;
            }
        """)
        schedule_layout.addWidget(self._schedule_table)

        # 添加/移除按钮
        btn_layout = QHBoxLayout()
        self._add_task_btn = QPushButton("添加任务")
        self._add_task_btn.setStyleSheet(BTN_ACTIVE)
        self._add_task_btn.clicked.connect(self._add_scheduled_task)
        btn_layout.addWidget(self._add_task_btn)

        self._remove_task_btn = QPushButton("移除")
        self._remove_task_btn.setStyleSheet(BTN_DEFAULT)
        self._remove_task_btn.clicked.connect(self._remove_scheduled_task)
        btn_layout.addWidget(self._remove_task_btn)

        self._save_schedule_btn = QPushButton("保存")
        self._save_schedule_btn.setStyleSheet(BTN_ACTIVE)
        self._save_schedule_btn.clicked.connect(self._save_scheduled_tasks)
        btn_layout.addWidget(self._save_schedule_btn)

        btn_layout.addStretch()
        schedule_layout.addLayout(btn_layout)

        schedule_group.setLayout(schedule_layout)
        layout.addWidget(schedule_group)

        layout.addStretch()
        self._update_device_info()

    def _checkbox_style(self) -> str:
        return """
            QCheckBox {
                color: #e8e8ee; font-size: 12px; font-family: Consolas; spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px; height: 16px; border-radius: 2px;
                border: 1px solid rgba(24, 209, 255, 0.30); background-color: transparent;
            }
            QCheckBox::indicator:checked {
                background-color: #18d1ff; border-color: #18d1ff;
            }
        """

    def _make_card(self, title: str) -> QGroupBox:
        group = QGroupBox()
        group.setStyleSheet("""
            QGroupBox {
                background-color: rgba(16, 16, 26, 0.85);
                border: 1px solid rgba(24, 209, 255, 0.08);
                border-radius: 3px;
                font-size: 13px; font-family: Consolas;
                color: #e8e8ee; font-weight: bold; letter-spacing: 1px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 16px; padding: 0 4px;
            }
        """)
        group.setTitle(title)
        return group

    # ── Device Connection Handlers ──

    def _scan_devices(self):
        """Scan for available ADB devices"""
        if not self.device_manager:
            self._scan_status_label.setText("设备管理器不可用")
            return

        self._scan_btn.setEnabled(False)
        self._scan_status_label.setText("扫描中...")

        try:
            devices = self.device_manager.scan_devices()
            self._scanned_devices = []
            self._device_table.setRowCount(len(devices))

            for i, d in enumerate(devices):
                serial = getattr(d, 'serial', str(d))
                status = getattr(d, 'status', 'device')
                model = getattr(d, 'model', '')

                self._scanned_devices.append({
                    'serial': serial,
                    'status': status,
                    'model': model
                })

                serial_item = QTableWidgetItem(serial)
                serial_item.setFlags(serial_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._device_table.setItem(i, 0, serial_item)

                status_item = QTableWidgetItem(status.upper())
                status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                status_item.setForeground(
                    Qt.GlobalColor.green if status == 'device' else Qt.GlobalColor.yellow
                )
                self._device_table.setItem(i, 1, status_item)

                model_item = QTableWidgetItem(model if model else '-')
                model_item.setFlags(model_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._device_table.setItem(i, 2, model_item)

            count = len(devices)
            self._scan_status_label.setText(f"发现 {count} 台设备" if count else "未发现设备")

        except Exception as e:
            self._scan_status_label.setText(f"扫描失败: {e}")
        finally:
            self._scan_btn.setEnabled(True)

    def _on_device_selected(self):
        """When a device row is selected, copy its serial to the input field"""
        rows = self._device_table.selectedItems()
        if rows:
            row = rows[0].row()
            serial_item = self._device_table.item(row, 0)
            if serial_item:
                self._serial_input.setText(serial_item.text())

    def _connect_device(self):
        """Connect to the device specified in the serial input"""
        serial = self._serial_input.text().strip()
        if not serial:
            QMessageBox.warning(self, "未指定设备", "请输入设备序列号或从列表中选择。")
            return

        if not self.device_manager:
            QMessageBox.critical(self, "错误", "设备管理器不可用。")
            return

        self._connect_btn.setEnabled(False)
        self._connect_btn.setText("连接中...")

        try:
            success = self.device_manager.connect_device(serial)
            if success:
                self._update_connection_status(True, serial)
                self.device_connected.emit(serial)
            else:
                QMessageBox.warning(self, "连接失败",
                    f"无法连接到设备: {serial}\n\n"
                    "请确认设备可用且 ADB 已正确配置。")
                self._update_connection_status(False)
        except Exception as e:
            QMessageBox.critical(self, "连接错误", f"连接设备时出错: {e}")
            self._update_connection_status(False)
        finally:
            self._connect_btn.setEnabled(True)
            self._connect_btn.setText("连接")

    def _disconnect_device(self):
        """Disconnect the current device"""
        if not self.device_manager:
            return

        try:
            self.device_manager.disconnect_device()
            self._update_connection_status(False)
            self.device_disconnected.emit()
        except Exception as e:
            QMessageBox.critical(self, "断开错误", f"断开时出错: {e}")

    def _update_connection_status(self, connected: bool, serial: str = ""):
        """更新 UI 反映连接状态"""
        if connected:
            self._status_indicator.setText(f"\u25cf 已连接 ({serial})")
            self._status_indicator.setStyleSheet(GREEN_STYLE)
            self._connect_btn.setEnabled(False)
            self._disconnect_btn.setEnabled(True)
            self._serial_input.setEnabled(False)
            self._last_device_label.setText(serial)
            self._last_device_label.setStyleSheet(GREEN_STYLE)
            self._status_timer.start(5000)  # 每 5 秒轮询
        else:
            self._status_indicator.setText("\u25cf 未连接")
            self._status_indicator.setStyleSheet(RED_STYLE)
            self._connect_btn.setEnabled(True)
            self._disconnect_btn.setEnabled(False)
            self._serial_input.setEnabled(True)
            self._status_timer.stop()

    def _poll_device_status(self):
        """Periodically check if device is still connected"""
        if not self.device_manager:
            return
        current = self.device_manager.get_current_device()
        if not current:
            self._update_connection_status(False)
            self.device_disconnected.emit()

    def _on_auto_connect_changed(self, state):
        enabled = state == Qt.CheckState.Checked
        self._config.setdefault('device', {})
        self._config['device']['auto_connect'] = enabled
        self.settings_changed.emit(self._config)

    def _update_device_info(self):
        """更新上次连接设备显示"""
        if self.device_manager:
            last_device = self.device_manager.get_last_connected_device()
            if last_device:
                self._last_device_label.setText(last_device)
                self._last_device_label.setStyleSheet(GREEN_STYLE)
            else:
                self._last_device_label.setText("无")
                self._last_device_label.setStyleSheet(RED_STYLE)

            # Also check if currently connected
            current = self.device_manager.get_current_device()
            if current:
                self._update_connection_status(True, current)

    # ── Schedule Handlers ──

    def _update_schedule_table(self):
        self._schedule_table.setRowCount(len(self._scheduled_tasks))
        for i, task in enumerate(self._scheduled_tasks):
            # Time column
            time_item = QTableWidgetItem(task.get('time', '00:00'))
            time_item.setData(Qt.ItemDataRole.EditRole, task.get('time', '00:00'))
            self._schedule_table.setItem(i, 0, time_item)

            # Flow name column
            flow_item = QTableWidgetItem(task.get('flow_name', 'standard'))
            flow_item.setData(Qt.ItemDataRole.EditRole, task.get('flow_name', 'standard'))
            self._schedule_table.setItem(i, 1, flow_item)

            # Enabled column
            enabled_widget = QCheckBox()
            enabled_widget.setChecked(task.get('enabled', True))
            enabled_widget.stateChanged.connect(lambda s, row=i: self._on_task_enabled_changed(row))
            self._schedule_table.setCellWidget(i, 2, enabled_widget)

    def _on_task_enabled_changed(self, row: int):
        if row < len(self._scheduled_tasks):
            checkbox = self._schedule_table.cellWidget(row, 2)
            self._scheduled_tasks[row]['enabled'] = checkbox.isChecked()

    def _add_scheduled_task(self):
        new_task = {
            'time': '08:00',
            'flow_name': 'standard',
            'enabled': True
        }
        self._scheduled_tasks.append(new_task)
        self._update_schedule_table()

    def _remove_scheduled_task(self):
        current_row = self._schedule_table.currentRow()
        if current_row >= 0 and current_row < len(self._scheduled_tasks):
            self._scheduled_tasks.pop(current_row)
            self._update_schedule_table()
        else:
            QMessageBox.warning(self, "未选择", "请选择要移除的任务。")

    def get_scheduled_tasks(self) -> List[Dict[str, Any]]:
        return self._scheduled_tasks

    def set_device_manager(self, device_manager):
        self.device_manager = device_manager
        self._update_device_info()
