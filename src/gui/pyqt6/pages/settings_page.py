from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QEvent, QObject, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
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
        self._env_path = get_project_root() / ".env"
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save_settings)
        # 模拟器子进程追踪：保存本会话内由「启动模拟器」按钮拉起的 Popen 对象
        # 仅供二次点击时避免重复启动 + 终止按钮使用；不持久化
        self._emulator_processes: List[subprocess.Popen] = []
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

        # ============================================================
        # Emulator Configuration - 模拟器路径与启动
        # ============================================================
        emulator_card = QGroupBox(locale.tr("emulator_config", "Emulator Configuration"))
        emulator_layout = QVBoxLayout(emulator_card)
        emulator_layout.setSpacing(10)

        emulator_hint = QLabel(locale.tr(
            "emulator_hint",
            "Configure the emulator executable path and extra launch arguments. "
            "Click 'Launch Emulator' to start it now; scheduled tasks can also auto-launch.",
        ))
        emulator_hint.setProperty("variant", "secondary")
        emulator_hint.setWordWrap(True)
        emulator_layout.addWidget(emulator_hint)

        self._emulator_path_input = QLineEdit()
        self._emulator_path_input.setPlaceholderText(locale.tr(
            "emulator_path_placeholder",
            "Absolute path to emulator executable, e.g. C:\\MuMu\\shell\\MuMuPlayer.exe",
        ))
        self._emulator_path_input.textChanged.connect(self._on_settings_changed)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        path_row.addWidget(self._emulator_path_input, 1)
        self._emulator_browse_btn = QPushButton(locale.tr("btn_browse", "Browse..."))
        self._emulator_browse_btn.setProperty("variant", "secondary")
        self._emulator_browse_btn.clicked.connect(self._browse_emulator_path)
        path_row.addWidget(self._emulator_browse_btn)
        path_wrapper = QWidget()
        path_wrapper.setLayout(path_row)

        self._emulator_args_input = QLineEdit()
        self._emulator_args_input.setPlaceholderText(locale.tr(
            "emulator_args_placeholder",
            "Extra launch arguments, e.g. -s 0 -v 0",
        ))
        self._emulator_args_input.textChanged.connect(self._on_settings_changed)

        emulator_form = QFormLayout()
        emulator_form.setSpacing(8)
        emulator_form.addRow(locale.tr("emulator_path", "Emulator Path"), path_wrapper)
        emulator_form.addRow(locale.tr("emulator_args", "Extra Arguments"), self._emulator_args_input)
        emulator_layout.addLayout(emulator_form)

        launch_row = QHBoxLayout()
        launch_row.setSpacing(8)
        self._launch_emulator_btn = QPushButton(locale.tr("btn_launch_emulator", "Launch Emulator"))
        self._launch_emulator_btn.clicked.connect(self._on_launch_emulator)
        launch_row.addWidget(self._launch_emulator_btn)
        self._kill_emulator_btn = QPushButton(locale.tr("emulator_kill_btn", "Kill Process"))
        self._kill_emulator_btn.setProperty("variant", "secondary")
        self._kill_emulator_btn.setEnabled(False)
        self._kill_emulator_btn.clicked.connect(self._on_kill_emulator)
        launch_row.addWidget(self._kill_emulator_btn)
        launch_row.addStretch()
        emulator_layout.addLayout(launch_row)

        content_root.addWidget(emulator_card)

        # ============================================================
        # Developer Settings toggle - hides/shows developer options
        # ============================================================
        self._developer_enabled = QCheckBox(locale.tr("settings_dev_enable", "Enable Developer Settings"))
        self._developer_enabled.setToolTip(locale.tr(
            "settings_dev_enable_tooltip",
            "Show advanced developer options (LLM backend, process recording)."
        ))
        self._developer_enabled.toggled.connect(self._on_developer_toggle)
        content_root.addWidget(self._developer_enabled)

        # ============================================================
        # Developer Options (hidden by default)
        # ============================================================
        self._dev_group = QGroupBox(locale.tr("settings_dev_group", "Developer Options"))
        dev_layout = QVBoxLayout(self._dev_group)
        dev_layout.setSpacing(10)

        # ---- LLM section ----
        llm_card = QGroupBox(locale.tr("settings_llm", "LLM Parameters"))
        llm_layout = QVBoxLayout(llm_card)

        # Provider selector (local | cloud) - persisted to .env as LLM_PROVIDER
        provider_row = QHBoxLayout()
        provider_row.addWidget(self._make_label(locale.tr("llm_provider", "Provider")))
        self._llm_provider_combo = QComboBox()
        self._llm_provider_combo.addItem(locale.tr("llm_provider_local", "Local (llama-server)"), "local")
        self._llm_provider_combo.addItem(locale.tr("llm_provider_cloud", "Cloud (OpenAI-compatible API)"), "cloud")
        self._llm_provider_combo.currentIndexChanged.connect(self._on_settings_changed)
        self._llm_provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_row.addWidget(self._llm_provider_combo, 1)
        llm_layout.addLayout(provider_row)

        # LLM enable + Local llama-server fields
        local_form = QFormLayout()
        self._llm_enabled = QCheckBox(locale.tr("llm_enable_local", "Enable local LLM"))
        self._llm_enabled.toggled.connect(self._on_settings_changed)
        local_form.addRow("", self._llm_enabled)

        self._model_path_input = QLineEdit()
        self._mmproj_path_input = QLineEdit()
        self._port_input = QSpinBox()
        self._port_input.setRange(1, 65535)
        self._threads_input = QSpinBox()
        self._threads_input.setRange(1, 256)
        self._model_path_input.textChanged.connect(self._on_settings_changed)
        self._mmproj_path_input.textChanged.connect(self._on_settings_changed)
        self._port_input.valueChanged.connect(self._on_settings_changed)
        self._threads_input.valueChanged.connect(self._on_settings_changed)
        local_form.addRow(locale.tr("model_path", "Model Path"), self._model_path_input)
        local_form.addRow(locale.tr("mmproj_path", "MMProj Path"), self._mmproj_path_input)
        local_form.addRow(locale.tr("port", "Port"), self._port_input)
        local_form.addRow(locale.tr("threads", "Threads"), self._threads_input)
        llm_layout.addLayout(local_form)

        # Cloud LLM fields - persisted to .env (NEVER to client_config.json)
        self._cloud_card = QGroupBox(locale.tr("llm_cloud_section", "Cloud API Configuration"))
        cloud_form = QFormLayout(self._cloud_card)
        self._cloud_base_url_input = QLineEdit()
        self._cloud_base_url_input.setPlaceholderText("https://your-cloud-llm-endpoint/v1")
        self._cloud_api_key_input = QLineEdit()
        self._cloud_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._cloud_api_key_input.setPlaceholderText(locale.tr("llm_cloud_api_key_hint", "Paste API key (stored to .env, not committed)"))
        self._cloud_model_input = QLineEdit()
        self._cloud_model_input.setPlaceholderText("qwen/qwen3.5-35b-a3b(free)")
        self._cloud_base_url_input.textChanged.connect(self._on_settings_changed)
        self._cloud_api_key_input.textChanged.connect(self._on_settings_changed)
        self._cloud_model_input.textChanged.connect(self._on_settings_changed)
        cloud_form.addRow(locale.tr("llm_cloud_base_url", "Base URL"), self._cloud_base_url_input)
        cloud_form.addRow(locale.tr("llm_cloud_api_key", "API Key"), self._cloud_api_key_input)
        cloud_form.addRow(locale.tr("llm_cloud_model", "Model"), self._cloud_model_input)
        llm_layout.addWidget(self._cloud_card)

        # Provider hint: changes require restart to take effect (互斥不运行时切换)
        self._provider_hint = QLabel(locale.tr(
            "llm_provider_hint",
            "Provider change takes effect on next runtime startup (mutually exclusive, no hot-switch)."
        ))
        self._provider_hint.setWordWrap(True)
        self._provider_hint.setStyleSheet("color: #8a8f99; font-size: 11px;")
        llm_layout.addWidget(self._provider_hint)

        dev_layout.addWidget(llm_card)

        # ---- Recording section ----
        recording_card = QGroupBox(locale.tr("settings_recording", "Process Recording"))
        recording_form = QFormLayout(recording_card)
        self._record_video = QCheckBox(locale.tr("record_video", "Record full video of each queue execution"))
        self._record_video.setToolTip(locale.tr(
            "record_video_tooltip",
            "Saves a complete MP4 video of device frames from queue start to finish."
        ))
        self._record_video.toggled.connect(self._on_settings_changed)
        recording_form.addRow("", self._record_video)
        dev_layout.addWidget(recording_card)

        # ---- Raw config preview (developer-only) ----
        # 完整配置 JSON 预览，含 llm 字段，归入开发者选项避免普通用户看到
        self._raw_preview = QTextEdit()
        self._raw_preview.setReadOnly(True)
        dev_layout.addWidget(self._raw_preview, 1)

        content_root.addWidget(self._dev_group)

        action_row = QHBoxLayout()
        self._reload_btn = QPushButton(locale.tr("btn_reload", "Reload"))
        self._reload_btn.setProperty("variant", "secondary")
        self._reload_btn.clicked.connect(self._load_settings)
        action_row.addWidget(self._reload_btn)
        action_row.addStretch()
        content_root.addLayout(action_row)

        _wheel_filter = _SpinBoxWheelFilter(self)
        self._preview_interval_spin.installEventFilter(_wheel_filter)
        self._port_input.installEventFilter(_wheel_filter)
        self._threads_input.installEventFilter(_wheel_filter)

    def _make_label(self, text: str) -> QLabel:
        return QLabel(text)

    def _on_developer_toggle(self, enabled: bool) -> None:
        self._dev_group.setVisible(enabled)
        # Persist immediately so the toggle survives restarts
        self._on_settings_changed()

    def _on_provider_changed(self, _idx: int) -> None:
        """Toggle visibility of cloud config section based on provider selection."""
        is_cloud = self._llm_provider_combo.currentData() == "cloud"
        self._cloud_card.setVisible(is_cloud)
        # Local fields are always visible (model_path etc. apply to local mode)

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
        env = self._read_env()

        # Developer toggle + recording: persisted in client_config.json under "developer"
        dev_cfg = config.get("developer", {}) or {}
        self._developer_enabled.blockSignals(True)
        self._dev_group.blockSignals(True)
        self._developer_enabled.setChecked(bool(dev_cfg.get("enabled", False)))
        self._dev_group.setVisible(bool(dev_cfg.get("enabled", False)))
        self._developer_enabled.blockSignals(False)
        self._dev_group.blockSignals(False)

        # Block signals to avoid triggering _on_settings_changed during load
        self._llm_enabled.blockSignals(True)
        self._model_path_input.blockSignals(True)
        self._mmproj_path_input.blockSignals(True)
        self._port_input.blockSignals(True)
        self._threads_input.blockSignals(True)
        self._preview_interval_spin.blockSignals(True)
        self._llm_provider_combo.blockSignals(True)
        self._cloud_base_url_input.blockSignals(True)
        self._cloud_api_key_input.blockSignals(True)
        self._cloud_model_input.blockSignals(True)
        self._record_video.blockSignals(True)
        self._emulator_path_input.blockSignals(True)
        self._emulator_args_input.blockSignals(True)

        llm = config.get("llm", {}) or {}
        self._llm_enabled.setChecked(bool(llm.get("enabled", True)))
        self._model_path_input.setText(str(llm.get("model_path", "")))
        self._mmproj_path_input.setText(str(llm.get("mmproj_path", "")))
        self._port_input.setValue(int(llm.get("port", 9998)))
        self._threads_input.setValue(int(llm.get("threads", 12)))
        self._preview_interval_spin.setValue(int(config.get("preview_interval_ms", 1500)))

        # Emulator config: stored under device.emulator in client_config.json
        # (kept in the same location used by scheduled_task_scheduler for compatibility)
        emulator_cfg = (config.get("device") or {}).get("emulator") or {}
        self._emulator_path_input.setText(str(emulator_cfg.get("path", "")).strip())
        self._emulator_args_input.setText(str(emulator_cfg.get("args", "")).strip())

        # Provider + cloud config: read from .env (authoritative source)
        provider = (env.get("LLM_PROVIDER") or "local").strip().lower()
        idx = self._llm_provider_combo.findData(provider)
        if idx < 0:
            idx = 0
        self._llm_provider_combo.setCurrentIndex(idx)
        self._cloud_base_url_input.setText(str(env.get("LLM_CLOUD_BASE_URL", "")))
        self._cloud_api_key_input.setText(str(env.get("LLM_CLOUD_API_KEY", "")))
        self._cloud_model_input.setText(str(env.get("LLM_CLOUD_MODEL", "")))

        self._record_video.setChecked(bool(dev_cfg.get("record_video", False)))

        self._llm_enabled.blockSignals(False)
        self._model_path_input.blockSignals(False)
        self._mmproj_path_input.blockSignals(False)
        self._port_input.blockSignals(False)
        self._threads_input.blockSignals(False)
        self._preview_interval_spin.blockSignals(False)
        self._llm_provider_combo.blockSignals(False)
        self._cloud_base_url_input.blockSignals(False)
        self._cloud_api_key_input.blockSignals(False)
        self._cloud_model_input.blockSignals(False)
        self._record_video.blockSignals(False)
        self._emulator_path_input.blockSignals(False)
        self._emulator_args_input.blockSignals(False)

        # Sync cloud card visibility with provider
        self._on_provider_changed(self._llm_provider_combo.currentIndex())

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
            # Developer settings persisted to client_config.json (no secrets here)
            config["developer"] = {
                "enabled": self._developer_enabled.isChecked(),
                "record_video": self._record_video.isChecked(),
            }
            # Emulator config persisted under device.emulator (与 scheduled_task_scheduler
            # 读取路径保持一致，便于定时任务「执行前启动模拟器」复用同一份配置)
            device_cfg = dict(config.get("device", {}))
            device_cfg["emulator"] = {
                "path": self._emulator_path_input.text().strip(),
                "args": self._emulator_args_input.text().strip(),
            }
            config["device"] = device_cfg
            config.pop("cache", None)

            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            # G8: 原子写入，避免中断导致配置文件损坏
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

            # Persist LLM provider + cloud config to .env (secrets must NOT go to client_config.json)
            self._save_env()
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

    def _read_env(self) -> Dict[str, str]:
        """Read .env file as a flat dict (KEY=VALUE). Returns {} if .env absent."""
        if not self._env_path.exists():
            return {}
        result: Dict[str, str] = {}
        try:
            for raw_line in self._env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                result[key.strip()] = value.strip().strip('"').strip("'")
        except OSError:
            pass
        return result

    def _save_env(self) -> None:
        """Persist LLM_PROVIDER + LLM_CLOUD_* into .env (atomic write).

        Secrets (API key) MUST live only in .env (gitignored). Other non-secret
        .env entries are preserved; only LLM_PROVIDER / LLM_CLOUD_BASE_URL /
        LLM_CLOUD_API_KEY / LLM_CLOUD_MODEL are updated.
        """
        existing = self._read_env()
        existing["LLM_PROVIDER"] = (self._llm_provider_combo.currentData() or "local").strip().lower()
        base_url = self._cloud_base_url_input.text().strip()
        api_key = self._cloud_api_key_input.text().strip()
        model = self._cloud_model_input.text().strip()
        if base_url:
            existing["LLM_CLOUD_BASE_URL"] = base_url
        else:
            existing.pop("LLM_CLOUD_BASE_URL", None)
        if api_key:
            existing["LLM_CLOUD_API_KEY"] = api_key
        else:
            existing.pop("LLM_CLOUD_API_KEY", None)
        if model:
            existing["LLM_CLOUD_MODEL"] = model
        else:
            existing.pop("LLM_CLOUD_MODEL", None)

        lines = [
            "# =============================================================================",
            "# IstinaEndfieldAssistant 环境变量 (auto-managed by Settings UI)",
            "# =============================================================================",
            "# LLM 后端互斥切换：local | cloud",
            "# - local : 本地 llama-server (config/llm.* 参数)",
            "# - cloud : 云端 OpenAI 兼容 API (LLM_CLOUD_* 参数)",
            "",
            f"LLM_PROVIDER={existing.get('LLM_PROVIDER', 'local')}",
            "",
            "# 云端 OpenAI 兼容 API 配置（仅 LLM_PROVIDER=cloud 时生效）",
        ]
        if "LLM_CLOUD_BASE_URL" in existing:
            lines.append(f"LLM_CLOUD_BASE_URL={existing['LLM_CLOUD_BASE_URL']}")
        if "LLM_CLOUD_API_KEY" in existing:
            lines.append(f"LLM_CLOUD_API_KEY={existing['LLM_CLOUD_API_KEY']}")
        if "LLM_CLOUD_MODEL" in existing:
            lines.append(f"LLM_CLOUD_MODEL={existing['LLM_CLOUD_MODEL']}")

        # Preserve other keys not managed here (rare, but keep user edits)
        managed = {"LLM_PROVIDER", "LLM_CLOUD_BASE_URL", "LLM_CLOUD_API_KEY", "LLM_CLOUD_MODEL"}
        extras = [(k, v) for k, v in existing.items() if k not in managed]
        if extras:
            lines.append("")
            lines.append("# Other user-defined variables")
            for k, v in extras:
                lines.append(f"{k}={v}")

        text = "\n".join(lines) + "\n"
        self._env_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=str(self._env_path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self._env_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def _apply_preview_interval(self, value: int) -> None:
        # 性能优化：PreviewWorker 已下沉 mmap 读取到后台线程，主线程不再有
        # preview_timer 轮询。此设置保留用于未来 worker 内部 sleep 间隔调整。
        # 当前为 no-op，避免引用已移除的 _preview_timer 属性。
        pass

    # ===================== Emulator launch =====================

    def _browse_emulator_path(self) -> None:
        start_dir = self._emulator_path_input.text().strip() or ""
        path, _ = QFileDialog.getOpenFileName(
            self,
            locale.tr("emulator_browse_title", "Select Emulator Executable"),
            start_dir,
            locale.tr("emulator_browse_filter", "Executables (*.exe);;All Files (*)"),
        )
        if path:
            self._emulator_path_input.setText(path)

    def _live_emulator_processes(self) -> List[subprocess.Popen]:
        """Return currently-alive emulator processes we started this session."""
        alive: List[subprocess.Popen] = []
        for proc in self._emulator_processes:
            if proc.poll() is None:
                alive.append(proc)
        self._emulator_processes = alive
        self._kill_emulator_btn.setEnabled(bool(alive))
        return alive

    def _on_launch_emulator(self) -> None:
        """启动模拟器：使用配置的路径 + 附加参数，subprocess.Popen 拉起子进程。

        - 路径为空：弹提示框，要求用户填写
        - 当前已有进程在运行：提示并不重复启动
        - 启动失败：弹错误对话框显示异常
        - 启动成功：把 Popen 加入追踪列表，启用「终止进程」按钮
        """
        # 同步保存最新输入到配置文件，避免启动前未落盘
        self._save_timer.stop()
        self._save_settings()

        path = self._emulator_path_input.text().strip()
        if not path:
            QMessageBox.information(
                self,
                locale.tr("emulator_launch_no_path_title", "No Path Configured"),
                locale.tr("emulator_launch_no_path_msg", "Please fill in the emulator executable path first."),
            )
            return

        alive = self._live_emulator_processes()
        if alive:
            pid = alive[0].pid
            QMessageBox.information(
                self,
                locale.tr("btn_launch_emulator", "Launch Emulator"),
                locale.tr(
                    "emulator_launch_running",
                    "An emulator process is already running (PID={pid}); not launching a new one.",
                ).format(pid=pid),
            )
            return

        args_str = self._emulator_args_input.text().strip()
        # posix=False: Windows 风格参数解析（不剥离引号，保留 -s 0 / -v 0 这类参数）
        args_list = shlex.split(args_str, posix=False) if args_str else []
        try:
            # cwd=exe 所在目录，便于模拟器读取相对路径下的配置/资源
            cwd = os.path.dirname(path) or None
            proc = subprocess.Popen([path] + args_list, cwd=cwd)
        except Exception as exc:
            QMessageBox.critical(
                self,
                locale.tr("emulator_launch_failed_title", "Launch Failed"),
                locale.tr("emulator_launch_failed_msg", "Failed to launch emulator: {exc}").format(exc=exc),
            )
            return

        self._emulator_processes.append(proc)
        self._kill_emulator_btn.setEnabled(True)
        QMessageBox.information(
            self,
            locale.tr("btn_launch_emulator", "Launch Emulator"),
            locale.tr(
                "emulator_launch_started",
                "Emulator process started (PID={pid}). Please wait for the emulator window to appear.",
            ).format(pid=proc.pid),
        )

    def _on_kill_emulator(self) -> None:
        """终止本会话内由「启动模拟器」按钮拉起的子进程。"""
        alive = self._live_emulator_processes()
        if not alive:
            return
        for proc in alive:
            try:
                proc.terminate()
            except Exception:
                pass
        # 给 OS 一点时间再确认状态
        QTimer.singleShot(500, self._refresh_kill_button_after_terminate)

    def _refresh_kill_button_after_terminate(self) -> None:
        killed_pids = [p.pid for p in self._emulator_processes if p.poll() is not None]
        self._live_emulator_processes()  # 重建 alive 列表并刷新按钮状态
        if killed_pids:
            QMessageBox.information(
                self,
                locale.tr("emulator_kill_btn", "Kill Process"),
                locale.tr(
                    "emulator_killed",
                    "Emulator process terminated (PID={pid}).",
                ).format(pid=killed_pids[0]),
            )
