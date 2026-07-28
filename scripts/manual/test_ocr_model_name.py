#!/usr/bin/env python3
"""Check if ONNX models are valid and test pipeline OCR with model name."""

import sys, os
from pathlib import Path
sys.path.insert(0, 'src')
os.environ['MAAFW_BINARY_PATH'] = str(Path('3rd-part/maaend/agent/maafw').resolve())

# 1. Check ONNX model validity
import onnxruntime
print("=== Check ONNX models ===")
model_dir = Path('3rd-part/maaend/resource/model/ocr')
for f in ["det.onnx", "rec.onnx"]:
    model_path = model_dir / f
    try:
        session = onnxruntime.InferenceSession(str(model_path))
        print(f"{f}: VALID - inputs={[i.name for i in session.get_inputs()]}, outputs={[o.name for o in session.get_outputs()]}")
        del session
    except Exception as e:
        print(f"{f}: INVALID - {e}")

# 2. Test pipeline OCR with explicit model name "ocr" (directory name)
print("\n=== Pipeline OCR with model='ocr' ===")
from maa.resource import Resource
from maa.controller import AdbController
from maa.tasker import Tasker
from maa.define import MaaAdbScreencapMethodEnum, MaaAdbInputMethodEnum

resource = Resource()
ctrl = AdbController(
    adb_path=Path('C:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/3rd-part/adb/adb.exe'),
    address='127.0.0.1:16416',
    screencap_methods=int(MaaAdbScreencapMethodEnum.Default),
    input_methods=int(MaaAdbInputMethodEnum.Maatouch),
    config={},
)
job = ctrl.post_connection()
job.wait()
print(f"Connected: {job.succeeded}")

# Load pipelines
bundle = resource.post_bundle(Path('3rd-part/maaend/resource'))
bundle.wait()
print(f"Bundle: {bundle.succeeded}")

# Load OCR model
import time
ocr_job = resource.post_ocr_model(Path('3rd-part/maaend/resource/model/ocr'))
time.sleep(2)
print(f"OCR model loaded: {ocr_job.succeeded}")

# Bind
tasker = Tasker()
tasker.bind(resource, ctrl)
print(f"Tasker inited: {tasker.inited}")

# Take screenshot
sc = ctrl.post_screencap()
sc.wait()
img = ctrl.cached_image
print(f"Screenshot: {img.shape}")

# Test pipeline OCR with model='ocr'
print("\n--- Pipeline OCR with model='ocr' ---")
pipeline_ocr_model = {
    "TestOCRPipeline": {
        "recognition": {
            "type": "OCR",
            "param": {
                "roi": [400, 200, 600, 300],
                "expected": ["开始游戏", "Start Game"],
                "model": "ocr",  # Directory name
            },
        },
        "action": {"type": "DoNothing"},
        "next": [],
    }
}
pjob = tasker.post_task("TestOCRPipeline", pipeline_ocr_model)
pjob.wait()
detail = pjob.get()
print(f"succeeded: {pjob.succeeded}")
if detail:
    for n in detail.nodes:
        print(f"  Node: '{n.name}', completed={n.completed}")
        if n.recognition:
            print(f"    hit={n.recognition.hit}, algorithm={n.recognition.algorithm}")
            if n.recognition.best_result:
                print(f"    best: text='{n.recognition.best_result.text}', score={n.recognition.best_result.score}")
            for r in n.recognition.all_results[:3]:
                print(f"    result: text='{r.text}', box={r.box}, score={r.score}")

# Test with model='' (default)
print("\n--- Pipeline OCR with model='' ---")
pipeline_default = {
    "TestOCRPipeline2": {
        "recognition": {
            "type": "OCR",
            "param": {
                "roi": [400, 200, 600, 300],
                "expected": ["开始游戏", "Start Game"],
            },
        },
        "action": {"type": "DoNothing"},
        "next": [],
    }
}
pjob2 = tasker.post_task("TestOCRPipeline2", pipeline_default)
pjob2.wait()
detail2 = pjob2.get()
print(f"succeeded: {pjob2.succeeded}")
if detail2:
    for n in detail2.nodes:
        print(f"  Node: '{n.name}', completed={n.completed}")
        if n.recognition:
            print(f"    hit={n.recognition.hit}, algorithm={n.recognition.algorithm}")

print("\nDone!")
