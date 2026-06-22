#!/usr/bin/env python3
"""检查 MaaFw 内部状态和 ADB 连接"""
import sys, json, subprocess
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

# 获取控制器信息
if _maafw._controller:
    try:
        info = _maafw._controller.info
        print(f"\n控制器信息:")
        print(json.dumps(info, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"控制器信息获取失败: {e}")
    
    # 获取原始分辨率
    try:
        res = _maafw._controller.resolution
        print(f"\ncontroller.resolution (原始): {res}")
    except Exception as e:
        print(f"resolution 获取失败: {e}")
    
    # 检查截图缓存
    try:
        img = _maafw._controller.cached_image
        if img is not None:
            print(f"cached_image 形状: {img.shape} (HxWxC)")
    except Exception as e:
        print(f"cached_image 获取失败: {e}")

# 检查 ADB 设备
print("\n=== ADB 设备列表 ===")
r = subprocess.run(ADB[:1] + ["devices"], capture_output=True, timeout=10)
print(r.stdout.decode())

# 检查 MaaFw 是否在 ADB 中创建了额外连接
print("=== ADB 连接状态 ===")
r = subprocess.run(ADB[:1] + ["shell", "dumpsys", "input"], capture_output=True, timeout=10)
out = r.stdout.decode(errors='replace')
# 查找 TouchStates
for l in out.split("\n"):
    if "TouchStates" in l or "touch" in l.lower():
        print(l.strip())
