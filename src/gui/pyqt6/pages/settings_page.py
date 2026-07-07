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
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.foundation.paths import get_project_root

from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.theme.hero import HeroHeader

locale = get_locale_manager()


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

        header = HeroHeader(locale.tr("settings_interface", "Settings"), locale.tr("settings_interface", "Interface theme settings"), content)
        content_root.addWidget(header)

        language_card = QGroupBox(locale.tr("settings_language", "Language"))
        language_form = QFormLayout(language_card)
        self._language_combo = QComboBox()
        for loc in locale.available_locales():
            self._language_combo.addItem(f"{loc['native']} ({loc['name']})", loc["id"])
        current = locale.current_locale()
        idx = self._language_combo.findData(current)
        if idx >= 0:
            self._language_combo.setCurrentIndex(idx)
        self._language_combo.currentIndexChanged.connect(self._on_language_changed)
        language_form.addRow(locale.tr("settings_language", "Language"), self._language_combo)
        content_root.addWidget(language_card)

        llm_card = QGroupBox(locale.tr("settings_llm", "LLM Parameters"))
        llm_form = QFormLayout(llm_card)
        self._llm_enabled = QCheckBox(locale.tr("settings_llm", "Enable LLM"))
        self._model_path_input = QLineEdit()
        self._mmproj_path_input = QLineEdit()
        self._port_input = QSpinBox()
        self._port_input.setRange(1, 65535)
        self._threads_input = QSpinBox()
        self._threads_input.setRange(1, 256)
        llm_form.addRow("", self._llm_enabled)
        llm_form.addRow(locale.tr("model_path", "Model Path"), self._model_path_input)
        llm_form.addRow(locale.tr("mmproj_path", "MMProj Path"), self._mmproj_path_input)
        llm_form.addRow(locale.tr("port", "Port"), self._port_input)
        llm_form.addRow(locale.tr("threads", "Threads"), self._threads_input)
        content_root.addWidget(llm_card)

        action_row = QHBoxLayout()
        self._reload_btn = QPushButton(locale.tr("btn_reload", "Reload"))
        self._reload_btn.setProperty("variant", "secondary")
        self._reload_btn.clicked.connect(self._load_settings)
        action_row.addWidget(self._reload_btn)

        self._save_btn = QPushButton(locale.tr("btn_save", "Save Settings"))
        self._save_btn.setProperty("variant", "primary")
        self._save_btn.clicked.connect(self._save_settings)
        action_row.addWidget(self._save_btn)
        action_row.addStretch()
        content_root.addLayout(action_row)

        self._raw_preview = QTextEdit()
        self._raw_preview.setReadOnly(True)
        content_root.addWidget(self._raw_preview, 1)

    def _on_language_changed(self, index: int) -> None:
        new_locale = self._language_combo.currentData()
        if not new_locale:
            return
        locale.set_locale(new_locale)
        main_window = self.window()
        if isinstance(main_window, QMainWindow):
            main_window.setWindowTitle(locale.tr("app_title", "IstinaEndfieldAssistant Sight"))
            main_window.statusBar().showMessage(locale.tr("status_ready", "Ready"), 2000)
        QMessageBox.information(
            self,
            locale.tr("language_changed", "Language changed"),
            locale.tr("restart_for_changes", "Some changes will take effect after restart."),
        )

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
        QMessageBox.information(self, locale.tr("settings_saved", "Saved"), locale.tr("settings_saved_msg", "Configuration written to {path}").format(path=self._config_path))

    def _read_config(self) -> Dict[str, Any]:
        if not self._config_path.exists():
            return {}
        try:
            return json.loads(self._config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            QMessageBox.warning(self, locale.tr("settings_corrupt", "Configuration Corrupt"), locale.tr("settings_corrupt_msg", "Failed to parse configuration file: {exc}").format(exc=exc))
            return {}
