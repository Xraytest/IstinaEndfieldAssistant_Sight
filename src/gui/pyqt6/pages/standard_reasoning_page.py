"""Standard Reasoning page - select and execute standard flow tasks"""
from typing import Optional, Dict, Any, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QScrollArea, QTextEdit, QMessageBox,
    QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

INFO_STYLE = "color: #9090a8; font-size: 12px; font-family: Consolas; padding: 3px 0;"
VAL_STYLE = "color: #e8e8ee; font-size: 12px; font-family: Consolas; padding: 3px 0;"
GREEN_STYLE = "color: #00ffa2; font-size: 12px; font-family: Consolas; padding: 3px 0;"
RED_STYLE = "color: #ff3355; font-size: 12px; font-family: Consolas; padding: 3px 0;"
BLUE_STYLE = "color: #18d1ff; font-size: 12px; font-family: Consolas; padding: 3px 0;"
HEADER_STYLE = "color: #18d1ff; font-size: 14px; font-family: Consolas; font-weight: bold; letter-spacing: 1px; padding: 4px 0;"

BTN_ACTIVE = """
    QPushButton {
        background-color: rgba(0, 255, 162, 0.12);
        color: #00ffa2;
        border: 1px solid rgba(0, 255, 162, 0.40);
        border-radius: 4px;
        font-size: 11px; font-family: Consolas; font-weight: bold; letter-spacing: 1px;
    }
    QPushButton:hover { background-color: rgba(0, 255, 162, 0.25); }
"""
BTN_STOP = """
    QPushButton {
        background-color: rgba(255, 51, 85, 0.12);
        color: #ff3355;
        border: 1px solid rgba(255, 51, 85, 0.40);
        border-radius: 4px;
        font-size: 11px; font-family: Consolas; font-weight: bold; letter-spacing: 1px;
    }
    QPushButton:hover { background-color: rgba(255, 51, 85, 0.25); }
"""
BTN_DEFAULT = """
    QPushButton {
        background-color: rgba(24, 209, 255, 0.10);
        color: #18d1ff;
        border: 1px solid rgba(24, 209, 255, 0.30);
        border-radius: 4px;
        font-size: 11px; font-family: Consolas; font-weight: bold; letter-spacing: 1px;
    }
    QPushButton:hover { background-color: rgba(24, 209, 255, 0.20); }
"""
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
CHECK_STYLE = """
    QCheckBox { color: #e8e8ee; font-size: 12px; font-family: Consolas; spacing: 8px; }
    QCheckBox::indicator {
        width: 16px; height: 16px; border-radius: 2px;
        border: 1px solid rgba(24, 209, 255, 0.30);
        background-color: transparent;
    }
    QCheckBox::indicator:checked { background-color: #18d1ff; border-color: #18d1ff; }
    QCheckBox::indicator:hover { border-color: #18d1ff; }
"""


