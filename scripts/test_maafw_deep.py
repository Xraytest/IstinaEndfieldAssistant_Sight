#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""娣卞害娴嬭瘯锛歁aaFw 鐐瑰嚮鏄惁鐪熺殑鍙戦€?ADB 鍛戒护"""
import sys, os, time, subprocess, hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT_ROOT / "3rd-part" / "python-packages"))

ADB = [str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"), "-s", "localhost:16512"]

def adb_screencap() -> bytes:
    r = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True, timeout=15)
    return r.stdout if r.returncode == 0 else b""

def adb_tap(x, y):
    r = subprocess.run(ADB + ["shell", "input", "tap", str(x), str(y)], capture_output=True, timeout=10)
    return r.returncode == 0

def hash_img(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()[:8] if data else "none"

# 鈹€鈹€ 鍒濆鍖?MaaFw 鈹€鈹€
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
            print(f"[MaaFw] 杩炴帴鎴愬姛, uuid={_maafw._uuid}")
        else:
            print("[MaaFw] 杩炴帴澶辫触")
            sys.exit(1)
except Exception as e:
    print(f"[MaaFw] 寮傚父: {e}")
    sys.exit(1)

print("\n=== 娴嬭瘯: 杩炵画鎴浘瑙傚療鑷劧鍙樺寲 ===")
for i in range(3):
    data = adb_screencap()
    print(f"  鎴浘 {i+1}: hash={hash_img(data)}, 澶у皬={len(data)}")
    time.sleep(1)

print("\n=== 娴嬭瘯: MaaFw click 鍚庢埅鍥?===")
# 鍏堟埅鍥?
before = adb_screencap()
print(f"  鐐瑰嚮鍓? hash={hash_img(before)}")

# MaaFw 鐐瑰嚮
print(f"  MaaFw click (800, 40)...")
t0 = time.time()
ok = _maafw.click(800, 40)
t1 = time.time()
print(f"  缁撴灉: {ok}, 鑰楁椂: {t1-t0:.2f}s")

time.sleep(3)  # 绛?UI 鍝嶅簲

after = adb_screencap()
print(f"  鐐瑰嚮鍚? hash={hash_img(after)}")
print(f"  鍙樺寲: {hash_img(before)} -> {hash_img(after)}")

print("\n=== 娴嬭瘯: 鐩存帴 ADB tap 鍚庢埅鍥?===")
before2 = adb_screencap()
print(f"  鐐瑰嚮鍓? hash={hash_img(before2)}")

print(f"  ADB tap (800, 40)...")
t0 = time.time()
ok = adb_tap(800, 40)
t1 = time.time()
print(f"  缁撴灉: {ok}, 鑰楁椂: {t1-t0:.2f}s")

time.sleep(3)

after2 = adb_screencap()
print(f"  鐐瑰嚮鍚? hash={hash_img(after2)}")
print(f"  鍙樺寲: {hash_img(before2)} -> {hash_img(after2)}")

print("\n=== 瀵规瘮鍒嗘瀽 ===")
# 濡傛灉 MaaFw 鍜?ADB 閮界偣鍑诲悓涓€浣嶇疆锛岀粨鏋滃簲璇ョ浉浼?
# 濡傛灉 MaaFw 鐐瑰嚮娌＄敓鏁堬紝MaaFw 鍓嶅悗鐨?hash 鍙樺寲搴旇鍜岃嚜鐒跺彉鍖栦竴鏍峰皬
# 鑰?ADB tap 鍓嶅悗鐨?hash 鍙樺寲搴旇鏇村ぇ锛堝洜涓?UI 鍙樺寲锛?

# 璁＄畻鑷劧鍙樺寲骞呭害
print("娉ㄦ剰锛氬鏋?MaaFw 鐐瑰嚮鍚庢埅鍥句笌鐐瑰嚮鍓嶅嚑涔庣浉鍚岋紙浠呭姩鐢诲櫔澹帮級锛?)
print("鑰?ADB tap 鍚庢埅鍥炬槑鏄句笉鍚岋紙UI 瀵艰埅锛夛紝鍒欒鏄?MaaFw 鐐瑰嚮鏈敓鏁堛€?)
