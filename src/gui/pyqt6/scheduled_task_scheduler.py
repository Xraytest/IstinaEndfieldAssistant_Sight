"""定时任务调度器。

设计：
- QTimer 每 30 秒 tick 一次，扫描所有启用的定时任务。
- 对每个任务：根据 trigger_time / weekdays / last_run_at 计算下次触发时间。
  若 now >= next_run_at 且今天尚未触发，则进入执行流程。
- 执行流程（异步链式）：
  1. （可选）启动模拟器：subprocess.Popen(path, args)
  2. 等待设备就绪：QTimer 轮询 "device info"（最长 120s）
  3. 连接指定设备（若 device_serial 非空）：system connect
  4. 执行目标：preset run <name> 或 queue run
  5. 更新 last_run_at / last_run_status / next_run_at
- 同一时刻只允许一个定时任务在执行（_running 锁）。
"""
from __future__ import annotations

import json
import shlex
import subprocess
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.foundation.logger import LogCategory, get_logger
from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.scheduled_task_store import (
    ScheduledTask,
    ScheduledTaskStore,
    compute_next_run,
)

locale = get_locale_manager()


class ScheduledTaskScheduler(QObject):
    """QTimer 驱动的定时任务调度器。"""

    # 信号：(task_id, message)
    task_log = pyqtSignal(str, str)
    # 信号：(task_id, status, last_run_at, next_run_at)
    task_state_changed = pyqtSignal(str, str, str, str)
    # 信号：(is_running) — 整体调度器繁忙状态变化
    busy_state_changed = pyqtSignal(bool)

    TICK_INTERVAL_MS = 30_000  # 30 秒
    EMULATOR_READY_POLL_MS = 5_000
    EMULATOR_READY_TIMEOUT_MS = 120_000
    DEVICE_CONNECT_TIMEOUT_MS = 30_000

    def __init__(self, store: ScheduledTaskStore, bridge: CLIBridge, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._store = store
        self._bridge = bridge
        self._logger = get_logger(__name__)
        self._running = False
        self._timer = QTimer(self)
        self._timer.setInterval(self.TICK_INTERVAL_MS)
        self._timer.timeout.connect(self._on_tick)
        self._emulator_process: Optional[subprocess.Popen] = None

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()
            self._logger.info(LogCategory.GUI, "定时任务调度器已启动")

    def stop(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
            self._logger.info(LogCategory.GUI, "定时任务调度器已停止")

    @property
    def is_running(self) -> bool:
        return self._running

    def trigger_now(self, task_id: str) -> bool:
        """手动触发某个任务（用户点击"立即运行"）。返回是否已接受。"""
        if self._running:
            return False
        task = self._store.get_task(task_id)
        if task is None:
            return False
        QTimer.singleShot(0, lambda: self._execute_task(task))
        return True

    def _on_tick(self) -> None:
        if self._running:
            return
        now = datetime.now()
        for task in self._store.list_tasks():
            if not task.enabled:
                continue
            # 计算预期触发时间
            expected = compute_next_run(task.trigger_time, task.weekdays, now=now, last_run_at=task.last_run_at)
            if expected is None:
                continue
            # 若预期触发时间已到（now >= expected），且今天尚未运行过，则触发
            if now >= expected:
                # 二次确认 last_run_at 不是今天（防止 tick 间重复触发）
                if task.last_run_at:
                    try:
                        last_dt = datetime.fromisoformat(task.last_run_at)
                        if last_dt.date() == now.date() and last_dt >= expected:
                            continue
                    except Exception:
                        pass
                self._execute_task(task)
                return  # 一次 tick 只触发一个

    # ===================== 执行流程 =====================

    def _execute_task(self, task: ScheduledTask) -> None:
        self._running = True
        self.busy_state_changed.emit(True)
        now_iso = datetime.now().isoformat(timespec="seconds")
        self._store.update_run_state(task.id, now_iso, "running", task.next_run_at)
        self.task_state_changed.emit(task.id, "running", now_iso, task.next_run_at or "")
        self._log(task.id, locale.tr(
            "sched_log_start",
            "Triggered scheduled task: {name}",
        ).format(name=task.name or task.id))

        if task.launch_emulator:
            self._launch_emulator(task)
        else:
            self._connect_device(task)

    def _launch_emulator(self, task: ScheduledTask) -> None:
        # 读取模拟器路径与参数（来自 client_config.json）
        from core.foundation.paths import get_project_root
        config_path = get_project_root() / "config" / "client_config.json"
        path, args_str = "", ""
        if config_path.exists():
            try:
                cfg = json.loads(config_path.read_text(encoding="utf-8"))
                emu = (cfg.get("device") or {}).get("emulator") or {}
                path = str(emu.get("path") or "").strip()
                args_str = str(emu.get("args") or "").strip()
            except Exception as exc:
                self._log(task.id, locale.tr("sched_log_emu_cfg_error", "Failed to read emulator config: {exc}").format(exc=exc))
                self._finish_task(task, success=False)
                return

        if not path:
            self._log(task.id, locale.tr("sched_log_emu_empty", "Emulator path is empty, skipping launch."))
            self._connect_device(task)
            return

        try:
            args_list = shlex.split(args_str, posix=False) if args_str else []
            self._log(task.id, locale.tr("sched_log_emu_launch", "Launching emulator: {path} {args}").format(path=path, args=args_str))
            self._emulator_process = subprocess.Popen([path] + args_list)
        except Exception as exc:
            self._log(task.id, locale.tr("sched_log_emu_launch_failed", "Failed to launch emulator: {exc}").format(exc=exc))
            self._finish_task(task, success=False)
            return

        # 轮询等待设备就绪
        self._emu_wait_start = datetime.now()
        self._emu_wait_task = task
        QTimer.singleShot(self.EMULATOR_READY_POLL_MS, self._poll_emulator_ready)

    def _poll_emulator_ready(self) -> None:
        task = getattr(self, "_emu_wait_task", None)
        if task is None:
            return
        elapsed_ms = int((datetime.now() - self._emu_wait_start).total_seconds() * 1000)
        if elapsed_ms > self.EMULATOR_READY_TIMEOUT_MS:
            self._log(task.id, locale.tr("sched_log_emu_timeout", "Emulator startup timed out after {sec}s.").format(sec=self.EMULATOR_READY_TIMEOUT_MS // 1000))
            self._emu_wait_task = None
            self._finish_task(task, success=False)
            return

        # 通过 device info 检查是否有可用设备
        self._bridge.execute_async(
            "device info",
            {},
            on_done=lambda res: self._on_emu_check_devices(task, res),
            on_error=lambda msg: self._on_emu_check_failed(task, msg),
            timeout_ms=15_000,
        )

    def _on_emu_check_devices(self, task: ScheduledTask, result: dict) -> None:
        devices = result.get("devices") or []
        ready = [d for d in devices if (d.get("state") or d.get("status") or "") == "device"] if devices else []
        if not ready:
            # 继续轮询
            QTimer.singleShot(self.EMULATOR_READY_POLL_MS, self._poll_emulator_ready)
            return
        self._log(task.id, locale.tr("sched_log_emu_ready", "Emulator device is ready."))
        self._emu_wait_task = None
        self._connect_device(task)

    def _on_emu_check_failed(self, task: ScheduledTask, msg: str) -> None:
        self._log(task.id, locale.tr("sched_log_emu_check_failed", "Device check failed: {msg}, retrying...").format(msg=msg))
        QTimer.singleShot(self.EMULATOR_READY_POLL_MS, self._poll_emulator_ready)

    def _connect_device(self, task: ScheduledTask) -> None:
        serial = task.device_serial.strip()
        if not serial:
            self._log(task.id, locale.tr("sched_log_no_device", "No device specified, using current connection."))
            self._run_target(task)
            return

        self._log(task.id, locale.tr("sched_log_connect", "Connecting device: {serial}").format(serial=serial))
        self._bridge.execute_async(
            "system connect",
            {"serial": serial},
            on_done=lambda res: self._on_connect_done(task, res),
            on_error=lambda msg: self._on_connect_error(task, msg),
            timeout_ms=self.DEVICE_CONNECT_TIMEOUT_MS,
        )

    def _on_connect_done(self, task: ScheduledTask, result: dict) -> None:
        ok = bool(result.get("status") == "success")
        if not ok:
            self._log(task.id, locale.tr("sched_log_connect_failed", "Device connect failed: {result}").format(result=result))
            self._finish_task(task, success=False)
            return
        self._log(task.id, locale.tr("sched_log_connect_ok", "Device connected."))
        self._run_target(task)

    def _on_connect_error(self, task: ScheduledTask, msg: str) -> None:
        self._log(task.id, locale.tr("sched_log_connect_error", "Device connect error: {msg}").format(msg=msg))
        self._finish_task(task, success=False)

    def _run_target(self, task: ScheduledTask) -> None:
        if task.target_type == "preset":
            preset_name = task.target_name.strip()
            if not preset_name:
                self._log(task.id, locale.tr("sched_log_no_preset", "Preset name is empty."))
                self._finish_task(task, success=False)
                return
            cmd = f"preset run {preset_name}"
            self._log(task.id, locale.tr("sched_log_run_preset", "Running preset: {name}").format(name=preset_name))
        else:
            cmd = "queue run"
            self._log(task.id, locale.tr("sched_log_run_queue", "Running current queue."))

        # 预设/队列执行可能很长，给 30 分钟超时
        self._bridge.execute_async(
            cmd,
            {},
            on_done=lambda res: self._on_run_done(task, res),
            on_error=lambda msg: self._on_run_error(task, msg),
            timeout_ms=30 * 60 * 1000,
        )

    def _on_run_done(self, task: ScheduledTask, result: dict) -> None:
        ok = bool(result.get("status") == "success")
        if ok:
            self._log(task.id, locale.tr("sched_log_done_ok", "Task finished: success"))
        else:
            self._log(task.id, locale.tr("sched_log_done_fail", "Task finished: failed — {result}").format(result=result))
        self._finish_task(task, success=ok)

    def _on_run_error(self, task: ScheduledTask, msg: str) -> None:
        self._log(task.id, locale.tr("sched_log_run_error", "Execution error: {msg}").format(msg=msg))
        self._finish_task(task, success=False)

    def _finish_task(self, task: ScheduledTask, success: bool) -> None:
        now = datetime.now()
        now_iso = now.isoformat(timespec="seconds")
        next_run = compute_next_run(task.trigger_time, task.weekdays, now=now, last_run_at=now_iso)
        next_iso = next_run.isoformat(timespec="seconds") if next_run else ""
        status = "success" if success else "failed"
        self._store.update_run_state(task.id, now_iso, status, next_iso)
        self.task_state_changed.emit(task.id, status, now_iso, next_iso)
        self._log(task.id, locale.tr(
            "sched_log_finish",
            "Scheduled task finished ({status}). Next run: {next}",
        ).format(status=status, next=next_iso or "N/A"))

        self._running = False
        self.busy_state_changed.emit(False)

    def _log(self, task_id: str, message: str) -> None:
        self._logger.info(LogCategory.GUI, f"[ScheduledTask:{task_id}] {message}")
        self.task_log.emit(task_id, message)
