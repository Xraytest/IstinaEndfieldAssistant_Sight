#!/usr/bin/env python3
"""Compare post_recognition vs pipeline OCR to diagnose MaaFW pipeline OCR failure."""

import sys, os, time
from pathlib import Path

# Setup paths
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
sys.path.insert(0, str(_project_root / "src"))

os.environ.setdefault("MAAFW_BINARY_PATH", str(_project_root / "3rd-part" / "maaend" / "agent" / "maafw"))
print(f"MAAFW_BINARY_PATH = {os.environ['MAAFW_BINARY_PATH']}")

from maa.resource import Resource
from maa.controller import AdbController
from maa.tasker import Tasker
from maa.pipeline import JOCR, JRecognitionType, JRecognitionParam
from maa.define import MaaAdbScreencapMethodEnum, MaaAdbInputMethodEnum
from maa.job import Job

# 1. Connect controller
print("=" * 60)
print("1. Connecting controller...")
resource = Resource()
ctrl = AdbController(
    adb_path=Path(_project_root / "3rd-part" / "adb" / "adb.exe"),
    address="127.0.0.1:16416",
    screencap_methods=int(MaaAdbScreencapMethodEnum.Default),
    input_methods=int(MaaAdbInputMethodEnum.Maatouch),
    config={},
)
job = ctrl.post_connection()
job.wait()
print(f"  Connected: {job.succeeded}")

# 2. Load resources via post_bundle (standard way)
print("=" * 60)
print("2. Loading resources via post_bundle...")
bundle_job = resource.post_bundle(_project_root / "3rd-part" / "maaend" / "resource")
bundle_job.wait()
print(f"  Bundle loaded: {resource.loaded}")

# Also load ADB resources
adb_resource = _project_root / "3rd-part" / "maaend" / "resource_adb"
if adb_resource.exists():
    adb_job = resource.post_bundle(adb_resource)
    adb_job.wait()
    print(f"  ADB resource loaded: {resource.loaded}")

# 3. Explicitly load OCR model (test if this is needed)
print("=" * 60)
print("3. Explicitly loading OCR model...")
model_dir = _project_root / "3rd-part" / "maaend" / "resource" / "model" / "ocr"
print(f"  Model dir: {model_dir}")
print(f"  det.onnx exists: {(model_dir / 'det.onnx').exists()}")
print(f"  rec.onnx exists: {(model_dir / 'rec.onnx').exists()}")
print(f"  keys.txt exists: {(model_dir / 'keys.txt').exists()}")

ocr_model_job = resource.post_ocr_model(model_dir)
ocr_model_job.wait()
print(f"  post_ocr_model status: {ocr_model_job.succeeded}")

# 4. Check what nodes are registered
print("=" * 60)
print("4. Checking registered nodes...")
node_list = resource.node_list
print(f"  Total nodes: {len(node_list)}")
if len(node_list) < 10:
    print(f"  WARNING: Only {len(node_list)} nodes loaded - resource may not be fully loaded!")

# 5. Bind tasker
print("=" * 60)
print("5. Binding tasker...")
tasker = Tasker()
tasker.bind(resource, ctrl)
print(f"  Tasker inited: {tasker.inited}")

# 6. Take screenshot
print("=" * 60)
print("6. Taking screenshot...")
sc = ctrl.post_screencap()
sc.wait()
img = ctrl.cached_image
print(f"  Screenshot: shape={img.shape}, dtype={img.dtype}")

