"""
OCR 模块 - 统一管理 OCR 采集和屏幕决策

提供 MaaEnd 式的 OCR 优先决策机制，替代 VLM 图像输入。
"""

from .ocr_manager import OCRManager
from .screen_decider import ScreenDecider, ScreenState

__all__ = ['OCRManager', 'ScreenDecider', 'ScreenState']
