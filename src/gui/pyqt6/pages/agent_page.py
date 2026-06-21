"""Agent page - Endfield terminal-style natural language interface"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                             QPushButton, QLabel, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QFont, QColor

from ..widgets.agent_chat_widget import AgentChatWidget


class AgentInteractionThread(QThread):
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, agent_executor, instruction):
        super().__init__()
        self.agent_executor = agent_executor
        self.instruction = instruction

    def run(self):
        try:
            result = self.agent_executor.send_instruction(self.instruction)
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))


class AgentPage(QWidget):
    def __init__(self, agent_executor=None, parent=None, inference_manager=None):
        super().__init__(parent)
        self.agent_executor = agent_executor
        self.inference_manager = inference_manager
        self._current_thread = None
        self._setup_ui()
        QTimer.singleShot(100, self._update_inference_mode_indicator)

    def _setup_ui(self):
        self.setStyleSheet("background-color: #0a0a0f;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 终端标题栏
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet("""
            QWidget {
                background-color: rgba(24, 209, 255, 0.03);
                border-bottom: 1px solid rgba(24, 209, 255, 0.10);
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        title = QLabel("AGENT TERMINAL")
        title.setStyleSheet("""
            QLabel {
                color: #18d1ff;
                font-size: 14px;
                font-family: Consolas;
                font-weight: bold;
                letter-spacing: 1px;
            }
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()

        # 状态指示灯
        status_dot = QLabel("●")
        status_dot.setStyleSheet("color: #00ffa2; font-size: 10px;")
        status_text = QLabel("ONLINE")
        status_text.setStyleSheet("color: #00ffa2; font-size: 11px; font-family: Consolas;")
        header_layout.addWidget(status_dot)
        header_layout.addSpacing(4)
        header_layout.addWidget(status_text)
        header_layout.addSpacing(8)

        # 本地推理状态指示
        self._local_inference_label = QLabel("CLOUD")
        self._local_inference_label.setStyleSheet("""
            QLabel {
                color: rgba(144, 144, 168, 0.50);
                font-size: 10px;
                font-family: Consolas;
                padding: 2px 8px;
                border: 1px solid rgba(144, 144, 168, 0.15);
                border-radius: 3px;
            }
        """)
        header_layout.addWidget(self._local_inference_label)
        header_layout.addSpacing(16)

        self.reset_btn = QPushButton("RESET")
        self.reset_btn.setFixedSize(90, 32)
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ff3355;
                border: 1px solid #ff3355;
                border-radius: 4px;
                font-size: 11px;
                font-family: Consolas;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background-color: rgba(255, 51, 85, 0.10);
            }
        """)
        self.reset_btn.clicked.connect(self._on_reset)
        header_layout.addWidget(self.reset_btn)

        main_layout.addWidget(header)

        # 聊天区域
        self.chat_widget = AgentChatWidget()
        main_layout.addWidget(self.chat_widget, 1)

        # 终端输入区域
        input_area = QWidget()
        input_area.setFixedHeight(80)
        input_area.setStyleSheet("""
            QWidget {
                background-color: rgba(24, 209, 255, 0.02);
                border-top: 1px solid rgba(24, 209, 255, 0.10);
            }
        """)
        input_layout = QHBoxLayout(input_area)
        input_layout.setContentsMargins(20, 12, 20, 12)

        # 输入提示符
        prompt = QLabel(">>>")
        prompt.setStyleSheet("""
            QLabel {
                color: #18d1ff;
                font-size: 16px;
                font-family: Consolas;
                font-weight: bold;
                padding: 0 8px 0 0;
            }
        """)
        prompt.setFixedWidth(36)
        input_layout.addWidget(prompt)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter command... (e.g., 'Go to the crafting menu')")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: rgba(10, 10, 15, 0.90);
                color: #e0e0e8;
                border: 1px solid rgba(24, 209, 255, 0.15);
                border-radius: 4px;
                padding: 10px 16px;
                font-size: 14px;
                font-family: Consolas;
            }
            QLineEdit:focus {
                border-color: rgba(24, 209, 255, 0.40);
            }
        """)
        self.input_field.returnPressed.connect(self._on_send)

        self.send_btn = QPushButton("EXEC")
        self.send_btn.setFixedSize(80, 40)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(24, 209, 255, 0.15);
                color: #18d1ff;
                border: 1px solid rgba(24, 209, 255, 0.30);
                border-radius: 4px;
                font-size: 12px;
                font-family: Consolas;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background-color: rgba(24, 209, 255, 0.25);
                border-color: #18d1ff;
            }
            QPushButton:disabled {
                background-color: rgba(60, 60, 80, 0.15);
                color: #404058;
                border-color: rgba(60, 60, 80, 0.20);
            }
        """)
        self.send_btn.clicked.connect(self._on_send)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)

        main_layout.addWidget(input_area)

    def _update_inference_mode_indicator(self):
        """更新本地/云端推理模式指示器"""
        if self.inference_manager and self.inference_manager.is_local_available():
            self._local_inference_label.setText("LOCAL")
            self._local_inference_label.setStyleSheet("""
                QLabel {
                    color: #00ffa2;
                    font-size: 10px;
                    font-family: Consolas;
                    padding: 2px 8px;
                    border: 1px solid rgba(0, 255, 162, 0.40);
                    border-radius: 3px;
                }
            """)
        else:
            self._local_inference_label.setText("CLOUD")
            self._local_inference_label.setStyleSheet("""
                QLabel {
                    color: rgba(144, 144, 168, 0.50);
                    font-size: 10px;
                    font-family: Consolas;
                    padding: 2px 8px;
                    border: 1px solid rgba(144, 144, 168, 0.15);
                    border-radius: 3px;
                }
            """)

    def set_agent_executor(self, agent_executor):
        self.agent_executor = agent_executor

    def _on_send(self):
        instruction = self.input_field.text().strip()
        if not instruction or not self.agent_executor:
            return

        if self._current_thread and self._current_thread.isRunning():
            return

        self.send_btn.setEnabled(False)
        self.input_field.setEnabled(False)
        self.chat_widget.add_message(instruction, is_user=True)
        self.input_field.clear()

        self._current_thread = AgentInteractionThread(self.agent_executor, instruction)
        self._current_thread.result_ready.connect(self._on_result)
        self._current_thread.error_occurred.connect(self._on_error)
        self._current_thread.start()

    def _on_result(self, result):
        self.send_btn.setEnabled(True)
        self.input_field.setEnabled(True)

        if result.get("status") == "success":
            reply = result.get("reply", "")
            if reply:
                self.chat_widget.add_message(reply, is_user=False)
            for ar in result.get("execution_results", []):
                self.chat_widget.add_action_result(
                    ar.get("action", "?"), ar.get("success", False)
                )
        else:
            self.chat_widget.add_message(
                f"Error: {result.get('message', 'Unknown error')}",
                is_user=False
            )

    def _on_error(self, error_msg):
        self.send_btn.setEnabled(True)
        self.input_field.setEnabled(True)
        self.chat_widget.add_message(f"Error: {error_msg}", is_user=False)

    def _on_reset(self):
        if self.agent_executor:
            self.agent_executor.reset_conversation()
        self.chat_widget.clear()
        self.input_field.clear()