"""
VLM 客户端中间体 — 所有 LLM/VLM 请求的唯一入口

职责：
1. 提供统一的图像分析、文本对话、动作决策、验证接口
2. 根据配置自动路由到本地 llama-server 或服务端 IstinaPlatform
3. 统一管理 API 密钥加载、JSON 响应解析、错误处理
4. 纯 Python 标准库 + requests，不依赖 PyQt，可独立测试

使用示例：
    # 本地模式（llama-server）
    client = VLMClient({"vlm_mode": "local"})
    result = client.analyze_image(b64, "分析画面")

    # 服务端模式（TCP → IstinaPlatform）
    client = VLMClient({"vlm_mode": "server"}, communicator=comm)
    result = client.analyze_image(b64, "分析画面")

    # 自动模式（本地优先，失败降级）
    client = VLMClient({"vlm_mode": "auto", "auto_fallback": True}, communicator=comm)
    result = client.analyze_image(b64, "分析画面")
"""

import json
import time
import base64
import re
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

# ── 日志 ──────────────────────────────────────────────────────
from core.logger import get_logger, LogCategory
logger = get_logger()


# ── 配置默认值 ────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "vlm_mode": "local",           # "local" | "server" | "auto"
    "llama_url": "http://127.0.0.1:8080",
    "vlm_timeout": 60,
    "auto_fallback": True,         # 本地失败时自动降级到服务端
    "max_tokens": 4096,
    "temperature": 0.1,
    "cherryin_api_url": "https://open.cherryin.ai/v1",
    "cherryin_model": "qwen/qwen3.6-plus",
}


