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
)

from core.foundation.paths import get_project_root
from gui.pyqt6.responsive import elide_text


class LogPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._config_path = get_project_root() / "config" / "client_config.json"
        self._setup_ui()
        self._load_log()

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

        header = QFrame(content)
        header.setObjectName("settingsHero")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(4)
        title = QLabel("日志")
        title.setProperty("variant", "hero")
        header_layout.addWidget(title)
        summary = QLabel("显示当前日志文件的完整内容。")
        summary.setProperty("variant", "secondary")
        header_layout.addWidget(summary)
        content_root.addWidget(header)

        action_row = QHBoxLayout()
        self._path_label = QLabel("")
        self._path_label.setProperty("variant", "secondary")
        action_row.addWidget(self._path_label, 1)
        refresh_btn = QPushButton("刷新日志")
        refresh_btn.clicked.connect(self._load_log)
        action_row.addWidget(refresh_btn)
        content_root.addLayout(action_row)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        content_root.addWidget(self._log_view, 1)

    def _load_log(self) -> None:
        config = self._read_config()
        relative_path = str(config.get("logging", {}).get("file") or "logs/iea_local.log")
        log_path = get_project_root() / relative_path
        self._path_label.setText(elide_text(self._path_label, f"日志文件：{log_path}"))
        if not log_path.exists():
            self._log_view.setPlainText("日志文件不存在。")
            return
        try:
            self._log_view.setPlainText(log_path.read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            self._log_view.setPlainText(f"读取日志失败：{exc}")

    def _read_config(self) -> Dict[str, Any]:
        if not self._config_path.exists():
            return {}
        try:
            return json.loads(self._config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
