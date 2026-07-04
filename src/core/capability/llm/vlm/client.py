from __future__ import annotations

from typing import Any

from core.capability.llm.client import LlmClient, LlmClientError

API_VLM_CHAT = "/chat/completions"
API_VLM_HEALTH = "/health"
API_VLM_INFILL = "/completions"


class VlmClientError(LlmClientError):
    """VLM 客户端异常"""


class VlmClient(LlmClient):
    """VLM 多模态客户端。

    继承 LlmClient 复用 _post() 等底层通信。
    """

    def __init__(self, base_url: str = "http://127.0.0.1:9997/v1", timeout: int = 300):
        super().__init__(base_url=base_url)
        self._timeout = timeout

    def analyze_image(
        self,
        image_data: bytes,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """VLM 图像理解——传入截图 + prompt，返回 LLM 结构输出。"""
        import base64

        image_b64 = base64.b64encode(image_data).decode("utf-8")

        body = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        data = self._post(API_VLM_CHAT, body)
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return {"text": text, "usage": usage}

    def health_check(self) -> bool:
        import urllib.request

        url = f"{self._base_url.rstrip('/')}{API_VLM_HEALTH}"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        import json
        import urllib.request
        url = f"{self._base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw)
        except Exception as exc:
            self._logger.error("VLM 请求失败 url=%s error=%s", url, str(exc))
            raise VlmClientError(str(exc)) from exc

    def analyze_with_tools(
        self,
        image_data: bytes,
        prompt: str,
        tools: list[dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: int = 8192,
    ) -> dict[str, Any]:
        """VLM Function Calling——返回 tool_calls 供 annotation 渲染。"""
        import base64

        image_b64 = base64.b64encode(image_data).decode("utf-8")

        body = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "tools": tools,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        data = self._post(API_VLM_CHAT, body)
        message = data["choices"][0]["message"]
        tool_calls = message.get("tool_calls", [])
        content = message.get("content", "")
        usage = data.get("usage", {})

        return {"content": content, "tool_calls": tool_calls, "usage": usage}
