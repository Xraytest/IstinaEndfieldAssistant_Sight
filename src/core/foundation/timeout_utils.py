"""超时执行工具。

封装 "result_box dict + daemon thread + join(timeout) + is_alive 检查" 模式，
用于对底层不可靠/可能阻塞的同步调用施加硬时限保护。

典型场景：
  - MaaFW job.wait() 在并发限制下可能无限阻塞
  - 截图调用 (screenshot_fn) 在底层 scrcpy 流断开时可能卡死
  - LLM HTTP 请求首 token 超时但流式响应可能持续很久

使用方式：
    data = run_with_timeout(lambda: screenshot_fn(), timeout=15.0, name="grab-frame")
    if data is None:
        # 超时或异常
        ...

注意：
  - 超时后 daemon 线程仍会继续运行到 fn 返回或抛出（无法强制 kill）。
    调用方应确保 fn 在超时后不会产生副作用或污染共享状态。
  - 异常会被捕获并以 None 返回（如果未提供 on_error）；如需区分超时与异常，
    请检查返回的 _TimeoutResult.is_timeout 字段。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class _TimeoutResult:
    """run_with_timeout 的执行结果。"""
    data: Any = None
    error: Optional[BaseException] = None
    is_timeout: bool = False
    is_error: bool = False

    @property
    def ok(self) -> bool:
        return not self.is_timeout and not self.is_error


def run_with_timeout(
    fn: Callable[[], Any],
    timeout: float,
    name: str = "task",
    *,
    thread_name: Optional[str] = None,
    on_timeout: Optional[Callable[[str, float], None]] = None,
    on_error: Optional[Callable[[str, BaseException], None]] = None,
) -> _TimeoutResult:
    """在线程中执行 fn，最多等待 timeout 秒。

    Args:
        fn: 要执行的可调用对象（无参数）。
        timeout: 最长等待秒数。
        name: 任务名称（用于日志和线程名）。
        thread_name: 自定义线程名，默认 ``f"{name}-timeout"``。
        on_timeout: 超时回调，签名为 ``(name, timeout)``，默认无操作。
        on_error: 异常回调，签名为 ``(name, exc)``，默认无操作。

    Returns:
        _TimeoutResult: 包含 data / error / is_timeout / is_error 字段。
        调用方通常检查 ``.ok`` 后取 ``.data``，或检查 ``.is_timeout`` / ``.is_error``。
    """
    result = _TimeoutResult()

    def _do() -> None:
        try:
            result.data = fn()
        except BaseException as exc:  # noqa: BLE001 - 显式捕获 BaseException 以处理 KeyboardInterrupt 等
            result.error = exc
            result.is_error = True

    t = threading.Thread(target=_do, daemon=True, name=thread_name or f"{name}-timeout")
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        result.is_timeout = True
        result.is_error = False
        if on_timeout is not None:
            on_timeout(name, timeout)
    elif result.is_error and on_error is not None:
        on_error(name, result.error)  # type: ignore[arg-type]
    return result


__all__ = ["run_with_timeout", "_TimeoutResult"]
