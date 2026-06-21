#!/usr/bin/env python3
"""测试 ADB tap 点击任务图标"""
import subprocess, time

ADB = r"C:\Users\xray\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant\3rd-party\adb\adb.exe"
DEVICE = "localhost:16512"

def adb_tap(x, y):
    r = subprocess.run([ADB, "-s", DEVICE, "shell", "input", "tap", str(x), str(y)], capture_output=True, timeout=5)
    return r.returncode == 0

def adb_back():
    subprocess.run([ADB, "-s", DEVICE, "shell", "input", "keyevent", "4"], capture_output=True)

# 先按返回回到世界
print("[前置] 回到世界...")
for _ in range(6):
    adb_back()
    time.sleep(0.3)
time.sleep(2)

# 测试多个坐标
# MaaFw 扫描确认 y=40 有效 (MaaFw 1280x720 横屏)
# 假设 ADB 也是 1280x720 横屏空间
test_coords = [
    (570, 40),   # MaaFw 最佳
    (570, 28),   # MaaFw 有效
    (855, 60),   # 原配置 (假设 1080x1920)
    (855, 40),   # 混合
    (40, 570),   # 旋转？
]

print("\n[测试] ADB tap 点击")
for x, y in test_coords:
    print(f"\n点击 ({x}, {y})...")
    adb_tap(x, y)
    time.sleep(3)
    
    # 截图检查
    r = subprocess.run([ADB, "-s", DEVICE, "exec-out", "screencap", "-p"], capture_output=True, timeout=10)
    if r.returncode == 0 and len(r.stdout) > 1000:
        print(f"  截图成功：{len(r.stdout)} bytes")
    else:
        print(f"  截图失败")
    
    # 按返回
    adb_back()
    time.sleep(1)

print("\n[完成]")
