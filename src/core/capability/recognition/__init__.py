"""
识别模块 - MaaEnd 式多源融合识别系统

包含：
- RecognitionEngine: 识别引擎（模板匹配/颜色匹配/And/Or）
- MaaFwPipelineOCR: MaaFw 管道 OCR 封装（原生 OCR，无需额外安装）
- StateMachineExecutor: 状态机执行引擎
- PREDEFINED_STATES: 预定义状态节点
"""

from .recognition_engine import (
    RecognitionEngine,
    MaaFwPipelineOCR,
    PREDEFINED_STATES,
)

from .state_machine import (
    StateMachineExecutor,
    ExecutionState
)

__all__ = [
    "RecognitionEngine",
    "MaaFwPipelineOCR",
    "StateMachineExecutor",
    "ExecutionState",
    "PREDEFINED_STATES",
]
