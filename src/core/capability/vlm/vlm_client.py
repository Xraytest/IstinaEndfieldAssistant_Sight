"""
VLMClient 已重命名为 GUIClient — 请使用 core.gui_client

此文件保留为向后兼容的废弃包装器。
新代码应直接导入 GUIClient：
    from core.service.gui_client import GUIClient, create_gui_client
"""

import warnings

warnings.warn(
    "VLMClient 已迁移到 core.gui_client，请使用 GUIClient",
    DeprecationWarning,
    stacklevel=2,
)

from core.service.gui_client import GUIClient, create_gui_client  # noqa: F401

# 向后兼容别名
VLMClient = GUIClient  # noqa: F811
create_vlm_client = create_gui_client  # noqa: F811