class StandardReasoningPage(QWidget):
    """Standard Reasoning - select and execute standard flow tasks"""

    def __init__(self, communicator=None, agent_executor=None, parent=None,
                 screen_capture=None, touch_executor=None, config=None,
                 inference_manager=None):
        super().__init__(parent)
        self.communicator = communicator
        self.agent_executor = agent_executor
        self.screen_capture = screen_capture
        self.touch_executor = touch_executor
        self.inference_manager = inference_manager
        self._config = config or {}
        self._flow_checkboxes: Dict[str, QCheckBox] = {}
        self._setup_ui()
        QTimer.singleShot(100, self._update_inference_mode_indicator)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("// STANDARD REASONING")
        title.setStyleSheet(HEADER_STYLE)
        header.addWidget(title)
        header.addStretch()

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
                margin-left: 8px;
            }
        """)
        header.addWidget(self._local_inference_label)
        layout.addLayout(header)

        # 初始化推理模式指示
        QTimer.singleShot(100, self._update_inference_mode_indicator)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)

        # Standard Flow Selection
        flow_card = self._make_card("STANDARD FLOWS")
        flow_layout = QVBoxLayout()
        flow_card.layout().addLayout(flow_layout)

        flow_list = QWidget()
        flow_list_layout = QVBoxLayout(flow_list)
        flow_list_layout.setSpacing(4)
        standard_flows = [
            "daily_quest", "weekly_quest", "resource_collection", "base_management",
            "character_ascension", "weapon_crafting", "event_rewards",
        ]
        for flow_id in standard_flows:
            cb = QCheckBox(flow_id.replace("_", " ").title())
            cb.setStyleSheet(CHECK_STYLE)
            self._flow_checkboxes[flow_id] = cb
            flow_list_layout.addWidget(cb)
        flow_layout.addWidget(flow_list)

        btn_row = QHBoxLayout()
        self._execute_btn = QPushButton("EXECUTE SELECTED")
        self._execute_btn.setFixedSize(160, 32)
        self._execute_btn.setStyleSheet(BTN_ACTIVE)
        self._execute_btn.clicked.connect(self._execute_selected_flows)
        btn_row.addWidget(self._execute_btn)

        self._exec_stop_btn = QPushButton("STOP")
        self._exec_stop_btn.setFixedSize(80, 32)
        self._exec_stop_btn.setStyleSheet(BTN_STOP)
        self._exec_stop_btn.setEnabled(False)
        self._exec_stop_btn.clicked.connect(self._stop_execution)
        btn_row.addWidget(self._exec_stop_btn)
        btn_row.addStretch()
        flow_layout.addLayout(btn_row)

        self._flow_status = QLabel("Ready")
        self._flow_status.setStyleSheet(VAL_STYLE)
        flow_layout.addWidget(self._flow_status)
        scroll_layout.addWidget(flow_card)

        # Execution Log
        log_card = self._make_card("EXECUTION LOG")
        log_layout_inner = QVBoxLayout()
        log_card.layout().addLayout(log_layout_inner)
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(200)
        self._log_text.setStyleSheet("""
            QTextEdit {
                background-color: rgba(10, 10, 15, 0.90);
                color: #e0e0e8;
                border: 1px solid rgba(24, 209, 255, 0.10);
                border-radius: 4px;
                font-size: 11px; font-family: Consolas;
                padding: 8px;
            }
        """)
        log_layout_inner.addWidget(self._log_text)
        scroll_layout.addWidget(log_card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

    def _make_card(self, title: str) -> QGroupBox:
        group = QGroupBox()
        group.setStyleSheet("""
            QGroupBox {
                background-color: rgba(16, 16, 26, 0.85);
                border: 1px solid rgba(24, 209, 255, 0.10);
                border-radius: 4px;
                font-size: 13px; font-family: Consolas;
                color: #e8e8ee; font-weight: bold; letter-spacing: 1px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 16px; padding: 0 4px;
            }
        """)
        group.setTitle(title)
        group.setLayout(QVBoxLayout())
        group.layout().setContentsMargins(20, 16, 20, 16)
        group.layout().setSpacing(6)
        return group

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
                    margin-left: 8px;
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
                    margin-left: 8px;
                }
            """)

    def _execute_selected_flows(self):
        selected = [fid for fid, cb in self._flow_checkboxes.items() if cb.isChecked()]
        if not selected:
            QMessageBox.warning(self, "No Flow Selected", "Select at least one standard flow to execute.")
            return
        if not self.agent_executor:
            QMessageBox.warning(self, "Agent Not Ready", "Agent executor not initialized.")
            return
        self._log(f"Executing flows: {', '.join(selected)}")
        self._execute_btn.setEnabled(False)
        self._exec_stop_btn.setEnabled(True)
        self._flow_status.setText("RUNNING")

        class FlowExecutionThread(QThread):
            flow_completed = pyqtSignal(str, bool, str)
            all_done = pyqtSignal()

            def __init__(self, agent_executor, flow_ids, stop_flag_ref):
                super().__init__()
                self.agent_executor = agent_executor
                self.flow_ids = flow_ids
                self._stop_flag = stop_flag_ref

            def run(self):
                for flow_id in self.flow_ids:
                    if self._stop_flag[0]:
                        self.flow_completed.emit(flow_id, False, "Stopped by user")
                        break
                    try:
                        result = self.agent_executor.send_instruction(f"Execute standard flow: {flow_id}")
                        if result.get("status") == "success":
                            self.flow_completed.emit(flow_id, True, "Completed")
                        else:
                            self.flow_completed.emit(flow_id, False, result.get('message', 'Unknown'))
                    except Exception as e:
                        self.flow_completed.emit(flow_id, False, str(e))
                self.all_done.emit()

        self._flow_stop_flag = [False]
        self._flow_thread = FlowExecutionThread(self.agent_executor, selected, self._flow_stop_flag)
        self._flow_thread.flow_completed.connect(self._on_flow_completed)
        self._flow_thread.all_done.connect(self._on_all_flows_done)
        self._flow_thread.start()

    def _on_flow_completed(self, flow_id: str, success: bool, message: str):
        status = "OK" if success else "FAIL"
        self._log(f"[{flow_id}] {status}: {message}")

    def _on_all_flows_done(self):
        self._execute_btn.setEnabled(True)
        self._exec_stop_btn.setEnabled(False)
        self._flow_status.setText("All flows completed.")

    def _stop_execution(self):
        self._flow_stop_flag[0] = True
        self._exec_stop_btn.setEnabled(False)
        self._log("Execution stopped by user.")

    def _log(self, text: str):
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._log_text.append(f"[{ts}] {text}")

    def set_communicator(self, communicator):
        self.communicator = communicator

    def set_agent_executor(self, agent_executor):
        self.agent_executor = agent_executor

    def set_screen_capture(self, screen_capture):
        self.screen_capture = screen_capture

    def set_touch_executor(self, touch_executor):
        self.touch_executor = touch_executor