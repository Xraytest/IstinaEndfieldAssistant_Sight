"""Agent chat widget - Endfield terminal-style conversation display"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame, QSizePolicy
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor, QPalette


class MessageBubble(QFrame):
    """Endfield terminal-style message bubble"""

    def __init__(self, content: str, is_user: bool = False, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)

        if not is_user:
            # 终端回复 - 青蓝左对齐
            prefix = QLabel(">>>")
            prefix.setStyleSheet("""
                QLabel {
                    color: #18d1ff;
                    font-size: 13px;
                    font-family: Consolas;
                    font-weight: bold;
                    padding: 12px 8px 12px 0;
                }
            """)
            prefix.setFixedWidth(36)
            prefix.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
            layout.addWidget(prefix)

            label = QLabel(content)
            label.setWordWrap(True)
            label.setStyleSheet("""
                QLabel {
                    background-color: rgba(16, 16, 26, 0.85);
                    color: #e0e0e8;
                    padding: 12px 16px;
                    border: 1px solid rgba(24, 209, 255, 0.12);
                    border-radius: 4px;
                    font-size: 13px;
                    font-family: Microsoft YaHei UI;
                }
            """)
            label.setMaximumWidth(560)
            layout.addWidget(label, 1)
            layout.addStretch()
        else:
            # 用户消息 - 品红/金右对齐
            layout.addStretch()
            label = QLabel(content)
            label.setWordWrap(True)
            label.setStyleSheet("""
                QLabel {
                    background-color: rgba(255, 26, 172, 0.08);
                    color: #ff1aac;
                    padding: 12px 16px;
                    border: 1px solid rgba(255, 26, 172, 0.20);
                    border-radius: 4px;
                    font-size: 13px;
                    font-family: Microsoft YaHei UI;
                }
            """)
            label.setMaximumWidth(480)
            layout.addWidget(label, 0, Qt.AlignmentFlag.AlignRight)


class AgentChatWidget(QWidget):
    """Endfield terminal-style scrollable chat container"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #0a0a0f;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #0a0a0f;
            }
            QScrollBar:vertical {
                background: #0a0a0f;
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background: rgba(24, 209, 255, 0.20);
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(24, 209, 255, 0.35);
            }
        """)

        self.messages_widget = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.messages_layout.setSpacing(6)
        self.messages_layout.setContentsMargins(16, 16, 16, 16)
        self.messages_layout.addStretch()

        self.scroll_area.setWidget(self.messages_widget)
        layout.addWidget(self.scroll_area)

        self._add_system_message("Agent Terminal ready. Awaiting command.")

    def _add_system_message(self, text: str):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("""
            QLabel {
                color: rgba(24, 209, 255, 0.50);
                font-size: 12px;
                padding: 12px;
                font-family: Consolas;
            }
        """)
        label.setMaximumWidth(500)
        center_layout = QHBoxLayout()
        center_layout.addStretch()
        center_layout.addWidget(label)
        center_layout.addStretch()
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, self._widget_from_layout(center_layout))

    def add_message(self, content: str, is_user: bool = False):
        bubble = MessageBubble(content, is_user)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, bubble)
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    def add_action_result(self, action_type: str, success: bool):
        status = "OK" if success else "FAIL"
        color = "#00ffa2" if success else "#ff3355"
        label = QLabel(f"  [{status}] {action_type}")
        label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 11px;
                font-family: Consolas;
                padding: 2px 16px 2px 52px;
                background-color: transparent;
            }}
        """)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, label)
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    def _widget_from_layout(self, layout):
        w = QWidget()
        w.setLayout(layout)
        return w

    def clear(self):
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._add_system_message("Terminal reset. Ready.")