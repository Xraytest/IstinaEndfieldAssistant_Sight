from __future__ import annotations

import json
from typing import Any, Dict, Optional

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
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


from gui.pyqt6.theme.hero import HeroHeader
from gui.pyqt6.theme.icons import get_action_icon
from gui.pyqt6.theme.theme_manager import get_theme


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

        header = HeroHeader("系统设置", "这里仅保留必要设置项。", content)
        content_root.addWidget(header)

        theme_card = QGroupBox("界面主题")
        theme_form = QFormLayout(theme_card)
        self._theme_combo = QComboBox()
        theme_manager = get_theme()
        for t in theme_manager.get_available_themes():
            self._theme_combo.addItem(f"{t['name']} - {t['description']}", t["id"])
        current_theme = theme_manager.get_current_theme()
        idx = self._theme_combo.findData(current_theme)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_form.addRow("主题", self._theme_combo)
        content_root.addWidget(theme_card)

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
        self._reload_btn.setIcon(get_action_icon("刷新"))
        self._reload_btn.clicked.connect(self._load_settings)
        action_row.addWidget(self._reload_btn)

        self._save_btn = QPushButton("保存设置")
        self._save_btn.setProperty("variant", "primary")
        self._save_btn.setIcon(get_action_icon("保存"))
        self._save_btn.clicked.connect(self._save_settings)
        action_row.addWidget(self._save_btn)
        action_row.addStretch()
        content_root.addLayout(action_row)

        self._raw_preview = QTextEdit()
        self._raw_preview.setReadOnly(True)
        content_root.addWidget(self._raw_preview, 1)

    def _on_theme_changed(self, index: int) -> None:
        theme_id = self._theme_combo.currentData()
        if not theme_id:
            return
        theme_manager = get_theme()
        theme_manager.set_current_theme(theme_id)
        app = QApplication.instance()
        if app is not None:
            theme_manager.apply_theme(app, theme_id)

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
