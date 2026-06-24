#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""娴嬭瘯 MaaFw 瑙︽帶鏄惁瀹為檯宸ヤ綔"""
import sys, os, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT_ROOT / "3rd-part" / "python-packages"))

ADB = [str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"), "-s", "localhost:16512"]

# 鈹€鈹€ MaaFw 鍒濆鍖?鈹€鈹€
_maafw = None
try:
    from core.capability.device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig, MAAFW_AVAILABLE
    if MAAFW_AVAILABLE:
        cfg = MaaFwTouchConfig(
            adb_path=str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"),
            address="localhost:16512",
            screencap_methods=MaaFwTouchConfig.SCREENCAP_ADB_SHELL,  # 鏄惧紡 AdbShell
            input_methods=MaaFwTouchConfig.INPUT_ADB_SHELL,  # 鏄惧紡 AdbShell
        )
        _maafw = MaaFwTouchExecutor(cfg)
        if _maafw.connect():
            print(f"[MaaFw] 杩炴帴鎴愬姛锛屽垎杈ㄧ巼: {_maafw.get_resolution()}")
        else:
            print("[MaaFw] 杩炴帴澶辫触")
            _maafw = None
    else:
        print("[MaaFw] MAAFW_AVAILABLE=False")
except Exception as e:
    print(f"[MaaFw] 寮傚父: {e}")
    _maafw = None

# 鈹€鈹€ 娴嬭瘯瑙︽帶 鈹€鈹€
if _maafw and _maafw.connected:
    print("\n=== 娴嬭瘯 MaaFw 鐐瑰嚮 ===")
    # 鐐瑰嚮灞忓箷涓ぎ (540, 960) - 妯℃嫙鍣?1080x1920
    print("鐐瑰嚮 (540, 960)...")
    t0 = time.time()
    result = _maafw.click(540, 960)
    elapsed = time.time() - t0
    print(f"  缁撴灉: {result} | 鑰楁椂: {elapsed:.2f}s")

    time.sleep(2)

    print("\n=== 娴嬭瘯 MaaFw 婊戝姩 ===")
    print("婊戝姩 (540,960) -> (540,100)...")
    t0 = time.time()
    result = _maafw.swipe(540, 960, 540, 100, 500)
    elapsed = time.time() - t0
    print(f"  缁撴灉: {result} | 鑰楁椂: {elapsed:.2f}s")

    time.sleep(2)

    print("\n=== 娴嬭瘯 MaaFw 闀挎寜 ===")
    print("闀挎寜 (540, 960) 1000ms...")
    t0 = time.time()
    result = _maafw.long_press(540, 960, 1000)
    elapsed = time.time() - t0
    print(f"  缁撴灉: {result} | 鑰楁椂: {elapsed:.2f}s")

    print("\n鉁?MaaFw 瑙︽帶娴嬭瘯瀹屾垚")
else:
    print("\n鉂?MaaFw 鏈繛鎺ワ紝璺宠繃瑙︽帶娴嬭瘯")
    # 鍥為€€锛氱敤 ADB 鐩存帴娴嬭瘯
    print("\n=== 鍥為€€: ADB 鐩存帴瑙︽帶娴嬭瘯 ===")
    import subprocess
    print("ADB tap (540, 960)...")
    subprocess.run(ADB + ["shell", "input", "tap", "540", "960"])
    print("  done")
