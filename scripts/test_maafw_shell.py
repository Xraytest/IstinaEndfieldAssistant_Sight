#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鐩存帴娴嬭瘯 MaaFw 鐨?ADB 鍛戒护鎵ц鑳藉姏
浣跨敤 post_shell 楠岃瘉 MaaFw 鏄惁鑳芥甯稿彂閫?ADB 鍛戒护
"""
import sys, time, subprocess
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

# 鈹€鈹€ 娴嬭瘯1: post_shell 鈹€鈹€
print("\n" + "="*60)
print("娴嬭瘯1: MaaFw post_shell - 鎵ц绠€鍗曞懡浠?)
print("="*60)

# 鎵ц shell 鍛戒护
job = _maafw._controller.post_shell("echo 'MaaFw_TEST_OK'")
job.wait()
print(f"  job.succeeded: {job.succeeded}")
print(f"  shell_output: {_maafw._controller.shell_output}")

# 鈹€鈹€ 娴嬭瘯2: 鐩存帴 ADB 瀵规瘮 鈹€鈹€
print("\n" + "="*60)
print("娴嬭瘯2: 鐩存帴 ADB shell 瀵规瘮")
print("="*60)
r = subprocess.run(ADB + ["shell", "echo", "ADB_TEST_OK"], capture_output=True, timeout=10, text=True)
print(f"  stdout: {r.stdout.strip()}")
print(f"  stderr: {r.stderr.strip()}")
print(f"  returncode: {r.returncode}")

# 鈹€鈹€ 娴嬭瘯3: MaaFw post_shell 鎵ц input tap 鈹€鈹€
print("\n" + "="*60)
print("娴嬭瘯3: MaaFw post_shell 鎵ц input tap")
print("="*60)

# 鍏堟埅鍥?
before = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True, timeout=15)
h_before = hash(before.stdout) % 1000000
print(f"  鐐瑰嚮鍓嶆埅鍥?hash: {h_before}")

# 鐢?post_shell 鎵ц input tap
job = _maafw._controller.post_shell("input tap 400 960")
job.wait()
print(f"  post_shell job.succeeded: {job.succeeded}")
print(f"  shell_output: '{_maafw._controller.shell_output}'")

time.sleep(2)

after = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True, timeout=15)
h_after = hash(after.stdout) % 1000000
print(f"  鐐瑰嚮鍚庢埅鍥?hash: {h_after}")
print(f"  鍙樺寲: {h_before} -> {h_after}")

# 鈹€鈹€ 娴嬭瘯4: MaaFw post_click 鈹€鈹€
print("\n" + "="*60)
print("娴嬭瘯4: MaaFw post_click (瀵规瘮)")
print("="*60)

before2 = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True, timeout=15)
h_before2 = hash(before2.stdout) % 1000000
print(f"  鐐瑰嚮鍓嶆埅鍥?hash: {h_before2}")

ok = _maafw.click(400, 960)
print(f"  MaaFw click: {ok}")

time.sleep(2)

after2 = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True, timeout=15)
h_after2 = hash(after2.stdout) % 1000000
print(f"  鐐瑰嚮鍚庢埅鍥?hash: {h_after2}")
print(f"  鍙樺寲: {h_before2} -> {h_after2}")

print("\n" + "="*60)
print("缁撹")
print("="*60)
print(f"""
濡傛灉娴嬭瘯1(post_shell echo)鎴愬姛 鈫?MaaFw 鐨?ADB 閫氶亾姝ｅ父
濡傛灉娴嬭瘯3(post_shell input tap)鏈夋埅鍥惧彉鍖?鈫?MaaFw 鐨?ADB shell 鎵ц姝ｅ父
濡傛灉娴嬭瘯4(post_click)鏃犳埅鍥惧彉鍖?鈫?post_click 鍐呴儴鏈夐棶棰?
""")

