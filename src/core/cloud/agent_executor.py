"""Agent execution engine - receives natural language instructions and executes via VLM feedback loop"""
import time
import base64
from typing import Optional, Dict, Any, List
from enum import Enum

from core.vlm_client import VLMClient


class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING_FEEDBACK = "waiting_feedback"
    DONE = "done"
    ERROR = "error"


class AgentExecutor:
    """Agent executor that processes natural language instructions through VLM feedback loop

    Supports local-first routing: when a local inference engine is available,
    uses it instead of the cloud server for faster, offline-capable execution.
    """

    def __init__(self, communicator, screen_capture, touch_executor, config=None, device_serial: str = "", vlm_client=None):
        self.communicator = communicator
        self.screen_capture = screen_capture
        self.touch_executor = touch_executor
        self.config = config or {}
        self.device_serial = device_serial
        self.vlm_client = vlm_client or VLMClient({"vlm_mode": "local"})
        self.state = AgentState.IDLE
        self.conversation_history: List[Dict[str, str]] = []
        self.session_id: Optional[str] = None
        self.model_tag: str = config.get('inference', {}).get('model_tag', 'exploration_deep') if config else 'exploration_deep'
        self.device_width = 1920
        self.device_height = 1080

    @property
    def local_inference_available(self) -> bool:
        """检查本地推理是否可用"""
        try:
            return self.vlm_client.is_local_available()
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"检查本地推理可用性失败：{e}")
            return False

    @property
    def effective_mode(self) -> str:
        """获取当前有效推理模式"""
        if self.local_inference_available:
            return "local"
        return "cloud"

    def send_instruction(self, instruction: str) -> Dict[str, Any]:
        """Send natural language instruction and execute via VLM feedback loop

        Local-first: uses VLMClient (auto-routes local/server).
        Communicator is optional — only needed for cloud-only mode.
        """
        self.state = AgentState.THINKING

        if not self.screen_capture:
            return {"status": "error", "message": "Screen capture module not initialized"}

        # Capture screenshot
        if self.device_serial:
            screenshot_result = self.screen_capture.capture_screen(self.device_serial)
        else:
            screenshot_result = None
        if not screenshot_result:
            return {"status": "error", "message": "Screenshot capture failed"}

        # Handle screenshot tuple or direct bytes
        if isinstance(screenshot_result, tuple):
            success, img_bytes = screenshot_result
            if not success:
                return {"status": "error", "message": "Screenshot capture failed"}
        else:
            img_bytes = screenshot_result

        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        # Get device info (communicator 可选)
        device_info = {}
        if self.communicator and hasattr(self.communicator, 'get_device_info'):
            try:
                device_info = self.communicator.get_device_info() or {}
            except Exception:
                device_info = {}
        self.device_width = device_info.get('width', self.device_width)
        self.device_height = device_info.get('height', self.device_height)

        # === 本地推理优先路径 ===
        if self.local_inference_available:
            try:
                return self._process_with_local_inference(instruction, img_b64)
            except Exception as e:
                # 本地失败时自动降级到云端
                import logging
                logging.getLogger(__name__).warning(
                    "Local inference failed, falling back to cloud: %s", str(e))

        # === 云端推理路径（默认/降级） ===
        return self._process_with_cloud_inference(instruction, img_b64)

    def _process_with_local_inference(self, instruction: str, img_b64: str) -> Dict[str, Any]:
        """使用本地推理处理指令"""
        # 构建任务上下文
        task_context = {
            "prompt": (
                f"You are PRTS agent for Arknights Endfield.\n"
                f"Instruction: {instruction}\n\n"
                f"Analyze the current screen and output JSON with:\n"
                f"- actions: list of {{action, x, y}} or {{action, x1, y1, x2, y2, duration}}\n"
                f"  action types: tap, swipe, wait\n"
                f"- task_completed: bool\n"
                f"- reasoning: str\n"
                f"Output ONLY valid JSON, no other text."
            ),
            "task_id": f"agent_{int(time.time())}",
            "temperature": 0.3,
            "max_tokens": 2048
        }

        # 通过 VLMClient 处理
        result = self.vlm_client.analyze_image(img_b64, task_context.get("prompt", instruction))

        if result.get("status") != "success":
            return {"status": "error", "message": result.get("error", "Local inference failed")}

        # 标准化响应格式
        reply_text = result.get("content", "")
        actions = []
        task_completed = False

        # 从 VLMClient 响应中提取
        parsed = result.get("parsed")
        if isinstance(parsed, dict):
            raw_actions = parsed.get("actions") or parsed.get("touch_actions") or []
            for act in raw_actions:
                normalized = self._normalize_action(act)
                if normalized:
                    actions.append(normalized)
            task_completed = parsed.get("task_completed", False)
            reply_text = parsed.get("reasoning") or parsed.get("text") or reply_text

        # 更新对话历史
        self.conversation_history.append({"role": "user", "content": instruction})
        self.conversation_history.append({"role": "assistant", "content": reply_text})

        # 执行动作
        self.state = AgentState.EXECUTING
        execution_results = []
        for action in actions:
            try:
                result_exec = self._execute_action(action)
            except Exception as e:
                result_exec = {"action": action.get("type", "unknown"), "success": False, "error": str(e)}
            execution_results.append(result_exec)
            if not result_exec.get("success"):
                self.state = AgentState.ERROR
                break

        self.state = AgentState.DONE if not execution_results or all(
            r.get("success", False) for r in execution_results
        ) else AgentState.ERROR

        return {
            "status": "success",
            "reply": reply_text,
            "execution_results": execution_results,
            "actions": actions,
            "mode": "local"
        }

    def _process_with_cloud_inference(self, instruction: str, img_b64: str) -> Dict[str, Any]:
        """使用 VLMClient 处理指令（云端/本地自动路由）"""
        try:
            system_prompt = (
                f"You are PRTS agent for Arknights Endfield.\n"
                f"Device resolution: {self.device_width}x{self.device_height}\n"
                f"Output JSON with: actions (list of {{action, x, y}} or {{action, x1, y1, x2, y2, duration}}), "
                f"task_completed (bool), reasoning (str).\n"
                f"Action types: tap, swipe, wait.\n"
                f"Output ONLY valid JSON, no other text."
            )
            result = self.vlm_client.analyze_image(
                img_b64,
                instruction,
                system_prompt=system_prompt,
                max_tokens=2048,
                temperature=0.3,
            )
        except Exception as e:
            self.state = AgentState.ERROR
            return {"status": "error", "message": f"VLM analysis failed: {str(e)}"}

        if result.get("status") != "success":
            self.state = AgentState.ERROR
            return {"status": "error", "message": result.get("error", "VLM analysis failed")}

        reply_text = result.get("content", "")
        parsed = result.get("parsed")

        self.conversation_history.append({"role": "user", "content": instruction})
        self.conversation_history.append({"role": "assistant", "content": reply_text})

        actions = []
        if isinstance(parsed, dict):
            raw_actions = parsed.get("actions") or []
            for act in raw_actions:
                normalized = self._normalize_action(act)
                if normalized:
                    actions.append(normalized)

        if not actions:
            self.state = AgentState.DONE
            return {"status": "success", "reply": reply_text}

        # Execute actions
        self.state = AgentState.EXECUTING

        if not self.touch_executor:
            self.state = AgentState.ERROR
            return {"status": "error", "message": "Touch executor not initialized"}

        execution_results = []
        for action in actions:
            try:
                result_exec = self._execute_action(action)
            except Exception as e:
                result_exec = {"action": action.get("type", "unknown"), "success": False, "error": str(e)}
            execution_results.append(result_exec)

            if not result_exec.get("success"):
                self.state = AgentState.ERROR
                break

        self.state = AgentState.DONE
        return {
            "status": "success",
            "reply": reply_text,
            "execution_results": execution_results,
            "actions": actions
        }

    def _normalize_action(self, action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """将本地引擎的动作格式标准化为云端兼容格式

        本地格式: {action: "tap", x: 100, y: 200}
        云端格式: {type: "tap", params: {x: 0.5, y: 0.5}}
        """
        if not isinstance(action, dict):
            return None

        # 检查是否已经是云端格式
        if "type" in action and "params" in action:
            return action

        # 从本地格式转换
        action_type = action.get("action", "")
        if not action_type:
            return None

        if action_type == "tap" or action_type == "click":
            x = action.get("x", 0)
            y = action.get("y", 0)
            # 归一化坐标
            if x > 1 or y > 1:
                x = x / self.device_width if self.device_width else x / 1920
                y = y / self.device_height if self.device_height else y / 1080
            return {"type": "tap", "params": {"x": x, "y": y}}

        elif action_type == "swipe":
            x1 = action.get("x1", 0)
            y1 = action.get("y1", 0)
            x2 = action.get("x2", 0)
            y2 = action.get("y2", 0)
            duration = action.get("duration", 300)
            # 归一化坐标
            if x1 > 1 or y1 > 1:
                x1 = x1 / self.device_width if self.device_width else x1 / 1920
                y1 = y1 / self.device_height if self.device_height else y1 / 1080
            if x2 > 1 or y2 > 1:
                x2 = x2 / self.device_width if self.device_width else x2 / 1920
                y2 = y2 / self.device_height if self.device_height else y2 / 1080
            return {"type": "swipe", "params": {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration": duration}}

        elif action_type == "wait":
            duration = action.get("duration", 1.0)
            return {"type": "wait", "params": {"duration": duration}}

        elif action_type == "screenshot_check":
            return {"type": "screenshot_check", "params": {}}

        return None

    def reset_conversation(self):
        """Reset agent conversation context"""
        self.conversation_history = []
        self.session_id = None
        self.state = AgentState.IDLE

    def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single action"""
        if not self.touch_executor:
            return {"action": "error", "success": False, "error": "Touch executor not initialized"}
        
        action_type = action.get("type", "")
        params = action.get("params", {})
        
        try:
            if action_type == "tap":
                x = int(params["x"] * self.device_width / 1920) if params.get("x", 0) <= 1 else int(params["x"])
                y = int(params["y"] * self.device_height / 1080) if params.get("y", 0) <= 1 else int(params["y"])
                self.touch_executor.safe_press(x, y)
            elif action_type == "swipe":
                x1 = int(params["x1"]) if params.get("x1", 0) > 1 else int(params["x1"] * self.device_width / 1920)
                y1 = int(params["y1"]) if params.get("y1", 0) > 1 else int(params["y1"] * self.device_height / 1080)
                x2 = int(params["x2"]) if params.get("x2", 0) > 1 else int(params["x2"] * self.device_width / 1920)
                y2 = int(params["y2"]) if params.get("y2", 0) > 1 else int(params["y2"] * self.device_height / 1080)
                duration = params.get("duration", 300)
                self.touch_executor.safe_swipe(x1, y1, x2, y2, duration=duration)
            elif action_type == "wait":
                time.sleep(params.get("duration", 1.0))
            elif action_type == "screenshot_check":
                pass
            else:
                return {"action": action_type, "success": False, "error": f"Unknown action: {action_type}"}
                
            return {"action": action_type, "success": True}
        except Exception as e:
            return {"action": action_type, "success": False, "error": str(e)}
