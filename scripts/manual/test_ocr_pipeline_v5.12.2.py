#!/usr/bin/env python3
"""Test pipeline OCR with new v5.12.2 DLLs."""

import os, sys, time, threading
from pathlib import Path

# Point to the new site-packages DLLs
_bin = Path(__file__).resolve().parent.parent / "3rd-part" / "python" / "Lib" / "site-packages" / "maa" / "bin"
os.environ["MAAFW_BINARY_PATH"] = str(_bin)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

print(f"DLLs from: {_bin}")
print(f"MaaFramework.dll: {os.path.getsize(_bin / 'MaaFramework.dll'):,} bytes")

from maa.resource import Resource
from maa.controller import AdbController
from maa.tasker import Tasker
from maa.define import MaaAdbScreencapMethodEnum, MaaAdbInputMethodEnum
from maa.pipeline import JOCR, JRecognitionType

root = Path(__file__).resolve().parent.parent

# Connect
resource = Resource()
ctrl = AdbController(adb_path=root/"3rd-part"/"adb"/"adb.exe", address="127.0.0.1:16416",
    screencap_methods=int(MaaAdbScreencapMethodEnum.Default),
    input_methods=int(MaaAdbInputMethodEnum.Maatouch), config={})
ctrl.post_connection().wait()
print(f"Connected: True")

# Load pipeline resources
resource.post_bundle(root/"3rd-part"/"maaend"/"resource").wait()
print(f"Pipeline loaded: True")

# Load OCR model explicitly
ocr_job = resource.post_ocr_model(root/"3rd-part"/"maaend"/"resource"/"model"/"ocr")
time.sleep(2)
print(f"OCR model loaded: {ocr_job.succeeded}")

# Bind tasker
tasker = Tasker()
tasker.bind(resource, ctrl)
print(f"Tasker inited: {tasker.inited}")

# Take screenshot
sc = ctrl.post_screencap()
sc.wait()
img = ctrl.cached_image
print(f"Screenshot: {img.shape}")

# Test direct post_recognition
print("\n=== Direct post_recognition ===")
ocr_param = JOCR(expected=["开始游戏", "Start Game"], roi=[400,200,600,300], threshold=0.3)
pjob = tasker.post_recognition(JRecognitionType.OCR, ocr_param, img)
detail = pjob.wait().get()
print(f"succeeded: {pjob.succeeded}")
if detail:
    for n in detail.nodes:
        if n.recognition:
            r = n.recognition
            print(f"  hit={r.hit}, all_results={len(r.all_results)}")
            for ar in r.all_results[:5]:
                print(f'  "{ar.text}" score={ar.score:.3f} box={ar.box}')

# Test pipeline OCR
print("\n=== Pipeline OCR ===")
pipeline = {
    "TestOCRPipeline": {
        "recognition": {"type": "OCR", "param": {
            "roi": [400, 200, 600, 300],
            "expected": ["开始游戏", "Start Game", "点击开始"],
        }},
        "action": {"type": "DoNothing"},
        "next": []
    }
}
pjob2 = tasker.post_task("TestOCRPipeline", pipeline)
pjob2.wait()
detail2 = pjob2.get()
print(f"succeeded: {pjob2.succeeded}")
if detail2 and detail2.nodes:
    for n in detail2.nodes:
        print(f'  Node: name="{n.name}", completed={n.completed}')
        if n.recognition:
            r = n.recognition
            print(f"    hit={r.hit}, algorithm={r.algorithm}, all_results={len(r.all_results)}")
            if r.best_result:
                print(f'    best: text="{r.best_result.text}" score={r.best_result.score:.3f}')
            for ar in r.all_results[:5]:
                print(f'    "{ar.text}" score={ar.score:.3f} box={ar.box}')
        if n.action:
            a = n.action
            print(f"    action: type={a.action}, success={a.success}")
else:
    print(f"  No nodes! detail={detail2}")

# Test real pipeline node from the project: CheckIn
print("\n=== Pre-built LoginFailed OCR node ===")
pjob3 = tasker.post_task("LoginFailed", {})
# Timeout after 10s
tbox = {"done": False, "detail": None}
def wait3():
    pjob3.wait()
    tbox["detail"] = pjob3.get()
    tbox["done"] = True
t = threading.Thread(target=wait3, daemon=True)
t.start()
t.join(timeout=10)
if tbox["done"]:
    d3 = tbox["detail"]
    print(f"succeeded: {pjob3.succeeded}")
    if d3 and d3.nodes:
        for n in d3.nodes:
            print(f'  Node: name="{n.name}", completed={n.completed}')
            if n.recognition:
                print(f"    hit={n.recognition.hit}")
else:
    print("  Timed out")

print("\nDone!")
