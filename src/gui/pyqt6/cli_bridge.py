"""GUI 调用 CLI 的桥接器

通过 QProcess 调用 `istina.py`，捕获 stdout JSON 结果，
转换为 Qt 信号/槽更新 UI。
子进程崩溃时自动重启，连续 5 次崩溃后弹窗提醒。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

from core.foundation.logger import get_logger, LogCategory
from core.foundation.paths import get_project_root, ensure_src_path
from gui.pyqt6.i18n import get_locale_manager

ensure_src_path(__file__)

locale = get_locale_manager()


class CLIBridge(QObject):
    """GUI 侧 CLI 调用桥接器"""

    commandFinished = pyqtSignal(str, dict)
    commandError = pyqtSignal(str, str)
    processCrashed = pyqtSignal(int)
    logMessage = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: Optional[QProcess] = None
        self._pending_commands: List[List[str]] = []
        self._current_command: Optional[List[str]] = None
        self._crash_count = 0
        self._max_crashes = 5
        self._restart_pending = False
        self._python_path = sys.executable
        self._istina_path = str(get_project_root() / "src" / "cli" / "istina.py")
        self._last_command: List[str] = []
        self._stdout_buffer = ""
        self._interactive = True
        self._command_ready = False
        self._logger = get_logger(__name__)

    def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> None:
        params = params or {}
        args = self._build_args(command, params)
        self._pending_commands.append(args)
        if self._interactive:
            self._send_next_if_idle()
        else:
            self._start_next_process()

    @staticmethod
    def _build_args(command: str, params: Dict[str, Any]) -> List[str]:
        args = command.split()
        for key, value in params.items():
            args.append(f"--{key}")
            args.append(str(value))
        return args

    def _send_next_if_idle(self) -> None:
        if self._process is not None and self._process.state() == QProcess.ProcessState.Running:
            if self._current_command is not None:
                return
            if not self._pending_commands:
                return
            args = self._pending_commands.pop(0)
            self._current_command = args
            self._last_command = list(args)
            self._stdout_buffer = ""
            self._send_pending_command()
        else:
            self._start_interactive_process()

    def _start_interactive_process(self) -> None:
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            return
        if not self._pending_commands:
            return

        args = self._pending_commands.pop(0)
        self._current_command = list(args)
        self._last_command = list(args)
        self._stdout_buffer = ""

        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

        cmd = [self._python_path, self._istina_path, "--interactive"]
        self._logger.debug(LogCategory.GUI, "启动 CLI 交互进程", cmd=" ".join(cmd))
        self._process.start(cmd[0], cmd[1:])
        started = self._process.waitForStarted(5000)
        self._logger.debug(LogCategory.GUI, "CLI 交互进程启动结果", started=started, pid=self._process.processId() if started else None)
        if not started:
            self._handle_process_error("进程启动超时")
            self._finalize_current_process()
            self._start_interactive_process()
            return
        self._command_ready = True
        self._send_pending_command()

    _start_next_process = _start_interactive_process

    def _send_pending_command(self) -> None:
        if not self._command_ready or self._process is None or self._current_command is None:
            return
        if self._process.state() == QProcess.ProcessState.NotRunning:
            return
        line = " ".join(self._current_command) + "\n"
        self._logger.debug(LogCategory.GUI, "写入 CLI 命令", command=line.strip())
        try:
            self._process.write(line.encode("utf-8"))
            self._process.waitForBytesWritten(1000)
        except Exception as exc:
            self._logger.error(LogCategory.GUI, "写入 CLI 命令失败", error=str(exc))

    def _on_stdout(self) -> None:
        data = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._stdout_buffer += data
        self._logger.debug(LogCategory.GUI, "CLI stdout 数据到达", size=len(data))
        while True:
            newline_index = self._stdout_buffer.find("\n")
            if newline_index == -1:
                break
            line = self._stdout_buffer[:newline_index + 1]
            self._stdout_buffer = self._stdout_buffer[newline_index + 1:]
            if not line.strip():
                continue
            self._logger.debug(LogCategory.GUI, "CLI stdout 行解析", line=line.strip()[:200])
            try:
                result = json.loads(line.strip())
                command = " ".join(self._last_command)
                self._logger.debug(LogCategory.GUI, "发出 commandFinished 信号", command=command, status=result.get("status") if isinstance(result, dict) else None)
                self.commandFinished.emit(command, result)
            except json.JSONDecodeError as exc:
                self._logger.warning(LogCategory.GUI, "CLI stdout JSON 解析失败", error=str(exc), line=line.strip()[:200])
            if self._interactive:
                self._current_command = None
                self._send_next_if_idle()

    def _on_stderr(self) -> None:
        data = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        self.logMessage.emit("CLI", data.strip())

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        if self._restart_pending:
            self._finalize_current_process()
            return
        if self._interactive:
            if exit_code != 0:
                self._crash_count += 1
                self._logger.warning(LogCategory.GUI, "CLI 交互进程异常退出", exit_code=exit_code, exit_status=str(exit_status), crash_count=self._crash_count)
                self.processCrashed.emit(self._crash_count)
            else:
                self._logger.info(LogCategory.GUI, "CLI 交互进程正常退出", exit_code=exit_code)
            if self._crash_count < self._max_crashes and not self._restart_pending:
                self._restart_pending = True
                if self._current_command:
                    self._pending_commands.insert(0, list(self._current_command))
                QTimer.singleShot(1000, self._restart_last_command)
            else:
                self._show_crash_dialog()
            self._finalize_current_process()
            return
        if exit_status == QProcess.ExitStatus.CrashExit:
            self._crash_count += 1
            self._logger.error(LogCategory.GUI, "CLI 进程崩溃", exit_code=exit_code, crash_count=self._crash_count)
            self.processCrashed.emit(self._crash_count)
            if self._crash_count < self._max_crashes and not self._restart_pending:
                self._restart_pending = True
                if self._current_command:
                    self._pending_commands.insert(0, list(self._current_command))
                QTimer.singleShot(1000, self._restart_last_command)
            else:
                self._show_crash_dialog()
        elif exit_code != 0:
            self._logger.debug(LogCategory.GUI, "CLI 业务错误", exit_code=exit_code, command=" ".join(self._last_command))
            self.commandError.emit(" ".join(self._last_command), f"业务错误: {exit_code}")
            # 即使业务返回非零退出码，也发出 commandFinished，
            # 避免 _sync_execute 中的嵌套事件循环永远等待而超时。
            self.commandFinished.emit(
                " ".join(self._last_command),
                {"status": "error", "exit_code": exit_code},
            )
        else:
            self._crash_count = 0
        self._finalize_current_process()
        self._start_next_process()

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.Crashed:
            self._crash_count += 1
            self.processCrashed.emit(self._crash_count)
            if self._crash_count < self._max_crashes and not self._restart_pending:
                self._restart_pending = True
                if self._current_command:
                    self._pending_commands.insert(0, list(self._current_command))
                QTimer.singleShot(1000, self._restart_last_command)
            else:
                self._show_crash_dialog()

    def _restart_last_command(self) -> None:
        self._restart_pending = False
        if self._current_command and (not self._pending_commands or self._pending_commands[0] != self._current_command):
            self._pending_commands.insert(0, list(self._current_command))
        self._finalize_current_process()
        self._start_next_process()

    def _handle_process_error(self, message: str) -> None:
        self._logger.error(LogCategory.MAIN, "CLI 进程错误", error=message)
        self.commandError.emit(" ".join(self._last_command), message)

    def _finalize_current_process(self) -> None:
        if self._process is not None:
            try:
                self._process.deleteLater()
            except Exception:
                pass
        self._process = None
        self._current_command = None
        self._restart_pending = False

    def _show_crash_dialog(self) -> None:
        QMessageBox.critical(
            None,
            locale.tr("crash_dialog_title", "CLI process crashed repeatedly"),
            locale.tr("crash_dialog_msg", "CLI subprocess crashed {count} times consecutively. Please check the environment and retry.").format(count=self._crash_count),
        )
