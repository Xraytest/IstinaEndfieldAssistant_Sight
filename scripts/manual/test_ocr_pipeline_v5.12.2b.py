#!/usr/bin/env python3
"""Test pipeline node resolution with v5.12.2."""

import os, sys, time, threading
from pathlib import Path

_bin = Path(__file__).resolve().parent.parent / "3rd-part" / "python" / "Lib" / "site-packages" / "maa" / "bin"
os.environ["MAAFW_BINARY_PATH"] = str(_bin)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from maa.resource import Resource
from maa.controller import AdbController
from maa.tasker import Tasker
from maa.define import MaaAdbScreencapMethodEnum, MaaAdbInputMethodEnum
from maa.pipeline import JOCR, JRecognitionType
import maa

root = Path(__file__).resolve().parent.parent

resource = Resource()
ctrl = AdbController(adb_path=root/"3rd-part"/"adb"/"adb.exe", address="127.0.0.1:16416",
    screencap_methods=int(MaaAdbScreencapMethodEnum.Default),
    input_methods=int(MaaAdbInputMethodEnum.Maatouch), config={})
ctrl.post_connection().wait()

resource.post_bundle(root/"3rd-part"/"maaend"/"resource").wait()
resource.post_ocr_model(root/"3rd-part"/"maaend"/"resource"/"model"/"ocr")
time.sleep(1)

tasker = Tasker()
tasker.bind(resource, ctrl)
print(f"Tasker inited: {tasker.inited}")

# Check all nodes registered
all_nodes = resource.node_list
print(f"Total nodes: {len(all_nodes)}")

# Test 1: DirectHit node (no OCR - baseline)
print("\n=== Test 1: DirectHit (no OCR) ===")
p1 = {"TestDH": {"recognition": {"type": "DirectHit", "param": {"roi": [0,0,100,100]}}, "action": {"type": "DoNothing"}, "next": []}}
j1 = tasker.post_task("TestDH", p1)
j1.wait()
d1 = j1.get()
print(f"succeeded: {j1.succeeded}")
if d1 and d1.nodes:
    for n in d1.nodes:
        print(f'  Node: name="{n.name}", completed={n.completed}, hit={n.recognition.hit if n.recognition else "N/A"}')

# Test 2: Use resource.override_pipeline FIRST, then post_task without override
print("\n=== Test 2: resource.override_pipeline before post_task ===")
resource.override_pipeline({
    "TestOCRBound": {
        "recognition": {"type": "OCR", "param": {"roi": [0,0,1280,720], "expected": ["知"]}},
        "action": {"type": "DoNothing"},
        "next": []
    }
})
# Verify the node exists now
bd_nodes = resource.node_list
has_test = "TestOCRBound" in bd_nodes
print(f"TestOCRBound in node_list: {has_test}")

j2 = tasker.post_task("TestOCRBound", {})
j2.wait()
d2 = j2.get()
print(f"succeeded: {j2.succeeded}")
if d2 and d2.nodes:
    for n in d2.nodes:
        print(f'  Node: name="{n.name}", completed={n.completed}')
        if n.recognition:
            r = n.recognition
            print(f'    hit={r.hit}, all_results={len(r.all_results)}, algorithm={r.algorithm}')
            for ar in r.all_results[:3]:
                print(f'    "{ar.text}" score={ar.score:.3f}')
        if n.action:
            print(f'    action: {n.action.action}, success={n.action.success}')

# Test 3: Override an existing pipeline node with OCR
print("\n=== Test 3: Override existing node (OpenGame nodes use next chain) ===")
# Use WaitCloseGameButton which is a TemplateMatch node
node_def = resource.get_node_data("WaitCloseGameButton")
print(f"WaitCloseGameButton original: {list(node_def.keys()) if node_def else 'NOT FOUND'}")

# Test 4: Check what InWorld looks like
print("\n=== Test 4: InWorld node def ===")
iw = resource.get_node_data("InWorld")
if iw:
    rec = iw.get("recognition", {})
    print(f"InWorld rec type: {rec.get('type', 'none')}")
    # Check if it's an And node with OCR sub-nodes
    param = rec.get("param", {})
    all_of = param.get("all_of", [])
    print(f"InWorld all_of items: {all_of[:3]}")
else:
    print("InWorld NOT FOUND in resource")
    # Search for it
    matching = [n for n in all_nodes if "nWorld" in n or "InWorld" in n]
    print(f"Similar nodes: {matching[:10]}")

# Test 5: Try running ClickContinue (has OCR but in the pre-bundled pipeline)
print("\n=== Test 5: ClickContinue (pre-built OCR node) ===")
cc_def = resource.get_node_data("ClickContinue")
if cc_def:
    print(f"ClickContinue found, keys: {list(cc_def.keys())}")
    j3 = tasker.post_task("ClickContinue", {})
    tbox = {"done": False}
    def w3():
        j3.wait()
        tbox["detail"] = j3.get()
        tbox["done"] = True
    t = threading.Thread(target=w3, daemon=True)
    t.start()
    t.join(timeout=15)
    if tbox["done"]:
        d3 = tbox["detail"]
        print(f"  succeeded: {j3.succeeded}")
        if d3 and d3.nodes:
            for n in d3.nodes:
                print(f'  Node: name="{n.name}", completed={n.completed}')
                if n.recognition:
                    print(f'    hit={n.recognition.hit} results={len(n.recognition.all_results)}')
    else:
        print("  Timed out (timeout or scan)")

# Test 6: Simple OCR with explicit timeout
print("\n=== Test 6: OCR node with rate_limit timeout ===")
p6 = {
    "TestOCRQuick": {
        "recognition": {"type": "OCR", "param": {"roi": [0,0,1280,720], "expected": ["知","提示"]}},
        "action": {"type": "DoNothing"},
        "rate_limit": 100,
        "timeout": 5000,
        "next": []
    }
}
j4 = tasker.post_task("TestOCRQuick", p6)
j4.wait()
d4 = j4.get()
print(f"succeeded: {j4.succeeded}")
if d4 and d4.nodes:
    for n in d4.nodes:
        print(f'  Node: name="{n.name}", completed={n.completed}')
        if n.recognition:
            print(f'    hit={n.recognition.hit} count={len(n.recognition.all_results)}')
            for ar in n.recognition.all_results[:3]:
                print(f'    "{ar.text}" score={ar.score:.3f}')
else:
    print(f"  No nodes! detail={d4}")

print("\nDone!")
