"""UI元素分析与任务知识库模块

提供基于VLM的UI元素识别、验证与持久化存储，
分离元素知识数据到 data/elements/ 和 data/tasks/，
避免与 cache/ 临时文件混合。

主要组件：
- models: 元素/任务/验证数据模型
- element_repo: 持久化存储读写
- element_analyzer: VLM高精度元素分析（调用IstinaPlatform大参数模型）
- task_analyzer: 每日/每周/活动任务分析
"""

from .models import (
    ElementKnowledge,
    ElementVerification,
    PageKnowledge,
    TaskDefinition,
    TaskStatus,
    TaskCycle,
    TaskInstance,
    AnalysisResult,
    EventActivity,
    ElementType,
    VerificationStatus,
    make_semantic_id,
)
from .element_repo import ElementRepository, AnalysisSession
from .element_analyzer import ElementAnalyzer
from .task_analyzer import TaskAnalyzer

__all__ = [
    'ElementKnowledge', 'ElementVerification', 'PageKnowledge',
    'TaskDefinition', 'TaskStatus', 'TaskCycle', 'TaskInstance',
    'AnalysisResult', 'EventActivity',
    'ElementType', 'VerificationStatus', 'make_semantic_id',
    'ElementRepository', 'AnalysisSession',
    'ElementAnalyzer', 'TaskAnalyzer',
]
