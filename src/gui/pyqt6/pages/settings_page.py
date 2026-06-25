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

    def _on_tray_changed(self, state):
        enabled = self._tray_cb.isChecked()
        print(f"[托盘设置] checkbox isChecked={self._tray_cb.isChecked()}, enabled={enabled}")
        self._config.setdefault('system', {})
        self._config['system']['minimize_to_tray'] = enabled
        print(f"[托盘设置] config updated: {self._config['system']}")
        self.settings_changed.emit(self._config)
        self.minimize_to_tray_changed.emit(enabled)


    def get_config(self) -> Dict[str, Any]:
        return self._config

    def set_config(self, config: Dict[str, Any]):
        self._config = config or {}
        self._load_config()
        self._start_gpu_check()