#!/usr/bin/env python3
"""检查 MaaFw 使用的 ADB 连接"""
import sys, os, time, subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT_ROOT / "3rd-part" / "python-packages"))

ADB = [str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe")]

# 连接前检查设备
print("=== 连接前 ADB 设备 ===")
r = subprocess.run(ADB + ["devices"], capture_output=True, timeout=10)
print(r.stdout.decode())

# 初始化 MaaFw
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
            print(f"\n[MaaFw] 连接成功, uuid={_maafw._uuid}")
        else:
            print("[MaaFw] 连接失败")
            sys.exit(1)
except Exception as e:
    print(f"[MaaFw] 异常: {e}")
    sys.exit(1)

# 连接后检查设备
print("\n=== 连接后 ADB 设备 ===")
r = subprocess.run(ADB + ["devices"], capture_output=True, timeout=10)
print(r.stdout.decode())

# 检查 MaaFw 内部使用的 ADB 路径
print(f"=== MaaFw 内部状态 ===")
print(f"  adb_path: {_maafw.config.adb_path}")
print(f"  address: {_maafw.config.address}")
print(f"  screencap_methods: {_maafw.config.screencap_methods}")
print(f"  input_methods: {_maafw.config.input_methods}")
print(f"  connected: {_maafw.connected}")
print(f"  resolution: {_maafw.get_resolution()}")

# 测试：用 MaaFw 点击后，检查 ADB 是否有新连接
print("\n=== 测试 MaaFw 点击 ===")
print("点击 (800, 40)...")
t0 = time.time()
ok = _maafw.click(800, 40)
t1 = time.time()
print(f"  结果: {ok}, 耗时: {t1-t0:.2f}s")

# 再检查设备
print("\n=== 点击后 ADB 设备 ===")
r = subprocess.run(ADB + ["devices"], capture_output=True, timeout=10)
print(r.stdout.decode())

# 检查 ADB 版本
print("=== ADB 版本 ===")
r = subprocess.run(ADB + ["version"], capture_output=True, timeout=10)
print(r.stdout.decode()[:200])