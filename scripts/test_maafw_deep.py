#!/usr/bin/env python3
"""深度测试：MaaFw 点击是否真的发送 ADB 命令"""
import sys, os, time, subprocess, hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT_ROOT / "3rd-party" / "python-packages"))

ADB = [str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"), "-s", "localhost:16512"]

def adb_screencap() -> bytes:
    r = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True, timeout=15)
    return r.stdout if r.returncode == 0 else b""

def adb_tap(x, y):
    r = subprocess.run(ADB + ["shell", "input", "tap", str(x), str(y)], capture_output=True, timeout=10)
    return r.returncode == 0

def hash_img(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()[:8] if data else "none"

# ── 初始化 MaaFw ──
_maafw = None
try:
    from device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig, MAAFW_AVAILABLE
    if MAAFW_AVAILABLE:
        cfg = MaaFwTouchConfig(
            adb_path=str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"),
            address="localhost:16512",
            screencap_methods=MaaFwTouchConfig.SCREENCAP_ADB_SHELL,
            input_methods=MaaFwTouchConfig.INPUT_ADB_SHELL,
        )
        _maafw = MaaFwTouchExecutor(cfg)
        if _maafw.connect():
            print(f"[MaaFw] 连接成功, uuid={_maafw._uuid}")
        else:
            print("[MaaFw] 连接失败")
            sys.exit(1)
except Exception as e:
    print(f"[MaaFw] 异常: {e}")
    sys.exit(1)

print("\n=== 测试: 连续截图观察自然变化 ===")
for i in range(3):
    data = adb_screencap()
    print(f"  截图 {i+1}: hash={hash_img(data)}, 大小={len(data)}")
    time.sleep(1)

print("\n=== 测试: MaaFw click 后截图 ===")
# 先截图
before = adb_screencap()
print(f"  点击前: hash={hash_img(before)}")

# MaaFw 点击
print(f"  MaaFw click (800, 40)...")
t0 = time.time()
ok = _maafw.click(800, 40)
t1 = time.time()
print(f"  结果: {ok}, 耗时: {t1-t0:.2f}s")

time.sleep(3)  # 等 UI 响应

after = adb_screencap()
print(f"  点击后: hash={hash_img(after)}")
print(f"  变化: {hash_img(before)} -> {hash_img(after)}")

print("\n=== 测试: 直接 ADB tap 后截图 ===")
before2 = adb_screencap()
print(f"  点击前: hash={hash_img(before2)}")

print(f"  ADB tap (800, 40)...")
t0 = time.time()
ok = adb_tap(800, 40)
t1 = time.time()
print(f"  结果: {ok}, 耗时: {t1-t0:.2f}s")

time.sleep(3)

after2 = adb_screencap()
print(f"  点击后: hash={hash_img(after2)}")
print(f"  变化: {hash_img(before2)} -> {hash_img(after2)}")

print("\n=== 对比分析 ===")
# 如果 MaaFw 和 ADB 都点击同一位置，结果应该相似
# 如果 MaaFw 点击没生效，MaaFw 前后的 hash 变化应该和自然变化一样小
# 而 ADB tap 前后的 hash 变化应该更大（因为 UI 变化）

# 计算自然变化幅度
print("注意：如果 MaaFw 点击后截图与点击前几乎相同（仅动画噪声），")
print("而 ADB tap 后截图明显不同（UI 导航），则说明 MaaFw 点击未生效。")