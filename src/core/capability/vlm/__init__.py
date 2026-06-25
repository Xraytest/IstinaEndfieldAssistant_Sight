"""VLM 分析模块 — 统一的 VLM 分析接口

导出：VLMOptions, vlm_analyze（来自 vlm_utils.py），
      GUIClient, create_gui_client（来自 core.service.gui_client）
"""

from .vlm_utils import VLMOptions, vlm_analyze
from core.service.gui_client import GUIClient, create_gui_client

__all__ = [
    "VLMOptions", "vlm_analyze",
    "GUIClient", "create_gui_client",
]