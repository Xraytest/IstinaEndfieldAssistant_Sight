from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from PyQt6.QtCore import QEvent, QObject, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.foundation.paths import get_project_root
from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.theme.hero import HeroHeader

locale = get_locale_manager()


class _SpinBoxWheelFilter(QObject):
    """Block wheel events for spin boxes to prevent accidental value changes."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            return True
        return False


class SettingsPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._config_path = get_project_root() / "config" / "client_config.json"
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save_settings)
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

        preview_card = QGroupBox(locale.tr("settings_preview", "Preview"))
        preview_form = QFormLayout(preview_card)
        self._preview_interval_spin = QSpinBox()
        self._preview_interval_spin.setRange(200, 10000)
        self._preview_interval_spin.setSuffix(" ms")
        self._preview_interval_spin.setToolTip(locale.tr("preview_interval_tooltip", "Interval between preview frames"))
        self._preview_interval_spin.valueChanged.connect(self._on_settings_changed)
        self._preview_interval_spin.valueChanged.connect(self._apply_preview_interval)
        preview_form.addRow(locale.tr("preview_interval", "Preview Interval"), self._preview_interval_spin)
        content_root.addWidget(preview_card)

        llm_card = QGroupBox(locale.tr("settings_llm", "LLM Parameters"))
        llm_form = QFormLayout(llm_card)
        self._llm_enabled = QCheckBox(locale.tr("settings_llm", "Enable LLM"))
        self._model_path_input = QLineEdit()
        self._mmproj_path_input = QLineEdit()
        self._port_input = QSpinBox()
        self._port_input.setRange(1, 65535)
        self._threads_input = QSpinBox()
        self._threads_input.setRange(1, 256)
        self._llm_enabled.toggled.connect(self._on_settings_changed)
        self._model_path_input.textChanged.connect(self._on_settings_changed)
        self._mmproj_path_input.textChanged.connect(self._on_settings_changed)
        self._port_input.valueChanged.connect(self._on_settings_changed)
        self._threads_input.valueChanged.connect(self._on_settings_changed)
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
        action_row.addStretch()
        content_root.addLayout(action_row)

        self._raw_preview = QTextEdit()
        self._raw_preview.setReadOnly(True)
        content_root.addWidget(self._raw_preview, 1)

        _wheel_filter = _SpinBoxWheelFilter(self)
        self._preview_interval_spin.installEventFilter(_wheel_filter)
        self._port_input.installEventFilter(_wheel_filter)
        self._threads_input.installEventFilter(_wheel_filter)

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
        self._llm_enabled.blockSignals(True)
        self._model_path_input.blockSignals(True)
        self._mmproj_path_input.blockSignals(True)
        self._port_input.blockSignals(True)
        self._threads_input.blockSignals(True)
        self._preview_interval_spin.blockSignals(True)
        self._llm_enabled.setChecked(bool(llm.get("enabled", True)))
        self._model_path_input.setText(str(llm.get("model_path", "")))
        self._mmproj_path_input.setText(str(llm.get("mmproj_path", "")))
        self._port_input.setValue(int(llm.get("port", 9998)))
        self._threads_input.setValue(int(llm.get("threads", 12)))
        self._preview_interval_spin.setValue(int(config.get("preview_interval_ms", 1500)))
        self._llm_enabled.blockSignals(False)
        self._model_path_input.blockSignals(False)
        self._mmproj_path_input.blockSignals(False)
        self._port_input.blockSignals(False)
        self._threads_input.blockSignals(False)
        self._preview_interval_spin.blockSignals(False)

        self._raw_preview.setPlainText(json.dumps(config, ensure_ascii=False, indent=2))

    def _on_settings_changed(self) -> None:
        # 防抖：按键/值变化频繁时合并为一次实际写入，避免每次按键都完整读写 JSON
        self._save_timer.stop()
        self._save_timer.start(400)

    def _save_settings(self) -> None:
        try:
            config = self._read_config()

            config["llm"] = {
                **dict(config.get("llm", {})),
                "enabled": self._llm_enabled.isChecked(),
                "model_path": self._model_path_input.text().strip(),
                "mmproj_path": self._mmproj_path_input.text().strip(),
                "port": self._port_input.value(),
                "threads": self._threads_input.value(),
            }
            config["preview_interval_ms"] = self._preview_interval_spin.value()
            config.pop("cache", None)

            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            # G8: 原子写入，避免中断导致配置文件损坏
            import tempfile
            import os
            data = json.dumps(config, ensure_ascii=False, indent=2)
            fd, tmp_path = tempfile.mkstemp(dir=str(self._config_path.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self._config_path)
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise
            self._raw_preview.setPlainText(data)
        except Exception as exc:
            logging.getLogger(__name__).warning("Settings save failed: %s", exc)
            QMessageBox.warning(
                self,
                locale.tr("settings_save_failed", "Save Failed"),
                locale.tr("settings_save_failed_msg", "Failed to save settings: {exc}").format(exc=exc),
            )

    def _read_config(self) -> Dict[str, Any]:
        if not self._config_path.exists():
            return {}
        try:
            return json.loads(self._config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            QMessageBox.warning(self, locale.tr("settings_corrupt", "Configuration Corrupt"), locale.tr("settings_corrupt_msg", "Failed to parse configuration file: {exc}").format(exc=exc))
            return {}

    def _apply_preview_interval(self, value: int) -> None:
        main_window = self.window()
        if isinstance(main_window, QMainWindow):
            timer = getattr(main_window, "_preview_timer", None)
            if timer is not None:
                timer.setInterval(value)
