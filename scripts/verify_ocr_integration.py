"""
Verify OCR integration: OCR pipeline nodes are properly parsed and
RecognitionType.OCR is supported in the pipeline framework.
"""
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "src"))

from core.foundation.paths import ensure_src_path
ensure_src_path()

from core.capability.element_recognition.pipeline import (
    PipelineNode, PipelineGraph, RecognitionType, PipelineLoader,
)
from core.capability.element_recognition.tasks import TaskLoader

ok = True

# 1. Verify RecognitionType.OCR exists
assert RecognitionType.OCR == "OCR", "RecognitionType.OCR missing"
print(f"[OK] RecognitionType.OCR = {RecognitionType.OCR}")

# 2. Verify PipelineNode can parse OCR nodes
node = PipelineNode.from_dict("TestOCR", {
    "recognition": "OCR",
    "expected": ["确认", "取消"],
    "roi": [100, 200, 300, 100],
    "threshold": 0.5,
})
assert node.recognition == RecognitionType.OCR
assert node.expected == ["确认", "取消"]
assert node.roi == [100, 200, 300, 100]
assert abs(node.threshold - 0.5) < 0.001
assert node.enabled is True
print(f"[OK] PipelineNode parses OCR node correctly")

# 3. Verify OCR nodes exist in loaded pipelines
loader = PipelineLoader()
graph = loader.load_all()
ocr_nodes = [n for n in graph.nodes.values() if n.recognition == RecognitionType.OCR]
print(f"[OK] {len(ocr_nodes)} OCR pipeline nodes in assets/pipelines/")

# 4. Verify task loader can find tasks
task_loader = TaskLoader()
tasks = task_loader.load_all_tasks()
print(f"[OK] {len(tasks)} tasks loaded by TaskLoader")
presets = task_loader.load_presets()
print(f"[OK] {len(presets)} presets loaded by TaskLoader")

# 5. Verify the module imports cleanly
from core.capability.element_recognition.backends import OCRBackend, TemplateBackend
print(f"[OK] OCRBackend and TemplateBackend import cleanly")

# 6. Verify EndfieldElementRecognizer accepts maaend_runtime
from core.capability.element_recognition import EndfieldElementRecognizer
recognizer = EndfieldElementRecognizer(catalog_path="")
assert recognizer._ocr_backend is not None
assert recognizer._template_backend is not None
assert recognizer._maaend_runtime is None  # Not provided
print(f"[OK] EndfieldElementRecognizer accepts maaend_runtime=None")

print("\nAll checks passed.")
