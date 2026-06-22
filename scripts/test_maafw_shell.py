#!/usr/bin/env python3
"""
直接测试 MaaFw 的 ADB 命令执行能力
使用 post_shell 验证 MaaFw 是否能正常发送 ADB 命令
"""
import sys, time, subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT_ROOT / "3rd-party" / "python-packages"))

ADB = [str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"), "-s", "localhost:16512"]

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
print(f"MaaFw 分辨率: {_maafw.get_resolution()}")

# ── 测试1: post_shell ──
print("\n" + "="*60)
print("测试1: MaaFw post_shell - 执行简单命令")
print("="*60)

# 执行 shell 命令
job = _maafw._controller.post_shell("echo 'MaaFw_TEST_OK'")
job.wait()
print(f"  job.succeeded: {job.succeeded}")
print(f"  shell_output: {_maafw._controller.shell_output}")

# ── 测试2: 直接 ADB 对比 ──
print("\n" + "="*60)
print("测试2: 直接 ADB shell 对比")
print("="*60)
r = subprocess.run(ADB + ["shell", "echo", "ADB_TEST_OK"], capture_output=True, timeout=10, text=True)
print(f"  stdout: {r.stdout.strip()}")
print(f"  stderr: {r.stderr.strip()}")
print(f"  returncode: {r.returncode}")

# ── 测试3: MaaFw post_shell 执行 input tap ──
print("\n" + "="*60)
print("测试3: MaaFw post_shell 执行 input tap")
print("="*60)

# 先截图
before = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True, timeout=15)
h_before = hash(before.stdout) % 1000000
print(f"  点击前截图 hash: {h_before}")

# 用 post_shell 执行 input tap
job = _maafw._controller.post_shell("input tap 400 960")
job.wait()
print(f"  post_shell job.succeeded: {job.succeeded}")
print(f"  shell_output: '{_maafw._controller.shell_output}'")

time.sleep(2)

after = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True, timeout=15)
h_after = hash(after.stdout) % 1000000
print(f"  点击后截图 hash: {h_after}")
print(f"  变化: {h_before} -> {h_after}")

# ── 测试4: MaaFw post_click ──
print("\n" + "="*60)
print("测试4: MaaFw post_click (对比)")
print("="*60)

before2 = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True, timeout=15)
h_before2 = hash(before2.stdout) % 1000000
print(f"  点击前截图 hash: {h_before2}")

ok = _maafw.click(400, 960)
print(f"  MaaFw click: {ok}")

time.sleep(2)

after2 = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True, timeout=15)
h_after2 = hash(after2.stdout) % 1000000
print(f"  点击后截图 hash: {h_after2}")
print(f"  变化: {h_before2} -> {h_after2}")

print("\n" + "="*60)
print("结论")
print("="*60)
print(f"""
如果测试1(post_shell echo)成功 → MaaFw 的 ADB 通道正常
如果测试3(post_shell input tap)有截图变化 → MaaFw 的 ADB shell 执行正常
如果测试4(post_click)无截图变化 → post_click 内部有问题
""")
