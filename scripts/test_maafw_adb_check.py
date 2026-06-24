#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""妫€鏌?MaaFw 浣跨敤鐨?ADB 杩炴帴"""
import sys, os, time, subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT_ROOT / "3rd-part" / "python-packages"))

ADB = [str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe")]

# 杩炴帴鍓嶆鏌ヨ澶?
print("=== 杩炴帴鍓?ADB 璁惧 ===")
r = subprocess.run(ADB + ["devices"], capture_output=True, timeout=10)
print(r.stdout.decode())

# 鍒濆鍖?MaaFw
_maafw = None
try:
    from core.capability.device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig, MAAFW_AVAILABLE
    if MAAFW_AVAILABLE:
        cfg = MaaFwTouchConfig(
            adb_path=str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"),
            address="localhost:16512",
            screencap_methods=MaaFwTouchConfig.SCREENCAP_ADB_SHELL,
            input_methods=MaaFwTouchConfig.INPUT_ADB_SHELL,
        )
        _maafw = MaaFwTouchExecutor(cfg)
        if _maafw.connect():
            print(f"\n[MaaFw] 杩炴帴鎴愬姛, uuid={_maafw._uuid}")
        else:
            print("[MaaFw] 杩炴帴澶辫触")
            sys.exit(1)
except Exception as e:
    print(f"[MaaFw] 寮傚父: {e}")
    sys.exit(1)

# 杩炴帴鍚庢鏌ヨ澶?
print("\n=== 杩炴帴鍚?ADB 璁惧 ===")
r = subprocess.run(ADB + ["devices"], capture_output=True, timeout=10)
print(r.stdout.decode())

# 妫€鏌?MaaFw 鍐呴儴浣跨敤鐨?ADB 璺緞
print(f"=== MaaFw 鍐呴儴鐘舵€?===")
print(f"  adb_path: {_maafw.config.adb_path}")
print(f"  address: {_maafw.config.address}")
print(f"  screencap_methods: {_maafw.config.screencap_methods}")
print(f"  input_methods: {_maafw.config.input_methods}")
print(f"  connected: {_maafw.connected}")
print(f"  resolution: {_maafw.get_resolution()}")

# 娴嬭瘯锛氱敤 MaaFw 鐐瑰嚮鍚庯紝妫€鏌?ADB 鏄惁鏈夋柊杩炴帴
print("\n=== 娴嬭瘯 MaaFw 鐐瑰嚮 ===")
print("鐐瑰嚮 (800, 40)...")
t0 = time.time()
ok = _maafw.click(800, 40)
t1 = time.time()
print(f"  缁撴灉: {ok}, 鑰楁椂: {t1-t0:.2f}s")

# 鍐嶆鏌ヨ澶?
print("\n=== 鐐瑰嚮鍚?ADB 璁惧 ===")
r = subprocess.run(ADB + ["devices"], capture_output=True, timeout=10)
print(r.stdout.decode())

# 妫€鏌?ADB 鐗堟湰
print("=== ADB 鐗堟湰 ===")
r = subprocess.run(ADB + ["version"], capture_output=True, timeout=10)
print(r.stdout.decode()[:200])