# 7. Test post_recognition (direct OCR call)
print("=" * 60)
print("7. Test post_recognition (Direct OCR call)...")
ocr_param = JOCR(
    expected=["开始游戏", "Start Game", "点击开始"],
    roi=[400, 200, 600, 300],
    threshold=0.3,
)
pjob = tasker.post_recognition(JRecognitionType.OCR, ocr_param, img)
detail = pjob.wait().get()
print(f"  succeeded: {pjob.succeeded}")
hit_nodes = []
if detail:
    for node in detail.nodes:
        if node.recognition:
            hit_nodes.append(node)
            print(f"  Node: {node.name}, hit={node.recognition.hit}")
            if node.recognition.hit:
                print(f"    algorithm: {node.recognition.algorithm}")
                print(f"    box: {node.recognition.box}")
                if node.recognition.best_result:
                    br = node.recognition.best_result
                    print(f"    best: text='{getattr(br, 'text', '?')}', score={br.score}")
                print(f"    all_results count: {len(node.recognition.all_results)}")
                for r in node.recognition.all_results:
                    print(f"      - text='{getattr(r, 'text', '?')}', box={r.box}, score={r.score}")
if not hit_nodes:
    print("  No recognition nodes in result (direct OCR returned no hits)")

# 8. Test pipeline OCR node (simulates what pipeline JSON does)
print("=" * 60)
print("8. Test pipeline OCR node...")
pipeline = {
    "TestOcrViaPipeline": {
        "recognition": {
            "type": "OCR",
            "param": {
                "roi": [400, 200, 600, 300],
                "expected": ["开始游戏", "Start Game", "点击开始"],
            },
        },
        "action": {"type": "DoNothing"},
        "next": [],
    }
}
pjob2 = tasker.post_task("TestOcrViaPipeline", pipeline)
detail2 = pjob2.wait().get()
print(f"  succeeded: {pjob2.succeeded}")
if detail2:
    print(f"  Task detail entry: {detail2.entry}")
    print(f"  Task status: {detail2.status}")
    print(f"  Nodes in result: {len(detail2.nodes)}")
    for node in detail2.nodes:
        print(f"  Node: {node.name}, completed={node.completed}")
        if node.recognition:
            rec = node.recognition
            print(f"    Recognition: hit={rec.hit}, algorithm={rec.algorithm}")
            if rec.best_result:
                br = rec.best_result
                print(f"    best: text='{getattr(br, 'text', '?')}', score={br.score}, box={br.box}")
            print(f"    all_results count: {len(rec.all_results)}")
            for r in rec.all_results[:3]:
                print(f"      - text='{getattr(r, 'text', '?')}', box={r.box}, score={r.score}")
        if node.action:
            act = node.action
            print(f"    Action: type={act.action}, success={act.success}")

# 9. Test pipeline OCR with explicit model field
print("=" * 60)
print("9. Test pipeline OCR with explicit model name...")
pipeline2 = {
    "TestOcrViaPipelineModel": {
        "recognition": {
            "type": "OCR",
            "param": {
                "roi": [400, 200, 600, 300],
                "expected": ["开始游戏", "Start Game", "点击开始"],
                "model": "PP-OCRv6",  # Try common model names
            },
        },
        "action": {"type": "DoNothing"},
        "next": [],
    }
}
pjob3 = tasker.post_task("TestOcrViaPipelineModel", pipeline2)
detail3 = pjob3.wait().get()
print(f"  succeeded: {pjob3.succeeded}")
if detail3:
    for node in detail3.nodes:
        if node.recognition:
            print(f"  Node: {node.name}, hit={node.recognition.hit}")

# 10. Test pipeline with DoNothing action and no recognition (trivial)
print("=" * 60)
print("10. Test minimal pipeline node (DirectHit)...")
pipeline3 = {
    "TestDirectHitNode": {
        "recognition": {
            "type": "DirectHit",
            "param": {
                "roi": [0, 0, 100, 100],
            },
        },
        "action": {"type": "DoNothing"},
        "next": [],
    }
}
pjob4 = tasker.post_task("TestDirectHitNode", pipeline3)
detail4 = pjob4.wait().get()
print(f"  succeeded: {pjob4.succeeded}")
if detail4:
    for node in detail4.nodes:
        if node.recognition:
            print(f"  Node: {node.name}, hit={node.recognition.hit}")

print("=" * 60)
print("Done!")
