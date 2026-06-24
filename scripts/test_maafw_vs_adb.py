#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""瀵规瘮娴嬭瘯锛歁aaFw click vs 鐩存帴 ADB tap"""
import sys, os, time, subprocess, hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT_ROOT / "3rd-part" / "python-packages"))

ADB = [str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe")]
DEVICE = "localhost:16512"

def adb_screencap() -> bytes:
    r = subprocess.run(ADB + ["-s", DEVICE, "exec-out", "screencap", "-p"], capture_output=True, timeout=15)
    return r.stdout if r.returncode == 0 else b""

def adb_tap(x, y):
    r = subprocess.run(ADB + ["-s", DEVICE, "shell", "input", "tap", str(x), str(y)], capture_output=True, timeout=10)
    return r.returncode == 0

def screenshot_hash(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()[:8] if data else "none"

# 鈹€鈹€ 鍒濆鍖?MaaFw 鈹€鈹€
_maafw = None
try:
    from core.capability.device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig, MAAFW_AVAILABLE
    if MAAFW_AVAILABLE:
        cfg = MaaFwTouchConfig(
            adb_path=str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"),
            address=DEVICE,
            screencap_methods=MaaFwTouchConfig.SCREENCAP_ADB_SHELL,
            input_methods=MaaFwTouchConfig.INPUT_ADB_SHELL,
        )
        _maafw = MaaFwTouchExecutor(cfg)
        if _maafw.connect():
            print(f"[MaaFw] 杩炴帴鎴愬姛, uuid={_maafw._uuid}, 鍒嗚鲸鐜?{_maafw.get_resolution()}")
        else:
            print("[MaaFw] 杩炴帴澶辫触")
except Exception as e:
    print(f"[MaaFw] 寮傚父: {e}")

print("\n=== 娴嬭瘯 1: 鐩存帴 ADB tap ===")
s1 = adb_screencap()
print(f"  鎴浘1 hash: {screenshot_hash(s1)} ({len(s1)} bytes)")
print(f"  ADB tap (540, 960)...")
t0 = time.time()
ok = adb_tap(540, 960)
t1 = time.time()
print(f"  缁撴灉: {ok} | 鑰楁椂: {t1-t0:.2f}s")
time.sleep(2)
s2 = adb_screencap()
print(f"  鎴浘2 hash: {screenshot_hash(s2)} ({len(s2)} bytes)")
print(f"  鐢婚潰鍙樺寲: {screenshot_hash(s1)} -> {screenshot_hash(s2)}")

print("\n=== 娴嬭瘯 2: MaaFw click ===")
s3 = adb_screencap()
print(f"  鎴浘3 hash: {screenshot_hash(s3)} ({len(s3)} bytes)")
print(f"  MaaFw click (800, 40)...")
t0 = time.time()
if _maafw and _maafw.connected:
    ok = _maafw.click(800, 40)
else:
    ok = False
t1 = time.time()
print(f"  缁撴灉: {ok} | 鑰楁椂: {t1-t0:.2f}s")
time.sleep(2)
s4 = adb_screencap()
print(f"  鎴浘4 hash: {screenshot_hash(s4)} ({len(s4)} bytes)")
print(f"  鐢婚潰鍙樺寲: {screenshot_hash(s3)} -> {screenshot_hash(s4)}")

print("\n=== 娴嬭瘯 3: MaaFw swipe ===")
s5 = adb_screencap()
print(f"  鎴浘5 hash: {screenshot_hash(s5)} ({len(s5)} bytes)")
print(f"  MaaFw swipe (540,960)->(540,100)...")
t0 = time.time()
if _maafw and _maafw.connected:
    ok = _maafw.swipe(540, 960, 540, 100, 500)
else:
    ok = False
t1 = time.time()
print(f"  缁撴灉: {ok} | 鑰楁椂: {t1-t0:.2f}s")
time.sleep(2)
s6 = adb_screencap()
print(f"  鎴浘6 hash: {screenshot_hash(s6)} ({len(s6)} bytes)")
print(f"  鐢婚潰鍙樺寲: {screenshot_hash(s5)} -> {screenshot_hash(s6)}")

print("\n=== 缁撹 ===")
print(f"ADB tap 鐢婚潰鍙樺寲: {screenshot_hash(s1)} -> {screenshot_hash(s2)}")
print(f"MaaFw click 鐢婚潰鍙樺寲: {screenshot_hash(s3)} -> {screenshot_hash(s4)}")
print(f"MaaFw swipe 鐢婚潰鍙樺寲: {screenshot_hash(s5)} -> {screenshot_hash(s6)}")
