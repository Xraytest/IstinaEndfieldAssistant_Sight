#!/usr/bin/env python3
"""Deep diagnosis of MaaFW pipeline OCR failure."""

import sys, os, time
from pathlib import Path

_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
sys.path.insert(0, str(_project_root / "src"))

os.environ.setdefault("MAAFW_BINARY_PATH", str(_project_root / "3rd-part" / "maaend" / "agent" / "maafw"))
print(f"MAAFW_BINARY_PATH = {os.environ['MAAFW_BINARY_PATH']}")
print(f"MaaFW version: ", end='', flush=True)

from maa.library import Library
print(Library.version())

from maa.resource import Resource, ResourceEventSink
from maa.controller import AdbController
from maa.tasker import Tasker
from maa.pipeline import JOCR, JRecognitionType
from maa.define import *
from maa.toolkit import Toolkit

# 1. Init toolkit for config
print("\n=== 1. Init toolkit ===")
Toolkit.init_option(str(_project_root / "3rd-part" / "maaend" / "config"))
print("Toolkit done")

# 2. Set save on error / debug mode
print("\n=== 2. Enable debug ===")
Tasker.set_save_draw(True)
Tasker.set_save_on_error(True)
Tasker.set_debug_mode(True)

# 3. Create resource with event monitoring
print("\n=== 3. Connecting controller ===")
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
print(f"Connected: {job.succeeded}")

# 4. Load pipeline resources
print("\n=== 4. Load pipeline resources ===")
bundle = resource.post_bundle(_project_root / "3rd-part" / "maaend" / "resource")
bundle.wait()
print(f"Pipeline loaded: {bundle.succeeded}")

# 5. Load OCR model explicitly
print("\n=== 5. Load OCR model ===")
model_dir = _project_root / "3rd-part" / "maaend" / "resource" / "model" / "ocr"
print(f"Model dir: {model_dir}")
print(f"det.onnx: {(model_dir / 'det.onnx').stat().st_size} bytes")
print(f"rec.onnx: {(model_dir / 'rec.onnx').stat().st_size} bytes")
ocr_job = resource.post_ocr_model(model_dir)
time.sleep(5)  # Wait extra for async loading
print(f"post_ocr_model status after wait: {ocr_job.succeeded}")

# Check node list to see if in-world scene is available
print("\n=== 6. Check resource state ===")
print(f"Resource loaded: {resource.loaded}")
all_nodes = resource.node_list
print(f"Total nodes: {len(all_nodes)}")

# Check if specific required nodes exist
for needed in ["InWorld", "SceneAnyEnterWorld", "EnterGame"]:
    has = needed in all_nodes
    print(f"  node '{needed}': {'YES' if has else 'NO'}")

# 7. Bind tasker
print("\n=== 7. Bind tasker ===")
tasker = Tasker()
tasker.bind(resource, ctrl)
print(f"Tasker inited: {tasker.inited}")

# 8. Test SceneAnyEnterWorld (the real pipeline that's failing in queue)
print("\n=== 8. Test SceneAnyEnterWorld pipeline ===")
pjob = tasker.post_task("SceneAnyEnterWorld", {})
pjob.wait()
detail = pjob.get()
print(f"succeeded: {pjob.succeeded}")
if detail:
    print(f"Task status: {detail.status}")
    print(f"Nodes: {len(detail.nodes)}")
    for i, node in enumerate(detail.nodes):
        print(f"  Node[{i}]: name='{node.name}', completed={node.completed}")
        if node.recognition:
            r = node.recognition
            print(f"    reco: type={r.algorithm}, hit={r.hit}, all={len(r.all_results)}")
            if r.best_result:
                print(f"    best: {r.best_result}")
        if node.action:
            a = node.action
            print(f"    action: type={a.action}, success={a.success}")

# 9. Test a known-good pipeline node that doesn't use OCR
print("\n=== 9. Test OpenGame pipeline (no OCR = should work) ===")
# Check if OpenGame node exists
open_game_pipeline = {
    "WaitCloseGameButton": {
        "recognition": {
            "type": "DirectHit",
            "param": {"roi": [0, 0, 69, 63]},
        },
        "action": {"type": "DoNothing"},
        "next": [],
    }
}
pjob2 = tasker.post_task("WaitCloseGameButton", open_game_pipeline)
pjob2.wait()
print(f"DirectHit pipeline: {pjob2.succeeded}")

# 10. Get node definition from resource to see expected format
print("\n=== 10. Check LoginFailed OCR node definition ===")
node_data = resource.get_node_data("LoginFailed")
if node_data:
    print(f"LoginFailed node exists")
    rec = node_data.get("recognition", {})
    print(f"  recognition type: {rec.get('type')}")
else:
    print("LoginFailed NOT found in resource")

# Also check InWorld node
inworld = resource.get_node_data("InWorld")
if inworld:
    print(f"InWorld node: {json.dumps(inworld, indent=2, ensure_ascii=False)[:500]}")
else:
    print("InWorld NOT found in resource")

import json
print("\n=== Done ===")
