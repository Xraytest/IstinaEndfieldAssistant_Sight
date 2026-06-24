"""
云端管理页面 - 本地版（Sight 分支）
纯本地模式，无云端功能
"""

from typing import Optional
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from core.foundation.paths import ensure_src_path
ensure_src_path(__file__)

from gui.pyqt6.theme.theme_manager import ThemeManager
from gui.pyqt6.widgets.base_widgets import CardWidget


class CloudPage(QWidget):
    """云端管理页面 - 本地版
    
    Sight 分支为纯本地版本，无云端功能。
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._theme = ThemeManager.get_instance()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("云端管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #e8e8ee;")
        layout.addWidget(title)

        card = CardWidget()
        card_layout = card.get_content_layout()
        card_layout.setContentsMargins(16, 16, 16, 16)

        label = QLabel("Sight 分支为纯本地版本，不依赖云端服务。\n所有推理在本地完成，无需连接 IstinaPlatform。")
        label.setStyleSheet("color: #a0a0b0; font-size: 13px;")
        label.setWordWrap(True)
        card_layout.addWidget(label)

        layout.addWidget(card)
        layout.addStretch()

    def refresh(self) -> None:
        pass
