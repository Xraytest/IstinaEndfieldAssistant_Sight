#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""鐢?getevent 妫€娴?MaaFw 鐐瑰嚮鏄惁浜х敓杈撳叆浜嬩欢"""
import sys, os, time, subprocess, threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT_ROOT / "3rd-part" / "python-packages"))

ADB_BASE = [str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"), "-s", "localhost:16512"]

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

# 娴嬭瘯 1: 鐢?getevent 鎹曡幏 MaaFw 鐐瑰嚮浜嬩欢
event_data = []
def capture_events(duration=3):
    """鍦ㄥ悗鍙版崟鑾疯緭鍏ヤ簨浠?""
    try:
        r = subprocess.run(
            ADB_BASE + ["shell", "getevent", "-t", "-l"],
            capture_output=True, timeout=duration, text=True
        )
        event_data.extend(r.stdout.split("\n"))
    except subprocess.TimeoutExpired as e:
        event_data.extend(e.output.decode(errors='replace').split("\n") if e.output else [])
    except Exception as e:
        event_data.append(f"Error: {e}")

print("\n=== 娴嬭瘯 1: MaaFw click 鐨?getevent 鎹曡幏 ===")
# 鍚姩 getevent 鍚庡彴绾跨▼
print("鍚姩 getevent 鎹曡幏 (3s)...")
t = threading.Thread(target=capture_events, args=(3,), daemon=True)
t.start()
time.sleep(0.5)

# 鎵ц MaaFw 鐐瑰嚮
print("鎵ц MaaFw click (800, 40)...")
t0 = time.time()
ok = _maafw.click(800, 40)
t1 = time.time()
print(f"缁撴灉: {ok}, 鑰楁椂: {t1-t0:.2f}s")

time.sleep(2)  # 绛夊緟 getevent 鎹曡幏瀹屾垚
t.join(timeout=1)

# 杩囨护浜嬩欢
relevant = [l for l in event_data if l.strip() and not l.startswith("could")]
print(f"\n鎹曡幏鍒?{len(relevant)} 鏉′簨浠?")
for l in relevant[-20:]:
    print(f"  {l[:150]}")

# 娴嬭瘯 2: 鐢?getevent 鎹曡幏 ADB tap 浜嬩欢锛堝姣旓級
event_data2 = []
def capture_events2(duration=3):
    try:
        r = subprocess.run(
            ADB_BASE + ["shell", "getevent", "-t", "-l"],
            capture_output=True, timeout=duration, text=True
        )
        event_data2.extend(r.stdout.split("\n"))
    except subprocess.TimeoutExpired as e:
        event_data2.extend(e.output.decode(errors='replace').split("\n") if e.output else [])
    except Exception as e:
        event_data2.append(f"Error: {e}")

print("\n=== 娴嬭瘯 2: ADB tap 鐨?getevent 鎹曡幏 ===")
print("鍚姩 getevent 鎹曡幏 (3s)...")
t2 = threading.Thread(target=capture_events2, args=(3,), daemon=True)
t2.start()
time.sleep(0.5)

print("鎵ц ADB tap (800, 40)...")
t0 = time.time()
subprocess.run(ADB_BASE + ["shell", "input", "tap", "800", "40"], capture_output=True, timeout=10)
t1 = time.time()
print(f"鑰楁椂: {t1-t0:.2f}s")

time.sleep(2)
t2.join(timeout=1)

relevant2 = [l for l in event_data2 if l.strip() and not l.startswith("could")]
print(f"\n鎹曡幏鍒?{len(relevant2)} 鏉′簨浠?")
for l in relevant2[-20:]:
    print(f"  {l[:150]}")
