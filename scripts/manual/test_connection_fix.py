#!/usr/bin/env python3
"""Test raw connection with new v5.12.2 DLLs + pipeline OCR."""

import os, sys, time
from pathlib import Path

_bin = Path(__file__).resolve().parent.parent / "3rd-part" / "python" / "Lib" / "site-packages" / "maa" / "bin"
os.environ["MAAFW_BINARY_PATH"] = str(_bin)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

print(f"DLLs: {_bin}")
from maa.resource import Resource
from maa.controller import AdbController
from maa.tasker import Tasker
from maa.define import MaaAdbScreencapMethodEnum, MaaAdbInputMethodEnum

root = Path(__file__).resolve().parent.parent

# Test 1: Raw connection with Maatouch
print("\n=== Test 1: Raw Maatouch ===")
resource = Resource()
ctrl = AdbController(adb_path=root/"3rd-part"/"adb"/"adb.exe", address="127.0.0.1:16416",
    screencap_methods=int(MaaAdbScreencapMethodEnum.Default),
    input_methods=int(MaaAdbInputMethodEnum.Maatouch), config={})
j1 = ctrl.post_connection()
j1.wait()
print(f"  Connected: {j1.succeeded}")
if j1.succeeded:
    sc = ctrl.post_screencap()
    sc.wait()
    img = ctrl.cached_image
    print(f"  Screenshot: {img.shape}")

# Test 2: Load resource and OCR model
print("\n=== Test 2: Load resources ===")
resource.post_bundle(root/"3rd-part"/"maaend"/"resource").wait()
ocr_job = resource.post_ocr_model(root/"3rd-part"/"maaend"/"resource"/"model"/"ocr")
time.sleep(2)
print(f"  OCR model: {ocr_job.succeeded}")

# Test 3: Bind and test OCR pipeline
print("\n=== Test 3: Pipeline OCR (via resource.override_pipeline) ===")
tasker = Tasker()
tasker.bind(resource, ctrl)
print(f"  Tasker inited: {tasker.inited}")

resource.override_pipeline({
    "TestOCRSimple": {
        "recognition": {"type": "OCR", "param": {"roi": [0,0,1280,720], "expected": ["知","提示"]}},
        "action": {"type": "DoNothing"},
        "rate_limit": 100,
        "timeout": 5000,
        "next": []
    }
})
j3 = tasker.post_task("TestOCRSimple", {})
j3.wait()
d3 = j3.get()
print(f"  succeeded: {j3.succeeded}")
if d3 and d3.nodes:
    for n in d3.nodes:
        print(f'  Node: name="{n.name}", completed={n.completed}')
        if n.recognition:
            print(f"    hit={n.recognition.hit} results={len(n.recognition.all_results)}")
            for ar in n.recognition.all_results[:3]:
                print(f'    "{ar.text}" score={ar.score:.3f}')

print("\nDone!")
