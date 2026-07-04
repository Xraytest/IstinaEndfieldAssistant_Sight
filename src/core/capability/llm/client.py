"""LlmClient - llama-server OpenAI 兼容 HTTP 客户端

提供最小可用接口：chat(prompt) -> output。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.foundation.logger import get_logger, LogCategory


class LlmClientError(Exception):
    """LlmClient 基础异常"""


class LlmClient:
    """OpenAI 兼容客户端，默认连接本地 llama-server"""

    def __init__(self, base_url: str = "http://127.0.0.1:9998/v1"):
        self._base_url = base_url.rstrip("/")
        self._logger = get_logger(__name__)

    def chat(self, prompt: str, *, system: Optional[str] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
        """调用 /v1/chat/completions，返回 assistant content"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": "local",
            "messages": messages,
        }
        if temperature is not None:
            payload["temperature"] = float(temperature)
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)

        data = self._post("/chat/completions", payload)
        choices = data.get("choices") or []
        if not choices:
            raise LlmClientError("LLM 返回空结果: " + str(data))
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not content:
            content = message.get("reasoning_content")
        if not content:
            raise LlmClientError("LLM 返回内容为空: " + str(message))
        return str(content)

    def health_check(self) -> bool:
        """检查 llama-server 是否可达"""
        import urllib.request
        url = f"{self._base_url}/health"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        import json
        import urllib.request
        url = f"{self._base_url}{path}"
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw)
        except Exception as exc:
            self._logger.error("[%s] LLM 请求失败 url=%s error=%s", LogCategory.MAIN, url, str(exc))
            raise LlmClientError(str(exc)) from exc
