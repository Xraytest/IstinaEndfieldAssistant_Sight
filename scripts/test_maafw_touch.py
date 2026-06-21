#!/usr/bin/env python3
"""测试 MaaFw 触控是否实际工作"""
import sys, os, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT_ROOT / "3rd-party" / "python-packages"))

ADB = [str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"), "-s", "localhost:16512"]

# ── MaaFw 初始化 ──
_maafw = None
try:
    from device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig, MAAFW_AVAILABLE
    if MAAFW_AVAILABLE:
        cfg = MaaFwTouchConfig(
            adb_path=str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"),
            address="localhost:16512",
            screencap_methods=MaaFwTouchConfig.SCREENCAP_ADB_SHELL,  # 显式 AdbShell
            input_methods=MaaFwTouchConfig.INPUT_ADB_SHELL,  # 显式 AdbShell
        )
        _maafw = MaaFwTouchExecutor(cfg)
        if _maafw.connect():
            print(f"[MaaFw] 连接成功，分辨率: {_maafw.get_resolution()}")
        else:
            print("[MaaFw] 连接失败")
            _maafw = None
    else:
        print("[MaaFw] MAAFW_AVAILABLE=False")
except Exception as e:
    print(f"[MaaFw] 异常: {e}")
    _maafw = None

# ── 测试触控 ──
if _maafw and _maafw.connected:
    print("\n=== 测试 MaaFw 点击 ===")
    # 点击屏幕中央 (540, 960) - 模拟器 1080x1920
    print("点击 (540, 960)...")
    t0 = time.time()
    result = _maafw.click(540, 960)
    elapsed = time.time() - t0
    print(f"  结果: {result} | 耗时: {elapsed:.2f}s")

    time.sleep(2)

    print("\n=== 测试 MaaFw 滑动 ===")
    print("滑动 (540,960) -> (540,100)...")
    t0 = time.time()
    result = _maafw.swipe(540, 960, 540, 100, 500)
    elapsed = time.time() - t0
    print(f"  结果: {result} | 耗时: {elapsed:.2f}s")

    time.sleep(2)

    print("\n=== 测试 MaaFw 长按 ===")
    print("长按 (540, 960) 1000ms...")
    t0 = time.time()
    result = _maafw.long_press(540, 960, 1000)
    elapsed = time.time() - t0
    print(f"  结果: {result} | 耗时: {elapsed:.2f}s")

    print("\n✅ MaaFw 触控测试完成")
else:
    print("\n❌ MaaFw 未连接，跳过触控测试")
    # 回退：用 ADB 直接测试
    print("\n=== 回退: ADB 直接触控测试 ===")
    import subprocess
    print("ADB tap (540, 960)...")
    subprocess.run(ADB + ["shell", "input", "tap", "540", "960"])
    print("  done")