"""LLM 能力包（llama.cpp 本地推理）

对外提供：
- LlamaServerRuntime：管理 llama-server.exe 常驻进程（纯文本 LLM）
- LlmClient：封装 OpenAI 兼容 HTTP 接口（纯文本）
- VlmServerRuntime：VLM 多模态服务端运行时（子模块）
- VlmClient：VLM 多模态客户端（子模块）
"""

from __future__ import annotations

from core.capability.llm.client import LlmClient
from core.capability.llm.runtime import LlamaServerRuntime
from core.capability.llm.vlm.client import VlmClient
from core.capability.llm.vlm.runtime import VlmServerRuntime

__all__ = [
    "LlmClient",
    "LlamaServerRuntime",
    "VlmClient",
    "VlmServerRuntime",
]
