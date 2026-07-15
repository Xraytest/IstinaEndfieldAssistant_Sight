"""LlmClient - llama-server OpenAI compatible HTTP client."""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from core.foundation.logger import LogCategory, get_logger


class LlmClientError(Exception):
    """LlmClient base exception."""


class LlmClientTimeout(LlmClientError):
    """Raised when an LLM call exceeds its deadline."""


class LlmClient:
    """OpenAI-compatible client for local llama-server.

    同步 ``chat()`` 默认 120s 超时，但 VLM 步进式导航等场景需要更短的步级
    超时与可取消的异步调用，避免单次推理卡住整条导航循环、让用户长时间
    感知到界面无响应。``chat_async()`` 在后台线程执行，调用方可轮询结果或
    在超时后放弃，主线程/UI 线程不会被阻塞。
    """

    # 默认超时（秒）。VLM 步进场景应通过 chat(timeout=...) 传入更短值。
    DEFAULT_TIMEOUT_S = 120.0

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
        timeout: Optional[float] = None,
        chat_template_kwargs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Call /v1/chat/completions and return assistant content.

        Args:
            timeout: 单次请求超时（秒）。None 则使用 DEFAULT_TIMEOUT_S。
                     VLM 步进导航建议 20-40s，避免单步卡死拖累整条循环。
            chat_template_kwargs: 透传给 llama-server 的 chat template 渲染参数。
                                  Qwen3 系列模型通过 ``{"enable_thinking": False}``
                                  可在请求粒度关闭 thinking 模式，避免输出冗长
                                  reasoning_content 拖垮 VLM 步进循环。
        """
        messages = self._build_messages(prompt, system, image, image_mime_type)
        payload: Dict[str, Any] = {"model": "local", "messages": messages}
        if temperature is not None:
            payload["temperature"] = float(temperature)
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)
        if chat_template_kwargs is not None:
            payload["chat_template_kwargs"] = chat_template_kwargs

        data = self._post("/chat/completions", payload, timeout=timeout)
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

    def chat_async(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        image: Optional[str] = None,
        image_mime_type: str = "image/png",
        timeout: Optional[float] = None,
        chat_template_kwargs: Optional[Dict[str, Any]] = None,
    ) -> "LlmAsyncHandle":
        """非阻塞版本的 ``chat()``。

        在后台线程发起推理，立即返回一个 ``LlmAsyncHandle``。调用方可在不阻塞
        UI/事件循环的前提下轮询结果；超时或取消时不影响 llama-server 本身（请求
        线程自然结束并丢弃结果）。这正是"避免用户直接观感影响"的关键：VLM 导航
        每一步都不会卡住预览/任务线程。
        """
        handle = LlmAsyncHandle()
        target = self._chat_async_target(
            handle, prompt, system, temperature, max_tokens,
            image, image_mime_type, timeout, chat_template_kwargs,
        )
        thread = threading.Thread(target=target, daemon=True, name="llm-chat-async")
        handle._bind_thread(thread)
        thread.start()
        return handle

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _build_messages(
        prompt: str,
        system: Optional[str],
        image: Optional[str],
        image_mime_type: str,
    ) -> list[Dict[str, Any]]:
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
        return messages

    def _chat_async_target(
        self,
        handle: "LlmAsyncHandle",
        prompt: str,
        system: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        image: Optional[str],
        image_mime_type: str,
        timeout: Optional[float],
        chat_template_kwargs: Optional[Dict[str, Any]],
    ) -> None:
        try:
            result = self.chat(
                prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                image=image,
                image_mime_type=image_mime_type,
                timeout=timeout,
                chat_template_kwargs=chat_template_kwargs,
            )
            handle._set_result(result)
        except Exception as exc:  # noqa: BLE001 — 后台线程需捕获一切异常
            handle._set_error(exc)

    def health_check(self) -> bool:
        """Check whether llama-server is reachable."""
        import urllib.request

        url = f"{self._base_url.split('/v1', 1)[0]}/health"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _post(self, path: str, payload: Dict[str, Any], timeout: Optional[float] = None) -> Dict[str, Any]:
        import json
        import urllib.request

        url = f"{self._base_url}{path}"
        req_timeout = float(timeout) if timeout is not None else self.DEFAULT_TIMEOUT_S
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=req_timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw)
        except Exception as exc:
            self._logger.error("[%s] LLM request failed url=%s error=%s", LogCategory.MAIN, url, str(exc))
            raise LlmClientError(str(exc)) from exc


class LlmAsyncHandle:
    """``chat_async()`` 返回的句柄，线程安全地承载结果或异常。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._done = threading.Event()
        self._result: Optional[str] = None
        self._error: Optional[BaseException] = None
        self._thread: Optional[threading.Thread] = None

    def _bind_thread(self, thread: threading.Thread) -> None:
        self._thread = thread

    def _set_result(self, result: str) -> None:
        with self._lock:
            self._result = result
        self._done.set()

    def _set_error(self, error: BaseException) -> None:
        with self._lock:
            self._error = error
        self._done.set()

    @property
    def done(self) -> bool:
        return self._done.is_set()

    @property
    def succeeded(self) -> bool:
        with self._lock:
            return self._result is not None

    def get(self, timeout: Optional[float] = None) -> str:
        """阻塞等待结果。超时抛出 ``LlmClientTimeout``，失败抛出原异常。"""
        if not self._done.wait(timeout=timeout):
            raise LlmClientTimeout("LLM async call exceeded deadline")
        with self._lock:
            if self._error is not None:
                raise self._error
            return self._result or ""

    def result_or(self, default: str, timeout: Optional[float] = None) -> str:
        """非抛出版本：超时或失败时返回 ``default``，便于导航循环降级处理。"""
        try:
            return self.get(timeout=timeout)
        except Exception:  # noqa: BLE001 — 降级路径
            return default
