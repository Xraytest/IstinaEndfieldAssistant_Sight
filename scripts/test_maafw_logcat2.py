#!/usr/bin/env python3
"""
监控 ADB 守护进程日志，验证 MaaFw 是否发送 input tap 命令
"""
import sys, time, subprocess, threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT_ROOT / "3rd-party" / "python-packages"))

ADB = [str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"), "-s", "localhost:16512"]

from device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig, MAAFW_AVAILABLE

cfg = MaaFwTouchConfig(
    adb_path=str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"),
    address="localhost:16512",
    screencap_methods=MaaFwTouchConfig.SCREENCAP_ADB_SHELL,
    input_methods=MaaFwTouchConfig.INPUT_ADB_SHELL,
)
_maafw = MaaFwTouchExecutor(cfg)
if not _maafw.connect():
    print("MaaFw 连接失败")
    sys.exit(1)

print(f"MaaFw 连接成功, uuid={_maafw._uuid}")
print(f"MaaFw 分辨率: {_maafw.get_resolution()}")

# 清空 logcat
subprocess.run(ADB + ["logcat", "-c"], capture_output=True, timeout=5)
time.sleep(0.3)

# 启动 logcat 后台捕获
log_data = []
log_lock = threading.Lock()

def capture_logcat(duration=5):
    """捕获 logcat 输出"""
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

print("\n启动 logcat 捕获 (5s)...")
t = threading.Thread(target=capture_logcat, args=(5,), daemon=True)
t.start()
time.sleep(0.5)

# 执行 MaaFw 点击
print("执行 MaaFw click (400, 960)...")
t0 = time.time()
ok = _maafw.click(400, 960)
t1 = time.time()
print(f"  结果: {ok}, 耗时: {t1-t0:.2f}s")

time.sleep(3)
t.join(timeout=2)

# 过滤日志
with log_lock:
    # 查找 input/tap/adb 相关日志
    relevant = [l for l in log_data if any(k in l.lower() for k in ["input", "tap", "adb", "shell", "touch"])]
    print(f"\n捕获到 {len(log_data)} 条日志, {len(relevant)} 条相关:")
    for l in relevant[-20:]:
        print(f"  {l[:200]}")
    
    if not relevant:
        print("  (无相关日志，显示最后5条)")
        for l in log_data[-5:]:
            print(f"  {l[:200]}")

# ── 对比: 直接 ADB tap ──
print("\n" + "="*60)
print("对比: 直接 ADB tap 的 logcat")
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

print("启动 logcat 捕获 (5s)...")
t2 = threading.Thread(target=capture_logcat2, args=(5,), daemon=True)
t2.start()
time.sleep(0.5)

print("执行 ADB tap (400, 960)...")
t0 = time.time()
subprocess.run(ADB + ["shell", "input", "tap", "400", "960"], capture_output=True, timeout=10)
t1 = time.time()
print(f"  耗时: {t1-t0:.2f}s")

time.sleep(3)
t2.join(timeout=2)

relevant2 = [l for l in log_data2 if any(k in l.lower() for k in ["input", "tap", "adb", "shell", "touch"])]
print(f"\n捕获到 {len(log_data2)} 条日志, {len(relevant2)} 条相关:")
for l in relevant2[-20:]:
    print(f"  {l[:200]}")

if not relevant2:
    print("  (无相关日志，显示最后5条)")
    for l in log_data2[-5:]:
        print(f"  {l[:200]}")
