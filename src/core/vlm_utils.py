"""
VLM 分析工具 - 从 adb_utils 拆分

提供统一的 VLM 分析接口，不依赖 ADB 操作。
"""

import base64
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class VLMOptions:
    """VLM 调用参数"""
    model_tag: str = "exploration_deep"
    timeout: int = 120
    temperature: float = 0.01
    max_tokens: int = 2048
    system_prompt: str = ""


DEFAULT_VLM_OPTS = VLMOptions()


def vlm_analyze(image_bytes: bytes,
                instruction: str = "识别当前画面",
                opts: Optional[VLMOptions] = None,
                vlm_client=None) -> Optional[Dict[str, Any]]:
    """通过 VLMClient 调用 VLM 分析画面

    Args:
        image_bytes: PNG 截图字节
        instruction: 分析指令
        opts: VLM 参数
        vlm_client: VLMClient 实例（必需）

    Returns:
        VLM 回复文本或 None
    """
    if opts is None:
        opts = DEFAULT_VLM_OPTS

    if vlm_client is None:
        return None

    b64 = base64.b64encode(image_bytes).decode("utf-8")

    result = vlm_client.analyze_image(
        b64,
        instruction,
        system_prompt=opts.system_prompt or "你是终末地界面分析器。输出 JSON 格式。",
        max_tokens=opts.max_tokens,
        temperature=opts.temperature,
    )

    if result and result.get("status") == "success":
        return result
    return None
