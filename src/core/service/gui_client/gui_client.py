"""
GUI 客户端中间体 — 所有 LLM/VLM 请求的唯一入口（纯本地版）

职责：
1. 提供统一的图像分析、文本对话、动作决策、验证接口
2. 固定路由到本地 llama-server
3. 统一管理 JSON 响应解析、错误处理
4. 纯 Python 标准库，不依赖 PyQt，可独立测试

使用示例：
    client = GUIClient({"vlm_mode": "local"})
    result = client.analyze_image(b64, "分析画面")
"""

import json
import time
import base64
import re
from typing import Dict, Any, Optional, List

from core.foundation.logger import get_logger, LogCategory
logger = get_logger()


DEFAULT_CONFIG = {
    "vlm_mode": "local",
    "llama_url": "http://127.0.0.1:8080",
    "vlm_timeout": 60,
    "max_tokens": 4096,
    "temperature": 0.1,
}


class GUIClient:
    """
    统一的 GUI 客户端中间体（纯本地版）

    所有 LLM/VLM 请求汇聚到此模块，固定使用本地 llama-server。
    不依赖 PyQt，纯 Python 标准库。
    """

    def __init__(
        self,
        config: Dict[str, Any],
        inference_manager: Any = None,
    ):
        """
        初始化 GUI 客户端

        Args:
            config: 配置字典
            inference_manager: InferenceManager 实例（可选，提供时优先使用）
        """
        self._config = {**DEFAULT_CONFIG, **config}
        self._inference_manager = inference_manager
        self._llama_url = self._config["llama_url"].rstrip("/")
        self._timeout = self._config["vlm_timeout"]

        logger.info(LogCategory.MAIN, "GUIClient 初始化",
                   mode="local",
                   llama_url=self._llama_url,
                   timeout=self._timeout,
                   has_inference_manager=inference_manager is not None)

    # ═══════════════════════════════════════════════════════════
    # 公共接口
    # ═══════════════════════════════════════════════════════════

    def analyze_image(
        self,
        image_base64: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        统一图像分析接口

        优先通过 InferenceManager 路由，否则直接调用本地 llama-server。

        Args:
            image_base64: Base64 编码的图像数据
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            **kwargs: 额外参数（max_tokens, temperature 等）

        Returns:
            {
                "status": "success" | "error",
                "content": str,
                "parsed": dict | None,
                "error": str | None,
                "mode_used": "local",
                "inference_time_ms": float,
            }
        """
        start = time.time()

        if self._inference_manager is not None:
            task_context = {
                "prompt": prompt,
                "system_prompt": system_prompt,
                **kwargs,
            }
            result = self._inference_manager.process_image(
                image_data=image_base64,
                task_context=task_context,
            )
            result["inference_time_ms"] = (time.time() - start) * 1000
            return result

        result = self._call_local(image_base64, prompt, system_prompt, **kwargs)
        result["mode_used"] = "local"
        result["inference_time_ms"] = (time.time() - start) * 1000
        return result

    def chat_text(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        纯文本 LLM 调用

        Args:
            messages: 消息列表 [{"role": "user"|"assistant"|"system", "content": str}]
            **kwargs: 额外参数

        Returns:
            {"status": "success"|"error", "content": str, ...}
        """
        start = time.time()

        if self._inference_manager is not None:
            task_context = {
                "prompt": messages[-1]["content"] if messages else "",
                "messages": messages,
                **kwargs,
            }
            result = self._inference_manager.process_image(
                image_data=b"",
                task_context=task_context,
            )
            result["inference_time_ms"] = (time.time() - start) * 1000
            return result

        result = self._call_local_text(messages, **kwargs)
        result["mode_used"] = "local"
        result["inference_time_ms"] = (time.time() - start) * 1000
        return result

    def decide_action(
        self,
        image: Any,
        page_result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        VLM 动作决策（兼容 VlmActionDecider 接口）
        """
        if context is None:
            context = {}

        prompt = self._build_decision_prompt(page_result, context)

        try:
            import cv2
            _, buf = cv2.imencode(".png", image)
            img_b64 = base64.b64encode(buf).decode()

            result = self.analyze_image(img_b64, prompt,
                                        max_tokens=300, temperature=0)

            if result.get("status") == "success" and result.get("parsed"):
                return result["parsed"]

            return self._fallback_parse(result.get("content", ""), page_result)

        except Exception as e:
            logger.exception(LogCategory.INFERENCE, "VLM 决策失败", error=str(e))
            return {
                "page_type": page_result.get("page_type", "unknown"),
                "suggested_action": "back",
                "reason": f"VLM 不可用: {e}",
                "confidence": 0.0,
            }

    def verify(
        self,
        image_base64: str,
        prompt: str,
        expected: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        VLM 验证（兼容 VLMVerifier 接口）
        """
        result = self.analyze_image(image_base64, prompt,
                                    max_tokens=2048, temperature=0.1)

        content = result.get("content", "")
        parsed = result.get("parsed")

        if parsed:
            verified = parsed.get("verified", False) or parsed.get("matches_expected", False)
            return {
                "verified": verified,
                "confidence": parsed.get("confidence", 0.5) or parsed.get("vlm_confidence", 0.5),
                "extracted_data": parsed,
                "raw_response": content,
                "model_used": result.get("mode_used"),
                "error": result.get("error"),
            }

        has_expected = expected and expected.lower() in content.lower() if expected else False
        return {
            "verified": has_expected,
            "confidence": 0.3 if has_expected else 0.0,
            "extracted_data": None,
            "raw_response": content,
            "model_used": result.get("mode_used"),
            "error": result.get("error"),
        }

    # ═══════════════════════════════════════════════════════════
    # 本地推理（llama-server HTTP）
    # ═══════════════════════════════════════════════════════════

    def _call_local(
        self,
        image_base64: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """调用本地 llama-server VLM API"""
        try:
            import urllib.request

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            user_content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                },
            ]
            messages.append({"role": "user", "content": user_content})

            payload = {
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", self._config["max_tokens"]),
                "temperature": kwargs.get("temperature", self._config["temperature"]),
                "chat_template_kwargs": {"enable_thinking": False},
            }

            req = urllib.request.Request(
                f"{self._llama_url}/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            resp = json.loads(urllib.request.urlopen(req, timeout=self._timeout).read())

            content = resp["choices"][0]["message"].get("content", "").strip()
            if not content:
                content = resp["choices"][0]["message"].get("reasoning_content", "").strip()

            parsed = self._parse_json(content)

            logger.info(LogCategory.INFERENCE, "本地推理成功",
                       content_length=len(content),
                       has_parsed=parsed is not None)

            return {
                "status": "success",
                "content": content,
                "parsed": parsed,
                "error": None,
            }

        except Exception as e:
            logger.exception(LogCategory.INFERENCE, "本地推理失败", error=str(e))
            return {
                "status": "error",
                "content": "",
                "parsed": None,
                "error": str(e),
            }

    def _call_local_text(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> Dict[str, Any]:
        """调用本地 llama-server 纯文本 API"""
        try:
            import urllib.request

            payload = {
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", self._config["max_tokens"]),
                "temperature": kwargs.get("temperature", self._config["temperature"]),
            }

            req = urllib.request.Request(
                f"{self._llama_url}/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            resp = json.loads(urllib.request.urlopen(req, timeout=self._timeout).read())

            content = resp["choices"][0]["message"].get("content", "").strip()

            return {
                "status": "success",
                "content": content,
                "parsed": self._parse_json(content),
                "error": None,
            }

        except Exception as e:
            return {
                "status": "error",
                "content": "",
                "parsed": None,
                "error": str(e),
            }

    # ═══════════════════════════════════════════════════════════
    # 统一 JSON 解析
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _parse_json(text: str) -> Optional[Dict[str, Any]]:
        """统一 JSON 解析，支持纯 JSON / 代码块 / 文本嵌入"""
        if not text:
            return None

        text = text.strip()
        if text.startswith("{"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        # 使用堆栈平衡算法处理嵌套 JSON（修复 BUG-011）
        result = self._extract_json_with_stack(text)
        if result:
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def _extract_json_with_stack(text: str) -> Optional[str]:
        """使用堆栈平衡算法提取完整 JSON 对象"""
        start = text.find("{")
        if start == -1:
            return None

        stack = []
        in_string = False
        escape_next = False
        
        for i, char in enumerate(text[start:], start):
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
                continue
            
            if in_string:
                continue
            
            if char == '{':
                stack.append(i)
            elif char == '}':
                if not stack:
                    return None
                stack.pop()
                if not stack:
                    return text[start:i + 1]
        
        return None

    # ═══════════════════════════════════════════════════════════
    # Prompt 构建
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _build_decision_prompt(
        page_result: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """构建 VLM 动作决策提示词"""
        page_type = page_result.get("page_type", "unknown")
        confidence = page_result.get("confidence", 0)
        features = page_result.get("features", {})
        expected = context.get("expected_page", "world")
        step_desc = context.get("step_desc", "")
        last_action = context.get("last_action", "")

        return f"""你正在操控《明日方舟：终末地》，需要根据当前画面决定下一步操作。

当前信息：
- OpenCV 判页：{page_type}（置信度 {confidence:.2f}）
- 期望页面：{expected}
- 当前步骤：{step_desc}
- 上次动作：{last_action}

画面特征：
- 左侧边栏亮度：{features.get('left_bar_brightness', 0):.1f}
- 右上角绿色像素：{features.get('green_pixels_top_right', 0):.0f}
- 全屏亮度：{features.get('full_brightness', 0):.1f}

请分析画面并返回 JSON 决策结果，格式如下：
{{
  "page_type": "world|quest_panel|exit_dialog|loading|title|menu|other",
  "suggested_action": "tap|swipe|back|wait|claim|navigate|skip",
  "target": "目标元素的中文描述",
  "coordinates": [x, y],
  "reason": "决策理由，一句话"
}}

动作说明：
- tap: 点击坐标
- swipe: 滑动（给出方向和距离）
- back: 按返回键
- wait: 等待加载
- claim: 领取奖励（找出领取按钮坐标）
- navigate: 需要导航到某个页面
- skip: 跳过当前画面（如标题页点继续）
"""

    @staticmethod
    def _fallback_parse(
        text: str,
        page_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """从非 JSON 文本中提取决策信息"""
        result = {
            "page_type": page_result.get("page_type", "unknown"),
            "suggested_action": "back",
            "reason": text[:200] if text else "VLM 无响应",
            "confidence": 0.0,
        }

        if not text:
            return result

        text_lower = text.lower()

        if "tap" in text_lower or "click" in text_lower or "点击" in text:
            result["suggested_action"] = "tap"
            coords = re.findall(r'\((\d+),\s*(\d+)\)', text)
            if coords:
                result["coordinates"] = [int(coords[0][0]), int(coords[0][1])]
        elif "swipe" in text_lower or "滑动" in text:
            result["suggested_action"] = "swipe"
        elif "back" in text_lower or "返回" in text:
            result["suggested_action"] = "back"
        elif "wait" in text_lower or "等待" in text:
            result["suggested_action"] = "wait"
        elif "claim" in text_lower or "领取" in text:
            result["suggested_action"] = "claim"
        elif "navigate" in text_lower or "导航" in text:
            result["suggested_action"] = "navigate"
        elif "skip" in text_lower or "跳过" in text:
            result["suggested_action"] = "skip"

        return result

    # ═══════════════════════════════════════════════════════════
    # 工具方法
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def should_invoke_vlm(
        page_result: Dict[str, Any],
        expected_page: Optional[str] = None,
    ) -> bool:
        """判断是否需要调用 VLM"""
        page_type = page_result.get("page_type", "unknown")
        confidence = page_result.get("confidence", 0)

        if confidence < 0.5:
            return True
        if page_type == "unknown":
            return True
        if expected_page and page_type != expected_page:
            return True
        return False

    @property
    def mode(self) -> str:
        return "local"

    @property
    def effective_mode(self) -> str:
        return "local"

    def is_local_available(self) -> bool:
        """检查本地推理是否可用"""
        try:
            import urllib.request
            req = urllib.request.Request(f"{self._llama_url}/health", method="GET")
            resp = urllib.request.urlopen(req, timeout=3)
            return resp.status == 200
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════
# 便捷工厂函数
# ═══════════════════════════════════════════════════════════════

def create_gui_client(
    config: Optional[Dict[str, Any]] = None,
    inference_manager: Any = None,
) -> "GUIClient":
    """创建 GUIClient 实例"""
    return GUIClient(config or {}, inference_manager=inference_manager)


def create_agent_executor(
    inference_manager: Any,
    screen_capture: Any,
    touch_executor: Any,
    config: Optional[Dict[str, Any]] = None,
    device_serial: str = "",
) -> Any:
    """创建 AgentExecutor 实例（工厂函数）

    将 AgentExecutor 的创建逻辑放在 service 层，避免 capability 层依赖 service。

    Args:
        inference_manager: InferenceManager 实例
        screen_capture: ScreenCapture 实例
        touch_executor: TouchManager 实例
        config: 配置字典
        device_serial: 设备序列号

    Returns:
        AgentExecutor 实例
    """
    from core.service.cloud.agent_executor import AgentExecutor

    agent_executor = AgentExecutor(
        screen_capture=screen_capture,
        touch_executor=touch_executor,
        config=config,
        device_serial=device_serial,
        inference_manager=inference_manager,
    )

    logger.info(LogCategory.MAIN, "Agent 执行器已创建",
               device_serial=device_serial or "(none)")

    return agent_executor
