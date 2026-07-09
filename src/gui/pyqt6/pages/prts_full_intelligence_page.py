from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.theme.hero import HeroHeader
from gui.pyqt6.theme.widget_styles import BLUE_STYLE, RED_STYLE

locale = get_locale_manager()


class LlmChatWorker(QThread):
    """Background worker for LLM chat to avoid blocking the UI."""

    finished = pyqtSignal(dict)

    def __init__(self, bridge: CLIBridge, prompt: str, image_b64: Optional[str], parent=None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._prompt = prompt
        self._image_b64 = image_b64

    def run(self) -> None:
        params: dict[str, object] = {"text": self._prompt}
        if self._image_b64:
            params["image"] = self._image_b64
        result = self._bridge.execute("llm chat", params)
        self.finished.emit(result or {"status": "error", "message": "empty"})


class PrtsFullIntelligencePage(QWidget):
    """PRTS 全智能页面 — VLM 驱动的全自动游戏 CoPilot（施工中）。"""

    def __init__(self, bridge: CLIBridge, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._bridge = bridge
        self._worker: Optional[LlmChatWorker] = None
        self._pending_image_b64: Optional[str] = None
        self._auto_started = False
        self._startup_timer: Optional[QTimer] = None
        self._startup_poll_count = 0
        self._setup_ui()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._auto_started:
            self._auto_started = True
            self._start_llm()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

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

        header = HeroHeader(
            locale.tr("prts_title", "PRTS Intelligence (施工中)"),
            locale.tr("prts_subtitle", "VLM 驱动的全自动游戏 CoPilot — 视觉语言模型自主导航与决策。"),
            content,
        )
        content_root.addWidget(header)

        # 施工中横幅
        banner = QLabel(locale.tr("prts_under_construction", "⚠ 此页面正在施工中，功能尚未完全实现。"))
        banner.setProperty("variant", "warning")
        banner.setWordWrap(True)
        banner.setStyleSheet("background-color: #fff3cd; color: #856404; padding: 8px 12px; border-radius: 6px; font-weight: 500;")
        content_root.addWidget(banner)

        # 顶部控制栏：启动/停止 + 状态
        control_row = QHBoxLayout()
        control_row.setSpacing(8)

        self._start_btn = QPushButton(locale.tr("llm_start", "Start LLM"))
        self._start_btn.clicked.connect(self._start_llm)
        control_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton(locale.tr("llm_stop", "Stop LLM"))
        self._stop_btn.clicked.connect(self._stop_llm)
        control_row.addWidget(self._stop_btn)

        self._status_label = QLabel(locale.tr("llm_status_idle", "Idle"))
        self._status_label.setProperty("variant", "secondary")
        control_row.addWidget(self._status_label)

        control_row.addStretch()
        content_root.addLayout(control_row)

        # 中间分割器：上方对话区，下方输入区
        splitter = QSplitter(Qt.Orientation.Vertical, self)

        # 对话输出
        self._chat_output = QTextEdit()
        self._chat_output.setReadOnly(True)
        splitter.addWidget(self._chat_output)

        # 输入区容器
        input_container = QWidget()
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        # 图像行
        image_row = QHBoxLayout()
        image_row.setSpacing(8)
        self._attach_image_btn = QPushButton(locale.tr("attach_image", "Attach Image"))
        self._attach_image_btn.clicked.connect(self._attach_image)
        image_row.addWidget(self._attach_image_btn)
        self._image_path_label = QLabel(locale.tr("no_image", "No image attached"))
        self._image_path_label.setProperty("variant", "secondary")
        image_row.addWidget(self._image_path_label, 1)
        input_layout.addLayout(image_row)

        # 输入框 + 发送按钮
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self._prompt_input = QLineEdit()
        self._prompt_input.setPlaceholderText(locale.tr("llm_prompt_placeholder", "Enter prompt for LLM..."))
        self._prompt_input.returnPressed.connect(self._send_chat)
        input_row.addWidget(self._prompt_input)

        self._send_btn = QPushButton(locale.tr("llm_send", "Send"))
        self._send_btn.clicked.connect(self._send_chat)
        input_row.addWidget(self._send_btn)

        input_layout.addLayout(input_row)
        splitter.addWidget(input_container)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        content_root.addWidget(splitter, 1)

        self._bridge.commandFinished.connect(self._on_command_finished)
        self._update_llm_status()

    # ------------------------------------------------------------------
    # LLM lifecycle
    # ------------------------------------------------------------------

    def _start_llm(self) -> None:
        self._append_chat("系统", locale.tr("llm_starting", "Starting LLM..."))
        self._status_label.setText(locale.tr("llm_starting", "Starting..."))
        self._status_label.setStyleSheet(BLUE_STYLE)
        self._bridge.execute("llm start", {})
        self._startup_poll_count = 0
        if self._startup_timer is None:
            self._startup_timer = QTimer(self)
            self._startup_timer.timeout.connect(self._poll_startup_status)
        self._startup_timer.start(2000)

    def _stop_llm(self) -> None:
        self._append_chat("系统", locale.tr("llm_stopping", "Stopping LLM..."))
        self._bridge.execute("llm stop", {})
        if self._startup_timer is not None:
            self._startup_timer.stop()
        self._update_llm_status()

    def _update_llm_status(self) -> None:
        self._bridge.execute("llm status", {})

    def _poll_startup_status(self) -> None:
        self._startup_poll_count += 1
        if self._startup_poll_count > 30:
            if self._startup_timer is not None:
                self._startup_timer.stop()
            self._status_label.setText(locale.tr("llm_timeout", "Timeout"))
            self._status_label.setStyleSheet(RED_STYLE)
            return
        self._bridge.execute("llm status", {})

    def _finalize_startup_status(self, ready: bool) -> None:
        if self._startup_timer is not None:
            self._startup_timer.stop()
        self._status_label.setText(locale.tr("llm_ready", "Ready") if ready else locale.tr("llm_not_ready", "Not Ready"))
        self._status_label.setStyleSheet(BLUE_STYLE if ready else RED_STYLE)

    def _on_command_finished(self, command: str, result: dict) -> None:
        if command == "llm status":
            ready = bool(result.get("ready"))
            self._finalize_startup_status(ready)
        elif command == "llm chat":
            if result.get("status") == "success":
                output = result.get("output", "")
                self._append_chat("LLM", output)
            else:
                self._append_chat("系统", locale.tr("llm_error", "Error: {msg}").format(msg=result.get("message", "unknown")))
            self._send_btn.setEnabled(True)
            self._prompt_input.setEnabled(True)
            self._worker = None

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    def _send_chat(self) -> None:
        text = self._prompt_input.text.strip()
        if not text and not self._pending_image_b64:
            return
        if self._worker is not None:
            return

        self._append_chat("User", text or locale.tr("image_only", "[Image]"))
        self._prompt_input.clear()
        self._send_btn.setEnabled(False)
        self._prompt_input.setEnabled(False)

        image_b64 = self._pending_image_b64
        self._pending_image_b64 = None
        self._image_path_label.setText(locale.tr("no_image", "No image attached"))

        self._worker = LlmChatWorker(self._bridge, text, image_b64, self)
        self._worker.finished.connect(self._on_command_finished)
        self._worker.start()

    def _attach_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            locale.tr("select_image", "Select Image"),
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not path:
            return
        try:
            data = Path(path).read_bytes()
            self._pending_image_b64 = base64.b64encode(data).decode("ascii")
            self._image_path_label.setText(Path(path).name)
        except Exception:
            self._append_chat("系统", locale.tr("image_read_failed", "Failed to read image"))

    def _append_chat(self, source: str, text: str) -> None:
        self._chat_output.append(f"<b>[{source}]</b> {text}")
        cursor = self._chat_output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._chat_output.setTextCursor(cursor)
