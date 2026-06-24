"""能力层 — 可独立使用的功能模块

包含：adb_utils（ADB 工具）、device（设备控制）、local_inference（本地推理）、
ocr（OCR 识别）、recognition（多源融合识别）、screen_analysis（画面分析）、
screenshot（截图）、vlm（VLM 分析接口）
"""

from .adb_utils import ADB, adb_screencap, list_devices, _adb_cmd, check_device
from .device import ADBDeviceManager, TouchManager, TouchDeviceType
from .local_inference import (
    GPUChecker, LocalInferenceEngine, ModelManager, InferenceManager,
    PromptCache, AsyncInferenceWorker, AsyncInferenceManager,
    TaskPriority, TaskStatus, InferenceTask,
)
from .ocr import OCRManager, ScreenDecider, ScreenState
from .recognition import (
    RecognitionEngine, MaaFwPipelineOCR, StateMachineExecutor,
    ExecutionState, PREDEFINED_STATES,
)
from .input.screenshot import ScreenCapture
from .screen_analysis import (
    PageType,
    SpatialFeatures,
    ColorFeatures,
    TextureFeatures,
    TemplateMatchResult,
    PageAnalysisResult,
    GameScreenAnalyzer,
)
from .vlm import VLMOptions, vlm_analyze, GUIClient, create_gui_client

__all__ = [
    # adb_utils
    "ADB", "adb_screencap", "list_devices", "_adb_cmd", "check_device",
    # device
    "ADBDeviceManager", "TouchManager", "TouchDeviceType",
    # local_inference
    "GPUChecker", "LocalInferenceEngine", "ModelManager", "InferenceManager",
    "PromptCache", "AsyncInferenceWorker", "AsyncInferenceManager",
    "TaskPriority", "TaskStatus", "InferenceTask",
    # ocr
    "OCRManager", "ScreenDecider", "ScreenState",
    # recognition
    "RecognitionEngine", "MaaFwPipelineOCR", "StateMachineExecutor",
    "ExecutionState", "PREDEFINED_STATES",
    # screenshot
    "ScreenCapture",
    # screen_analysis
    "PageType", "SpatialFeatures", "ColorFeatures", "TextureFeatures",
    "TemplateMatchResult", "PageAnalysisResult", "GameScreenAnalyzer",
    # vlm
    "VLMOptions", "vlm_analyze", "GUIClient", "create_gui_client",
]