from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.foundation.paths import get_project_root
from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.responsive import elide_text
from gui.pyqt6.theme.hero import HeroHeader
from gui.pyqt6.theme.widget_styles import COMBO_STYLE, INPUT_STYLE
from gui.pyqt6.theme.theme_manager import COLORS

locale = get_locale_manager()

_LOG_LEVEL_COLORS = {
    "INFO": COLORS["primary"],
    "WARN": "#ffb84d",
    "ERROR": "#ff4d4d",
    "DEBUG": "#8b919e",
    "TRACE": "#a6a9b0",
}

# 首次同步加载的行数：足够快速展示页面，又不至于阻塞 UI
_INITIAL_LINES = 200
# 后台分块加载时每次处理的行数：越小 UI 越跟手，越大整体加载越快
_CHUNK_LINES = 500


def _highlight_line(line: str) -> str:
    """对单行日志做 HTML 转义与高亮，返回可直接拼入 HTML 的片段。"""
    # 先正确转义 HTML 特殊字符，防止日志中的 HTML 标签被 Qt 渲染执行
    escaped = html.escape(line, quote=False)
    # Highlight timestamp pattern like 2026-07-07 16:09:23
    escaped = re.sub(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})",
        r"<span style='color: #8b919e;'>\1</span>",
        escaped,
    )
    # Highlight log levels
    for level, color in _LOG_LEVEL_COLORS.items():
        escaped = re.sub(
            rf"\b({level})\b",
            rf"<span style='color: {color}; font-weight: bold;'>\1</span>",
            escaped,
            flags=re.IGNORECASE,
        )
    return escaped


