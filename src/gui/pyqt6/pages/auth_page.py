"""
认证管理页面 - 本地版（Sight 分支）
纯本地模式，无服务端认证依赖
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt

from core.foundation.utils.paths import ensure_src_path
ensure_src_path(__file__)

from gui.pyqt6.theme.theme_manager import ThemeManager
from gui.pyqt6.widgets.base_widgets import CardWidget


class RegistrationDialog(QWidget):
    """注册对话框桩——本地模式无需注册"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("用户注册")
        self.setFixedSize(360, 150)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        label = QLabel("本地模式无需注册，直接使用即可。")
        label.setStyleSheet("color: #e8e8ee; font-size: 13px;")
        layout.addWidget(label)
        btn = QPushButton("确定")
        btn.clicked.connect(self.close)
        layout.addWidget(btn)


class AuthPage(QWidget):
    """认证管理页面 - 本地版
    
    纯本地模式，显示本地用户状态，无服务端认证功能。
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._theme = ThemeManager.get_instance()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 标题
        title = QLabel("认证管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #e8e8ee;")
        layout.addWidget(title)

        # 状态卡片
        card = CardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(8)

        status_row = QHBoxLayout()
        status_label = QLabel("运行模式：")
        status_label.setStyleSheet("color: #a0a0b0; font-size: 13px;")
        status_value = QLabel("纯本地模式")
        status_value.setStyleSheet("color: #18d1ff; font-size: 13px; font-weight: bold;")
        status_row.addWidget(status_label)
        status_row.addWidget(status_value)
        status_row.addStretch()
        card_layout.addLayout(status_row)

        user_row = QHBoxLayout()
        user_label = QLabel("当前用户：")
        user_label.setStyleSheet("color: #a0a0b0; font-size: 13px;")
        user_value = QLabel("local")
        user_value.setStyleSheet("color: #e8e8ee; font-size: 13px;")
        user_row.addWidget(user_label)
        user_row.addWidget(user_value)
        user_row.addStretch()
        card_layout.addLayout(user_row)

        layout.addWidget(card)

        # 说明
        note = QLabel("Sight 分支为纯本地版本，无需服务端认证。\n所有推理在本地完成，不依赖 IstinaPlatform 服务。")
        note.setStyleSheet("color: #707080; font-size: 12px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch()

    def refresh(self) -> None:
        """刷新页面状态（本地模式无操作）"""
        pass

    def try_auto_login(self) -> bool:
        """自动登录（本地模式始终成功）"""
        return True
