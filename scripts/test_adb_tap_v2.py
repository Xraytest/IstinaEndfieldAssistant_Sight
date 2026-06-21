#!/usr/bin/env python3
"""测试 ADB tap 坐标 - 像素差异分析"""
import subprocess, time, cv2, numpy as np

ADB = r"C:\Users\xray\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant\3rd-party\adb\adb.exe"
DEVICE = "localhost:16512"

def adb_tap(x, y):
    subprocess.run([ADB, "-s", DEVICE, "shell", "input", "tap", str(x), str(y)], capture_output=True, timeout=5)

def adb_back():
    subprocess.run([ADB, "-s", DEVICE, "shell", "input", "keyevent", "4"], capture_output=True)

def adb_screencap():
    r = subprocess.run([ADB, "-s", DEVICE, "exec-out", "screencap", "-p"], capture_output=True, timeout=10)
    if r.returncode == 0 and len(r.stdout) > 1000:
        return cv2.imdecode(np.frombuffer(r.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
    return None

# 回到世界
print("[前置] 回到世界...")
for _ in range(6):
    adb_back()
    time.sleep(0.3)
time.sleep(2)

# 基准截图
img_base = adb_screencap()
if img_base is None:
    print("[ERROR] 基准截图失败")
    exit(1)
print(f"[基准] 分辨率：{img_base.shape[1]}x{img_base.shape[0]}")

# 测试坐标 (基于 MaaFw 扫描结果 y=40 有效)
# MaaFw 1280x720 → ADB 可能是 1280x720 或 1920x1080
test_coords = [
    ("MaaFw 最佳", 570, 40),
    ("MaaFw 有效", 570, 28),
    ("配置旧", 855, 33),
    ("配置新", 855, 60),
    ("旋转 1", 40, 570),
    ("旋转 2", 60, 855),
]

print("\n[测试] ADB tap + 像素差异分析")
print("="*70)

for name, x, y in test_coords:
    adb_tap(x, y)
    time.sleep(2.5)
    
    img = adb_screencap()
    if img is None:
        print(f"{name:12s} ({x:4d}, {y:4d}): 截图失败")
        adb_back()
        time.sleep(1)
        continue
    
    # 像素差异
    diff = cv2.absdiff(img_base, img)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    changed = cv2.countNonZero(thresh)
    rate = changed / (thresh.shape[0] * thresh.shape[1]) * 100
    
    status = "✅" if rate > 30 else ("⚠️" if rate > 10 else "❌")
    print(f"{status} {name:12s} ({x:4d}, {y:4d}): {changed:8d} px ({rate:5.1f}%)")
    
    adb_back()
    time.sleep(1)

print("\n[结论] >30% 表示面板打开，<10% 表示无变化")
