#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""妫€鏌?MaaFw 鍐呴儴鐘舵€佸拰 ADB 杩炴帴"""
import sys, json, subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT_ROOT / "3rd-part" / "python-packages"))

ADB = [str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"), "-s", "localhost:16512"]

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
print(f"MaaFw 鍒嗚鲸鐜? {_maafw.get_resolution()}")

# 鑾峰彇鎺у埗鍣ㄤ俊鎭?
if _maafw._controller:
    try:
        info = _maafw._controller.info
        print(f"\n鎺у埗鍣ㄤ俊鎭?")
        print(json.dumps(info, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"鎺у埗鍣ㄤ俊鎭幏鍙栧け璐? {e}")
    
    # 鑾峰彇鍘熷鍒嗚鲸鐜?
    try:
        res = _maafw._controller.resolution
        print(f"\ncontroller.resolution (鍘熷): {res}")
    except Exception as e:
        print(f"resolution 鑾峰彇澶辫触: {e}")
    
    # 妫€鏌ユ埅鍥剧紦瀛?
    try:
        img = _maafw._controller.cached_image
        if img is not None:
            print(f"cached_image 褰㈢姸: {img.shape} (HxWxC)")
    except Exception as e:
        print(f"cached_image 鑾峰彇澶辫触: {e}")

# 妫€鏌?ADB 璁惧
print("\n=== ADB 璁惧鍒楄〃 ===")
r = subprocess.run(ADB[:1] + ["devices"], capture_output=True, timeout=10)
print(r.stdout.decode())

# 妫€鏌?MaaFw 鏄惁鍦?ADB 涓垱寤轰簡棰濆杩炴帴
print("=== ADB 杩炴帴鐘舵€?===")
r = subprocess.run(ADB[:1] + ["shell", "dumpsys", "input"], capture_output=True, timeout=10)
out = r.stdout.decode(errors='replace')
# 鏌ユ壘 TouchStates
for l in out.split("\n"):
    if "TouchStates" in l or "touch" in l.lower():
        print(l.strip())

