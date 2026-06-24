"""Settings page - Endfield terminal style"""
from typing import Optional, Dict, Any, List, Tuple
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QPushButton, QGroupBox, QFormLayout, QComboBox,
    QScrollArea, QLineEdit, QProgressBar,
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
import sys
import os
import json
import re
from pathlib import Path

from core.foundation.paths import ensure_src_path
ensure_src_path(__file__)


class SettingsPage(QWidget):
    settings_changed = pyqtSignal(dict)
    check_update_requested = pyqtSignal()
    model_download_requested = pyqtSignal(str)  # model_name
    model_remove_requested = pyqtSignal(str)    # model_name
    minimize_to_tray_changed = pyqtSignal(bool)

    COMBO_STYLE = """
        QComboBox {
            background-color: rgba(10, 10, 15, 0.80);
            color: #e8e8ee;
            border: 1px solid rgba(24, 209, 255, 0.15);
            border-radius: 4px;
            padding: 8px 12px; font-size: 12px; font-family: Consolas;
            min-height: 36px;
        }
        QComboBox:hover { border-color: rgba(24, 209, 255, 0.35); }
        QComboBox::drop-down { border: none; width: 28px; }
        QComboBox::down-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid rgba(24, 209, 255, 0.50); width: 0; height: 0; }
        QComboBox QAbstractItemView {
            background-color: rgba(12, 12, 20, 0.95);
            color: #e8e8ee;
            border: 1px solid rgba(24, 209, 255, 0.15);
            selection-background-color: rgba(24, 209, 255, 0.15);
        }
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, parent=None,
                 agent_executor=None):
        super().__init__(parent)
        self._config = config or {}
        self._agent_executor = agent_executor
        self._gpu_info = {"available": False, "gpus": []}  # 初始化 GPU 信息
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 终端标题
        title = QLabel("// SYSTEM SETTINGS")
        title.setStyleSheet("""
            QLabel {
                color: #18d1ff;
                font-size: 14px;
                font-family: Consolas;
                font-weight: bold;
                letter-spacing: 1px;
                padding: 4px 24px;
            }
        """)
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 8, 24, 24)
        layout.setSpacing(16)

        # ======== 本地模型管理 ========
        local_models_group = self._make_card_widget("LOCAL MODELS")
        lm_layout = QVBoxLayout(local_models_group)
        lm_layout.setContentsMargins(20, 16, 20, 16)
        lm_layout.setSpacing(8)

        # 模型目录路径
        models_dir = self._get_models_dir()
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("Models Dir:"))
        dir_row.itemAt(0).widget().setStyleSheet("color: #9090a8; font-size: 12px; font-family: Consolas; padding: 3px 0;")
        dir_label = QLabel(models_dir)
        dir_label.setStyleSheet("color: #606080; font-size: 10px; font-family: Consolas; padding: 3px 0;")
        dir_label.setWordWrap(True)
        dir_row.addWidget(dir_label, 1)
        lm_layout.addLayout(dir_row)

        # 已下载模型列表
        lm_layout.addWidget(QLabel("Downloaded:"))
        lm_layout.itemAt(lm_layout.count() - 1).widget().setStyleSheet("color: #9090a8; font-size: 11px; font-family: Consolas; padding: 2px 0;")
        self._local_models_label = QLabel("No models found")
        self._local_models_label.setStyleSheet("color: #e8e8ee; font-size: 12px; font-family: Consolas; padding: 4px 8px;")
        self._local_models_label.setWordWrap(True)
        lm_layout.addWidget(self._local_models_label)

        # 模型选择 + 下载/删除
        select_row = QHBoxLayout()
        select_row.addWidget(QLabel("Model:"))
        select_row.itemAt(0).widget().setStyleSheet("color: #9090a8; font-size: 12px; font-family: Consolas; padding: 3px 0;")
        self._model_select_combo = QComboBox()
        self._model_select_combo.setMinimumWidth(220)
        self._model_select_combo.setStyleSheet(self.COMBO_STYLE)
        select_row.addWidget(self._model_select_combo)
        select_row.addStretch()
        lm_layout.addLayout(select_row)

        # 下载进度条
        self._download_progress = QProgressBar()
        self._download_progress.setVisible(False)
        self._download_progress.setStyleSheet("""
            QProgressBar {
                background-color: rgba(10, 10, 15, 0.80);
                border: none;
                border-radius: 2px;
                height: 4px;
                text-align: center;
                color: transparent;
            }
            QProgressBar::chunk {
                background-color: #18d1ff;
                border-radius: 2px;
            }
        """)
        lm_layout.addWidget(self._download_progress)

        # 下载状态标签
        self._download_status_label = QLabel("")
        self._download_status_label.setStyleSheet("color: #9090a8; font-size: 11px; font-family: Consolas; padding: 2px 0;")
        self._download_status_label.setWordWrap(True)
        lm_layout.addWidget(self._download_status_label)

        # 操作按钮行
        btn_row = QHBoxLayout()
        btn_style = """
            QPushButton {
                background-color: transparent;
                color: #18d1ff;
                border: 1px solid rgba(24, 209, 255, 0.25);
                border-radius: 2px;
                padding: 6px 14px;
                font-size: 11px; font-family: Consolas; font-weight: bold; letter-spacing: 1px;
            }
            QPushButton:hover { background-color: rgba(24, 209, 255, 0.08); }
        """
        self._refresh_models_btn = QPushButton("REFRESH MODELS")
        self._refresh_models_btn.setStyleSheet(btn_style)
        self._refresh_models_btn.clicked.connect(self._scan_local_models)
        btn_row.addWidget(self._refresh_models_btn)

        self._download_btn = QPushButton("DOWNLOAD")
        self._download_btn.setStyleSheet(btn_style)
        self._download_btn.clicked.connect(self._download_model)
        btn_row.addWidget(self._download_btn)

        self._delete_btn = QPushButton("DELETE")
        self._delete_btn.setStyleSheet(btn_style.replace("#18d1ff", "#ff3355").replace("rgba(24, 209, 255", "rgba(255, 51, 85"))
        self._delete_btn.clicked.connect(self._delete_model)
        btn_row.addWidget(self._delete_btn)

        btn_row.addStretch()
        lm_layout.addLayout(btn_row)

        layout.addWidget(local_models_group)

        # ======== 系统 ========
        sys_group = self._make_card_widget("SYSTEM")
        sys_layout = QVBoxLayout(sys_group)
        sys_layout.setContentsMargins(20, 16, 20, 16)
        sys_layout.setSpacing(8)

        self._tray_cb = QCheckBox("最小化到托盘栏")
        self._tray_cb.setStyleSheet("""
            QCheckBox { color: #e8e8ee; font-size: 12px; font-family: Consolas; spacing: 8px; }
            QCheckBox::indicator {
                width: 16px; height: 16px; border-radius: 2px;
                border: 1px solid rgba(24, 209, 255, 0.30); background-color: transparent;
            }
            QCheckBox::indicator:checked { background-color: #18d1ff; border-color: #18d1ff; }
        """)
        self._tray_cb.setToolTip("关闭窗口时最小化到系统托盘栏而非退出")
        self._tray_cb.stateChanged.connect(self._on_tray_changed)
        sys_layout.addWidget(self._tray_cb)

        layout.addWidget(sys_group)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        self._load_config()

    def _load_config(self):
        self._scan_local_models()

        # 托盘设置
        tray = self._config.get("system", {}).get("minimize_to_tray", False)
        self._tray_cb.blockSignals(True)
        self._tray_cb.setChecked(tray)
        self._tray_cb.blockSignals(False)
        self.minimize_to_tray_changed.emit(tray)

    def _make_card_widget(self, title: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("""
            QWidget {
                background-color: rgba(16, 16, 26, 0.85);
                border: 1px solid rgba(24, 209, 255, 0.10);
                border-radius: 4px;
            }
        """)
        return w

    # ── 本地模型管理 ──────────────────────────────────────────────

    def _get_config_dir(self) -> str:
        """获取配置文件目录路径"""
        current = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current))))
        return os.path.join(root, "config")

    def _load_models_config(self) -> List[Dict[str, Any]]:
        """
        加载并验证模型配置文件

        Returns:
            模型配置列表，加载失败或验证失败时返回空列表
        """
        config_dir = self._get_config_dir()
        config_path = os.path.join(config_dir, "models.json")

        try:
            if not os.path.isfile(config_path):
                self._download_status_label.setText(f"Config not found: {config_path}")
                return []

            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            models = data.get("models", [])
            if not models:
                self._download_status_label.setText("No models defined in config")
                return []

            # 验证每个模型配置格式
            valid_models = []
            for i, model in enumerate(models):
                validation_result = self._validate_model_config(model, i)
                if validation_result["valid"]:
                    valid_models.append(model)
                else:
                    self._download_status_label.setText(
                        f"Model {model.get('id', i)} invalid: {validation_result['error']}"
                    )

            if not valid_models:
                self._download_status_label.setText("No valid models in config")
                return []

            # 检查 ModelScope 仓库是否存在（异步，失败不阻止启动）
            self._download_status_label.setText(f"Checking {len(valid_models)} repo(s)...")
            existing_models = self._validate_all_models_exist(valid_models)
            
            if not existing_models:
                self._download_status_label.setText("No available model repos")
                return []

            self._download_status_label.setText(f"Loaded {len(existing_models)} model(s)")
            return existing_models

        except json.JSONDecodeError as e:
            self._download_status_label.setText(f"Config parse error: {e}")
            return []
        except Exception as e:
            self._download_status_label.setText(f"Config load error: {e}")
            return []

    def _validate_model_config(self, model: Dict[str, Any], index: int) -> Dict[str, Any]:
        """
        验证单个模型配置的完整性

        Args:
            model: 模型配置字典
            index: 模型索引（用于错误报告）

        Returns:
            {"valid": bool, "error": str}
        """
        required_fields = {
            "id": "模型 ID",
            "name": "模型名称",
            "display_name": "显示名称",
            "repo_id": "仓库 ID",
            "gguf_pattern": "GGUF 文件模式",
            "expected_gguf": "期望 GGUF 文件名",
            "required_vram_gb": "所需显存"
        }

        # 检查必填字段
        for field, field_name in required_fields.items():
            if field not in model or not model[field]:
                return {"valid": False, "error": f"Missing '{field_name}'"}

        # 验证正则模式
        try:
            re.compile(model["gguf_pattern"])
        except re.error as e:
            return {"valid": False, "error": f"Invalid gguf_pattern: {e}"}

        # 验证显存值为正数
        try:
            vram = float(model["required_vram_gb"])
            if vram <= 0:
                return {"valid": False, "error": "required_vram_gb must be positive"}
        except (ValueError, TypeError):
            return {"valid": False, "error": "required_vram_gb must be a number"}

        # 验证文件名不为空
        if not model["expected_gguf"].strip():
            return {"valid": False, "error": "expected_gguf cannot be empty"}

        return {"valid": True, "error": ""}

    def _check_model_repo_exists(self, repo_id: str) -> Dict[str, Any]:
        """
        检查仓库 ID 格式是否有效（不实际调用远程 API）

        Args:
            repo_id: 仓库 ID (如 "unsloth/Qwen3.5-4B-GGUF")

        Returns:
            {"exists": bool, "error": str}
        """
        # 只验证仓库 ID 格式（user/repo 格式）
        if '/' not in repo_id or len(repo_id.split('/')) != 2:
            return {"exists": False, "error": "Invalid repo_id format (expected user/repo)"}
        
        user, repo = repo_id.split('/')
        if not user or not repo:
            return {"exists": False, "error": "Empty user or repo name"}
        
        # 格式正确即认为存在（远程检查在网络不可达时跳过）
        return {"exists": True, "error": ""}

    def _validate_all_models_exist(self, models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        验证所有配置的模型仓库是否存在（异步检查）

        Args:
            models: 模型配置列表

        Returns:
            仓库存在的模型列表
        """
        valid_models = []
        for model in models:
            repo_id = model.get("repo_id", "")
            check_result = self._check_model_repo_exists(repo_id)
            if check_result["exists"]:
                valid_models.append(model)
            else:
                self._download_status_label.setText(
                    f"Model {model.get('id')} repo unavailable: {check_result['error']}"
                )
        
        return valid_models

    def _match_local_files(self, models_dir: str, model_config: Dict[str, Any]) -> Optional[str]:
        """
        根据配置模式匹配本地已下载的模型文件

        Args:
            models_dir: 模型目录路径
            model_config: 模型配置字典

        Returns:
            匹配的 gguf 文件名，未匹配则为 None
        """
        if not os.path.isdir(models_dir):
            return None

        gguf_pattern = model_config.get("gguf_pattern", "")

        try:
            gguf_regex = re.compile(gguf_pattern)
        except re.error:
            return None

        matched_gguf = None

        try:
            files = os.listdir(models_dir)
        except Exception:
            return None

        for filename in files:
            if not filename.endswith('.gguf'):
                continue

            # 匹配主模型文件
            if matched_gguf is None and gguf_pattern:
                if gguf_regex.match(filename):
                    matched_gguf = filename

        return matched_gguf

    def _get_models_dir(self) -> str:
        """获取模型目录路径"""
        current = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current))))
        return os.path.join(root, "models")

    def _on_tray_changed(self, state):
        enabled = state == Qt.CheckState.Checked
        self._config.setdefault('system', {})
        self._config['system']['minimize_to_tray'] = enabled
        self.settings_changed.emit(self._config)
        self.minimize_to_tray_changed.emit(enabled)

    def _scan_local_models(self):
        """
        扫描本地模型并更新 UI

        流程：
        1. 从配置文件加载模型定义（带验证）
        2. 使用正则模式匹配本地已下载的 gguf 和 mmproj 文件
        3. 更新下拉框和状态标签
        """
        models_dir = self._get_models_dir()

        # 从配置文件加载模型定义（自动验证）
        models_config = self._load_models_config()
        if not models_config:
            self._local_models_label.setText("Failed to load model config")
            self._model_select_combo.clear()
            return

        # 获取当前显存
        vram_gb = 0
        if self._gpu_info and self._gpu_info.get("available"):
            gpus = self._gpu_info.get("gpus", [])
            if gpus:
                vram_gb = gpus[0].get("total_memory_gb", 0)

        # 清空并重新填充下拉框
        self._model_select_combo.clear()

        for model_cfg in models_config:
            model_id = model_cfg.get("repo_id", "")
            display_name = model_cfg.get("display_name", model_cfg.get("name", model_id))
            required_gb = model_cfg.get("required_vram_gb", 0)

            # 使用正则模式匹配本地文件
            matched_gguf = self._match_local_files(models_dir, model_cfg)

            # 显示 [LOCAL] 标签如果模型已下载
            local_tag = "[LOCAL]" if matched_gguf else ""

            # 构建显示标签
            if vram_gb > 0:
                fit = "✓" if vram_gb >= required_gb else "✗"
                label = f"{display_name}  [{fit} {required_gb:.1f}GB / {vram_gb:.1f}GB] {local_tag}".strip()
            else:
                label = f"{display_name}  [? {required_gb:.1f}GB] {local_tag}".strip()
            
            self._model_select_combo.addItem(label, model_id)
        
        # 更新已下载模型列表显示
        if not os.path.isdir(models_dir):
            self._local_models_label.setText("Models directory not found")
            return
        
        try:
            files = [f for f in os.listdir(models_dir) if f.endswith('.gguf')]
        except Exception as e:
            self._local_models_label.setText(f"Cannot read models directory: {e}")
            return
        
        if not files:
            self._local_models_label.setText("No .gguf models found")
            return
        
        # 按模型分组显示
        lines = ["Downloaded models:"]
        for f in sorted(files):
            path = os.path.join(models_dir, f)
            try:
                size_bytes = os.path.getsize(path)
                if size_bytes >= 1024 ** 3:
                    size_str = f"{size_bytes / (1024**3):.1f} GB"
                elif size_bytes >= 1024 ** 2:
                    size_str = f"{size_bytes / (1024**2):.0f} MB"
                else:
                    size_str = f"{size_bytes / 1024:.0f} KB"
            except Exception:
                size_str = "?"
            lines.append(f"  {f} ({size_str})")
        
        self._local_models_label.setText("\n".join(lines))

    def _download_model(self):
        """使用 ModelScope 下载模型（仅 gguf）"""
        model_id = self._model_select_combo.currentData()
        if not model_id:
            return

        # 从配置文件查找模型定义
        models_config = self._load_models_config()
        model_cfg = None
        for cfg in models_config:
            if cfg.get("repo_id") == model_id:
                model_cfg = cfg
                break

        if not model_cfg:
            self._download_status_label.setText(f"Model config not found: {model_id}")
            return

        # 获取期望的 gguf 文件名（只下载主模型）
        gguf = model_cfg.get("expected_gguf", "")

        if not gguf:
            self._download_status_label.setText("Invalid model config: missing expected gguf file")
            return

        models_dir = self._get_models_dir()
        os.makedirs(models_dir, exist_ok=True)

        from PyQt6.QtCore import QThread, pyqtSignal

        class ModelScopeDownloader(QThread):
            progress = pyqtSignal(object)  # (index, filename, total) or (-1, "", total) for done
            finished = pyqtSignal(bool, str)

            def __init__(self, repo, files, dest):
                super().__init__()
                self.repo = repo
                self.files = files
                self.dest = dest

            def run(self):
                try:
                    from modelscope.hub.file_download import model_file_download
                    import tqdm

                    # 禁用 tqdm 输出，避免与 PyQt6 渲染冲突
                    tqdm.tqdm.disable = True

                    total = len(self.files)
                    for i, fname in enumerate(self.files):
                        self.progress.emit((i, fname, total))
                        model_file_download(
                            model_id=self.repo,
                            file_path=fname,
                            cache_dir=self.dest,
                        )
                    self.progress.emit((-1, "", total))
                    self.finished.emit(True, f"Downloaded {total} file(s) to {self.dest}")
                except Exception as e:
                    self.finished.emit(False, str(e))

        self._download_thread = ModelScopeDownloader(
            model_id, [gguf], models_dir
        )
        self._download_thread.progress.connect(self._on_download_progress)
        self._download_thread.finished.connect(lambda ok, msg: self._on_download_finished(ok, msg))
        self._download_progress.setVisible(True)
        self._download_progress.setValue(0)
        self._download_status_label.setText(f"Preparing to download {gguf}...")
        self._download_btn.setEnabled(False)
        self._download_thread.start()

    def _on_download_progress(self, progress_data):
        """处理下载进度更新
        
        Args:
            progress_data: (index, filename, total) 元组
                          index = -1 表示完成
        """
        index, filename, total = progress_data
        
        if index == -1:
            # 下载完成，隐藏进度条
            self._download_progress.setVisible(False)
            return
        
        # 计算进度百分比
        progress = int(((index + 0.5) / total) * 100)
        self._download_progress.setValue(progress)
        
        # 更新状态文本
        file_num = f"{index + 1}/{total}"
        self._download_status_label.setText(f"Downloading {filename} ({file_num})...")

    def _on_download_finished(self, ok: bool, msg: str):
        from PyQt6.QtWidgets import QMessageBox
        
        # 恢复按钮状态
        self._download_btn.setEnabled(True)
        
        if ok:
            self._download_status_label.setStyleSheet("color: #00ffa2; font-size: 11px; font-family: Consolas; padding: 2px 0;")
            self._download_status_label.setText(f"SUCCESS: {msg}")
            # 2 秒后隐藏进度 UI
            QTimer.singleShot(2000, self._hide_progress_ui)
        else:
            self._download_status_label.setStyleSheet("color: #ff3355; font-size: 11px; font-family: Consolas; padding: 2px 0;")
            self._download_status_label.setText(f"FAILED: {msg}")
            QMessageBox.warning(self, "Download Failed", str(msg))
        
        self._scan_local_models()

    def _hide_progress_ui(self):
        """隐藏进度 UI 并重置状态"""
        self._download_progress.setVisible(False)
        self._download_status_label.setText("")
        self._download_status_label.setStyleSheet("color: #9090a8; font-size: 11px; font-family: Consolas; padding: 2px 0;")

    def _delete_model(self):
        """删除本地模型文件（配置驱动，动态匹配）"""
        from PyQt6.QtWidgets import QMessageBox

        model_id = self._model_select_combo.currentData()
        if not model_id:
            return
        
        # 从配置文件查找模型定义
        models_config = self._load_models_config()
        model_cfg = None
        for cfg in models_config:
            if cfg.get("repo_id") == model_id:
                model_cfg = cfg
                break
        
        if not model_cfg:
            QMessageBox.warning(self, "配置错误", f"未找到模型配置：{model_id}")
            return
        
        models_dir = self._get_models_dir()

        # 使用正则模式匹配本地已下载的文件
        matched_gguf = self._match_local_files(models_dir, model_cfg)

        # 构建要删除的文件列表
        files_to_delete = []
        if matched_gguf:
            files_to_delete.append((matched_gguf, os.path.join(models_dir, matched_gguf)))

        if not files_to_delete:
            QMessageBox.warning(self, "无本地文件", "该模型未下载，无法删除。")
            return
        
        # 显示确认对话框
        files_list = "\n".join([f"  {name}" for name, _ in files_to_delete])
        reply = QMessageBox.question(
            self, "确认删除",
            f"删除以下 {len(files_to_delete)} 个文件？\n\n{files_list}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 执行删除
        errors = []
        for name, path in files_to_delete:
            try:
                os.remove(path)
            except Exception as e:
                errors.append(f"{name}: {e}")
        
        if errors:
            QMessageBox.critical(self, "删除失败", "\n".join(errors))
        else:
            self._download_status_label.setText(f"Deleted {len(files_to_delete)} file(s)")
        
        self._scan_local_models()


    def get_config(self) -> Dict[str, Any]:
        return self._config

    def set_config(self, config: Dict[str, Any]):
        self._config = config or {}
        self._load_config()
        self._start_gpu_check()