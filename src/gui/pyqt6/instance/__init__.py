"""IEA 多实例 GUI 模块。

提供实例注册表、实例上下文管理、实例侧栏 UI 与相关对话框。

主要导出：
    - :class:`InstanceManager` : 实例注册表与活动实例管理（全局单例）
    - :class:`InstanceContext` : 单实例运行时上下文（聚合 bridge/scheduler/queue_state）
    - :class:`InstanceMeta` : 实例元数据（id/display_name/color/icon/...）
    - :class:`InstanceSidebarWidget` : 最左侧实例切换侧栏
"""
from __future__ import annotations

from .manager import InstanceContext, InstanceManager, InstanceMeta
from .sidebar import InstanceSidebarWidget

__all__ = [
    "InstanceContext",
    "InstanceManager",
    "InstanceMeta",
    "InstanceSidebarWidget",
]
