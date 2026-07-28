#!/usr/bin/env python3
"""Full queue test with all fixes applied."""
import os, sys, json
from pathlib import Path

_bin = Path(__file__).resolve().parent.parent / "3rd-part" / "python" / "Lib" / "site-packages" / "maa" / "bin"
os.environ["MAAFW_BINARY_PATH"] = str(_bin)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.service.maa_end.runtime import MaaEndRuntime
from core.foundation.logger import get_logger

logger = get_logger()
root = Path(__file__).resolve().parent.parent

# 1. Connect
rt = MaaEndRuntime(device_address="127.0.0.1:16416")
ok = rt.connect()
print(f"Connect: {ok}")
if not ok:
    sys.exit(1)

# 2. Load resources
ok = rt.load_resource()
print(f"Load resource: {ok}")
if not ok:
    sys.exit(1)

# 3. Load queue from state file
state = json.loads((root / "config" / "maaend_task_state.json").read_text("utf-8"))
items = state.get("queue_items", [])
print(f"Queue items: {len(items)}")

for item in items:
    name = item.get("name")
    options = item.get("options", {})
    if name:
        rt.add_task(name, options)
        print(f"  Added: {name}")

# 4. Run queue
print("\n--- Running queue ---")
ok = rt.run_queue()
print(f"\nQueue result: {ok}")
sys.exit(0 if ok else 1)
