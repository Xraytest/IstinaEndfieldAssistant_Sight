"""PRTS Full Intelligence page - full game takeover with particle effects
   Design references ak.hypergryph.com particle composition effect"""
import os
import json
import random
import math
from typing import Optional, Dict, Any, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QScrollArea, QTextEdit, QMessageBox,
    QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QFont, QPen

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


class ParticleWidget(QWidget):
    """Animated particle composition effect referencing ak.hypergryph.com"""
    
    class Particle:
        def __init__(self, w, h):
            self.x = random.uniform(0, w)
            self.y = random.uniform(0, h)
            self.vx = random.uniform(-0.3, 0.3)
            self.vy = random.uniform(-0.3, 0.3)
            self.size = random.uniform(1.5, 4.0)
            self.alpha = random.uniform(0.2, 0.6)
            self.color = QColor(
                random.randint(18, 100),
                random.randint(180, 220),
                random.randint(230, 255),
                int(self.alpha * 255)
            )
            self.w = w
            self.h = h
        
        def update(self):
            self.x += self.vx
            self.y += self.vy
            self.alpha += random.uniform(-0.02, 0.02)
            self.alpha = max(0.1, min(0.8, self.alpha))
            self.color.setAlpha(int(self.alpha * 255))
            if self.x < 0 or self.x > self.w:
                self.vx *= -1
            if self.y < 0 or self.y > self.h:
                self.vy *= -1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._particles: List[ParticleWidget.Particle] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_particles)
        self._timer.start(33)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def stop_animation(self):
        if self._timer.isActive():
            self._timer.stop()

    def start_animation(self):
        if not self._timer.isActive():
            self._timer.start(33)
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        if not self._particles:
            self._particles = [self.Particle(w, h) for _ in range(60)]
        else:
            for p in self._particles:
                p.w = w
                p.h = h
    
    def _update_particles(self):
        for p in self._particles:
            p.update()
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for p in self._particles:
            painter.setBrush(QBrush(p.color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(p.x - p.size/2, p.y - p.size/2, p.size, p.size))
        # draw connection lines for nearby particles
        for i, p1 in enumerate(self._particles):
            for j, p2 in enumerate(self._particles):
                if i >= j:
                    continue
                dx = p1.x - p2.x
                dy = p1.y - p2.y
                dist = math.sqrt(dx*dx + dy*dy)
                if dist < 120:
                    alpha = int((1 - dist/120) * 60)
                    pen = QPen(QColor(24, 209, 255, alpha))
                    pen.setWidthF(0.5)
                    painter.setPen(pen)
                    painter.drawLine(int(p1.x), int(p1.y), int(p2.x), int(p2.y))
        painter.end()


class PrtsFullIntelligencePage(QWidget):
    """PRTS Full Intelligence - full game takeover, auto-find completable content"""

    def __init__(self, communicator=None, agent_executor=None, parent=None,
                 screen_capture=None, touch_executor=None, config=None, inference_manager=None):
        super().__init__(parent)
        self.communicator = communicator
        self.agent_executor = agent_executor
        self.screen_capture = screen_capture
        self.touch_executor = touch_executor
        self.inference_manager = inference_manager  # 本地推理管理器（可选）
        self._config = config or {}
        self._selected_model_tag = self._load_model_tag()
        self._bypass_special = False
        self._running = False
        self._setup_ui()
        QTimer.singleShot(100, self._update_inference_mode_indicator)

    def _get_cache_dir(self) -> str:
        current = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current))))
        cache = os.path.join(root, "cache")
        os.makedirs(cache, exist_ok=True)
        return cache

    def _load_model_tag(self) -> str:
        path = os.path.join(self._get_cache_dir(), "model_tag.json")
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            return data.get("prts_full_intelligence", "exploration_deep")
        except Exception:
            return "exploration_deep"

    def set_model_tag(self, tag: str):
        self._selected_model_tag = tag

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Particle overlay
        self._particle_widget = ParticleWidget(self)
        self._particle_widget.setGeometry(0, 0, self.width(), self.height())
        self._particle_widget.lower()
        self._particle_widget.setStyleSheet("background: transparent;")

        header = QHBoxLayout()
        title = QLabel("// PRTS FULL INTELLIGENCE")
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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)

        # Main Control Card
        main_card = self._make_card("PRTS TAKEOVER")
        main_layout = QVBoxLayout()
        main_card.layout().addLayout(main_layout)

        self._bypass_check = QCheckBox("Bypass Special Commissions (不做特委任务)")
        self._bypass_check.setStyleSheet("""
            QCheckBox { color: #e8e8ee; font-size: 12px; font-family: Consolas; spacing: 8px; }
            QCheckBox::indicator {
                width: 16px; height: 16px; border-radius: 2px;
                border: 1px solid rgba(24, 209, 255, 0.30);
                background-color: transparent;
            }
            QCheckBox::indicator:checked { background-color: #18d1ff; border-color: #18d1ff; }
            QCheckBox::indicator:hover { border-color: #18d1ff; }
        """)
        self._bypass_check.toggled.connect(lambda c: setattr(self, '_bypass_special', c))
        main_layout.addWidget(self._bypass_check)

        # Scope indicators
        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("SCOPE:"))
        scope_row.itemAt(0).widget().setStyleSheet(INFO_STYLE)
        self._scope_label = QLabel("Main Story / Side Missions / World Quests / Events")
        self._scope_label.setStyleSheet(VAL_STYLE)
        self._scope_label.setWordWrap(True)
        scope_row.addWidget(self._scope_label, 1)
        main_layout.addLayout(scope_row)

        ctrl_row = QHBoxLayout()
        self._start_btn = QPushButton("START PRTS TAKEOVER")
        self._start_btn.setFixedSize(180, 36)
        self._start_btn.setStyleSheet(BTN_ACTIVE)
        self._start_btn.clicked.connect(self._start_takeover)
        ctrl_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("STOP")
        self._stop_btn.setFixedSize(80, 36)
        self._stop_btn.setStyleSheet(BTN_STOP)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_takeover)
        ctrl_row.addWidget(self._stop_btn)
        ctrl_row.addStretch()
        main_layout.addLayout(ctrl_row)

        # Status display
        self._status_label = QLabel("PRTS Standby")
        self._status_label.setStyleSheet(BLUE_STYLE)
        main_layout.addWidget(self._status_label)

        stats_row = QHBoxLayout()
        stats_row.addWidget(QLabel("Completed:"))
        stats_row.itemAt(0).widget().setStyleSheet(INFO_STYLE)
        self._completed_label = QLabel("0")
        self._completed_label.setStyleSheet(GREEN_STYLE)
        stats_row.addWidget(self._completed_label)
        stats_row.addSpacing(16)
        stats_row.addWidget(QLabel("Failed:"))
        stats_row.itemAt(stats_row.count() - 1).widget().setStyleSheet(INFO_STYLE)
        self._failed_label = QLabel("0")
        self._failed_label.setStyleSheet(RED_STYLE)
        stats_row.addWidget(self._failed_label)
        stats_row.addSpacing(16)
        stats_row.addWidget(QLabel("VLM Calls:"))
        stats_row.itemAt(stats_row.count() - 1).widget().setStyleSheet(INFO_STYLE)
        self._vlm_calls_label = QLabel("0")
        self._vlm_calls_label.setStyleSheet(VAL_STYLE)
        stats_row.addWidget(self._vlm_calls_label)
        stats_row.addStretch()
        main_layout.addLayout(stats_row)

        scroll_layout.addWidget(main_card)

        # Execution Log
        log_card = self._make_card("PRTS LOG")
        log_layout = QVBoxLayout()
        log_card.layout().addLayout(log_layout)
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(250)
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
        log_layout.addWidget(self._log_text)
        scroll_layout.addWidget(log_card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._particle_widget.setGeometry(0, 0, self.width(), self.height())

    def hideEvent(self, event):
        super().hideEvent(event)
        self._particle_widget.stop_animation()

    def showEvent(self, event):
        super().showEvent(event)
        self._particle_widget.start_animation()

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

    def _start_takeover(self):
        if not self.agent_executor or not self.communicator:
            QMessageBox.warning(self, "Not Ready", "Agent executor and communicator required.")
            return
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._running = True
        self._status_label.setText("PRTS ACTIVE - Scanning for tasks...")
        self._log("PRTS takeover started.")
        from PyQt6.QtCore import QThread

        class TakeoverThread(QThread):
            finished = pyqtSignal()
            def __init__(self, page):
                super().__init__()
                self.page = page
            def run(self):
                try:
                    self.page._takeover_loop()
                except Exception as e:
                    self.page._log(f"[ERROR] {e}")
                self.finished.emit()

        self._takeover_thread = TakeoverThread(self)
        self._takeover_thread.finished.connect(self._on_takeover_finished)
        self._takeover_thread.start()

    def _stop_takeover(self):
        self._running = False
        self._stop_btn.setEnabled(False)
        self._log("PRTS takeover stopping...")

    def _on_takeover_finished(self):
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status_label.setText("PRTS Standby")

    def _takeover_loop(self):
        completed = 0
        failed = 0
        vlm_calls = 0

        # 更新推理模式指示
        self._update_inference_mode_indicator()

        from core.cloud.realtime_combat_controller import VLMController, CombatState
        vlm_ctrl = VLMController(
            self.communicator, self.touch_executor, self.screen_capture,
            large_vlm_config={"model_tag": self._selected_model_tag, "session_id": ""}
        )
        while self._running:
            screenshot = self.screen_capture.capture_screen(
                getattr(self.agent_executor, 'device_serial', '')
            )
            if not screenshot:
                self._sleep(1.0)
                continue
            if isinstance(screenshot, tuple):
                _, img_bytes = screenshot
            else:
                img_bytes = screenshot
            b64 = __import__('base64').b64encode(img_bytes).decode("utf-8")
            vlm_calls += 1
            self._vlm_calls_label.setText(str(vlm_calls))

            # === 本地推理优先路径 ===
            if self.inference_manager and self.inference_manager.is_local_available():
                try:
                    self._takeover_loop_local(b64)
                    continue
                except Exception as e:
                    self._log(f"[LOCAL FALLBACK] {e}")

            # === 云端推理路径（默认/降级） ===
            try:
                response = self.communicator.send_request("agent_chat", {
                    "instruction": (
                        "You are PRTS full intelligence system for Arknights Endfield. "
                        "Analyze the current screen and determine what task can be completed. "
                        "Auto-navigate to find completable content: main story, side missions, world quests, events. "
                        + ("Bypass special commission tasks." if self._bypass_special else "")
                        + " Output JSON: {\\\"action\\\": \\\"tap/swipe/wait\\\", "
                        "\\\"params\\\": {\\\"x\\\": 0.5, \\\"y\\\": 0.5}, "
                        "\\\"task_type\\\": \\\"main/side/world/event/unknown\\\", "
                        "\\\"task_name\\\": \\\"...\\\", \\\"completed\\\": bool}"
                    ),
                    "screenshot": b64,
                    "model_tag": self._selected_model_tag,
                    "session_id": getattr(self.agent_executor, 'session_id', '') or ''
                })
                if response and response.get("status") == "success":
                    reply = response.get("reply", "")
                    try:
                        import json as _json
                        parsed = _json.loads(reply)
                        if parsed.get("completed"):
                            completed += 1
                            self._completed_label.setText(str(completed))
                            self._log(f"Completed: {parsed.get('task_name', 'Unknown')}")
                            self._update_status(f"Task done: {parsed.get('task_name', '')}")
                        actions = response.get("actions", [])
                        if actions:
                            for act in actions:
                                self.agent_executor._execute_action(act)
                    except json.JSONDecodeError:
                        actions = response.get("actions", [])
                        if actions:
                            for act in actions:
                                self.agent_executor._execute_action(act)
                else:
                    failed += 1
                    self._failed_label.setText(str(failed))
            except Exception as e:
                failed += 1
                self._failed_label.setText(str(failed))
                self._log(f"[ERROR] {e}")
                self._sleep(2.0)
            self._sleep(1.0)
        self._log("PRTS takeover ended.")

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

    def _takeover_loop_local(self, b64: str):
        """使用本地推理的接管循环（单步）"""
        import json as _json
        prompt = (
            "You are PRTS full intelligence system for Arknights Endfield. "
            "Analyze the current screen and determine what task can be completed. "
            "Auto-navigate to find completable content: main story, side missions, world quests, events. "
            + ("Bypass special commission tasks." if self._bypass_special else "")
            + " Output ONLY valid JSON: "
            '{"action": "tap/swipe/wait", "x": 0.5, "y": 0.5, '
            '"task_type": "main/side/world/event/unknown", '
            '"task_name": "...", "completed": bool}'
        )
        task_context = {
            "prompt": prompt,
            "task_id": f"prts_takeover_{int(__import__('time').time())}",
            "temperature": 0.3,
            "max_tokens": 1024
        }
        result = self.inference_manager.process_image(b64, task_context)
        if result.get("status") != "success":
            self._log(f"[LOCAL ERROR] {result.get('error', 'Unknown')}")
            return

        result_data = result.get("result", result)
        if isinstance(result_data, dict):
            # 解析动作
            raw_actions = result_data.get("actions") or result_data.get("touch_actions") or []
            task_completed = result_data.get("task_completed", False)
            task_name = result_data.get("task_name", "Unknown")
            reasoning = result_data.get("reasoning", "")

            if task_completed:
                completed = int(self._completed_label.text()) + 1
                self._completed_label.setText(str(completed))
                self._log(f"Completed: {task_name}")
                self._update_status(f"Task done: {task_name}")

            # 执行动作
            for act in raw_actions:
                normalized = self.agent_executor._normalize_action(act) if hasattr(self.agent_executor, '_normalize_action') else act
                if normalized:
                    try:
                        self.agent_executor._execute_action(normalized)
                    except Exception as e:
                        self._log(f"[ACTION ERROR] {e}")

    def _sleep(self, secs):
        import time
        for _ in range(int(secs * 10)):
            if not self._running:
                break
            time.sleep(0.1)

    def _update_status(self, text: str):
        self._status_label.setText(text)

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

    def get_model_tag(self) -> str:
        return self._selected_model_tag