#!/usr/bin/env python3
"""
登出对话框处理脚本 - 使用多种方法确保点击成功
"""

import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def click_with_adb(device_serial: str, x: int, y: int):
    """使用 ADB 直接点击"""
    print(f"[ADB] 点击 ({x}, {y})")
    adb_path = PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"
    result = subprocess.run(
        [str(adb_path), "-s", device_serial, "shell", "input", "tap", str(x), str(y)],
        capture_output=True,
        text=True
    )
    print(f"  结果：{result.returncode}")
    return result.returncode == 0

def click_multiple_times(device_serial: str, x: int, y: int, times: int = 3):
    """多次点击以提高成功率"""
    print(f"[点击] 尝试 {times} 次 @ ({x}, {y})")
    for i in range(times):
        print(f"  第 {i+1}/{times} 次")
        click_with_adb(device_serial, x, y)
        import time
        time.sleep(0.5)

def main():
    device_serial = "192.168.1.12:16512"
    
    print("\n" + "="*60)
    print("登出对话框处理 - 多次点击确认按钮")
    print("="*60)
    
    # 登出对话框确认按钮位置
    # 物理坐标：1920x1080, 按钮在底部中央
    # 逻辑坐标：1280x720
    # 按钮大约在 (640, 580) 左右
    
    print("\n尝试 1: 使用逻辑坐标 (640, 580)")
    click_multiple_times(device_serial, 640, 580, times=3)
    
    import time
    time.sleep(2)
    
    print("\n尝试 2: 使用物理坐标 (960, 850)")
    click_multiple_times(device_serial, 960, 850, times=3)
    
    time.sleep(2)
    
    print("\n尝试 3: 使用屏幕底部中央 (640, 650)")
    click_multiple_times(device_serial, 640, 650, times=3)
    
    time.sleep(2)
    
    print("\n" + "="*60)
    print("点击完成，请检查设备状态")
    print("="*60)
    
    # 截图确认
    print("\n截图确认...")
    result = subprocess.run(
        ["adb", "-s", device_serial, "exec-out", "screencap", "-p"],
        capture_output=True
    )
    if result.returncode == 0:
        output_path = PROJECT_ROOT / "cache" / "logout_check.png"
        with open(output_path, "wb") as f:
            f.write(result.stdout)
        print(f"截图已保存：{output_path}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
