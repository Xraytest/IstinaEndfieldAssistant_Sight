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

ensure_src_path(__file__)


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
        self._logger = get_logger(__name__)

    def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> None:
        params = params or {}
        args = self._build_args(command, params)
        self._pending_commands.append(args)
        self._start_next_process()

    def _build_args(self, command: str, params: Dict[str, Any]) -> List[str]:
        args: List[str] = []
        current = ""
        depth = 0
        for char in command:
            if char in "{[":
                depth += 1
                current += char
            elif char in "}]":
                depth = max(0, depth - 1)
                current += char
            elif char == " " and depth == 0:
                if current:
                    args.append(current)
                    current = ""
            else:
                current += char
        if current:
            args.append(current)
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, bool):
                if value:
                    args.append(f"--{key}")
            else:
                args.extend([f"--{key}", str(value)])
        return args

    def _start_next_process(self) -> None:
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

        cmd = [self._python_path, self._istina_path] + args
        self._logger.debug(LogCategory.GUI, "启动 CLI 子进程", cmd=" ".join(cmd))
        self._process.start(cmd[0], cmd[1:])
        if not self._process.waitForStarted(5000):
            self._handle_process_error("进程启动超时")
            self._finalize_current_process()
            self._start_next_process()

    def _on_stdout(self) -> None:
        data = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._stdout_buffer += data
        while True:
            newline_index = self._stdout_buffer.find("\n")
            if newline_index == -1:
                break
            line = self._stdout_buffer[:newline_index].strip()
            self._stdout_buffer = self._stdout_buffer[newline_index + 1:]
            if not line:
                continue
            try:
                result = json.loads(line)
                command = " ".join(self._last_command)
                self.commandFinished.emit(command, result)
            except json.JSONDecodeError:
                pass

    def _on_stderr(self) -> None:
        data = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        self.logMessage.emit("CLI", data.strip())

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        if self._restart_pending:
            self._finalize_current_process()
            return
        if exit_code != 0:
            self._handle_process_error(f"进程异常退出: {exit_code}")
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
            "CLI 进程连续崩溃",
            f"CLI 子进程已连续崩溃 {self._crash_count} 次，请检查环境或重试。",
        )
