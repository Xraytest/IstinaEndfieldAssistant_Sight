from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QComboBox,
)

from core.foundation.paths import get_project_root
from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.responsive import elide_text


from gui.pyqt6.theme.hero import HeroHeader
from gui.pyqt6.theme.icons import get_action_icon


locale = get_locale_manager()

_LOG_LEVEL_COLORS = {
    "INFO": "#18d1ff",
    "WARN": "#ffb84d",
    "ERROR": "#ff4d4d",
    "DEBUG": "#8b919e",
    "TRACE": "#a6a9b0",
}


class LogPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._config_path = get_project_root() / "config" / "client_config.json"
        self._logs_dir = get_project_root() / "logs"
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
        refresh_btn.setIcon(get_action_icon("刷新"))
        refresh_btn.clicked.connect(self._load_selected_log)
        action_row.addWidget(refresh_btn)

        self._file_combo = QComboBox()
        self._file_combo.setMinimumWidth(220)
        self._file_combo.currentIndexChanged.connect(self._load_selected_log)
        action_row.addWidget(self._file_combo)

        content_root.addLayout(action_row)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        content_root.addWidget(self._log_view, 1)

    def _refresh_file_list(self) -> None:
        self._file_combo.clear()
        if not self._logs_dir.exists():
            self._file_combo.addItem(locale.tr("log_dir_missing", "Log directory not found"))
            return
        files = sorted(self._logs_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        log_files = [f for f in files if f.is_file() and f.suffix.lower() in (".log", ".txt")]
        if not log_files:
            self._file_combo.addItem(locale.tr("no_log_files", "No log files found"))
            return
        for f in log_files:
            self._file_combo.addItem(f.name, str(f))

    def _load_selected_log(self) -> None:
        data = self._file_combo.currentData()
        if not data:
            return
        log_path = Path(str(data))
        self._path_label.setText(elide_text(self._path_label, locale.tr("log_file_path", "Log file: {path}").format(path=log_path)))
        if not log_path.exists():
            self._log_view.setPlainText(locale.tr("log_file_missing", "Log file does not exist."))
            return
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
            self._log_view.setHtml(self._highlight_log(text))
        except OSError as exc:
            self._log_view.setPlainText(locale.tr("read_log_failed", "Failed to read log: {exc}").format(exc=exc))

    def _highlight_log(self, text: str) -> str:
        import re
        lines = text.splitlines()
        html_lines = []
        for line in lines:
            escaped = line.replace("&", "&").replace("<", "<").replace(">", ">")
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
            html_lines.append(escaped)
        return "<br>".join(html_lines)

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
