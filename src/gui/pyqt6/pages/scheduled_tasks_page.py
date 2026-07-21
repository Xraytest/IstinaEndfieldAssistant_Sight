"""定时任务页：管理按计划自动执行的任务队列。

功能：
- 添加/编辑/删除定时任务
- 批量启用/禁用/删除
- 立即手动触发
- 选择执行目标：当前队列 或 预设列表
- 选择执行设备（可空，空=使用当前已连接设备）
- 选择执行时间（HH:MM）+ 重复星期几
- "启动模拟器后再执行"选项（仅当 client_config.device.emulator.path 已配置时启用）
- 用户首次选择"预设"作为执行目标时弹出说明：预设内任务选项走任务全局设置
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from PyQt6.QtCore import Qt, QTimer, QTime
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from core.foundation.paths import get_project_root
from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.scheduled_task_scheduler import ScheduledTaskScheduler
from gui.pyqt6.scheduled_task_store import (
    ScheduledTask,
    ScheduledTaskStore,
)
from gui.pyqt6.theme.hero import HeroHeader
from gui.pyqt6.theme.widget_styles import TABLE_STYLE

if TYPE_CHECKING:
    from gui.pyqt6.pages.maaend_control_page import MaaEndControlPage

locale = get_locale_manager()


_WEEKDAY_LABEL_KEYS = [
    "weekday_mon", "weekday_tue", "weekday_wed", "weekday_thu",
    "weekday_fri", "weekday_sat", "weekday_sun",
]


class ScheduledTaskDialog(QDialog):
    """添加/编辑定时任务的对话框。"""

    def __init__(
        self,
        store: ScheduledTaskStore,
        bridge: CLIBridge,
        presets: List[str],
        devices: List[str],
        task: Optional[ScheduledTask] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._bridge = bridge
        self._presets = list(presets)
        self._devices = list(devices)
        self._task = task
        self._result_task: Optional[ScheduledTask] = None

        self.setWindowTitle(locale.tr(
            "sched_dlg_title_edit" if task is not None else "sched_dlg_title_add",
            "Edit Scheduled Task" if task is not None else "Add Scheduled Task",
        ))
        self.setMinimumWidth(520)
        self._setup_ui()
        self._load_task()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText(locale.tr("sched_dlg_name_ph", "e.g. Daily Morning Routine"))
        form.addRow(locale.tr("sched_dlg_name", "Name"), self._name_input)

        # 执行目标：单个下拉列表，第 1 项为"当前队列"，后续为各预设队列
        target_widget = QWidget()
        target_layout = QVBoxLayout(target_widget)
        target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.setSpacing(6)

        self._target_combo = QComboBox()
        # 第 0 项：当前队列（data 为空字符串标识）
        self._target_combo.addItem(locale.tr("sched_dlg_target_queue", "Current Queue"), "")
        for name in self._presets:
            # data 存预设名，用于区分"当前队列"与"预设"
            self._target_combo.addItem(
                locale.tr("sched_dlg_target_preset", "Preset: {name}").format(name=name),
                name,
            )
        self._target_combo.currentIndexChanged.connect(self._on_target_changed)
        target_layout.addWidget(self._target_combo)

        # 预设提醒：仅当选中预设项时显示
        self._preset_reminder_label = QLabel(locale.tr(
            "sched_preset_reminder_inline",
            "Note: Tasks inside a preset use task global settings (configured in Standard Inference page), not task defaults or current queue settings.",
        ))
        self._preset_reminder_label.setProperty("variant", "secondary")
        self._preset_reminder_label.setWordWrap(True)
        self._preset_reminder_label.setVisible(False)
        target_layout.addWidget(self._preset_reminder_label)

        form.addRow(locale.tr("sched_dlg_target", "Execution Target"), target_widget)

        # 执行设备
        self._device_combo = QComboBox()
        self._device_combo.addItem(locale.tr("sched_dlg_device_default", "(use current device)"), "")
        for serial in self._devices:
            self._device_combo.addItem(serial, serial)
        self._device_combo.setEditable(True)
        form.addRow(locale.tr("sched_dlg_device", "Device"), self._device_combo)

        # 执行时间
        self._time_edit = QTimeEdit()
        self._time_edit.setDisplayFormat("HH:mm")
        self._time_edit.setTime(QTime(8, 0))
        form.addRow(locale.tr("sched_dlg_time", "Trigger Time"), self._time_edit)

        # 重复星期
        repeat_widget = QWidget()
        repeat_layout = QHBoxLayout(repeat_widget)
        repeat_layout.setContentsMargins(0, 0, 0, 0)
        repeat_layout.setSpacing(8)
        self._weekday_checks: List[QCheckBox] = []
        for i, key in enumerate(_WEEKDAY_LABEL_KEYS):
            cb = QCheckBox(locale.tr(key, ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][i]))
            cb.setChecked(True)
            self._weekday_checks.append(cb)
            repeat_layout.addWidget(cb)
        repeat_layout.addStretch()
        form.addRow(locale.tr("sched_dlg_weekdays", "Repeat"), repeat_widget)

        # 启动模拟器
        self._launch_emulator_check = QCheckBox(locale.tr(
            "sched_dlg_launch_emulator",
            "Launch emulator before execution (requires emulator path in Settings)",
        ))
        emulator_ok = self._is_emulator_configured()
        self._launch_emulator_check.setEnabled(emulator_ok)
        if not emulator_ok:
            self._launch_emulator_check.setToolTip(locale.tr(
                "sched_dlg_launch_emulator_disabled_tip",
                "Configure emulator path in Settings to enable this option.",
            ))
        form.addRow("", self._launch_emulator_check)

        # 启用
        self._enabled_check = QCheckBox(locale.tr("sched_dlg_enabled", "Enabled"))
        self._enabled_check.setChecked(True)
        form.addRow("", self._enabled_check)

        layout.addLayout(form)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(locale.tr("btn_ok", "OK"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(locale.tr("btn_cancel", "Cancel"))
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _is_emulator_configured(self) -> bool:
        cfg_path = get_project_root() / "config" / "client_config.json"
        if not cfg_path.exists():
            return False
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            emu = (cfg.get("device") or {}).get("emulator") or {}
            return bool(str(emu.get("path") or "").strip())
        except Exception:
            return False

    def _load_task(self) -> None:
        if self._task is None:
            self._target_combo.setCurrentIndex(0)
            self._on_target_changed(0)
            return
        t = self._task
        self._name_input.setText(t.name)
        if t.target_type == "preset":
            idx = self._target_combo.findData(t.target_name)
            if idx < 0:
                # 预设列表中没有此预设（已删除？），追加一个临时项保留原值
                idx = self._target_combo.count()
                self._target_combo.blockSignals(True)
                self._target_combo.addItem(
                    locale.tr("sched_dlg_target_preset", "Preset: {name}").format(name=t.target_name),
                    t.target_name,
                )
                self._target_combo.blockSignals(False)
            self._target_combo.setCurrentIndex(idx)
        else:
            self._target_combo.setCurrentIndex(0)
        self._on_target_changed(self._target_combo.currentIndex())

        idx = self._device_combo.findData(t.device_serial)
        if idx >= 0:
            self._device_combo.setCurrentIndex(idx)
        elif t.device_serial:
            self._device_combo.setEditText(t.device_serial)
        try:
            hh, mm = t.trigger_time.split(":")
            self._time_edit.setTime(QTime(int(hh), int(mm)))
        except Exception:
            pass
        if t.weekdays:
            for i, cb in enumerate(self._weekday_checks):
                cb.setChecked(i in t.weekdays)
        else:
            for cb in self._weekday_checks:
                cb.setChecked(True)
        self._launch_emulator_check.setChecked(t.launch_emulator and self._is_emulator_configured())
        self._enabled_check.setChecked(t.enabled)

    def _on_target_changed(self, index: int) -> None:
        """下拉选择变化时，按是否为预设项显示/隐藏提醒文字。"""
        if index < 0:
            return
        preset_name = self._target_combo.itemData(index)
        is_preset = bool(preset_name)
        self._preset_reminder_label.setVisible(is_preset)

    def _on_accept(self) -> None:
        name = self._name_input.text().strip()
        if not name:
            QMessageBox.warning(self, locale.tr("sched_dlg_name_required_title", "Name Required"),
                                locale.tr("sched_dlg_name_required_msg", "Please enter a task name."))
            return
        preset_name = self._target_combo.currentData()
        if preset_name:
            target_type = "preset"
            target_name = str(preset_name).strip()
        else:
            target_type = "queue"
            target_name = ""

        weekdays = [i for i, cb in enumerate(self._weekday_checks) if cb.isChecked()]
        # 全选 = 每天 = 用空列表表示
        if len(weekdays) == 7:
            weekdays = []

        trigger_time = self._time_edit.time().toString("HH:mm")
        device_serial = self._device_combo.currentData() or self._device_combo.currentText().strip()
        launch_emulator = self._launch_emulator_check.isChecked() and self._launch_emulator_check.isEnabled()

        if self._task is None:
            self._result_task = ScheduledTask(
                name=name,
                target_type=target_type,
                target_name=target_name,
                device_serial=device_serial,
                trigger_time=trigger_time,
                weekdays=weekdays,
                launch_emulator=launch_emulator,
                enabled=self._enabled_check.isChecked(),
            )
        else:
            t = self._task
            t.name = name
            t.target_type = target_type
            t.target_name = target_name
            t.device_serial = device_serial
            t.trigger_time = trigger_time
            t.weekdays = weekdays
            t.launch_emulator = launch_emulator
            t.enabled = self._enabled_check.isChecked()
            self._result_task = t

        self.accept()

    @property
    def result_task(self) -> Optional[ScheduledTask]:
        return self._result_task


class ScheduledTasksPage(QWidget):
    """定时任务主页面。"""

    def __init__(
        self,
        bridge: CLIBridge,
        store: Optional[ScheduledTaskStore] = None,
        scheduler: Optional[ScheduledTaskScheduler] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._store = store or ScheduledTaskStore()
        self._scheduler = scheduler or ScheduledTaskScheduler(self._store, self._bridge, parent=self)
        self._presets: List[str] = []
        self._devices: List[str] = []
        # 标准推理页引用：调度器执行日志路由到此页的日志面板，定时任务页不再保留独立日志
        self._maaend_page: Optional["MaaEndControlPage"] = None
        self._setup_ui()
        self._refresh_metadata()
        self._refresh_table()

        # 启动调度器
        self._scheduler.task_log.connect(self._on_scheduler_log)
        self._scheduler.task_state_changed.connect(self._on_scheduler_state_changed)
        self._scheduler.busy_state_changed.connect(self._on_scheduler_busy_changed)
        self._scheduler.start()

        # 周期性刷新设备列表（用于对话框下拉选项）
        self._meta_timer = QTimer(self)
        self._meta_timer.setInterval(60_000)
        self._meta_timer.timeout.connect(self._refresh_metadata)
        self._meta_timer.start()

    def set_maaend_page(self, page: "MaaEndControlPage") -> None:
        """注入标准推理页引用，用于将定时任务执行日志转发到其日志面板。"""
        self._maaend_page = page

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
        content_root.setSpacing(12)

        header = HeroHeader(
            locale.tr("sched_title", "Scheduled Tasks"),
            locale.tr("sched_subtitle", "Manage scheduled task queue executions. Tasks can target the current queue or a preset."),
            content,
        )
        content_root.addWidget(header)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self._add_btn = QPushButton(locale.tr("btn_add", "Add"))
        self._add_btn.clicked.connect(self._on_add)
        toolbar.addWidget(self._add_btn)

        self._edit_btn = QPushButton(locale.tr("btn_edit", "Edit"))
        self._edit_btn.setProperty("variant", "secondary")
        self._edit_btn.clicked.connect(self._on_edit)
        toolbar.addWidget(self._edit_btn)

        self._delete_btn = QPushButton(locale.tr("btn_delete", "Delete"))
        self._delete_btn.setProperty("variant", "danger")
        self._delete_btn.clicked.connect(self._on_delete)
        toolbar.addWidget(self._delete_btn)

        toolbar.addSpacing(12)

        self._enable_btn = QPushButton(locale.tr("btn_enable", "Enable"))
        self._enable_btn.setProperty("variant", "secondary")
        self._enable_btn.clicked.connect(lambda: self._set_selected_enabled(True))
        toolbar.addWidget(self._enable_btn)

        self._disable_btn = QPushButton(locale.tr("btn_disable", "Disable"))
        self._disable_btn.setProperty("variant", "secondary")
        self._disable_btn.clicked.connect(lambda: self._set_selected_enabled(False))
        toolbar.addWidget(self._disable_btn)

        self._run_now_btn = QPushButton(locale.tr("btn_run_now", "Run Now"))
        self._run_now_btn.clicked.connect(self._on_run_now)
        toolbar.addWidget(self._run_now_btn)

        toolbar.addStretch()

        self._status_label = QLabel(locale.tr("sched_status_idle", "Scheduler: idle"))
        self._status_label.setProperty("variant", "secondary")
        toolbar.addWidget(self._status_label)

        content_root.addLayout(toolbar)

        # 任务表
        table_card = QGroupBox(locale.tr("sched_table_title", "Scheduled Task List"))
        table_layout = QVBoxLayout(table_card)
        self._table = QTableWidget(0, 8)
        self._table.setStyleSheet(TABLE_STYLE)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setHorizontalHeaderLabels([
            locale.tr("sched_col_name", "Name"),
            locale.tr("sched_col_target", "Target"),
            locale.tr("sched_col_time", "Time"),
            locale.tr("sched_col_device", "Device"),
            locale.tr("sched_col_emulator", "Emulator"),
            locale.tr("sched_col_last_run", "Last Run"),
            locale.tr("sched_col_next_run", "Next Run"),
            locale.tr("sched_col_enabled", "Enabled"),
        ])
        header_view = self._table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setMinimumHeight(220)
        self._table.itemDoubleClicked.connect(self._on_edit)
        table_layout.addWidget(self._table)

        # 提示
        hint = QLabel(locale.tr(
            "sched_hint",
            "Tip: Tasks targeting a preset use task global settings (configured in Standard Inference page), not current queue settings.",
        ))
        hint.setProperty("variant", "secondary")
        hint.setWordWrap(True)
        table_layout.addWidget(hint)

        content_root.addWidget(table_card)

        # 执行日志说明：定时任务的执行日志统一打印到「标准推理」页的日志面板，
        # 定时任务页本身不再保留独立日志区，避免日志分散。
        log_hint = QLabel(locale.tr(
            "sched_log_hint",
            "Execution logs are printed to the Standard Inference page. Switch there to view scheduled task execution details.",
        ))
        log_hint.setProperty("variant", "secondary")
        log_hint.setWordWrap(True)
        content_root.addWidget(log_hint)
        content_root.addStretch()

    # ============ 元数据刷新 ============

    def _refresh_metadata(self) -> None:
        # 通过 metadata list 获取预设列表
        self._bridge.execute_async(
            "metadata list",
            {},
            on_done=self._on_metadata_done,
            on_error=self._on_metadata_error,
            timeout_ms=10_000,
        )
        # 同时刷新设备列表
        self._bridge.execute_async(
            "device info",
            {},
            on_done=self._on_device_info_done,
            on_error=lambda _msg: None,
            timeout_ms=10_000,
        )

    def _on_metadata_done(self, result: dict) -> None:
        presets = result.get("presets") or []
        names: List[str] = []
        for p in presets:
            if isinstance(p, dict):
                name = str(p.get("name") or "").strip()
                if name:
                    names.append(name)
            elif isinstance(p, str):
                names.append(p)
        self._presets = names

    def _on_metadata_error(self, msg: str) -> None:
        # 静默失败：可能在启动时 CLI 未就绪
        pass

    def _on_device_info_done(self, result: dict) -> None:
        devices = result.get("devices") or []
        serials: List[str] = []
        for d in devices:
            if isinstance(d, dict):
                serial = str(d.get("serial") or d.get("address") or "").strip()
                if serial:
                    serials.append(serial)
            elif isinstance(d, str):
                serials.append(d)
        self._devices = serials
        # 同时合并 client_config.json 中的 device.history
        try:
            cfg_path = get_project_root() / "config" / "client_config.json"
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                history = (cfg.get("device") or {}).get("history") or []
                for h in history:
                    h = str(h).strip()
                    if h and h not in self._devices:
                        self._devices.append(h)
        except Exception:
            pass

    # ============ 表格刷新 ============

    def _refresh_table(self) -> None:
        tasks = self._store.list_tasks()
        self._table.setRowCount(0)
        for task in tasks:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(task.name))
            if task.target_type == "preset":
                target_text = locale.tr("sched_target_preset", "Preset: {name}").format(name=task.target_name)
            else:
                target_text = locale.tr("sched_target_queue", "Current Queue")
            self._table.setItem(row, 1, QTableWidgetItem(target_text))

            if task.weekdays:
                days_label = " ".join(
                    locale.tr(_WEEKDAY_LABEL_KEYS[i], ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][i])
                    for i in sorted(task.weekdays)
                )
            else:
                days_label = locale.tr("sched_every_day", "Every day")
            self._table.setItem(row, 2, QTableWidgetItem(f"{task.trigger_time}  {days_label}"))

            self._table.setItem(row, 3, QTableWidgetItem(task.device_serial or locale.tr("sched_default_device", "(default)")))
            self._table.setItem(row, 4, QTableWidgetItem("✓" if task.launch_emulator else ""))
            self._table.setItem(row, 5, QTableWidgetItem(self._format_dt(task.last_run_at)))
            next_text = self._format_dt(task.next_run_at)
            if not task.enabled:
                next_text = f"[{locale.tr('sched_disabled', 'disabled')}]"
            self._table.setItem(row, 6, QTableWidgetItem(next_text))
            self._table.setItem(row, 7, QTableWidgetItem(locale.tr("sched_yes", "Yes") if task.enabled else locale.tr("sched_no", "No")))

            # 保存 id 到第 0 列 item 的 data
            name_item = self._table.item(row, 0)
            if name_item is not None:
                name_item.setData(Qt.ItemDataRole.UserRole, task.id)
                if not task.enabled:
                    name_item.setForeground(Qt.GlobalColor.gray)

    @staticmethod
    def _format_dt(iso_str: Optional[str]) -> str:
        if not iso_str:
            return "-"
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return iso_str

    def _selected_task_ids(self) -> List[str]:
        ids: List[str] = []
        for item in self._table.selectedItems():
            if item.column() != 0:
                continue
            tid = item.data(Qt.ItemDataRole.UserRole)
            if tid and tid not in ids:
                ids.append(tid)
        return ids

    # ============ 操作 ============

    def _on_add(self) -> None:
        dlg = ScheduledTaskDialog(self._store, self._bridge, self._presets, self._devices, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_task is not None:
            self._store.add_task(dlg.result_task)
            self._refresh_table()
            self._append_log(locale.tr("sched_log_added", "Added scheduled task: {name}").format(name=dlg.result_task.name))

    def _on_edit(self) -> None:
        ids = self._selected_task_ids()
        if not ids:
            QMessageBox.information(self, locale.tr("sched_no_selection_title", "No Selection"),
                                    locale.tr("sched_no_selection_msg", "Please select a task first."))
            return
        if len(ids) > 1:
            QMessageBox.information(self, locale.tr("sched_single_selection_title", "Multiple Selected"),
                                    locale.tr("sched_single_selection_msg", "Please select only one task to edit."))
            return
        task = self._store.get_task(ids[0])
        if task is None:
            return
        dlg = ScheduledTaskDialog(self._store, self._bridge, self._presets, self._devices, task=task, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_task is not None:
            self._store.update_task(dlg.result_task)
            self._refresh_table()
            self._append_log(locale.tr("sched_log_updated", "Updated scheduled task: {name}").format(name=dlg.result_task.name))

    def _on_delete(self) -> None:
        ids = self._selected_task_ids()
        if not ids:
            QMessageBox.information(self, locale.tr("sched_no_selection_title", "No Selection"),
                                    locale.tr("sched_no_selection_msg", "Please select a task first."))
            return
        confirm = QMessageBox.question(
            self,
            locale.tr("sched_delete_confirm_title", "Confirm Delete"),
            locale.tr("sched_delete_confirm_msg", "Delete {count} scheduled task(s)?").format(count=len(ids)),
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        removed = self._store.delete_tasks(ids)
        self._refresh_table()
        self._append_log(locale.tr("sched_log_deleted", "Deleted {count} scheduled task(s).").format(count=removed))

    def _set_selected_enabled(self, enabled: bool) -> None:
        ids = self._selected_task_ids()
        if not ids:
            return
        count = self._store.set_enabled(ids, enabled)
        self._refresh_table()
        action = locale.tr("sched_enabled", "enabled") if enabled else locale.tr("sched_disabled", "disabled")
        self._append_log(locale.tr("sched_log_set_enabled", "{count} task(s) {action}.").format(count=count, action=action))

    def _on_run_now(self) -> None:
        ids = self._selected_task_ids()
        if not ids:
            QMessageBox.information(self, locale.tr("sched_no_selection_title", "No Selection"),
                                    locale.tr("sched_no_selection_msg", "Please select a task first."))
            return
        if len(ids) > 1:
            QMessageBox.information(self, locale.tr("sched_single_selection_title", "Multiple Selected"),
                                    locale.tr("sched_single_run_msg", "Please select only one task to run."))
            return
        if self._scheduler.is_running:
            QMessageBox.information(self, locale.tr("sched_busy_title", "Scheduler Busy"),
                                    locale.tr("sched_busy_msg", "Another scheduled task is running. Please wait."))
            return
        ok = self._scheduler.trigger_now(ids[0])
        if not ok:
            QMessageBox.warning(self, locale.tr("sched_trigger_failed_title", "Trigger Failed"),
                                locale.tr("sched_trigger_failed_msg", "Failed to trigger task. It may not exist or scheduler is busy."))
        else:
            self._append_log(locale.tr("sched_log_manual_trigger", "Manually triggered task: {id}").format(id=ids[0]))

    # ============ 调度器回调 ============

    def _on_scheduler_log(self, task_id: str, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        # 调度器执行日志统一转发到「标准推理」页日志面板
        self._append_log(f"[{ts}] [{task_id[:8]}] {message}")

    def _on_scheduler_state_changed(self, task_id: str, status: str, last_run_at: str, next_run_at: str) -> None:
        self._refresh_table()

    def _on_scheduler_busy_changed(self, busy: bool) -> None:
        if busy:
            self._status_label.setText(locale.tr("sched_status_running", "Scheduler: running"))
        else:
            self._status_label.setText(locale.tr("sched_status_idle", "Scheduler: idle"))

    def _append_log(self, message: str) -> None:
        """将日志转发到「标准推理」页的日志面板（source 标记为"定时任务"）。

        若标准推理页引用未注入（启动早期或注入失败），静默丢弃，避免阻断调度器流程。
        """
        page = self._maaend_page
        if page is None:
            return
        try:
            page.append_external_log(locale.tr("sched_log_source", "Scheduled"), message)
        except Exception:
            # 日志转发失败不影响调度器主流程
            pass

    def shutdown(self) -> None:
        """在主窗口关闭时调用，停止调度器。"""
        self._scheduler.stop()