class VLMClient:
    """
    统一的 VLM 客户端中间体

    所有 LLM/VLM 请求汇聚到此模块，根据配置决定：
    - local: 调用本地 llama-server HTTP API
    - server: 通过 TCP 通信器调用 IstinaPlatform
    - auto: 本地优先，失败自动降级到服务端

    不嵌入任何其他代码，不依赖 PyQt，纯 Python 标准库 + requests。
    """

    def __init__(
        self,
        config: Dict[str, Any],
        communicator: Any = None,
    ):
        """
        初始化 VLM 客户端

        Args:
            config: 配置字典，支持以下键：
                - vlm_mode: "local" | "server" | "auto"（默认 "local"）
                - llama_url: llama-server 地址（默认 "http://127.0.0.1:8080"）
                - vlm_timeout: 请求超时秒数（默认 60）
                - auto_fallback: 本地失败时自动降级到服务端（默认 True）
                - max_tokens: 最大生成 token 数（默认 4096）
                - temperature: 推理温度（默认 0.1）
                - cherryin_api_url: cherryin.ai API 地址
                - cherryin_model: cherryin.ai 模型名
            communicator: ClientCommunicator 实例（服务端模式必需）
        """
        self._config = {**DEFAULT_CONFIG, **config}
        self._communicator = communicator
        self._mode = self._config["vlm_mode"]
        self._llama_url = self._config["llama_url"].rstrip("/")
        self._timeout = self._config["vlm_timeout"]
        self._auto_fallback = self._config["auto_fallback"]

        # 缓存 API 密钥（避免重复文件 I/O）
        self._api_key: Optional[str] = None

        logger.info(LogCategory.MAIN, "VLMClient 初始化",
                   mode=self._mode,
                   llama_url=self._llama_url,
                   timeout=self._timeout,
                   auto_fallback=self._auto_fallback)

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

        根据配置自动路由到本地 llama-server 或服务端 IstinaPlatform。

        Args:
            image_base64: Base64 编码的图像数据
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            **kwargs: 额外参数（max_tokens, temperature 等）

        Returns:
            {
                "status": "success" | "error",
                "content": str,          # VLM 返回的文本内容
                "parsed": dict | None,   # 解析后的 JSON（如果返回的是 JSON）
                "error": str | None,     # 错误信息
                "mode_used": str,        # 实际使用的模式
                "inference_time_ms": float,
            }
        """
        start = time.time()

        # 确定有效模式
        mode = self._resolve_mode()

        if mode == "server":
            result = self._call_server(image_base64, prompt, system_prompt, **kwargs)
        else:
            result = self._call_local(image_base64, prompt, system_prompt, **kwargs)

        # 自动降级：本地失败 → 服务端
        if (
            mode != "server"
            and result.get("status") == "error"
            and self._auto_fallback
            and self._communicator
        ):
            logger.warning(LogCategory.INFERENCE,
                          "本地推理失败，自动降级到服务端",
                          error=result.get("error"))
            result = self._call_server(image_base64, prompt, system_prompt, **kwargs)
            result["mode_used"] = "server(fallback)"
        else:
            result["mode_used"] = mode

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
        mode = self._resolve_mode()

        if mode == "server":
            result = self._call_server_text(messages, **kwargs)
        else:
            result = self._call_local_text(messages, **kwargs)

        if (
            mode != "server"
            and result.get("status") == "error"
            and self._auto_fallback
            and self._communicator
        ):
            result = self._call_server_text(messages, **kwargs)
            result["mode_used"] = "server(fallback)"
        else:
            result["mode_used"] = mode

        result["inference_time_ms"] = (time.time() - start) * 1000
        return result

    def decide_action(
        self,
        image: Any,  # np.ndarray
        page_result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        VLM 动作决策（兼容 VlmActionDecider 接口）

        当 OpenCV 无法确定下一步时，调用 VLM 进行语义决策。

        Args:
            image: OpenCV 图像 (np.ndarray)
            page_result: 页面分析结果 {page_type, confidence, features}
            context: 上下文 {expected_page, last_action, step_desc}

        Returns:
            {"page_type": str, "suggested_action": str, "coordinates": [x,y], ...}
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

            # 解析失败，从文本中提取
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

        Args:
            image_base64: Base64 编码的图像
            prompt: 验证提示词
            expected: 期望值（可选）

        Returns:
            {"verified": bool, "confidence": float, "extracted_data": dict, ...}
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

        # 无 JSON 解析结果，基于文本启发式判断
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
    # 模式解析
    # ═══════════════════════════════════════════════════════════

    def _resolve_mode(self) -> str:
        """解析有效模式"""
        if self._mode == "auto":
            # 检查本地是否可用
            if self._check_local_available():
                return "local"
            if self._communicator:
                return "server"
            return "local"  # 默认本地
        return self._mode

    def _check_local_available(self) -> bool:
        """检查本地 llama-server 是否可用"""
        try:
            import urllib.request
            req = urllib.request.Request(f"{self._llama_url}/health", method="GET")
            resp = urllib.request.urlopen(req, timeout=3)
            return resp.status == 200
        except Exception:
            return False

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
    # 服务端推理（TCP → IstinaPlatform）
    # ═══════════════════════════════════════════════════════════

    def _call_server(
        self,
        image_base64: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """通过 TCP 通信器调用 IstinaPlatform"""
        if not self._communicator:
            return {
                "status": "error",
                "content": "",
                "parsed": None,
                "error": "通信器未初始化，无法使用服务端模式",
            }

        try:
            # 解码 base64 为 bytes（communicator 需要 bytes）
            image_bytes = base64.b64decode(image_base64)

            request_data = {
                "type": "process_image",
                "image": base64.b64encode(image_bytes).decode("utf-8"),
                "context": {
                    "prompt": prompt,
                    "system_prompt": system_prompt,
                    **kwargs,
                },
            }

            response = self._communicator.send_request("process_image", request_data)

            if response is None:
                return {
                    "status": "error",
                    "content": "",
                    "parsed": None,
                    "error": "服务端无响应",
                }

            # 解析服务端响应
            content = ""
            if "result" in response:
                result = response["result"]
                if isinstance(result, dict):
                    content = result.get("text", "") or result.get("content", "") or json.dumps(result)
                else:
                    content = str(result)
            elif "content" in response:
                content = response["content"]
            elif "text" in response:
                content = response["text"]

            parsed = self._parse_json(content)

            logger.info(LogCategory.INFERENCE, "服务端推理成功",
                       content_length=len(content),
                       has_parsed=parsed is not None)

            return {
                "status": "success",
                "content": content,
                "parsed": parsed,
                "error": None,
                "raw_response": response,
            }

        except Exception as e:
            logger.exception(LogCategory.INFERENCE, "服务端推理失败", error=str(e))
            return {
                "status": "error",
                "content": "",
                "parsed": None,
                "error": str(e),
            }

    def _call_server_text(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> Dict[str, Any]:
        """通过 TCP 通信器调用 IstinaPlatform 纯文本"""
        if not self._communicator:
            return {"status": "error", "content": "", "parsed": None,
                    "error": "通信器未初始化"}

        try:
            response = self._communicator.send_request("agent_chat", {
                "messages": messages,
                **kwargs,
            })

            if response is None:
                return {"status": "error", "content": "", "parsed": None,
                        "error": "服务端无响应"}

            content = response.get("content", "") or response.get("text", "") or str(response)

            return {
                "status": "success",
                "content": content,
                "parsed": self._parse_json(content),
                "error": None,
            }

        except Exception as e:
            return {"status": "error", "content": "", "parsed": None,
                    "error": str(e)}

    # ═══════════════════════════════════════════════════════════
    # 统一 JSON 解析
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _parse_json(text: str) -> Optional[Dict[str, Any]]:
        """
        统一 JSON 解析

        支持多种格式：
        - 纯 JSON: {"key": "value"}
        - 代码块: ```json {"key": "value"} ```
        - 文本中嵌入 JSON
        """
        if not text:
            return None

        # 尝试直接解析
        text = text.strip()
        if text.startswith("{"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # 尝试提取 ```json ... ``` 块
        m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取第一个 { ... } 块
        m = re.search(r'\{[\s\S]*?\}', text)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass

        # 尝试提取最外层 { ... }（可能跨多行）
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

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

        # 动作关键词匹配
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
    # API 密钥管理
    # ═══════════════════════════════════════════════════════════

    def _get_api_key(self) -> str:
        """统一 API 密钥加载（缓存）"""
        if self._api_key:
            return self._api_key

        # 从 client_config.json 加载
        config_path = (
            Path(__file__).resolve().parent.parent.parent
            / "config" / "client_config.json"
        )
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                key = cfg.get("vendors", {}).get("newapi_channel", {}).get("key", "")
                if key and key != "YOUR_API_KEY_HERE":
                    self._api_key = key
                    return key
            except (json.JSONDecodeError, OSError):
                pass

        # 从环境变量加载
        key = os.environ.get("CHERRYIN_API_KEY", "")
        if key:
            self._api_key = key
            return key

        return ""

    # ═══════════════════════════════════════════════════════════
    # 工具方法
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def should_invoke_vlm(
        page_result: Dict[str, Any],
        expected_page: Optional[str] = None,
    ) -> bool:
        """
        判断是否需要调用 VLM

        条件：
        1. OpenCV 置信度 < 0.5
        2. 页面类型为 unknown
        3. 页面与预期不符
        """
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
        """当前配置模式"""
        return self._mode

    @property
    def effective_mode(self) -> str:
        """当前有效模式（考虑自动选择）"""
        return self._resolve_mode()

    def is_local_available(self) -> bool:
        """检查本地推理是否可用"""
        return self._check_local_available()

    def is_server_available(self) -> bool:
        """检查服务端是否可用"""
        return self._communicator is not None

    def switch_mode(self, mode: str) -> bool:
        """切换模式"""
        if mode not in ("local", "server", "auto"):
            return False
        self._mode = mode
        logger.info(LogCategory.MAIN, "VLMClient 模式已切换", mode=mode)
        return True


# ═══════════════════════════════════════════════════════════════
# 便捷工厂函数
# ═══════════════════════════════════════════════════════════════

def create_vlm_client(
    config: Optional[Dict[str, Any]] = None,
    communicator: Any = None,
) -> VLMClient:
    """创建 VLMClient 实例"""
    return VLMClient(config or {}, communicator=communicator)


# ═══════════════════════════════════════════════════════════════
# 独立测试
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("VLMClient 独立测试")
    print("=" * 60)

    # 测试 1：初始化
    print("\n[测试 1] 初始化（本地模式）")
    client = VLMClient({"vlm_mode": "local"})
    print(f"  模式: {client.mode}")
    print(f"  本地可用: {client.is_local_available()}")

    # 测试 2：JSON 解析
    print("\n[测试 2] JSON 解析")
    test_cases = [
        '{"key": "value"}',
        '```json\n{"key": "value"}\n```',
        '一些文字 {"key": "value"} 更多文字',
        '{"actions": [{"action": "tap", "x": 100, "y": 200}]}',
        '非 JSON 文本',
        '',
    ]
    for tc in test_cases:
        result = VLMClient._parse_json(tc)
        print(f"  输入: {tc[:50]}... → 结果: {result}")

    # 测试 3：决策提示词构建
    print("\n[测试 3] 决策提示词构建")
    prompt = VLMClient._build_decision_prompt(
        {"page_type": "unknown", "confidence": 0.3, "features": {}},
        {"expected_page": "world", "step_desc": "前置验证"},
    )
    print(f"  提示词长度: {len(prompt)} 字符")

    # 测试 4：回退解析
    print("\n[测试 4] 回退解析")
    result = VLMClient._fallback_parse(
        "建议点击 (500, 300) 处的领取按钮",
        {"page_type": "quest_panel"},
    )
    print(f"  结果: {result}")

    # 测试 5：服务端模式（无 communicator）
    print("\n[测试 5] 服务端模式（无 communicator）")
    client2 = VLMClient({"vlm_mode": "server"})
    result = client2.analyze_image("fake_base64", "test")
    print(f"  结果: {result['status']} - {result.get('error')}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
