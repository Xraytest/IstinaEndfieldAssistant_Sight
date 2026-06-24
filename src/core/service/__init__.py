"""服务层 — 组合能力层模块实现业务逻辑

包含：device_state（设备状态管理）、page_analyzer（页面分析）、
gui_client（GUI 客户端中间体）、state_detector（状态检测）、
state_recovery（状态恢复）、cloud（云端业务逻辑）、
element_analysis（元素分析与任务知识库）
"""

from .device_state import DeviceStateManager
from .page_analyzer import HighPrecisionPageAnalyzerV2, HighPrecisionPageAnalyzer
from .gui_client import GUIClient, create_gui_client
from .state_detector import StateDetector
from .state_recovery import StateRecoveryStrategy
from .cloud import (
    AgentExecutor,
    PageTree, PageNode, PageEdge, UIElement, ElementType, PageState,
    ExplorationEngine, ExplorationState, ExplorationConfig,
    LocalLogManager, ArknightsEndfieldExceptionDetector,
)
from .element_analysis import (
    ElementKnowledge, ElementVerification, PageKnowledge,
    TaskDefinition, TaskStatus, TaskCycle, TaskInstance,
    AnalysisResult, EventActivity,
    ElementType, VerificationStatus, make_semantic_id,
    ElementRepository, AnalysisSession,
    ElementAnalyzer, TaskAnalyzer,
)

__all__ = [
    # device_state
    "DeviceStateManager",
    # page_analyzer
    "HighPrecisionPageAnalyzerV2", "HighPrecisionPageAnalyzer",
    # gui_client
    "GUIClient", "create_gui_client",
    # state_detector
    "StateDetector",
    # state_recovery
    "StateRecoveryStrategy",
    # cloud
    "AgentExecutor",
    "PageTree", "PageNode", "PageEdge", "UIElement", "ElementType", "PageState",
    "ExplorationEngine", "ExplorationState", "ExplorationConfig",
    "LocalLogManager", "ArknightsEndfieldExceptionDetector",
    # element_analysis
    "ElementKnowledge", "ElementVerification", "PageKnowledge",
    "TaskDefinition", "TaskStatus", "TaskCycle", "TaskInstance",
    "AnalysisResult", "EventActivity",
    "ElementType", "VerificationStatus", "make_semantic_id",
    "ElementRepository", "AnalysisSession",
    "ElementAnalyzer", "TaskAnalyzer",
]