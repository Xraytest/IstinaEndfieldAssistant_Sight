#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鐩戞帶 ADB 瀹堟姢杩涚▼鏃ュ織锛岄獙璇?MaaFw 鏄惁鍙戦€?input tap 鍛戒护
"""
import sys, time, subprocess, threading
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

# 娓呯┖ logcat
subprocess.run(ADB + ["logcat", "-c"], capture_output=True, timeout=5)
time.sleep(0.3)

# 鍚姩 logcat 鍚庡彴鎹曡幏
log_data = []
log_lock = threading.Lock()

def capture_logcat(duration=5):
    """鎹曡幏 logcat 杈撳嚭"""
    try:
        proc = subprocess.Popen(
            ADB + ["logcat", "-v", "time"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1
        )
        start = time.time()
        while time.time() - start < duration:
            line = proc.stdout.readline()
            if line:
                with log_lock:
                    log_data.append(line.rstrip())
            else:
                time.sleep(0.01)
        proc.kill()
        proc.wait(timeout=2)
    except Exception as e:
        with log_lock:
            log_data.append(f"Error: {e}")

print("\n鍚姩 logcat 鎹曡幏 (5s)...")
t = threading.Thread(target=capture_logcat, args=(5,), daemon=True)
t.start()
time.sleep(0.5)

# 鎵ц MaaFw 鐐瑰嚮
print("鎵ц MaaFw click (400, 960)...")
t0 = time.time()
ok = _maafw.click(400, 960)
t1 = time.time()
print(f"  缁撴灉: {ok}, 鑰楁椂: {t1-t0:.2f}s")

time.sleep(3)
t.join(timeout=2)

# 杩囨护鏃ュ織
with log_lock:
    # 鏌ユ壘 input/tap/adb 鐩稿叧鏃ュ織
    relevant = [l for l in log_data if any(k in l.lower() for k in ["input", "tap", "adb", "shell", "touch"])]
    print(f"\n鎹曡幏鍒?{len(log_data)} 鏉℃棩蹇? {len(relevant)} 鏉＄浉鍏?")
    for l in relevant[-20:]:
        print(f"  {l[:200]}")
    
    if not relevant:
        print("  (鏃犵浉鍏虫棩蹇楋紝鏄剧ず鏈€鍚?鏉?")
        for l in log_data[-5:]:
            print(f"  {l[:200]}")

# 鈹€鈹€ 瀵规瘮: 鐩存帴 ADB tap 鈹€鈹€
print("\n" + "="*60)
print("瀵规瘮: 鐩存帴 ADB tap 鐨?logcat")
print("="*60)

subprocess.run(ADB + ["logcat", "-c"], capture_output=True, timeout=5)
time.sleep(0.3)

log_data2 = []
def capture_logcat2(duration=5):
    try:
        proc = subprocess.Popen(
            ADB + ["logcat", "-v", "time"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1
        )
        start = time.time()
        while time.time() - start < duration:
            line = proc.stdout.readline()
            if line:
                log_data2.append(line.rstrip())
            else:
                time.sleep(0.01)
        proc.kill()
        proc.wait(timeout=2)
    except Exception as e:
        log_data2.append(f"Error: {e}")

print("鍚姩 logcat 鎹曡幏 (5s)...")
t2 = threading.Thread(target=capture_logcat2, args=(5,), daemon=True)
t2.start()
time.sleep(0.5)

print("鎵ц ADB tap (400, 960)...")
t0 = time.time()
subprocess.run(ADB + ["shell", "input", "tap", "400", "960"], capture_output=True, timeout=10)
t1 = time.time()
print(f"  鑰楁椂: {t1-t0:.2f}s")

time.sleep(3)
t2.join(timeout=2)

relevant2 = [l for l in log_data2 if any(k in l.lower() for k in ["input", "tap", "adb", "shell", "touch"])]
print(f"\n鎹曡幏鍒?{len(log_data2)} 鏉℃棩蹇? {len(relevant2)} 鏉＄浉鍏?")
for l in relevant2[-20:]:
    print(f"  {l[:200]}")

if not relevant2:
    print("  (鏃犵浉鍏虫棩蹇楋紝鏄剧ず鏈€鍚?鏉?")
    for l in log_data2[-5:]:
        print(f"  {l[:200]}")

