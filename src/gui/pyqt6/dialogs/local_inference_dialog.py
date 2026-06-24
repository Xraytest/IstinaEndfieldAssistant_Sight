"""Local inference dialog for first-run GPU check and model recommendation"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QGroupBox, QFormLayout, QMessageBox,
                             QProgressBar, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from typing import Optional, Dict, Any
import sys
import os

from core.foundation.paths import ensure_src_path
ensure_src_path(__file__)

try:
    from core.capability.local_inference.gpu_checker import GPUChecker
except ImportError:
    GPUChecker = None


class GPUCheckWorker(QThread):
    """Worker thread for GPU checking"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
    def run(self):
        try:
            if GPUChecker is None:
                result = {
                    "available": False,
                    "error": "GPUChecker module not available"
                }
            else:
                checker = GPUChecker()
                result = checker.check_gpu_availability()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class LocalInferenceDialog(QDialog):
    """Dialog for first-run local inference setup"""
    
    # Signals
    local_inference_enabled = pyqtSignal(bool)  # True if user chooses local
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("本地推理设置")
        self.setModal(True)
        self.resize(500, 400)
        self._gpu_info = None
        self._setup_ui()
        self._start_gpu_check()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("欢迎使用 Istina Endfield Assistant")
        title.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #e0e0e0;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("检测到您的系统可以使用本地推理以获得更快的响应速度和更好的隐私保护。")
        subtitle.setStyleSheet("""
            QLabel {
                color: #b0b0b0;
                margin-bottom: 20px;
            }
        """)
        layout.addWidget(subtitle)
        
        # GPU Info Group
        gpu_group = QGroupBox("硬件检测结果")
        gpu_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3a3a5c;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        gpu_layout = QFormLayout()
        self._gpu_status_label = QLabel("检测中...")
        self._gpu_name_label = QLabel("未知")
        self._vram_label = QLabel("未知")
        self._ram_label = QLabel("未知")
        self._requirements_label = QLabel("检测中...")
        self._recommended_model_label = QLabel("未知")
        gpu_layout.addRow("状态:", self._gpu_status_label)
        gpu_layout.addRow("GPU 型号:", self._gpu_name_label)
        gpu_layout.addRow("显存:", self._vram_label)
        gpu_layout.addRow("系统内存:", self._ram_label)
        gpu_layout.addRow("满足要求:", self._requirements_label)
        gpu_layout.addRow("推荐模型:", self._recommended_model_label)
        gpu_group.setLayout(gpu_layout)
        layout.addWidget(gpu_group)
        
        # Progress bar (hidden by default)
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)
        
        # Buttons
        button_layout = QHBoxLayout()
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.clicked.connect(self.reject)
        self._use_cloud_btn = QPushButton("仅使用云端")
        self._use_cloud_btn.clicked.connect(self._choose_cloud)
        self._use_local_btn = QPushButton("使用本地推理")
        self._use_local_btn.clicked.connect(self._choose_local)
        self._use_local_btn.setEnabled(False)  # Enabled after GPU check
        
        button_layout.addWidget(self._cancel_btn)
        button_layout.addStretch()
        button_layout.addWidget(self._use_cloud_btn)
        button_layout.addWidget(self._use_local_btn)
        layout.addLayout(button_layout)
        
        # Checkbox for not showing again
        self._dont_show_again = QCheckBox("不再显示此对话框")
        layout.addWidget(self._dont_show_again)
        
    def _start_gpu_check(self):
        """Start GPU check"""
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)  # Indeterminate
        self._use_local_btn.setEnabled(False)
        self._use_cloud_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        
        self._worker = GPUCheckWorker()
        self._worker.finished.connect(self._on_gpu_check_finished)
        self._worker.error.connect(self._on_gpu_check_error)
        self._worker.start()
        
    def _on_gpu_check_finished(self, result: dict):
        """Handle GPU check results"""
        self._progress_bar.setVisible(False)
        self._cancel_btn.setEnabled(True)
        self._use_cloud_btn.setEnabled(True)
        
        self._gpu_info = result
        
        if not result.get("available", False):
            self._gpu_status_label.setText("未检测到 NVIDIA GPU")
            self._gpu_status_label.setStyleSheet("color: #ff6b6b;")
            self._gpu_name_label.setText("N/A")
            self._vram_label.setText("N/A")
            self._ram_label.setText("N/A")
            self._requirements_label.setText("不满足 (无 GPU)")
            self._requirements_label.setStyleSheet("color: #ff6b6b;")
            self._recommended_model_label.setText("N/A")
            self._use_local_btn.setEnabled(False)
            self._use_cloud_btn.setText("仅使用云端 (推荐)")
            return
            
        # GPU available
        gpus = result.get("gpus", [])
        if gpus:
            gpu = gpus[0]
            self._gpu_status_label.setText("GPU 检测正常")
            self._gpu_status_label.setStyleSheet("color: #4ecdc4;")
            self._gpu_name_label.setText(gpu.get("name", "未知"))
            self._vram_label.setText(f"{gpu.get('total_memory_gb', 0):.1f} GB")
            # Note: We don't have total RAM in the result, so we'll skip for now
            self._ram_label.setText("待检测")  # This would need separate psutil call
            meets_req = result.get("meets_requirements", False)
            self._requirements_label.setText("满足" if meets_req else "不满足")
            color = "#4ecdc4" if meets_req else "#ff6b6b"
            self._requirements_label.setStyleSheet(f"color: {color};")
            self._recommended_model_label.setText(result.get("recommended_model", "未知"))
            
            if meets_req:
                self._use_local_btn.setEnabled(True)
                self._use_local_btn.setText("使用本地推理 (推荐)")
                self._use_cloud_btn.setText("仅使用云端")
            else:
                self._use_local_btn.setEnabled(False)
                self._use_local_btn.setText("使用本地推理 (硬件不足)")
                self._use_cloud_btn.setText("仅使用云端 (推荐)")
        else:
            self._gpu_status_label.setText("GPU 检测异常")
            self._gpu_status_label.setStyleSheet("color: #ff6b6b;")
            self._gpu_name_label.setText("未知")
            self._vram_label.setText("N/A")
            self._ram_label.setText("N/A")
            self._requirements_label.setText("不满足")
            self._requirements_label.setStyleSheet("color: #ff6b6b;")
            self._recommended_model_label.setText("N/A")
            self._use_local_btn.setEnabled(False)
            self._use_cloud_btn.setText("仅使用云端 (推荐)")
            
    def _on_gpu_check_error(self, error_msg: str):
        """Handle GPU check error"""
        self._progress_bar.setVisible(False)
        self._cancel_btn.setEnabled(True)
        self._use_cloud_btn.setEnabled(True)
        
        self._gpu_status_label.setText("检测失败")
        self._gpu_status_label.setStyleSheet("color: #ff6b6b;")
        self._gpu_name_label.setText("错误")
        self._vram_label.setText("N/A")
        self._ram_label.setText("N/A")
        self._requirements_label.setText("错误")
        self._requirements_label.setStyleSheet("color: #ff6b6b;")
        self._recommended_model_label.setText("N/A")
        self._use_local_btn.setEnabled(False)
        self._use_cloud_btn.setText("仅使用云端 (推荐)")
        
    def _choose_local(self):
        """User chose to use local inference"""
        if self._gpu_info and self._gpu_info.get("meets_requirements", False):
            self.local_inference_enabled.emit(True)
            self.accept()
        else:
            # Should not happen if button is enabled correctly
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "无法使用本地推理",
                "当前硬件不满足本地推理的要求。\n"
                "请确保您的 NVIDIA GPU 显存 >= 6GB 或显存+系统内存 >= 48GB。"
            )
            
    def _choose_cloud(self):
        """User chose to use cloud only"""
        self.local_inference_enabled.emit(False)
        self.accept()
        
    def get_user_choice(self) -> bool:
        """Get user choice (True for local, False for cloud)"""
        # This is handled via signals, but we can also check the dialog result
        return self.result() == QDialog.DialogCode.Accepted and \
               self._use_local_btn.isEnabled() and \
               self._gpu_info and \
               self._gpu_info.get("meets_requirements", False)


def show_local_inference_dialog(parent=None) -> bool:
    """
    Show the local inference dialog and return user choice.
    
    Args:
        parent: Parent widget
        
    Returns:
        True if user chose local inference, False if chose cloud only
    """
    dialog = LocalInferenceDialog(parent)
    result = dialog.exec()
    return dialog.get_user_choice()