#!/usr/bin/env python3
"""验证 ADB tap 坐标 - 直接测试 (860, 80)"""
import subprocess, time, cv2, numpy as np, sys

PROJECT_ROOT = r'C:\Users\xray\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant'
ADB = f"{PROJECT_ROOT}\\3rd-party\\adb\\adb.exe"
DEVICE = "localhost:16512"

def adb_tap(x, y):
    r = subprocess.run([ADB, "-s", DEVICE, "shell", "input", "tap", str(int(x)), str(int(y))], 
                       capture_output=True, timeout=5)
    print(f"  ADB tap ({x}, {y}): {r.returncode}")
    return r.returncode == 0

def adb_back():
    subprocess.run([ADB, "-s", DEVICE, "shell", "input", "keyevent", "4"], capture_output=True)

def adb_screencap():
    r = subprocess.run([ADB, "-s", DEVICE, "exec-out", "screencap", "-p"], 
                       capture_output=True, timeout=10)
    if r.returncode == 0 and len(r.stdout) > 1000:
        return cv2.imdecode(np.frombuffer(r.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
    return None

# 回到世界
print("[前置] 回到世界...")
for _ in range(8):
    adb_back()
    time.sleep(0.3)
time.sleep(2)

# 基准截图
img_base = adb_screencap()
if img_base is None:
    print("[ERROR] 基准截图失败")
    sys.exit(1)
print(f"[基准] 分辨率：{img_base.shape[1]}x{img_base.shape[0]}")

# 测试坐标
test_coords = [
    ("配置新", 860, 80),
    ("配置旧", 820, 40),
    ("扫描最佳", 860, 80),
    ("中央", 960, 540),
]

print("\n[测试] ADB tap 坐标验证")
print("="*70)

for name, x, y in test_coords:
    print(f"\n{name}: ({x}, {y})")
    adb_tap(x, y)
    time.sleep(3)
    
    img = adb_screencap()
    if img is None:
        print(f"  截图失败")
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
    print(f"  {status} 变化：{changed:8d} px ({rate:5.1f}%)")
    
    # 按返回
    adb_back()
    time.sleep(1)

print("\n[结论] >30% 表示面板打开，<10% 表示无变化")
