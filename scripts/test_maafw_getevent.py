#!/usr/bin/env python3
"""用 getevent 检测 MaaFw 点击是否产生输入事件"""
import sys, os, time, subprocess, threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT_ROOT / "3rd-party" / "python-packages"))

ADB_BASE = [str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"), "-s", "localhost:16512"]

# 初始化 MaaFw
from core.capability.device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig, MAAFW_AVAILABLE
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

# 测试 1: 用 getevent 捕获 MaaFw 点击事件
event_data = []
def capture_events(duration=3):
    """在后台捕获输入事件"""
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

print("\n=== 测试 1: MaaFw click 的 getevent 捕获 ===")
# 启动 getevent 后台线程
print("启动 getevent 捕获 (3s)...")
t = threading.Thread(target=capture_events, args=(3,), daemon=True)
t.start()
time.sleep(0.5)

# 执行 MaaFw 点击
print("执行 MaaFw click (800, 40)...")
t0 = time.time()
ok = _maafw.click(800, 40)
t1 = time.time()
print(f"结果: {ok}, 耗时: {t1-t0:.2f}s")

time.sleep(2)  # 等待 getevent 捕获完成
t.join(timeout=1)

# 过滤事件
relevant = [l for l in event_data if l.strip() and not l.startswith("could")]
print(f"\n捕获到 {len(relevant)} 条事件:")
for l in relevant[-20:]:
    print(f"  {l[:150]}")

# 测试 2: 用 getevent 捕获 ADB tap 事件（对比）
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

print("\n=== 测试 2: ADB tap 的 getevent 捕获 ===")
print("启动 getevent 捕获 (3s)...")
t2 = threading.Thread(target=capture_events2, args=(3,), daemon=True)
t2.start()
time.sleep(0.5)

print("执行 ADB tap (800, 40)...")
t0 = time.time()
subprocess.run(ADB_BASE + ["shell", "input", "tap", "800", "40"], capture_output=True, timeout=10)
t1 = time.time()
print(f"耗时: {t1-t0:.2f}s")

time.sleep(2)
t2.join(timeout=1)

relevant2 = [l for l in event_data2 if l.strip() and not l.startswith("could")]
print(f"\n捕获到 {len(relevant2)} 条事件:")
for l in relevant2[-20:]:
    print(f"  {l[:150]}")