class _LogLoaderWorker(QThread):
    """后台分块读取剩余日志并高亮，通过信号回传到 GUI 线程追加展示。

    所有文件读取与正则高亮都在后台线程完成，GUI 线程只负责小段 HTML 的追加，
    因此加载过程中页面浏览不会被阻塞。
    """

    chunk_loaded = pyqtSignal(str)
    loading_done = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        path: Path,
        skip_lines: int,
        chunk_lines: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._skip_lines = skip_lines
        self._chunk_lines = chunk_lines
        self._cancel_flag = False

    def cancel(self) -> None:
        self._cancel_flag = True

    def run(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8", errors="replace") as f:
                batch: List[str] = []
                count = 0
                line_no = 0
                for line in f:
                    if self._cancel_flag:
                        return
                    # 跳过首段已同步加载的行
                    if line_no < self._skip_lines:
                        line_no += 1
                        continue
                    line_no += 1
                    batch.append(_highlight_line(line.rstrip("\r\n")))
                    count += 1
                    if count >= self._chunk_lines:
                        self.chunk_loaded.emit("<br>".join(batch))
                        batch = []
                        count = 0
                if batch:
                    self.chunk_loaded.emit("<br>".join(batch))
                self.loading_done.emit()
        except OSError as exc:
            self.error_occurred.emit(str(exc))


class LogPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._config_path = get_project_root() / "config" / "client_config.json"
        self._logs_dir = get_project_root() / "logs"
        self._loader: Optional[_LogLoaderWorker] = None
        self._retired_workers: List[_LogLoaderWorker] = []
        self._load_token = 0
        self._loading = False
        self._current_path: Optional[Path] = None
        self._setup_ui()
        self._refresh_file_list()
        self._load_selected_log()

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
        content_root.setSpacing(14)

        header = HeroHeader(locale.tr("log_title", "Logs"), locale.tr("log_subtitle", "Display all log file contents."), content)
        content_root.addWidget(header)

        action_row = QHBoxLayout()
        self._path_label = QLabel("")
        self._path_label.setProperty("variant", "secondary")
        action_row.addWidget(self._path_label, 1)

        refresh_btn = QPushButton(locale.tr("log_refresh", "Refresh"))
        refresh_btn.clicked.connect(self._load_selected_log)
        action_row.addWidget(refresh_btn)

        self._file_combo = QComboBox()
        self._file_combo.setStyleSheet(COMBO_STYLE)
        self._file_combo.setMinimumWidth(220)
        self._file_combo.currentIndexChanged.connect(self._load_selected_log)
        action_row.addWidget(self._file_combo)

        content_root.addLayout(action_row)

        self._log_view = QTextEdit()
        self._log_view.setStyleSheet(INPUT_STYLE)
        self._log_view.setReadOnly(True)
        content_root.addWidget(self._log_view, 1)

    def _refresh_file_list(self) -> None:
        self._file_combo.clear()
        if not self._logs_dir.exists():
            self._file_combo.addItem(locale.tr("log_dir_missing", "Log directory not found"))
            return
        try:
            files = sorted(self._logs_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            self._file_combo.addItem(locale.tr("no_log_files", "No log files found"))
            return
        log_files = [f for f in files if f.is_file() and f.suffix.lower() in (".log", ".txt")]
        if not log_files:
            self._file_combo.addItem(locale.tr("no_log_files", "No log files found"))
            return
        for f in log_files:
            self._file_combo.addItem(f.name, str(f))

    def _load_selected_log(self) -> None:
        # 切换文件/刷新时取消尚未完成的后台加载，避免向新内容中混入旧日志
        self._cancel_loader()
        data = self._file_combo.currentData()
        if not data:
            self._current_path = None
            self._update_path_label(loading=False)
            return
        log_path = Path(str(data))
        self._current_path = log_path
        if not log_path.exists():
            self._log_view.setPlainText(locale.tr("log_file_missing", "Log file does not exist."))
            self._update_path_label(loading=False)
            return
        try:
            # 先同步加载首段：让页面立即出现可读内容，不等待整份日志读完
            lines: List[str] = []
            reached_limit = False
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    if i >= _INITIAL_LINES:
                        reached_limit = True
                        break
                    lines.append(_highlight_line(line.rstrip("\r\n")))
            self._log_view.setHtml("<br>".join(lines))
            self._log_view.moveCursor(QTextCursor.MoveOperation.End)
            if reached_limit:
                # 剩余部分交由后台线程持续分块加载，期间用户可自由浏览已展示内容
                self._start_loader(log_path, skip_lines=len(lines))
            else:
                self._loading = False
                self._update_path_label(loading=False)
        except OSError as exc:
            self._log_view.setPlainText(locale.tr("read_log_failed", "Failed to read log: {exc}").format(exc=exc))
            self._update_path_label(loading=False)

    def _start_loader(self, log_path: Path, skip_lines: int) -> None:
        self._load_token += 1
        token = self._load_token
        self._loading = True
        self._update_path_label(loading=True)
        loader = _LogLoaderWorker(log_path, skip_lines, _CHUNK_LINES, self)
        # token 用于丢弃切换文件/刷新后残留的旧信号
        loader.chunk_loaded.connect(lambda html_chunk: self._on_chunk_loaded(html_chunk, token))
        loader.loading_done.connect(lambda: self._on_loading_done(token))
        loader.error_occurred.connect(lambda msg: self._on_loader_error(msg, token))
        loader.finished.connect(lambda w=loader: self._cleanup_worker(w))
        self._loader = loader
        loader.start()

    def _cancel_loader(self) -> None:
        loader = self._loader
        self._loader = None
        self._loading = False
        if loader is None:
            return
        if loader.isRunning():
            loader.cancel()
            # 保留引用直到线程真正结束，避免运行中的 QThread 被 GC
            self._retired_workers.append(loader)
        else:
            loader.deleteLater()

    def _cleanup_worker(self, worker: _LogLoaderWorker) -> None:
        try:
            self._retired_workers.remove(worker)
        except ValueError:
            pass
        if self._loader is worker:
            self._loader = None
        worker.deleteLater()

    def _on_chunk_loaded(self, html_chunk: str, token: int) -> None:
        if token != self._load_token:
            return
        view = self._log_view
        bar = view.verticalScrollBar()
        # 追加新内容时保持用户当前滚动位置，不抢占浏览焦点
        saved_scroll = bar.value()
        saved_cursor = view.textCursor()
        cursor = QTextCursor(view.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml("<br>" + html_chunk)
        view.setTextCursor(saved_cursor)
        bar.setValue(saved_scroll)

    def _on_loading_done(self, token: int) -> None:
        if token != self._load_token:
            return
        self._loading = False
        self._update_path_label(loading=False)

    def _on_loader_error(self, msg: str, token: int) -> None:
        if token != self._load_token:
            return
        self._loading = False
        self._update_path_label(loading=False)
        cursor = QTextCursor(self._log_view.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(
            "<br><span style='color: #ff4d4d;'>" + html.escape(msg, quote=False) + "</span>"
        )

    def _update_path_label(self, loading: bool) -> None:
        if self._current_path is None:
            self._path_label.setText("")
            return
        base = elide_text(
            self._path_label,
            locale.tr("log_file_path", "Log file: {path}").format(path=self._current_path),
        )
        if loading:
            base += "  " + locale.tr("log_loading", "(loading...)")
        self._path_label.setText(base)

    def _highlight_log(self, text: str) -> str:
        return "<br>".join(_highlight_line(line) for line in text.splitlines())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_file_list()
        self._load_selected_log()

    def _read_config(self) -> Dict[str, Any]:
        if not self._config_path.exists():
            return {}
        try:
            return json.loads(self._config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
