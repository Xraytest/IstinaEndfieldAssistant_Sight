"""LlmClient - llama-server OpenAI compatible HTTP client."""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.foundation.logger import get_logger, LogCategory


class LlmClientError(Exception):
    """LlmClient base exception."""


class LlmClient:
    """OpenAI-compatible client for local llama-server."""

    def __init__(self, base_url: str = "http://127.0.0.1:9998/v1"):
        self._base_url = base_url.rstrip("/")
        self._logger = get_logger(__name__)

    def chat(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        image: Optional[str] = None,
        image_mime_type: str = "image/png",
    ) -> str:
        """Call /v1/chat/completions and return assistant content."""
        messages: list[Dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        if image:
            image_url = image if image.startswith("data:") else f"data:{image_mime_type};base64,{image}"
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            )
        else:
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
            raise LlmClientError("LLM returned empty result: " + str(data))
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not content:
            content = message.get("reasoning_content")
        if not content:
            raise LlmClientError("LLM returned empty content: " + str(message))
        return str(content)

    def health_check(self) -> bool:
        """Check whether llama-server is reachable."""
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
            self._logger.error("[%s] LLM request failed url=%s error=%s", LogCategory.MAIN, url, str(exc))
            raise LlmClientError(str(exc)) from exc
