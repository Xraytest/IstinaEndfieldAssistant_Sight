"""Confirm dialog for Endfield terminal style"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt


INFO_STYLE = "color: #9090a8; font-size: 12px; font-family: Consolas; padding: 3px 0;"
BTN_STYLE = """
    QPushButton {
        background-color: rgba(24, 209, 255, 0.10);
        color: #18d1ff;
        border: 1px solid rgba(24, 209, 255, 0.30);
        border-radius: 4px;
        padding: 8px 24px;
        font-size: 11px;
        font-family: Consolas;
        font-weight: bold;
        letter-spacing: 1px;
    }
    QPushButton:hover {
        background-color: rgba(24, 209, 255, 0.20);
    }
"""
BTN_DANGER = BTN_STYLE.replace("#18d1ff", "#ff3355").replace("rgba(24, 209, 255", "rgba(255, 51, 85")


class ConfirmDialog(QDialog):
    def __init__(self, title="确认", message="确定执行此操作？", parent=None,
                 confirm_text="确认", cancel_text="取消", danger=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(400, 180)
        self._confirmed = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        msg = QLabel(message)
        msg.setStyleSheet(INFO_STYLE)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(cancel_text)
        cancel_btn.setStyleSheet(BTN_STYLE)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        confirm_btn = QPushButton(confirm_text)
        confirm_btn.setStyleSheet(BTN_DANGER if danger else BTN_STYLE)
        confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)
        self.setStyleSheet("background-color: #0c0c14;")

    def _on_confirm(self):
        self._confirmed = True
        self.accept()

    def is_confirmed(self) -> bool:
        return self._confirmed