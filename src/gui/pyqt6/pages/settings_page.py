from __future__ import annotations

import json
from typing import Any, Dict, Optional

from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.foundation.paths import get_project_root


class SettingsPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._config_path = get_project_root() / "config" / "client_config.json"
        self._setup_ui()
        self._load_settings()

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

        title = QLabel("系统设置")
        title.setProperty("variant", "hero")
        header_layout.addWidget(title)

        summary = QLabel("这里仅保留必要设置项。")
        summary.setProperty("variant", "secondary")
        header_layout.addWidget(summary)
        content_root.addWidget(header)

        llm_card = QGroupBox("LLM 参数")
        llm_form = QFormLayout(llm_card)
        self._llm_enabled = QCheckBox("启用 LLM")
        self._model_path_input = QLineEdit()
        self._mmproj_path_input = QLineEdit()
        self._port_input = QSpinBox()
        self._port_input.setRange(1, 65535)
        self._threads_input = QSpinBox()
        self._threads_input.setRange(1, 256)
        llm_form.addRow("", self._llm_enabled)
        llm_form.addRow("模型路径", self._model_path_input)
        llm_form.addRow("MMProj 路径", self._mmproj_path_input)
        llm_form.addRow("端口", self._port_input)
        llm_form.addRow("线程数", self._threads_input)
        content_root.addWidget(llm_card)

        action_row = QHBoxLayout()
        self._reload_btn = QPushButton("重新加载")
        self._reload_btn.setProperty("variant", "secondary")
        self._reload_btn.clicked.connect(self._load_settings)
        action_row.addWidget(self._reload_btn)

        self._save_btn = QPushButton("保存设置")
        self._save_btn.setProperty("variant", "primary")
        self._save_btn.clicked.connect(self._save_settings)
        action_row.addWidget(self._save_btn)
        action_row.addStretch()
        content_root.addLayout(action_row)

        self._raw_preview = QTextEdit()
        self._raw_preview.setReadOnly(True)
        content_root.addWidget(self._raw_preview, 1)

    def _load_settings(self) -> None:
        config = self._read_config()

        llm = config.get("llm", {})
        self._llm_enabled.setChecked(bool(llm.get("enabled", True)))
        self._model_path_input.setText(str(llm.get("model_path", "")))
        self._mmproj_path_input.setText(str(llm.get("mmproj_path", "")))
        self._port_input.setValue(int(llm.get("port", 9998)))
        self._threads_input.setValue(int(llm.get("threads", 12)))

        self._raw_preview.setPlainText(json.dumps(config, ensure_ascii=False, indent=2))

    def _save_settings(self) -> None:
        config = self._read_config()

        config["llm"] = {
            **dict(config.get("llm", {})),
            "enabled": self._llm_enabled.isChecked(),
            "model_path": self._model_path_input.text().strip(),
            "mmproj_path": self._mmproj_path_input.text().strip(),
            "port": self._port_input.value(),
            "threads": self._threads_input.value(),
        }
        config.pop("cache", None)

        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        self._raw_preview.setPlainText(json.dumps(config, ensure_ascii=False, indent=2))
        QMessageBox.information(self, "保存成功", f"配置已写入 {self._config_path}")

    def _read_config(self) -> Dict[str, Any]:
        if not self._config_path.exists():
            return {}
        try:
            return json.loads(self._config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            QMessageBox.warning(self, "配置损坏", f"配置文件解析失败: {exc}")
            return {}
