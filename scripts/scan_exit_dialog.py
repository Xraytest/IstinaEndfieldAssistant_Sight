#!/usr/bin/env python3
"""扫描退出对话框的取消按钮位置"""
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

# 先回到世界
print("[前置] 回到世界...")
for _ in range(8):
    adb_back()
    time.sleep(0.3)
time.sleep(2)

# 触发退出对话框：按 Home 键然后返回
print("[触发] 按 Home 键触发退出对话框...")
subprocess.run([ADB, "-s", DEVICE, "shell", "input", "keyevent", "3"], capture_output=True)
time.sleep(3)

# 基准截图（应该有退出对话框）
img_base = adb_screencap()
if img_base is None:
    print("[ERROR] 截图失败")
    sys.exit(1)
print(f"[基准] 分辨率：{img_base.shape[1]}x{img_base.shape[0]}")

# 退出对话框通常在中央，取消按钮在左侧或底部
# 扫描中央区域：x: 400-1200, y: 400-800 (1920x1080 空间)
print("\n[扫描] 退出对话框取消按钮 (ADB tap 坐标)")
print("="*70)

results = []
for x in range(400, 1200, 100):
    for y in range(400, 800, 50):
        adb_tap(x, y)
        time.sleep(2)
        
        img = adb_screencap()
        if img is None:
            continue
        
        # 像素差异
        diff = cv2.absdiff(img_base, img)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
        changed = cv2.countNonZero(thresh)
        rate = changed / (img.shape[0] * img.shape[1]) * 100
        
        results.append({'x': x, 'y': y, 'changed': changed, 'rate': rate})
        
        # 对话框关闭会有较大变化 (>20%)
        status = "✅" if rate > 20 else ("⚠️" if rate > 5 else " ")
        if rate > 5:
            print(f"{status} ({x:4d}, {y:4d}): {changed:8d} px ({rate:5.1f}%)")

print("\n" + "="*70)
if results:
    best = max(results, key=lambda r: r['rate'])
    print(f"[最佳] ({best['x']:4d}, {best['y']:4d}): {best['changed']:8d} px ({best['rate']:5.1f}%)")
    if best['rate'] > 20:
        print("[结论] ✅ 找到取消按钮位置")
    else:
        print("[结论] ❌ 未找到，可能需要调整扫描区域")

# 恢复：按返回关闭对话框
print("\n[恢复] 按返回关闭对话框...")
adb_back()
time.sleep(1)
