"""
Endfield element recognition backends.
"""

from .template_backend import TemplateBackend
from .ocr_backend import OCRBackend
from .color_backend import ColorBackend
from .yolo_backend import YOLOBackend

__all__ = [
    "TemplateBackend",
    "OCRBackend",
    "ColorBackend",
    "YOLOBackend",
]
