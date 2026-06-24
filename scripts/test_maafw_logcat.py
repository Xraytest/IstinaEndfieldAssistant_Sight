#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""妫€鏌?MaaFw 鐐瑰嚮鏄惁鐪熺殑鍙戦€?input tap"""
import sys, os, time, subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT_ROOT / "3rd-part" / "python-packages"))

ADB = [str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"), "-s", "localhost:16512"]

# 鍒濆鍖?MaaFw
from core.capability.device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig, MAAFW_AVAILABLE
cfg = MaaFwTouchConfig(
    adb_path=str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"),
    address="localhost:16512",
    screencap_methods=MaaFwTouchConfig.SCREENCAP_ADB_SHELL,
    input_methods=MaaFwTouchConfig.INPUT_ADB_SHELL,
)
_maafw = MaaFwTouchExecutor(cfg)
if not _maafw.connect():
    print("MaaFw 杩炴帴澶辫触")
    sys.exit(1)
print(f"MaaFw 杩炴帴鎴愬姛, uuid={_maafw._uuid}")

# 娓呯┖ logcat
subprocess.run(ADB + ["logcat", "-c"], capture_output=True, timeout=5)
time.sleep(0.5)

# 鎵ц MaaFw 鐐瑰嚮
print("\n鎵ц MaaFw click (800, 40)...")
t0 = time.time()
ok = _maafw.click(800, 40)
t1 = time.time()
print(f"缁撴灉: {ok}, 鑰楁椂: {t1-t0:.2f}s")

time.sleep(1)

# 妫€鏌?logcat 涓槸鍚︽湁 input 鐩稿叧鏃ュ織
r = subprocess.run(ADB + ["logcat", "-d"], capture_output=True, timeout=5, text=True)
input_lines = [l for l in r.stdout.split("\n") if "input" in l.lower() or "tap" in l.lower()]
print(f"\n鎵惧埌 {len(input_lines)} 鏉?input/tap 鐩稿叧鏃ュ織:")
for l in input_lines[-10:]:
    print(f"  {l[:200]}")

# 涔熸鏌ョ洿鎺?ADB tap 鐨勫姣?
print("\n=== 瀵规瘮: 鐩存帴 ADB tap ===")
subprocess.run(ADB + ["logcat", "-c"], capture_output=True, timeout=5)
time.sleep(0.5)

print("鎵ц ADB tap (800, 40)...")
t0 = time.time()
subprocess.run(ADB + ["shell", "input", "tap", "800", "40"], capture_output=True, timeout=10)
t1 = time.time()
print(f"鑰楁椂: {t1-t0:.2f}s")

time.sleep(1)

r = subprocess.run(ADB + ["logcat", "-d"], capture_output=True, timeout=5, text=True)
input_lines2 = [l for l in r.stdout.split("\n") if "input" in l.lower() or "tap" in l.lower()]
print(f"鎵惧埌 {len(input_lines2)} 鏉?input/tap 鐩稿叧鏃ュ織:")
for l in input_lines2[-10:]:
    print(f"  {l[:200]}")
