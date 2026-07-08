"""
Endfield element recognition backends.
"""

from .color_backend import ColorBackend
from .ocr_backend import OCRBackend
from .template_backend import TemplateBackend
from .yolo_backend import YOLOBackend

__all__ = [
    "TemplateBackend",
    "OCRBackend",
    "ColorBackend",
    "YOLOBackend",
]
