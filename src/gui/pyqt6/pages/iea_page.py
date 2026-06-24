"""IEA Management page - local agent orchestration features"""
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QGroupBox, QScrollArea,
                               QTextEdit, QMessageBox, QSpinBox)
from PyQt6.QtCore import pyqtSignal, QThread

INFO_STYLE = "color: #9090a8; font-size: 12px; font-family: Consolas; padding: 3px 0;"
VAL_STYLE = "color: #e8e8ee; font-size: 12px; font-family: Consolas; padding: 3px 0;"
GREEN_STYLE = "color: #00ffa2; font-size: 12px; font-family: Consolas; padding: 3px 0;"
RED_STYLE = "color: #ff3355; font-size: 12px; font-family: Consolas; padding: 3px 0;"
BLUE_STYLE = "color: #18d1ff; font-size: 12px; font-family: Consolas; padding: 3px 0;"
YELLOW_STYLE = "color: #ffcc33; font-size: 12px; font-family: Consolas; padding: 3px 0;"
HEADER_STYLE = "color: #18d1ff; font-size: 14px; font-family: Consolas; font-weight: bold; letter-spacing: 1px; padding: 4px 0;"
SECTION_STYLE = "color: #e8e8ee; font-size: 13px; font-family: Consolas; font-weight: bold; letter-spacing: 1px;"

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


class IeaExploreThread(QThread):
    progress = pyqtSignal(str, object)
    finished = pyqtSignal()

    def __init__(self, engine):
        super().__init__()
        self._engine = engine

    def run(self):
        if self._engine:
            self._engine.start()
        self.finished.emit()


