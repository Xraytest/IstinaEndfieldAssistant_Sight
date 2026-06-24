"""CLI Executor Widget — UI 调用 CLI 的桥接组件

GUI 页面通过此组件运行 CLI 命令，而非直接调用业务逻辑。
输出实时显示在终端风格的文本区域中。
"""

import sys, os, subprocess, json, signal, shlex
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QTextEdit, QPushButton, QLabel, QComboBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from typing import Optional, List

PROJECT_ROOT = str(Path(__file__).resolve().parents[4])
ISTINA_CLI = os.path.join(PROJECT_ROOT, "scripts", "istina.py")


STYLE_TERMINAL = """
    QTextEdit {
        background-color: #0a0a12;
        color: #c0c0d0;
        border: 1px solid rgba(24, 209, 255, 0.15);
        border-radius: 4px;
        font-family: Consolas, 'Courier New', monospace;
        font-size: 12px;
        padding: 8px;
        selection-background-color: rgba(24, 209, 255, 0.25);
    }
"""


class CliRunThread(QThread):
    """后台运行 CLI 命令的线程"""
    output_line = pyqtSignal(str)
    finished = pyqtSignal(int)

    def __init__(self, args: List[str]):
        super().__init__()
        self.args = args
        self._process = None

    def run(self):
        cmd = [sys.executable, ISTINA_CLI] + self.args
        self._process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        for line in iter(self._process.stdout.readline, ""):
            self.output_line.emit(line.rstrip())
        self._process.stdout.close()
        ret = self._process.wait()
        self.finished.emit(ret)

    def stop(self):
        if self._process and self._process.poll() is None:
            self._process.terminate()
            if not self._process.wait(3):
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(self._process.pid)], 
                                   capture_output=True)
                else:
                    self._process.kill()


class CliExecutorWidget(QWidget):
    """CLI 执行器组件 — 可嵌入任意 GUI 页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: Optional[CliRunThread] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 控制栏
        control = QHBoxLayout()
        control.setSpacing(8)

        self._cmd_combo = QComboBox()
        self._cmd_combo.setEditable(True)
        self._cmd_combo.setPlaceholderText("输入 CLI 命令...")
        self._cmd_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(24, 209, 255, 0.06);
                color: #c0c0d0;
                border: 1px solid rgba(24, 209, 255, 0.20);
                border-radius: 4px;
                padding: 4px 8px;
                font-family: Consolas; font-size: 12px;
            }
        """)
        # 常用命令预设
        self._cmd_combo.addItems([
            "doctor",
            "daily --model exploration_deep",
            "daily --dry-run",
            "analyze",
            "device status",
            "device screenshot",
            "config",
            "model list",
        ])
        control.addWidget(self._cmd_combo, 1)

        self._run_btn = QPushButton("▶ RUN")
        self._run_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 255, 162, 0.12);
                color: #00ffa2;
                border: 1px solid rgba(0, 255, 162, 0.35);
                border-radius: 4px;
                padding: 4px 16px;
                font-family: Consolas; font-weight: bold; font-size: 11px;
            }
            QPushButton:hover { background-color: rgba(0, 255, 162, 0.22); }
            QPushButton:disabled { color: #404050; border-color: #303040; }
        """)
        self._run_btn.clicked.connect(self._run_command)
        control.addWidget(self._run_btn)

        self._stop_btn = QPushButton("■ STOP")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 51, 85, 0.12);
                color: #ff3355;
                border: 1px solid rgba(255, 51, 85, 0.35);
                border-radius: 4px;
                padding: 4px 16px;
                font-family: Consolas; font-weight: bold; font-size: 11px;
            }
            QPushButton:hover { background-color: rgba(255, 51, 85, 0.22); }
        """)
        self._stop_btn.clicked.connect(self._stop_command)
        control.addWidget(self._stop_btn)

        self._clear_btn = QPushButton("× CLEAR")
        self._clear_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #606080;
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 4px;
                padding: 4px 12px;
                font-family: Consolas; font-size: 11px;
            }
            QPushButton:hover { color: #ff3355; border-color: #ff3355; }
        """)
        self._clear_btn.clicked.connect(self._clear_output)
        control.addWidget(self._clear_btn)

        layout.addLayout(control)

        # 输出区域
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setStyleSheet(STYLE_TERMINAL)
        self._output.setMinimumHeight(200)
        layout.addWidget(self._output, 1)

        # 状态栏
        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet("color: #606080; font-family: Consolas; font-size: 11px; padding: 2px 0;")
        layout.addWidget(self._status_label)

    def _run_command(self):
        text = self._cmd_combo.currentText().strip()
        if not text:
            return
        try:
            args = shlex.split(text)
        except ValueError as e:
            self._append_output(f"[PARSE ERROR] {e}", "#ff3355")
            return
        self._set_running(True)
        self._append_output(f"> istina {text}", "#18d1ff")
        self._status_label.setText(f"运行中: istina {text}")
        self._thread = CliRunThread(args)
        self._thread.output_line.connect(lambda line: self._append_output(line, "#c0c0d0"))
        self._thread.finished.connect(lambda retcode: self._on_finished(retcode, text, args))
        self._thread.start()

    def _stop_command(self):
        if self._thread:
            self._thread.stop()
            self._append_output("[STOPPED]", "#ff3355")
        self._set_running(False)

    def _on_finished(self, retcode: int, text: str, args: list):
        color = "#00ffa2" if retcode == 0 else "#ff3355"
        status = "完成" if retcode == 0 else f"失败 (exit={retcode})"
        self._append_output(f"[{status}]", color)
        self._status_label.setText(f"{status} | 上次: istina {text}")
        self._set_running(False)
        self._thread = None

    def _set_running(self, running: bool):
        self._run_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)
        self._cmd_combo.setEnabled(not running)

    def _append_output(self, text: str, color: str = "#c0c0d0"):
        self._output.append(f'<span style="color:{color};">{text}</span>')

    def _clear_output(self):
        self._output.clear()

    def run(self, command: str):
        """外部调用的快捷方法"""
        self._cmd_combo.setCurrentText(command)
        self._run_command()
