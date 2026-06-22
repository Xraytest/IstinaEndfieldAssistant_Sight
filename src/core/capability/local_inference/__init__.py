"""
本地推理模块 - 提供IEA客户端本地VLM推理功能

该模块包含:
- GPUChecker: 显卡检测器
- LocalInferenceEngine: 本地推理引擎
- ModelManager: 模型管理器
- InferenceManager: 推理管理器
- PromptCache: Prompt缓存管理器
- AsyncInferenceWorker: 异步推理工作线程
- AsyncInferenceManager: 异步推理管理器
- TaskPriority: 任务优先级枚举
- TaskStatus: 任务状态枚举
"""

from .gpu_checker import GPUChecker
from .local_inference_engine import LocalInferenceEngine
from .model_manager import ModelManager
from .inference_manager import InferenceManager
from .prompt_cache import PromptCache
from .async_inference_worker import (
    AsyncInferenceWorker,
    AsyncInferenceManager,
    TaskPriority,
    TaskStatus,
    InferenceTask
)

__all__ = [
    'GPUChecker',
    'LocalInferenceEngine',
    'ModelManager',
    'InferenceManager',
    'PromptCache',
    'AsyncInferenceWorker',
    'AsyncInferenceManager',
    'TaskPriority',
    'TaskStatus',
    'InferenceTask',
]
