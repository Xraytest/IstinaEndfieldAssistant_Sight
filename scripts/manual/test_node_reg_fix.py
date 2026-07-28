#!/usr/bin/env python3
"""Quick test of the NODE-REG-FIX: verify resource.override_pipeline + post_task."""

import os, sys, time
from pathlib import Path

_bin = Path(__file__).resolve().parent.parent / "3rd-part" / "python" / "Lib" / "site-packages" / "maa" / "bin"
os.environ["MAAFW_BINARY_PATH"] = str(_bin)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.service.maa_end.runtime import MaaEndRuntime
from core.foundation.logger import get_logger

logger = get_logger()

# 1. Create runtime and connect
rt = MaaEndRuntime(device_address="127.0.0.1:16416")
ok = rt.connect()
print(f"Connect: {ok}")

# 2. Load resources
ok = rt.load_resource()
print(f"Load resource: {ok}")

# 3. Test a simple pipeline with OCR
print("\n=== Test OCR pipeline via run_pipeline ===")
ok = rt.run_pipeline("TestOCRQuick", {
    "TestOCRQuick": {
        "recognition": {"type": "OCR", "param": {
            "roi": [0, 0, 1280, 720],
            "expected": ["知","提示"],
        }},
        "action": {"type": "DoNothing"},
        "next": []
    }
})
print(f"run_pipeline OCR result: {ok}")

# 4. Test the AndroidOpenGame CloudCN scenario
print("\n=== Test AndroidOpenGame with CloudCN override ===")
ok = rt.run_task("AndroidOpenGame", {"ClientVersion": "CloudCN"})
print(f"AndroidOpenGame(CloudCN): {ok}")

# 5. Test SceneAnyEnterWorld (was failing before)
print("\n=== Test SceneAnyEnterWorld ===")
ok = rt.run_pipeline("SceneAnyEnterWorld", {})
print(f"SceneAnyEnterWorld: {ok}")

print("\nDone!")
