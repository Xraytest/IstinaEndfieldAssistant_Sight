#!/usr/bin/env python3
"""检查 MaaFw 点击是否真的发送 input tap"""
import sys, os, time, subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT_ROOT / "3rd-party" / "python-packages"))

ADB = [str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"), "-s", "localhost:16512"]

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

# 清空 logcat
subprocess.run(ADB + ["logcat", "-c"], capture_output=True, timeout=5)
time.sleep(0.5)

# 执行 MaaFw 点击
print("\n执行 MaaFw click (800, 40)...")
t0 = time.time()
ok = _maafw.click(800, 40)
t1 = time.time()
print(f"结果: {ok}, 耗时: {t1-t0:.2f}s")

time.sleep(1)

# 检查 logcat 中是否有 input 相关日志
r = subprocess.run(ADB + ["logcat", "-d"], capture_output=True, timeout=5, text=True)
input_lines = [l for l in r.stdout.split("\n") if "input" in l.lower() or "tap" in l.lower()]
print(f"\n找到 {len(input_lines)} 条 input/tap 相关日志:")
for l in input_lines[-10:]:
    print(f"  {l[:200]}")

# 也检查直接 ADB tap 的对比
print("\n=== 对比: 直接 ADB tap ===")
subprocess.run(ADB + ["logcat", "-c"], capture_output=True, timeout=5)
time.sleep(0.5)

print("执行 ADB tap (800, 40)...")
t0 = time.time()
subprocess.run(ADB + ["shell", "input", "tap", "800", "40"], capture_output=True, timeout=10)
t1 = time.time()
print(f"耗时: {t1-t0:.2f}s")

time.sleep(1)

r = subprocess.run(ADB + ["logcat", "-d"], capture_output=True, timeout=5, text=True)
input_lines2 = [l for l in r.stdout.split("\n") if "input" in l.lower() or "tap" in l.lower()]
print(f"找到 {len(input_lines2)} 条 input/tap 相关日志:")
for l in input_lines2[-10:]:
    print(f"  {l[:200]}")