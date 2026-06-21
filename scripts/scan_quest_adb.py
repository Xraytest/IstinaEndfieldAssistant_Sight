#!/usr/bin/env python3
"""扫描任务图标位置 - 使用 ADB tap + 像素差异法"""
import subprocess, time, cv2, numpy as np, sys

PROJECT_ROOT = r'C:\Users\xray\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant'
ADB = f"{PROJECT_ROOT}\\3rd-party\\adb\\adb.exe"
DEVICE = "localhost:16512"

def adb_tap(x, y):
    subprocess.run([ADB, "-s", DEVICE, "shell", "input", "tap", str(int(x)), str(int(y))], 
                   capture_output=True, timeout=5)

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

# 旋转基准图到横屏分析
img_base_rot = cv2.rotate(img_base, cv2.ROTATE_90_COUNTERCLOCKWISE)
img_base_resized = cv2.resize(img_base_rot, (1280, 720))

# 扫描 x 坐标范围 (任务图标应该在顶部导航栏)
# 基于之前的测试：(855, 60) 能打开面板
# 扫描 x: 800-900, y: 40-80
print("\n[扫描] 任务图标位置 (ADB tap 坐标)")
print("="*70)

results = []
for x in range(800, 920, 20):
    for y in range(40, 90, 10):
        adb_tap(x, y)
        time.sleep(2.5)
        
        img = adb_screencap()
        if img is None:
            adb_back()
            time.sleep(1)
            continue
        
        # 旋转到横屏比较
        img_rot = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        img_resized = cv2.resize(img_rot, (1280, 720))
        
        # 像素差异
        diff = cv2.absdiff(img_base_resized, img_resized)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
        changed = cv2.countNonZero(thresh)
        rate = changed / (1280 * 720) * 100
        
        results.append({'x': x, 'y': y, 'changed': changed, 'rate': rate})
        
        status = "✅" if rate > 40 else ("⚠️" if rate > 15 else " ")
        print(f"{status} ({x:4d}, {y:3d}): {changed:8d} px ({rate:5.1f}%)")
        
        adb_back()
        time.sleep(0.5)

print("\n" + "="*70)
if results:
    best = max(results, key=lambda r: r['rate'])
    print(f"[最佳] ({best['x']:4d}, {best['y']:3d}): {best['changed']:8d} px ({best['rate']:5.1f}%)")
    if best['rate'] > 40:
        print("[结论] ✅ 找到任务图标位置")
    else:
        print("[结论] ❌ 未找到有效位置，可能需要扩大扫描范围")
