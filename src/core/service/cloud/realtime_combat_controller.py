"""
实时战斗控制器

大 VLM 判断战斗状态，小 VLM 执行实时控制。
负责 TPS 监控和 3C 动作：移动、技能、跳跃、闪避。
"""
import os
import sys
import time
import json
import base64
import threading
from typing import Optional, Dict, Any, List
from enum import Enum

if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.service.gui_client import GUIClient

from core.foundation.logger import get_logger, LogCategory
logger = get_logger()


class CombatState(Enum):
    IDLE = "idle"
    EXPLORING = "exploring"
    COMBAT_ACTIVE = "combat_active"
    COMBAT_TRANSITION = "combat_transition"
    ERROR = "error"


class VLMController:
    """
    Large/small VLM communication coordinator.
    Large VLM evaluates if combat is active; small VLM generates real-time control.
    """
    def __init__(self, vlm_client=None, touch_executor=None, screen_capture=None,
                 large_vlm_config: Dict[str, Any] = None,
                 small_vlm=None):
        self._vlm_client = vlm_client or GUIClient({"vlm_mode": "local"})
        self._touch = touch_executor
        self._screen = screen_capture
        self._large_config = large_vlm_config or {}
        self._small_vlm = small_vlm
        self._state = CombatState.IDLE
        self._last_large_context: Optional[Dict] = None
        self._last_small_report: Optional[str] = None
        self._state_history: List[Dict] = []

    def set_small_vlm(self, engine):
        self._small_vlm = engine

    def evaluate_combat_state(self, screenshot_b64: str) -> CombatState:
        """Large VLM evaluates whether current screen is combat/real-time action"""
        try:
            prompt = (
                "Analyze the current screen of Arknights Endfield. "
                "Determine if the player is in active combat/real-time action state. "
                "Return JSON: {\"is_combat\": bool, \"state\": \"idle/exploring/combat\", \"reason\": \"...\"}"
            )
            result = self._vlm_client.analyze_image(
                screenshot_b64,
                prompt,
                max_tokens=300,
                temperature=0,
            )
            if result.get("status") == "success":
                content = result.get("content", "")
                parsed = result.get("parsed")
                if parsed:
                    if parsed.get("is_combat"):
                        self._state = CombatState.COMBAT_ACTIVE
                        return CombatState.COMBAT_ACTIVE
                    state_str = parsed.get("state", "idle")
                    if state_str == "exploring":
                        self._state = CombatState.EXPLORING
                        return CombatState.EXPLORING
                elif any(kw in content.lower() for kw in ["combat", "战斗", "battle"]):
                    self._state = CombatState.COMBAT_ACTIVE
                    return CombatState.COMBAT_ACTIVE
            self._state = CombatState.IDLE
            return CombatState.IDLE
        except Exception as e:
            logger.error(LogCategory.INFERENCE, "Combat state evaluation failed", error=str(e))
            return CombatState.ERROR

    def get_combat_instruction(self, screenshot_b64: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Small VLM generates real-time control instruction"""
        if not self._small_vlm or not self._small_vlm.is_available():
            return {"status": "error", "error": "Realtime inference engine not ready"}
        prompt = self._build_realtime_prompt(context)
        
        # 修复 BUG-015: 检查 Small VLM 的实际类型并调用正确的方法
        # RealtimeInferenceEngine 有 process() 方法，而 InferenceManager 有 process_image()
        if hasattr(self._small_vlm, 'process'):
            # RealtimeInferenceEngine
            result = self._small_vlm.process(screenshot_b64, prompt)
        elif hasattr(self._small_vlm, 'process_image'):
            # InferenceManager - 需要转换参数格式
            task_context = {"prompt": prompt, "task_type": "combat_control"}
            result = self._small_vlm.process_image(screenshot_b64, task_context)
        else:
            return {"status": "error", "error": "Unknown VLM interface"}
            
        if result.get("status") == "success":
            text = result.get("text") or result.get("content", "")
            try:
                actions = json.loads(text)
            except json.JSONDecodeError:
                actions = self._fallback_parse(text)
            return {"status": "success", "actions": actions, "raw": text, "tps": result.get("tps", 0)}
        return result

    def _build_realtime_prompt(self, context: Dict[str, Any] = None) -> str:
        return (
            "You are controlling a character in Arknights Endfield combat. "
            "Based on the current screen, generate the next action. "
            "Output JSON: {\"action\": \"move_left/move_right/move_forward/move_backward/"
            "skill_1/skill_2/skill_3/jump/dodge/attack/wait\", \"params\": {\"duration_ms\": 300}}"
            + (f" Context: {json.dumps(context)}" if context else "")
        )

    def _fallback_parse(self, text: str) -> Dict:
        action = "wait"
        tl = text.lower()
        if any(kw in tl for kw in ["left", "左"]):
            action = "move_left"
        elif any(kw in tl for kw in ["right", "右"]):
            action = "move_right"
        elif any(kw in tl for kw in ["forward", "前"]):
            action = "move_forward"
        elif any(kw in tl for kw in ["backward", "后", "back"]):
            action = "move_backward"
        elif any(kw in tl for kw in ["jump", "跳", "跳跃"]):
            action = "jump"
        elif any(kw in tl for kw in ["dodge", "闪", "闪避"]):
            action = "dodge"
        elif any(kw in tl for kw in ["skill", "技能"]):
            action = "skill_1"
        elif any(kw in tl for kw in ["attack", "攻击"]):
            action = "attack"
        return {"action": action, "params": {"duration_ms": 300}}

    def prepare_context_for_small(self) -> Dict[str, Any]:
        return {
            "last_state": self._state.value,
            "last_action_results": self._state_history[-3:] if self._state_history else [],
            "objective": "defeat enemies" if self._state == CombatState.COMBAT_ACTIVE else "explore"
        }


class CombatController:
    """3C controls: movement, skill, jump, dodge"""
    _ACTIONS = {
        "move_left": {"type": "swipe", "params": {"x1": 500, "y1": 500, "x2": 100, "y2": 500, "duration": 200}},
        "move_right": {"type": "swipe", "params": {"x1": 100, "y1": 500, "x2": 500, "y2": 500, "duration": 200}},
        "move_forward": {"type": "swipe", "params": {"x1": 300, "y1": 500, "x2": 300, "y2": 300, "duration": 200}},
        "move_backward": {"type": "swipe", "params": {"x1": 300, "y1": 300, "x2": 300, "y2": 500, "duration": 200}},
        "jump": {"type": "tap", "params": {"x": 600, "y": 200, "duration": 50}},
        "dodge": {"type": "swipe", "params": {"x1": 500, "y1": 500, "x2": 500, "y2": 200, "duration": 100}},
        "attack": {"type": "tap", "params": {"x": 700, "y": 900, "duration": 50}},
        "skill_1": {"type": "tap", "params": {"x": 200, "y": 950, "duration": 50}},
        "skill_2": {"type": "tap", "params": {"x": 300, "y": 950, "duration": 50}},
        "skill_3": {"type": "tap", "params": {"x": 400, "y": 950, "duration": 50}},
        "wait": {"type": "wait", "params": {"duration": 0.5}},
    }

    def __init__(self, touch_executor, device_width=1920, device_height=1080):
        self._touch = touch_executor
        self._width = device_width
        self._height = device_height

    def execute_action(self, action_name: str, params: Dict = None) -> bool:
        if action_name not in self._ACTIONS:
            return False
        schema = self._ACTIONS[action_name]
        merged = {**schema["params"], **(params or {})}
        if action_name == "wait":
            time.sleep(merged.get("duration", 0.5))
            return True
        if schema["type"] == "tap":
            x = int(merged["x"] * self._width / 1920)
            y = int(merged["y"] * self._height / 1080)
            return self._touch.safe_press(x, y, merged.get("duration", 50))
        elif schema["type"] == "swipe":
            x1 = int(merged["x1"] * self._width / 1920)
            y1 = int(merged["y1"] * self._height / 1080)
            x2 = int(merged["x2"] * self._width / 1920)
            y2 = int(merged["y2"] * self._height / 1080)
            return self._touch.safe_swipe(x1, y1, x2, y2, merged.get("duration", 200))
        return False


class CombatLoop:
    """Small VLM → execute → screenshot → repeat, with periodic large VLM re-evaluation"""
    def __init__(self, vlm_controller: VLMController, combat_controller: CombatController, screen_capture):
        self._vlm = vlm_controller
        self._combat = combat_controller
        self._screen = screen_capture
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._recent_actions: List[Dict] = []
        self._large_eval_interval = 30
        self._step_counter = 0
        self._device_serial = ""

    def start(self, device_serial: str = ""):
        if self._running:
            return
        self._device_serial = device_serial
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(LogCategory.INFERENCE, "Combat loop started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        logger.info(LogCategory.INFERENCE, "Combat loop stopped")

    def _loop(self):
        while self._running:
            try:
                self._step_counter += 1
                screenshot = self._screen.capture_screen(self._device_serial) if self._device_serial else None
                if not screenshot:
                    time.sleep(0.5)
                    continue
                if isinstance(screenshot, tuple):
                    _, img_bytes = screenshot
                else:
                    img_bytes = screenshot
                b64 = base64.b64encode(img_bytes).decode("utf-8")

                if self._step_counter % self._large_eval_interval == 0:
                    state = self._vlm.evaluate_combat_state(b64)
                    if state != CombatState.COMBAT_ACTIVE:
                        logger.info(LogCategory.INFERENCE, f"Combat state changed: {state.value}")
                        time.sleep(2.0)
                        continue

                context = self._vlm.prepare_context_for_small()
                result = self._vlm.get_combat_instruction(b64, context)
                if result.get("status") == "success":
                    actions = result.get("actions", {})
                    if isinstance(actions, dict):
                        action_name = actions.get("action", "wait")
                        params = actions.get("params", {})
                        success = self._combat.execute_action(action_name, params)
                        self._recent_actions.append({
                            "action": action_name, "success": success, "time": time.time()
                        })
                        self._recent_actions = self._recent_actions[-20:]
                time.sleep(0.3)
            except Exception as e:
                logger.error(LogCategory.INFERENCE, "Combat loop exception", error=str(e))
                time.sleep(1.0)