class IeaPage(QWidget):
    """IEA管理页面——服务端协调的功能总览"""

    refresh_requested = pyqtSignal()

    def __init__(self, agent_executor=None, parent=None, screen_capture=None, touch_executor=None):
        super().__init__(parent)
        self.agent_executor = agent_executor
        self.screen_capture = screen_capture
        self.touch_executor = touch_executor
        self._exploration_engine = None
        self._exploration_thread = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 标题栏
        header = QHBoxLayout()
        title = QLabel("// IEA CONTROL PANEL")
        title.setStyleSheet(HEADER_STYLE)
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)

        # ---- 1. Agent 编排器状态 ----
        agent_group = self._make_card("AGENT ORCHESTRATOR")
        self._agent_layout = QVBoxLayout()
        agent_group.layout().addLayout(self._agent_layout)
        self._make_kv_row(self._agent_layout, "STATE:", "IDLE", VAL_STYLE)
        self._make_kv_row(self._agent_layout, "SESSION:", "NULL", VAL_STYLE)
        self._make_kv_row(self._agent_layout, "PROVIDER:", "NULL", VAL_STYLE)
        self._make_kv_row(self._agent_layout, "MODEL TAG:", "NULL", VAL_STYLE)
        scroll_layout.addWidget(agent_group)

        # ---- 3. 状态模板 ----
        template_group = self._make_card("STATE TEMPLATES")
        self._template_layout = QVBoxLayout()
        template_group.layout().addLayout(self._template_layout)
        self._template_status = QLabel("未加载")
        self._template_status.setStyleSheet(VAL_STYLE)
        self._template_layout.addWidget(self._template_status)
        scroll_layout.addWidget(template_group)

        # ---- 4. 参考图像 ----
        ref_group = self._make_card("REFERENCE IMAGES")
        self._ref_layout = QVBoxLayout()
        ref_group.layout().addLayout(self._ref_layout)
        self._ref_status = QLabel("未加载")
        self._ref_status.setStyleSheet(VAL_STYLE)
        self._ref_layout.addWidget(self._ref_status)
        scroll_layout.addWidget(ref_group)

        # ---- 5. 页面探索 ----
        explore_group = self._make_card("PAGE EXPLORATION")
        self._explore_layout = QVBoxLayout()
        explore_group.layout().addLayout(self._explore_layout)

        ctrl_row = QHBoxLayout()
        self._explore_start_btn = QPushButton("START")
        self._explore_start_btn.setFixedSize(80, 32)
        self._explore_start_btn.setStyleSheet(BTN_ACTIVE)
        self._explore_start_btn.clicked.connect(self._start_exploration)
        ctrl_row.addWidget(self._explore_start_btn)

        self._explore_stop_btn = QPushButton("STOP")
        self._explore_stop_btn.setFixedSize(80, 32)
        self._explore_stop_btn.setStyleSheet(BTN_STOP)
        self._explore_stop_btn.clicked.connect(self._stop_exploration)
        self._explore_stop_btn.setEnabled(False)
        ctrl_row.addWidget(self._explore_stop_btn)

        self._explore_pause_btn = QPushButton("PAUSE")
        self._explore_pause_btn.setFixedSize(80, 32)
        self._explore_pause_btn.setStyleSheet(BTN_DEFAULT)
        self._explore_pause_btn.clicked.connect(self._toggle_pause_exploration)
        self._explore_pause_btn.setEnabled(False)
        ctrl_row.addWidget(self._explore_pause_btn)
        ctrl_row.addStretch()
        self._explore_layout.addLayout(ctrl_row)

        stats_row = QHBoxLayout()
        self._explore_stats_label = QLabel("Pages: 0 | Elements: 0 | Edges: 0 | VLM: 0 | Taps: 0")
        self._explore_stats_label.setStyleSheet(VAL_STYLE)
        stats_row.addWidget(self._explore_stats_label)
        stats_row.addStretch()
        self._explore_layout.addLayout(stats_row)

        config_row = QHBoxLayout()
        config_row.addWidget(QLabel("Depth:"))
        config_row.itemAt(config_row.count() - 1).widget().setStyleSheet(INFO_STYLE)
        self._depth_spin = QSpinBox()
        self._depth_spin.setRange(1, 50)
        self._depth_spin.setValue(20)
        self._depth_spin.setStyleSheet("color: #e8e8ee; background: rgba(10,10,15,0.9); border: 1px solid rgba(24,209,255,0.2); font-size: 11px;")
        config_row.addWidget(self._depth_spin)
        config_row.addWidget(QLabel("Verify:"))
        config_row.itemAt(config_row.count() - 1).widget().setStyleSheet(INFO_STYLE)
        self._verify_spin = QSpinBox()
        self._verify_spin.setRange(1, 5)
        self._verify_spin.setValue(3)
        self._verify_spin.setStyleSheet("color: #e8e8ee; background: rgba(10,10,15,0.9); border: 1px solid rgba(24,209,255,0.2); font-size: 11px;")
        config_row.addWidget(self._verify_spin)
        config_row.addStretch()
        self._explore_layout.addLayout(config_row)

        self._explore_log = QTextEdit()
        self._explore_log.setReadOnly(True)
        self._explore_log.setMaximumHeight(200)
        self._explore_log.setStyleSheet("""
            QTextEdit {
                background-color: rgba(10, 10, 15, 0.90);
                color: #e0e0e8;
                border: 1px solid rgba(24, 209, 255, 0.10);
                border-radius: 4px;
                font-size: 11px;
                font-family: Consolas;
                padding: 8px;
            }
        """)
        self._explore_layout.addWidget(self._explore_log)
        scroll_layout.addWidget(explore_group)

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
                font-size: 13px;
                font-family: Consolas;
                color: #e8e8ee;
                font-weight: bold;
                letter-spacing: 1px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 4px;
            }
        """)
        group.setTitle(title)
        group.setLayout(QVBoxLayout())
        group.layout().setContentsMargins(20, 16, 20, 16)
        group.layout().setSpacing(6)
        return group

    def _make_kv_row(self, parent_layout, key: str, val: str, val_style: str):
        row = QHBoxLayout()
        kl = QLabel(key)
        kl.setStyleSheet(INFO_STYLE)
        row.addWidget(kl)
        vl = QLabel(val)
        vl.setStyleSheet(val_style)
        row.addWidget(vl)
        row.addStretch()
        parent_layout.addLayout(row)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    # ==================== 公共接口 ====================

    def set_agent_executor(self, agent_executor):
        self.agent_executor = agent_executor

    def set_screen_capture(self, screen_capture):
        self.screen_capture = screen_capture

    def set_touch_executor(self, touch_executor):
        self.touch_executor = touch_executor

    # ==================== 页面探索 ====================

    def _start_exploration(self):
        if not self.screen_capture or not self.touch_executor:
            QMessageBox.warning(self, "Exploration", "Missing dependencies: screen_capture or touch_executor")
            return

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from core.service.cloud.exploration_engine import ExplorationEngine, ExplorationConfig

        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        cache_dir = os.path.join(project_root, "cache")
        os.makedirs(cache_dir, exist_ok=True)

        config = ExplorationConfig(
            device_serial="localhost:16512",
            verification_passes=self._verify_spin.value(),
            max_depth=self._depth_spin.value(),
            output_file=os.path.join(cache_dir, "game_map.md"),
            output_json=os.path.join(cache_dir, "page_tree.json"),
        )

        self._exploration_engine = ExplorationEngine(
            communicator=None,
            screen_capture=self.screen_capture,
            touch_executor=self.touch_executor,
            agent_executor=self.agent_executor,
            config=config,
        )

        self._exploration_engine.on("page_discovered", self._on_page_discovered)
        self._exploration_engine.on("state_changed", self._on_explore_state_changed)
        self._exploration_engine.on("error", self._on_explore_error)
        self._exploration_engine.on("save", self._on_explore_save)

        self._explore_start_btn.setEnabled(False)
        self._explore_stop_btn.setEnabled(True)
        self._explore_pause_btn.setEnabled(True)
        self._explore_pause_btn.setText("PAUSE")

        self._exploration_thread = IeaExploreThread(self._exploration_engine)
        self._exploration_thread.finished.connect(self._on_explore_finished)
        self._exploration_thread.start()

        self._log_explore("Exploration started...")

    def _stop_exploration(self):
        if self._exploration_engine:
            self._exploration_engine.stop()
        if self._exploration_thread and self._exploration_thread.isRunning():
            self._exploration_thread.quit()
            self._exploration_thread.wait(3000)

        self._explore_start_btn.setEnabled(True)
        self._explore_stop_btn.setEnabled(False)
        self._explore_pause_btn.setEnabled(False)
        self._log_explore("Exploration stopped.")

    def _on_explore_finished(self):
        self._explore_start_btn.setEnabled(True)
        self._explore_stop_btn.setEnabled(False)
        self._explore_pause_btn.setEnabled(False)
        self._log_explore("Exploration finished.")

    def _toggle_pause_exploration(self):
        if not self._exploration_engine:
            return
        if self._exploration_engine.running and self._explore_pause_btn.text() == "PAUSE":
            self._exploration_engine.pause()
            self._explore_pause_btn.setText("RESUME")
            self._explore_pause_btn.setStyleSheet(BTN_ACTIVE)
            self._log_explore("Exploration paused.")
        else:
            self._exploration_engine.resume()
            self._explore_pause_btn.setText("PAUSE")
            self._explore_pause_btn.setStyleSheet(BTN_DEFAULT)
            self._log_explore("Exploration resumed.")

    def _on_page_discovered(self, page=None):
        if page:
            tree = self._exploration_engine.page_tree if self._exploration_engine else None
            stats = tree.stats if tree else {"pages_discovered": 0, "elements_found": 0, "edges_created": 0}
            es = self._exploration_engine.stats if self._exploration_engine else {}
            self._explore_stats_label.setText(
                f"Pages: {stats['pages_discovered']} | Elements: {stats['elements_found']} | "
                f"Edges: {stats['edges_created']} | VLM: {es.get('vlm_calls', 0)} | Taps: {es.get('taps', 0)}"
            )
            self._log_explore(f"New page: {page.name} [{len(page.elements)} elements]")

    def _on_explore_state_changed(self, state=None):
        state_str = state.value if state else "unknown"
        self._log_explore(f"State: {state_str}")

    def _on_explore_error(self, message=""):
        self._log_explore(f"[ERROR] {message}", RED_STYLE)

    def _on_explore_save(self, md_file="", json_file=""):
        self._log_explore(f"Saved results: {md_file}, {json_file}", GREEN_STYLE)

    def _log_explore(self, text: str, style: str = VAL_STYLE):
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._explore_log.append(f"[{ts}] {text}")

