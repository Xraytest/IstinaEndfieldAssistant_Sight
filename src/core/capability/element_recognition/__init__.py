"""
终末地画面元素识别模块 — 统一识别入口

提供 EndfieldElementRecognizer：整合模板匹配、OCR、颜色匹配、YOLO 检测
到一个统一接口，输出 ElementInfo + PageInfo。

架构分层::

    ElementRecognizer
      ├── Backends (模板/OCR/颜色/YOLO)
      │     └── TemplateBackend
      │           └── Pipeline 模块化框架
      │                 ├── TemplateRegistry (单例模板管理)
      │                 ├── TemplateMatcher  (OpenCV 匹配)
      │                 ├── PipelineLoader   (管道节点加载)
      │                 └── PipelineRunner   (管道执行)
      ├── Pipeline (独立运行)
      └── Tasks (任务编排)

使用方式::

    from src.core.capability.element_recognition import EndfieldElementRecognizer

    recognizer = EndfieldElementRecognizer()
    page = recognizer.recognize(screen)

    for elem in page.elements:
        print(f"{elem.source}: {elem.label} at {elem.center}")

    print(f"Page: {page.page_type} ({page.confidence:.2f})")

    # 模块化 Pipeline
    from src.core.capability.element_recognition.pipeline import (
        TemplateRegistry, PipelineLoader, PipelineRunner
    )
    registry = TemplateRegistry()
    registry.load_module("Common")
    pipeline_runner = PipelineRunner(registry)
"""
from .element_info import ElementInfo, PageInfo, ELEMENT_TYPES, PAGE_TYPES
from .recognizer import EndfieldElementRecognizer
from .scene_service import SceneUnderstandingService

__all__ = [
    "ElementInfo",
    "PageInfo",
    "ELEMENT_TYPES",
    "PAGE_TYPES",
    "EndfieldElementRecognizer",
    "SceneUnderstandingService",
]
