"""LlmClient - llama-server OpenAI compatible HTTP client.

全流式传输架构：
- 所有 LLM/VLM 请求启用 stream=True（SSE 流式）
- 首 token 超时 = 1800s（30min），后续流式输出不限每块超时
- socket-level timeout 保护首 token 等待，线程 join timeout 放宽保护流式完成
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from core.foundation.logger import LogCategory, get_logger


class LlmClientError(Exception):
    """LlmClient base exception."""


class LlmClientTimeout(LlmClientError):
    """Raised when an LLM call exceeds its deadline."""


def _is_socket_timeout(exc: BaseException) -> bool:
    """Check if an exception is a socket read/connect timeout."""
    import socket
    if isinstance(exc, socket.timeout):
        return True
    # urllib wraps socket.timeout in URLError
    cause = getattr(exc, "reason", None)
    if isinstance(cause, socket.timeout):
        return True
    return False


class LlmClient:
    """OpenAI-compatible HTTP client.

    支持两种互斥后端：
    - **本地 llama-server**：``base_url`` 指向本地 llama-server（如
      ``http://127.0.0.1:9998/v1``），不需要 API key，可选 ``chat_template_kwargs``
      透传给 llama-server 的 chat template 渲染（如 Qwen3 的
      ``{"enable_thinking": False}``）。
    - **云端 OpenAI 兼容 API**：``base_url`` 指向云端 endpoint（如
      ``https://your-cloud-llm-endpoint/v1``），``api_key`` 必填，``model`` 字段必填
      （云端按 model 字段路由，本地 llama-server 通常忽略此字段）。

    两种模式互斥：调用方根据配置选择其一，不在运行时切换。

    同步 ``chat()`` 默认 120s 超时，但 VLM 步进式导航等场景需要更短的步级
    超时与可取消的异步调用，避免单次推理卡住整条导航循环、让用户长时间
    感知到界面无响应。``chat_async()`` 在后台线程执行，调用方可轮询结果或
    在超时后放弃，主线程/UI 线程不会被阻塞。
    """

    # 默认首 token 超时（秒）30 分钟 = 1800s。
    # 流式传输：socket-level timeout 保护首 token 等待；首 token 到达后后续流式
    # 输出不限每块超时（urllib 的 timeout 仅约束单个 read 操作，首 token 到达后
    # 每个 read 有 1800s 响应窗口，对 token-by-token 流式输出相当于无限制）。
    DEFAULT_TIMEOUT_S = 1800.0

    # 首 token 超时 + 流式内容完成预留缓冲。thread join 需要等待完整响应（可能
    # 包含大量 token），比 socket timeout 更宽松以避免误杀正在输出的流。
    _STREAM_JOIN_BUFFER_S = 3600.0

    # 浏览器 User-Agent：部分云端 API 网关（经 Cloudflare）会
    # 拦截 urllib 默认 UA 返回 403（error code 1010），使用浏览器 UA 绕过。
    _BROWSER_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:9998/v1",
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self._base_url = base_url.rstrip("/")
        # api_key 为 None 时走本地 llama-server 模式（无 Authorization header）；
        # 非 None 时走云端模式，每次请求带 ``Authorization: Bearer <key>``。
        self._api_key = api_key
        # 云端模式必须指定 model（如 "qwen/qwen3.5-35b-a3b(free)"）；本地模式可为 None，
        # payload 仍写 "local" 以兼容 llama-server。
        self._model = model
        self._logger = get_logger(__name__)

    def _supports_enable_thinking(self) -> bool:
        """判断当前云端模型是否支持 top-level ``enable_thinking`` 参数。

        - qwen3.5 系列：支持，且需要 ``enable_thinking=False`` 关闭 thinking
          避免 reasoning_content 占满 max_tokens
        - qwen3-vl 系列（instruct 版）：不支持该参数，发送会返回 400
        - 其他/未知模型：保守起见发送（若 400 则需扩展本方法）
        """
        if not self._model:
            return True
        m = self._model.lower()
        # qwen3-vl-instruct 系列（非 thinking 版）不支持 enable_thinking
        if "qwen3-vl" in m and "thinking" not in m:
            return False
        # qwen3.5 系列支持
        if "qwen3.5" in m:
            return True
        return True

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
        """Call /v1/chat/completions (streaming) and return assistant content.

        Args:
            timeout: 首 token 超时（秒）。None 则使用 DEFAULT_TIMEOUT_S = 1800s.
                     流式模式下此值仅约束首 token 等待时长，后续输出不限时。
            chat_template_kwargs: 透传给 llama-server 的 chat template 渲染参数。
                                  Qwen3 系列通过 ``{"enable_thinking": False}``
                                  在请求粒度关闭 thinking 模式。
        """
        messages = self._build_messages(prompt, system, image, image_mime_type)
        payload: Dict[str, Any] = {
            "model": self._model or "local",
            "messages": messages,
            "stream": True,
        }
        if temperature is not None:
            payload["temperature"] = float(temperature)
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)
        if chat_template_kwargs is not None:
            if self._api_key:
                enable_thinking = chat_template_kwargs.get("enable_thinking")
                if enable_thinking is not None and self._supports_enable_thinking():
                    payload["enable_thinking"] = enable_thinking
            else:
                payload["chat_template_kwargs"] = chat_template_kwargs

        req_timeout = float(timeout) if timeout is not None else self.DEFAULT_TIMEOUT_S
        # 线程 join timeout = 首 token 超时 + 流式内容缓冲（流式响应可能很长）
        join_timeout = req_timeout + self._STREAM_JOIN_BUFFER_S
        result_box: Dict[str, Any] = {"data": None, "error": None}

        def _do_post() -> None:
            try:
                result_box["data"] = self._post("/chat/completions", payload, timeout=req_timeout)
            except BaseException as exc:
                result_box["error"] = exc

        t = threading.Thread(target=_do_post, daemon=True, name="llm-chat-post")
        t.start()
        t.join(timeout=join_timeout)
        if t.is_alive():
            self._logger.warning(
                "[%s] LLM chat 超时 %ss（首 token 等待 %ss），放弃本次请求",
                LogCategory.MAIN, join_timeout, req_timeout,
            )
            raise LlmClientTimeout(f"chat timeout after {join_timeout}s (first-token {req_timeout}s)")
        if result_box["error"] is not None:
            raise result_box["error"]
        data = result_box["data"]
        choices = data.get("choices") or []
        if not choices:
            raise LlmClientError("LLM returned empty result: " + str(data))
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not content:
            raise LlmClientError("LLM returned empty content (thinking discarded): " + str(message))
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
        """Check whether the LLM backend is reachable.

        - 本地 llama-server：``GET <base>/health`` 返回 200。
        - 云端 OpenAI 兼容 API：``GET <base>/models`` 带 Authorization 返回 200。
        """
        import urllib.request

        if self._api_key:
            # 云端模式：用 /models 端点验证可达性与鉴权
            url = f"{self._base_url}/models"
            headers = {"Authorization": f"Bearer {self._api_key}", "User-Agent": self._BROWSER_UA}
        else:
            # 本地模式：用 llama-server 的 /health
            url = f"{self._base_url.split('/v1', 1)[0]}/health"
            headers = {"User-Agent": self._BROWSER_UA}
        try:
            req = urllib.request.Request(url, method="GET", headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _post(self, path: str, payload: Dict[str, Any], timeout: Optional[float] = None) -> Dict[str, Any]:
        import json
        import time as _time
        import urllib.request

        url = f"{self._base_url}{path}"
        req_timeout = float(timeout) if timeout is not None else self.DEFAULT_TIMEOUT_S
        headers = {"Content-Type": "application/json", "User-Agent": self._BROWSER_UA}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        is_stream = bool(payload.get("stream"))

        max_retries = 2
        last_exc: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            try:
                body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=body_bytes,
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=req_timeout) as resp:
                    if not is_stream:
                        raw = resp.read().decode("utf-8", errors="replace")
                        return json.loads(raw)
                    # STREAM-SSE: 逐行读取 SSE，delta content 累加构造最终响应
                    full_content: list[str] = []
                    role: str = ""
                    finish_reason: str = ""
                    buf = bytearray()
                    while True:
                        chunk = resp.read(1)  # 逐字节直到找到 \n\n
                        if not chunk:
                            break
                        buf.extend(chunk)
                        if chunk == b'\n':
                            line = buf.decode("utf-8", errors="replace").strip()
                            buf.clear()
                            if not line:
                                continue
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str == "[DONE]":
                                    break
                                try:
                                    ev = json.loads(data_str)
                                except json.JSONDecodeError:
                                    continue
                                choices = ev.get("choices") or []
                                if not choices:
                                    continue
                                delta = choices[0].get("delta") or {}
                                content_part = delta.get("content") or ""
                                if content_part:
                                    full_content.append(content_part)
                                if delta.get("role"):
                                    role = delta["role"]
                                fr = choices[0].get("finish_reason")
                                if fr:
                                    finish_reason = fr
                    return {
                        "choices": [{
                            "message": {"role": role or "assistant", "content": "".join(full_content)},
                            "finish_reason": finish_reason or "stop",
                        }]
                    }
            except urllib.error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    pass
                if exc.code in (502, 503, 504, 520) and attempt < max_retries:
                    self._logger.warning(
                        "[%s] LLM HTTP %d, retrying %d/%d",
                        LogCategory.MAIN, exc.code, attempt + 1, max_retries,
                    )
                    _time.sleep(1.5 * (attempt + 1))
                    last_exc = exc
                    continue
                self._logger.error(
                    "[%s] LLM HTTP error url=%s status=%s body=%s",
                    LogCategory.MAIN, url, exc.code, body[:500],
                )
                raise LlmClientError(f"HTTP {exc.code}: {body[:300]}") from exc
            except Exception as exc:
                last_exc = exc
                is_timeout = (
                    "timed out" in str(exc).lower()
                    or "timeout" in str(exc).lower()
                    or _is_socket_timeout(exc)
                )
                if attempt < max_retries and not is_timeout:
                    self._logger.warning(
                        "[%s] LLM request failed (retry %d/%d): %s",
                        LogCategory.MAIN, attempt + 1, max_retries, str(exc),
                    )
                    _time.sleep(1.5 * (attempt + 1))
                    continue
                self._logger.error("[%s] LLM request failed url=%s error=%s", LogCategory.MAIN, url, str(exc))
                raise LlmClientError(str(exc)) from exc
        raise LlmClientError(f"LLM request exhausted retries: {last_exc}")


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
