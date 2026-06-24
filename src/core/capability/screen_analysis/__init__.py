"""屏幕分析模块 — 多特征游戏画面分析

提供 GameScreenAnalyzer 用于基于 OpenCV 的多特征画面状态检测。
"""

from .advanced_analyzer import (
    PageType,
    SpatialFeatures,
    ColorFeatures,
    TextureFeatures,
    TemplateMatchResult,
    PageAnalysisResult,
    GameScreenAnalyzer,
)

__all__ = [
    "PageType",
    "SpatialFeatures",
    "ColorFeatures",
    "TextureFeatures",
    "TemplateMatchResult",
    "PageAnalysisResult",
    "GameScreenAnalyzer",
]
