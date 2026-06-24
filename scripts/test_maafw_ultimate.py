#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
缁堟瀬娴嬭瘯锛氱敤澶氱鏂规硶楠岃瘉 MaaFw 鐐瑰嚮鏄惁鐪熺殑鍙戦€?ADB 鍛戒护

鏂规硶1: adb shell dumpsys input - 妫€鏌ユ渶鍚庤Е鎽镐簨浠?
鏂规硶2: adb shell getevent -t - 鎹曡幏鍘熷杈撳叆浜嬩欢锛堝悗鍙扮嚎绋嬶級
鏂规硶3: 鐩存帴瀵规瘮 MaaFw click 鍜?ADB tap 鐨勬埅鍥惧彉鍖?
"""
import sys, os, time, subprocess, threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT_ROOT / "3rd-part" / "python-packages"))

ADB = [str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"), "-s", "localhost:16512"]

def run_adb(cmd, timeout=10):
    r = subprocess.run(ADB + cmd, capture_output=True, timeout=timeout)
    return r.stdout.decode(errors='replace'), r.stderr.decode(errors='replace'), r.returncode

# 鈹€鈹€ 鍒濆鍖?MaaFw 鈹€鈹€
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

# 鈹€鈹€ 鏂规硶1: dumpsys input 鈹€鈹€
print("\n" + "="*60)
print("鏂规硶1: dumpsys input - 妫€鏌ユ渶鍚庤Е鎽镐簨浠?)
print("="*60)

# 鍏堟竻绌虹姸鎬?
print("\n[娓呯┖鐘舵€乚 鎵ц ADB tap (1, 1) 閲嶇疆瑙︽懜鐘舵€?..")
run_adb(["shell", "input", "tap", "1", "1"])
time.sleep(0.5)

# 妫€鏌ュ綋鍓嶈Е鎽哥姸鎬?
out, _, _ = run_adb(["shell", "dumpsys", "input"])
# 鏌ユ壘 Touch 鐩稿叧琛?
touch_lines = [l for l in out.split("\n") if "Touch" in l or "touch" in l.lower() or "Stream" in l]
print(f"\n褰撳墠瑙︽懜鐘舵€?({len(touch_lines)} 琛?:")
for l in touch_lines[-10:]:
    print(f"  {l.strip()}")

# 鎵ц MaaFw 鐐瑰嚮
print(f"\n>>> 鎵ц MaaFw click (800, 40)...")
t0 = time.time()
ok = _maafw.click(800, 40)
t1 = time.time()
print(f"    缁撴灉: {ok}, 鑰楁椂: {t1-t0:.2f}s")
time.sleep(0.5)

# 鍐嶆妫€鏌ヨЕ鎽哥姸鎬?
out, _, _ = run_adb(["shell", "dumpsys", "input"])
touch_lines2 = [l for l in out.split("\n") if "Touch" in l or "touch" in l.lower() or "Stream" in l]
print(f"\nMaaFw 鐐瑰嚮鍚庤Е鎽哥姸鎬?({len(touch_lines2)} 琛?:")
for l in touch_lines2[-10:]:
    print(f"  {l.strip()}")

# 鈹€鈹€ 鏂规硶2: getevent 鈹€鈹€
print("\n" + "="*60)
print("鏂规硶2: getevent - 鎹曡幏鍘熷杈撳叆浜嬩欢")
print("="*60)

# 浣跨敤 Popen 瀹炴椂璇诲彇 getevent 杈撳嚭
event_data = []
event_lock = threading.Lock()

def capture_getevent(duration=3):
    """浣跨敤 Popen 瀹炴椂璇诲彇 getevent 杈撳嚭"""
    try:
        proc = subprocess.Popen(
            ADB + ["shell", "getevent", "-t"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1
        )
        start = time.time()
        while time.time() - start < duration:
            line = proc.stdout.readline()
            if line:
                with event_lock:
                    event_data.append(line.rstrip())
            else:
                time.sleep(0.01)
        proc.kill()
        proc.wait(timeout=2)
    except Exception as e:
        with event_lock:
            event_data.append(f"Error: {e}")

print("鍚姩 getevent 鎹曡幏 (3s)...")
t = threading.Thread(target=capture_getevent, args=(3,), daemon=True)
t.start()
time.sleep(0.5)

print("鎵ц MaaFw click (400, 960)...")  # 灞忓箷涓績闄勮繎
t0 = time.time()
ok = _maafw.click(400, 960)
t1 = time.time()
print(f"  缁撴灉: {ok}, 鑰楁椂: {t1-t0:.2f}s")

time.sleep(2)
t.join(timeout=2)

with event_lock:
    print(f"\n鎹曡幏鍒?{len(event_data)} 鏉′簨浠?")
    for l in event_data[-15:]:
        print(f"  {l}")

# 鈹€鈹€ 鏂规硶3: 瀵规瘮鎴浘鍙樺寲 鈹€鈹€
print("\n" + "="*60)
print("鏂规硶3: 瀵规瘮鎴浘鍙樺寲 (MaaFw click vs ADB tap)")
print("="*60)

def adb_screencap():
    r = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True, timeout=15)
    return r.stdout if r.returncode == 0 else b""

# 鑷劧鍙樺寲鍩虹嚎
print("\n[鍩虹嚎] 杩炵画3娆℃埅鍥捐瀵熻嚜鐒跺彉鍖?")
hashes = []
for i in range(3):
    data = adb_screencap()
    h = hash(data) % 1000000
    hashes.append(h)
    print(f"  鎴浘{i+1}: hash={h}, 澶у皬={len(data)}")
    time.sleep(0.5)
print(f"  鑷劧鍙樺寲: {hashes[0]} -> {hashes[1]} -> {hashes[2]}")

# MaaFw click
print("\n[MaaFw click] 鐐瑰嚮 (400, 960) 鍚庢埅鍥?")
before = adb_screencap()
h_before = hash(before) % 1000000
print(f"  鐐瑰嚮鍓? hash={h_before}")

ok = _maafw.click(400, 960)
print(f"  MaaFw click: {ok}")
time.sleep(2)

after = adb_screencap()
h_after = hash(after) % 1000000
print(f"  鐐瑰嚮鍚? hash={h_after}")
print(f"  鍙樺寲: {h_before} -> {h_after} (宸?{abs(h_after-h_before)})")

# ADB tap
print("\n[ADB tap] 鐐瑰嚮 (400, 960) 鍚庢埅鍥?")
before2 = adb_screencap()
h_before2 = hash(before2) % 1000000
print(f"  鐐瑰嚮鍓? hash={h_before2}")

run_adb(["shell", "input", "tap", "400", "960"])
print(f"  ADB tap: 瀹屾垚")
time.sleep(2)

after2 = adb_screencap()
h_after2 = hash(after2) % 1000000
print(f"  鐐瑰嚮鍚? hash={h_after2}")
print(f"  鍙樺寲: {h_before2} -> {h_after2} (宸?{abs(h_after2-h_before2)})")

print("\n" + "="*60)
print("缁撹鍒嗘瀽")
print("="*60)
print(f"""
MaaFw click 鐘舵€? {'鎴愬姛' if ok else '澶辫触'}
MaaFw 鍒嗚鲸鐜? {_maafw.get_resolution()}

濡傛灉 MaaFw click 鍚庢埅鍥?hash 鍙樺寲涓庤嚜鐒跺彉鍖栧熀绾跨浉杩戯紝
鑰?ADB tap 鍚庢埅鍥?hash 鍙樺寲鏄庢樉鏇村ぇ锛?
鍒欒鏄?MaaFw click 鏈骇鐢熷疄闄呰Е鎺т簨浠躲€?

濡傛灉涓よ€呭彉鍖栧箙搴︾浉浼硷紝
鍒欒鏄?MaaFw click 纭疄鍙戦€佷簡瑙︽帶浜嬩欢銆?
""")

