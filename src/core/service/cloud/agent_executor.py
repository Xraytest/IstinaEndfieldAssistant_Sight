"""Agent execution engine - receives natural language instructions and executes via VLM feedback loop

通过 InferenceManager 进行推理（纯本地版）。
"""
import time
import base64
from typing import Optional, Dict, Any, List
from enum import Enum


class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING_FEEDBACK = "waiting_feedback"
    DONE = "done"
    ERROR = "error"


class AgentExecutor:
    """Agent executor - 纯本地版

    通过 InferenceManager 进行 VLM 推理，无云端依赖。
    """

    def __init__(self, screen_capture, touch_executor, config=None,
                 device_serial: str = "", inference_manager=None):
        self.screen_capture = screen_capture
        self.touch_executor = touch_executor
        self.config = config or {}
        self.device_serial = device_serial
        self.inference_manager = inference_manager
        self.state = AgentState.IDLE
        self.conversation_history: List[Dict[str, str]] = []
        self.model_tag: str = config.get('inference', {}).get('model_tag', 'exploration_deep') if config else 'exploration_deep'
        self.device_width = 1920
        self.device_height = 1080

    @property
    def local_inference_available(self) -> bool:
        """检查本地推理是否可用"""
        if self.inference_manager is not None:
            try:
                return self.inference_manager.is_local_available()
            except Exception:
                pass
        return False

    @property
    def effective_mode(self) -> str:
        return "local"

    def send_instruction(self, instruction: str) -> Dict[str, Any]:
        """发送自然语言指令并通过 VLM 反馈循环执行"""
        self.state = AgentState.THINKING

        if not self.screen_capture:
            return {"status": "error", "message": "Screen capture module not initialized"}

        if self.device_serial:
            screenshot_result = self.screen_capture.capture_screen(self.device_serial)
        else:
            screenshot_result = None
        if not screenshot_result:
            return {"status": "error", "message": "Screenshot capture failed"}

        if isinstance(screenshot_result, tuple):
            success, img_bytes = screenshot_result
            if not success:
                return {"status": "error", "message": "Screenshot capture failed"}
        else:
            img_bytes = screenshot_result

        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        if self.inference_manager is not None:
            return self._process_with_inference_manager(instruction, img_b64)

        return {"status": "error", "message": "No inference method available"}

    def _process_with_inference_manager(self, instruction: str, img_b64: str) -> Dict[str, Any]:
        """通过 InferenceManager 处理指令"""
        task_context = {
            "prompt": instruction,
            "task_type": "agent_instruction",
            "conversation_history": self.conversation_history[-10:],
        }

        result = self.inference_manager.process_image(
            image_data=img_b64,
            task_context=task_context,
        )

        if result.get("status") == "success":
            self.state = AgentState.EXECUTING
            parsed = result.get("parsed")
            if parsed and "action" in parsed:
                action_result = self._execute_action(parsed["action"])
                result["action_result"] = action_result
            self.conversation_history.append({"role": "user", "content": instruction})
            self.conversation_history.append({"role": "assistant", "content": result.get("content", "")})
        else:
            self.state = AgentState.ERROR

        return result

    def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """执行 VLM 返回的动作"""
        action_type = action.get("type", "")
        params = action.get("params", {})

        try:
            if action_type == "tap":
                x = int(params["x"] * self.device_width) if abs(params.get("x", 0)) <= 1.0 else int(params["x"])
                y = int(params["y"] * self.device_height) if abs(params.get("y", 0)) <= 1.0 else int(params["y"])
                self.touch_executor.safe_press(x, y)
            elif action_type == "swipe":
                x1 = int(params["x1"] * self.device_width) if abs(params.get("x1", 0)) <= 1.0 else int(params["x1"])
                y1 = int(params["y1"] * self.device_height) if abs(params.get("y1", 0)) <= 1.0 else int(params["y1"])
                x2 = int(params["x2"] * self.device_width) if abs(params.get("x2", 0)) <= 1.0 else int(params["x2"])
                y2 = int(params["y2"] * self.device_height) if abs(params.get("y2", 0)) <= 1.0 else int(params["y2"])
                duration = params.get("duration", 300)
                self.touch_executor.safe_swipe(x1, y1, x2, y2, duration=duration)
            elif action_type == "back":
                self.touch_executor.safe_back()
            elif action_type == "wait":
                import time as _time
                _time.sleep(params.get("duration", 1))
            else:
                return {"status": "error", "message": f"Unknown action type: {action_type}"}

            return {"status": "success", "action": action_type}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _normalize_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """将 VLM 返回的动作归一化为标准格式"""
        action_type = action.get("type", action.get("action", ""))

        if action_type == "tap" or action_type == "click":
            x = action.get("x", 0)
            y = action.get("y", 0)
            if abs(x) > 1.0 or abs(y) > 1.0:
                x = x / self.device_width if self.device_width else x / 1920
                y = y / self.device_height if self.device_height else y / 1080
            return {"type": "tap", "params": {"x": x, "y": y}}

        elif action_type == "swipe":
            x1 = action.get("x1", 0)
            y1 = action.get("y1", 0)
            x2 = action.get("x2", 0)
            y2 = action.get("y2", 0)
            duration = action.get("duration", 300)
            if abs(x1) > 1.0 or abs(y1) > 1.0:
                x1 = x1 / self.device_width if self.device_width else x1 / 1920
                y1 = y1 / self.device_height if self.device_height else y1 / 1080
            if abs(x2) > 1.0 or abs(y2) > 1.0:
                x2 = x2 / self.device_width if self.device_width else x2 / 1920
                y2 = y2 / self.device_height if self.device_height else y2 / 1080
            return {"type": "swipe", "params": {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration": duration}}

        elif action_type == "back":
            return {"type": "back", "params": {}}

        elif action_type == "wait":
            return {"type": "wait", "params": {"duration": action.get("duration", 1)}}

        return {"type": action_type, "params": action}

    def reset(self) -> None:
        """重置 Agent 状态"""
        self.state = AgentState.IDLE
        self.conversation_history.clear()
