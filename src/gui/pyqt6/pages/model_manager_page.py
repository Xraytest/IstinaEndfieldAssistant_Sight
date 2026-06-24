"""Model manager page - Endfield terminal style for local model management"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QComboBox, QProgressBar, 
                             QMessageBox, QGroupBox, QFormLayout)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from typing import Optional, Dict, Any
import os


INFO_STYLE = "color: #9090a8; font-size: 12px; font-family: Consolas; padding: 3px 0;"
VAL_STYLE = "color: #e8e8ee; font-size: 12px; font-family: Consolas; padding: 3px 0;"


class ModelManagerPage(QWidget):
    """Page for managing local inference models - Endfield terminal style"""
    
    model_selected = pyqtSignal(str)
    model_download_requested = pyqtSignal(str)
    model_remove_requested = pyqtSignal(str)
    refresh_requested = pyqtSignal()
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self._config = config or {}
        self._available_models = []
        self._downloaded_models = []
        self._setup_ui()
        self._refresh_models()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # 终端标题
        title = QLabel("// MODEL REPOSITORY")
        title.setStyleSheet("""
            QLabel {
                color: #18d1ff;
                font-size: 14px;
                font-family: Consolas;
                font-weight: bold;
                letter-spacing: 1px;
                padding: 4px 0;
            }
        """)
        layout.addWidget(title)
        
        # GPU 状态面板
        gpu_group = QWidget()
        gpu_group.setStyleSheet("""
            QWidget {
                background-color: rgba(16, 16, 26, 0.85);
                border: 1px solid rgba(24, 209, 255, 0.10);
                border-radius: 4px;
            }
        """)
        gpu_layout = QVBoxLayout(gpu_group)
        gpu_layout.setContentsMargins(20, 16, 20, 16)
        gpu_layout.setSpacing(6)
        
        gpu_title = QLabel("GPU STATUS")
        gpu_title.setStyleSheet("color: #e8e8ee; font-size: 13px; font-family: Consolas; font-weight: bold; letter-spacing: 1px;")
        gpu_layout.addWidget(gpu_title)
        
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("GPU STATUS:"))
        row1.itemAt(0).widget().setStyleSheet(INFO_STYLE)
        self._gpu_status_label = QLabel("SCANNING...")
        self._gpu_status_label.setStyleSheet(VAL_STYLE)
        row1.addWidget(self._gpu_status_label)
        row1.addStretch()
        gpu_layout.addLayout(row1)
        
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("VRAM:"))
        row2.itemAt(0).widget().setStyleSheet(INFO_STYLE)
        self._vram_label = QLabel("UNKNOWN")
        self._vram_label.setStyleSheet(VAL_STYLE)
        row2.addWidget(self._vram_label)
        row2.addStretch()
        gpu_layout.addLayout(row2)
        
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("SYSTEM RAM:"))
        row3.itemAt(0).widget().setStyleSheet(INFO_STYLE)
        self._ram_label = QLabel("UNKNOWN")
        self._ram_label.setStyleSheet(VAL_STYLE)
        row3.addWidget(self._ram_label)
        row3.addStretch()
        gpu_layout.addLayout(row3)
        
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("REQUIREMENTS:"))
        row4.itemAt(0).widget().setStyleSheet(INFO_STYLE)
        self._meets_requirements_label = QLabel("SCANNING...")
        self._meets_requirements_label.setStyleSheet(VAL_STYLE)
        row4.addWidget(self._meets_requirements_label)
        row4.addStretch()
        gpu_layout.addLayout(row4)
        
        layout.addWidget(gpu_group)
        
        # 模型管理面板
        model_group = QWidget()
        model_group.setStyleSheet("""
            QWidget {
                background-color: rgba(16, 16, 26, 0.85);
                border: 1px solid rgba(24, 209, 255, 0.10);
                border-radius: 4px;
            }
        """)
        model_layout = QVBoxLayout(model_group)
        model_layout.setContentsMargins(20, 16, 20, 16)
        model_layout.setSpacing(12)
        
        model_title = QLabel("MODEL MANAGEMENT")
        model_title.setStyleSheet("color: #e8e8ee; font-size: 13px; font-family: Consolas; font-weight: bold; letter-spacing: 1px;")
        model_layout.addWidget(model_title)
        
        # 模型选择
        select_row = QHBoxLayout()
        select_label = QLabel("SELECT MODEL:")
        select_label.setStyleSheet(INFO_STYLE)
        select_row.addWidget(select_label)
        
        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(320)
        self._model_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(10, 10, 15, 0.80);
                color: #e8e8ee;
                border: 1px solid rgba(24, 209, 255, 0.15);
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 12px;
                font-family: Consolas;
                min-height: 36px;
            }
            QComboBox:hover {
                border-color: rgba(24, 209, 255, 0.35);
            }
            QComboBox::drop-down {
                border: none;
                width: 28px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid rgba(24, 209, 255, 0.50);
                width: 0;
                height: 0;
            }
            QComboBox QAbstractItemView {
                background-color: rgba(12, 12, 20, 0.95);
                color: #e8e8ee;
                border: 1px solid rgba(24, 209, 255, 0.15);
                border-radius: 4px;
                selection-background-color: rgba(24, 209, 255, 0.15);
            }
        """)
        self._model_combo.currentTextChanged.connect(self._on_model_selected)
        select_row.addWidget(self._model_combo)
        select_row.addStretch()
        model_layout.addLayout(select_row)
        
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
        model_layout.addWidget(self._download_progress)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        btn_style = """
            QPushButton {
                background-color: transparent;
                color: #18d1ff;
                border: 1px solid rgba(24, 209, 255, 0.25);
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 11px;
                font-family: Consolas;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background-color: rgba(24, 209, 255, 0.08);
            }
            QPushButton:disabled {
                color: #404058;
                border-color: rgba(60, 60, 80, 0.15);
            }
        """
        btn_danger_style = btn_style.replace("#18d1ff", "#ff3355").replace("rgba(24, 209, 255", "rgba(255, 51, 85")
        
        self._refresh_btn = QPushButton("REFRESH")
        self._refresh_btn.setStyleSheet(btn_style)
        self._refresh_btn.clicked.connect(self._refresh_models)
        
        self._download_btn = QPushButton("DOWNLOAD")
        self._download_btn.setStyleSheet(btn_style)
        self._download_btn.clicked.connect(self._download_selected_model)
        self._download_btn.setEnabled(False)
        
        self._remove_btn = QPushButton("DELETE")
        self._remove_btn.setStyleSheet(btn_danger_style)
        self._remove_btn.clicked.connect(self._remove_selected_model)
        self._remove_btn.setEnabled(False)
        
        button_layout.addWidget(self._refresh_btn)
        button_layout.addWidget(self._download_btn)
        button_layout.addWidget(self._remove_btn)
        button_layout.addStretch()
        model_layout.addLayout(button_layout)
        
        layout.addWidget(model_group)
        
        # 状态
        self._status_label = QLabel("READY")
        self._status_label.setStyleSheet("color: #606080; font-size: 11px; font-family: Consolas; font-style: italic; padding: 4px 0;")
        layout.addWidget(self._status_label)
        
        layout.addStretch()
        
    def _get_models_dir(self) -> str:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
        return os.path.join(project_root, "models")

    def _scan_local_models(self) -> list:
        models_dir = self._get_models_dir()
        if not os.path.exists(models_dir):
            return []
        models = []
        for f in os.listdir(models_dir):
            if f.endswith('.gguf'):
                models.append(os.path.splitext(f)[0])
        return models

    def _refresh_models(self):
        self._status_label.setText("SCANNING MODEL LIST...")
        self._refresh_btn.setEnabled(False)
        self.refresh_requested.emit()
        
    def update_models(self, available_models: list, downloaded_models: list):
        self._available_models = available_models
        self._downloaded_models = downloaded_models
        
        self._model_combo.clear()
        for model in available_models:
            status = "[LOCAL]" if model in downloaded_models else ""
            self._model_combo.addItem(f"{model} {status}".strip(), model)
        
        current_model = self._model_combo.currentData()
        if current_model:
            self._download_btn.setEnabled(current_model not in downloaded_models)
            self._remove_btn.setEnabled(current_model in downloaded_models)
        else:
            self._download_btn.setEnabled(False)
            self._remove_btn.setEnabled(False)
            
        self._status_label.setText(f"FOUND {len(available_models)} MODELS, {len(downloaded_models)} LOCAL")
        self._refresh_btn.setEnabled(True)
        
    def update_gpu_status(self, gpu_info: dict):
        red_style = "color: #ff3355; font-size: 12px; font-family: Consolas; padding: 3px 0;"
        green_style = "color: #00ffa2; font-size: 12px; font-family: Consolas; padding: 3px 0;"
        
        if not gpu_info.get("available", False):
            self._gpu_status_label.setText("NO NVIDIA GPU")
            self._vram_label.setText("N/A")
            self._ram_label.setText("N/A")
            self._meets_requirements_label.setText("NOT MET (NO GPU)")
            self._gpu_status_label.setStyleSheet(red_style)
            self._vram_label.setStyleSheet(red_style)
            self._ram_label.setStyleSheet(red_style)
            self._meets_requirements_label.setStyleSheet(red_style)
            self._model_combo.setEnabled(False)
            self._download_btn.setEnabled(False)
            self._remove_btn.setEnabled(False)
            return
            
        self._gpu_status_label.setText("GPU DETECTED")
        self._vram_label.setText(f"{gpu_info.get('gpus', [{}])[0].get('total_memory_gb', 0):.1f} GB")
        self._ram_label.setText("PENDING")
        meets_req = gpu_info.get("meets_requirements", False)
        self._meets_requirements_label.setText("MET" if meets_req else "NOT MET")
        color = green_style if meets_req else red_style
        self._gpu_status_label.setStyleSheet(color)
        self._vram_label.setStyleSheet(color)
        self._ram_label.setStyleSheet(color)
        self._meets_requirements_label.setStyleSheet(color)
        
        self._model_combo.setEnabled(True)
        
    def _on_model_selected(self, model_name: str):
        if model_name:
            self.model_selected.emit(model_name)
            
    def _download_selected_model(self):
        model_name = self._model_combo.currentData()
        if model_name:
            self._download_btn.setEnabled(False)
            self._remove_btn.setEnabled(False)
            self._download_progress.setVisible(True)
            self._download_progress.setValue(0)
            self._status_label.setText(f"DOWNLOADING {model_name}...")
            self.model_download_requested.emit(model_name)
            
    def _remove_selected_model(self):
        model_name = self._model_combo.currentData()
        if model_name:
            reply = QMessageBox.question(
                self, 
                "CONFIRM DELETE", 
                f"DELETE MODEL '{model_name}'?\nThis operation cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._status_label.setText(f"DELETING {model_name}...")
                self.model_remove_requested.emit(model_name)
                
    def set_download_progress(self, value: int):
        self._download_progress.setValue(value)
        if value >= 100:
            self._status_label.setText("DOWNLOAD COMPLETE")
        else:
            self._status_label.setText(f"DOWNLOADING: {value}%")
            
    def set_download_finished(self, success: bool, message: str = ""):
        self._download_progress.setVisible(False)
        self._download_btn.setEnabled(True)
        if success:
            self._status_label.setText(f"DOWNLOAD SUCCESS: {message}")
            self.refresh_requested.emit()
        else:
            self._status_label.setText(f"DOWNLOAD FAILED: {message}")
            self._remove_btn.setEnabled(False)