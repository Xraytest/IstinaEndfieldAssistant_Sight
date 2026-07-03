"""LLM 能力包（llama.cpp 本地推理）

对外提供两类接口：
- LlamaServerRuntime：管理 llama-server.exe 常驻进程
- LlmClient：封装 OpenAI 兼容 HTTP 接口
"""

from __future__ import annotations

from core.capability.llm.client import LlmClient
from core.capability.llm.runtime import LlamaServerRuntime

__all__ = ["LlmClient", "LlamaServerRuntime"]
