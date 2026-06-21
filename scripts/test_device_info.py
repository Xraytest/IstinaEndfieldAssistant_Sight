#!/usr/bin/env python3
"""检查设备实际分辨率"""
import sys, subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ADB = [str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"), "-s", "localhost:16512"]

def run(cmd):
    r = subprocess.run(ADB + cmd, capture_output=True, timeout=10)
    return r.stdout.decode(errors='replace')

print("=== wm size ===")
print(run(["shell", "wm", "size"]))

print("=== wm density ===")
print(run(["shell", "wm", "density"]))

print("=== getevent -p (first 3000 chars) ===")
print(run(["shell", "getevent", "-p"])[:3000])

print("=== dumpsys display (mDisplayWidth/Height) ===")
out = run(["shell", "dumpsys", "display"])
for l in out.split("\n"):
    if "mDisplayWidth" in l or "mDisplayHeight" in l or "DisplayDeviceInfo" in l:
        print(l.strip())
