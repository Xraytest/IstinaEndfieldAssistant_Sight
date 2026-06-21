#!/usr/bin/env python3
"""重新扫描任务图标 - 先确认页面状态"""
import subprocess, time, cv2, numpy as np, sys
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\xray\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant')
ADB_PATH = f"{PROJECT_ROOT}\\3rd-party\\adb\\adb.exe"
DEVICE = "localhost:16512"

def adb_cmd(args):
    r = subprocess.run([ADB_PATH, "-s", DEVICE] + args, capture_output=True, timeout=10)
    return r

def adb_tap(x, y):
    adb_cmd(["shell", "input", "tap", str(int(x)), str(int(y))])

def adb_back():
    adb_cmd(["shell", "input", "keyevent", "4"])

def adb_screencap():
    r = adb_cmd(["exec-out", "screencap", "-p"])
    if r.returncode == 0 and len(r.stdout) > 1000:
        return cv2.imdecode(np.frombuffer(r.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
    return None

def count_gold(img):
    if img is None:
        return 0
    img_rot = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    img_resized = cv2.resize(img_rot, (1280, 720))
    hsv = cv2.cvtColor(img_resized, cv2.COLOR_BGR2HSV)
    lower_gold = np.array([25, 100, 100])
    upper_gold = np.array([35, 255, 255])
    mask = cv2.inRange(hsv, lower_gold, upper_gold)
    kernel = np.ones((3,3),np.uint8)
    dilated_mask = cv2.dilate(mask, kernel, iterations=2)
    eroded_mask = cv2.erode(dilated_mask, kernel, iterations=1)
    contours, _ = cv2.findContours(eroded_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return len([c for c in contours if cv2.contourArea(c) > 50])

def classify_page(gold_count):
    if gold_count >= 20:
        return "quest_panel (任务面板)"
    elif gold_count >= 18:
        return "world (世界)"
    elif gold_count >= 12:
        return "exit_dialog (退出对话框)"
    else:
        return "other (其他页面)"

# 回到主界面
print("[前置] 返回键 x10 回到主界面...")
for i in range(10):
    adb_back()
    time.sleep(0.3)
time.sleep(2)

# 检查页面
img = adb_screencap()
if img is None:
    print("[ERROR] 截图失败")
    sys.exit(1)

gold = count_gold(img)
page = classify_page(gold)
print(f"\n[当前页面] 分辨率：{img.shape[1]}x{img.shape[0]}")
print(f"[当前页面] 金色元素：{gold}")
print(f"[当前页面] 类型：{page}")

# 如果不在世界页面，尝试点击屏幕中央进入
if gold < 15:
    print("\n[提示] 不在世界页面，尝试点击中央进入...")
    # 横屏中央约 (640, 360)，对应竖屏坐标需要转换
    # 竖屏 1920x1080，横屏内容在中央区域
    adb_tap(540, 960)  # 竖屏中央偏下
    time.sleep(3)
    
    img2 = adb_screencap()
    gold2 = count_gold(img2)
    page2 = classify_page(gold2)
    print(f"[点击后] 金色元素：{gold2}, 类型：{page2}")

# 再次检查
img = adb_screencap()
gold = count_gold(img)
page = classify_page(gold)
print(f"\n[最终页面] 金色元素：{gold}, 类型：{page}")

# 扫描导航栏区域
if gold >= 15:
    print("\n" + "="*70)
    print("[扫描] 导航栏图标 (x: 700-1000, y: 30-100)")
    print("="*70)
    
    img_base = adb_screencap()
    img_base_rot = cv2.rotate(img_base, cv2.ROTATE_90_COUNTERCLOCKWISE)
    img_base_resized = cv2.resize(img_base_rot, (1280, 720))
    
    best_result = None
    best_rate = 0
    
    for x in range(700, 1020, 30):
        for y in range(30, 100, 15):
            adb_tap(x, y)
            time.sleep(2.5)
            
            img = adb_screencap()
            if img is not None:
                img_rot = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
                img_resized = cv2.resize(img_rot, (1280, 720))
                
                diff = cv2.absdiff(img_base_resized, img_resized)
                gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
                _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
                changed = cv2.countNonZero(thresh)
                rate = changed / (1280 * 720) * 100
                
                if rate > best_rate:
                    best_rate = rate
                    best_result = (x, y, rate)
                
                status = "✅" if rate > 40 else ("⚠️" if rate > 20 else " ")
                if rate > 20:
                    print(f"{status} ({x:4d}, {y:3d}): {rate:5.1f}%")
            
            adb_back()
            time.sleep(0.5)
    
    print("\n" + "="*70)
    if best_result and best_rate > 40:
        print(f"[最佳] ({best_result[0]}, {best_result[1]}): {best_rate:.1f}%")
        print("[结论] ✅ 找到有效坐标")
    else:
        print(f"[最佳] ({best_result[0] if best_result else 'N/A'}, {best_result[1] if best_result else 'N/A'}): {best_rate:.1f}%")
        print("[结论] ❌ 未找到有效坐标")
else:
    print("\n[跳过] 不在世界页面，无法扫描任务图标")
    print("[提示] 请先手动进入游戏世界页面后重新运行")
