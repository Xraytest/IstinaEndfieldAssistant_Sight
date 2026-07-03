"""基础工具函数集合

提供项目内通用的工具函数，避免在各模块中重复实现相同逻辑。
"""

import json
import logging
import re
import sys
import traceback
from typing import Any, Callable, Dict, Optional, TypeVar

T = TypeVar("T")


def safe_parse_json(text: str) -> Optional[Dict[str, Any]]:
    """统一 JSON 解析，支持纯 JSON / 代码块 / 文本嵌入

    解析优先级：
    1. 纯 JSON 字符串
    2. ```json ... ``` 代码块
    3. 文本中第一个完整 JSON 对象（使用堆栈平衡算法）

    Args:
        text: 可能包含 JSON 的文本

    Returns:
        解析后的字典，失败返回 None
    """
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

    result = _extract_json_with_stack(text)
    if result:
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            pass

    return None


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


def log_exception(logger: logging.Logger, message: str, exc: Exception) -> None:
    """统一异常日志格式

    Args:
        logger: 日志记录器
        message: 上下文消息
        exc: 捕获的异常对象
    """
    logger.error(f"{message}: {exc}")
    if sys.version_info >= (3, 10):
        logger.debug(traceback.format_exc())


def safe_call(
    func: Callable[..., T],
    logger: Optional[logging.Logger] = None,
    default: T = None,  # type: ignore[assignment]
    message: str = "safe_call failed",
) -> T:
    """统一异常捕获并返回默认值

    Args:
        func: 需要安全调用的函数
        logger: 可选的日志记录器
        default: 异常时的返回值
        message: 异常日志前缀

    Returns:
        func() 的返回值，异常时返回 default
    """
    try:
        return func()
    except Exception as exc:  # pragma: no cover - 防御性日志
        if logger is not None:
            log_exception(logger, message, exc)
        return default
