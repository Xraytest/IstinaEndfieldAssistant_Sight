#!/usr/bin/env python3
"""Quick test: use OCR to find and click '拜访好友' button, then verify friend list reachable."""

import os, sys, json, time, subprocess
from pathlib import Path

_bin = Path(__file__).resolve().parent.parent / "3rd-part" / "python" / "Lib" / "site-packages" / "maa" / "bin"
os.environ["MAAFW_BINARY_PATH"] = str(_bin)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

root = Path(__file__).resolve().parent.parent
adb = root / "3rd-part" / "adb" / "adb.exe"
serial = "127.0.0.1:16416"

from core.service.maa_end.runtime import MaaEndRuntime

rt = MaaEndRuntime(device_address=serial, game_package="com.hypergryph.cloud.endfield")
rt.connect()
rt.load_resource()

# Load queue from state
state = json.loads((root / "config" / "maaend_task_state.json").read_text("utf-8"))
items = state.get("queue_items", [])
for item in items:
    rt.add_task(item["name"], item.get("options", {}))
print(f"Queue loaded: {len(items)} tasks")

# Run full queue
ok = rt.run_queue()
print(f"\n=== QUEUE RESULT: {ok} ===")
sys.exit(0 if ok else 1)
