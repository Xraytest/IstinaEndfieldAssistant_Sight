#!/usr/bin/env python3
"""
手动截图诊断 - 保存当前画面以便人工分析
"""

import subprocess, time, cv2, numpy as np, sys, os
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ADB = str(PROJECT / '3rd-party' / 'adb' / 'adb.exe')
SERIAL = 'localhost:16512'
OUTPUT_DIR = PROJECT / 'cache' / 'diagnosis'
OUTPUT_DIR.mkdir(exist_ok=True)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True, timeout=10)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], 
                   capture_output=True, timeout=5)

def screencap():
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       capture_output=True, timeout=15)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def detect_golden(img):
    if img is None:
        return 0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower = np.array([15, 80, 150])
    upper = np.array([35, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    golden = [c for c in contours if cv2.contourArea(c) > 30]
    return len(golden), golden

def main():
    print("\n" + "="*70)
    print("手动截图诊断")
    print("="*70)
    
    # 确保在世界页面
    print("\n[准备] 按返回键回到基础状态...")
    for i in range(10):
        back()
        time.sleep(0.5)
    time.sleep(1)
    
    # 截图 1：初始状态
    print("\n[截图 1] 初始状态...")
    img1 = screencap()
    gold1, _ = detect_golden(img1)
    print(f"  金色元素：{gold1}")
    cv2.imwrite(str(OUTPUT_DIR / '01_initial.png'), img1)
    
    # 截图 2：点击任务图标前
    print("\n[截图 2] 点击任务图标前...")
    time.sleep(0.5)
    img2 = screencap()
    gold2, golden2 = detect_golden(img2)
    print(f"  金色元素：{gold2}")
    cv2.imwrite(str(OUTPUT_DIR / '02_before_tap.png'), img2)
    
    # 在截图上标注金色元素位置
    img2_annotated = img2.copy()
    for i, cnt in enumerate(golden2):
        M = cv2.moments(cnt)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            cv2.circle(img2_annotated, (cx, cy), 5, (255, 0, 0), -1)
    cv2.imwrite(str(OUTPUT_DIR / '02_before_tap_annotated.png'), img2_annotated)
    
    # 点击任务图标
    print("\n[操作] 点击任务图标 (860, 80)...")
    tap(860, 80)
    time.sleep(3)
    
    # 截图 3：点击后
    print("\n[截图 3] 点击任务图标后...")
    img3 = screencap()
    gold3, golden3 = detect_golden(img3)
    print(f"  金色元素：{gold3}")
    cv2.imwrite(str(OUTPUT_DIR / '03_after_tap_860_80.png'), img3)
    
    # 标注
    img3_annotated = img3.copy()
    for i, cnt in enumerate(golden3):
        M = cv2.moments(cnt)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            cv2.circle(img3_annotated, (cx, cy), 5, (0, 255, 0), -1)
    cv2.imwrite(str(OUTPUT_DIR / '03_after_tap_860_80_annotated.png'), img3_annotated)
    
    # 按返回
    print("\n[操作] 按返回键...")
    back()
    time.sleep(1)
    
    # 截图 4：返回后
    print("\n[截图 4] 按返回后...")
    img4 = screencap()
    gold4, _ = detect_golden(img4)
    print(f"  金色元素：{gold4}")
    cv2.imwrite(str(OUTPUT_DIR / '04_after_back.png'), img4)
    
    # 尝试点击其他位置
    print("\n[操作] 点击菜单图标 (1392, 79)...")
    tap(1392, 79)
    time.sleep(3)
    
    # 截图 5：点击菜单后
    print("\n[截图 5] 点击菜单图标后...")
    img5 = screencap()
    gold5, _ = detect_golden(img5)
    print(f"  金色元素：{gold5}")
    cv2.imwrite(str(OUTPUT_DIR / '05_after_tap_menu.png'), img5)
    
    print("\n" + "="*70)
    print("截图完成")
    print("="*70)
    print(f"\n截图保存在：{OUTPUT_DIR}")
    print("\n请检查以下截图：")
    print("  01_initial.png - 初始状态")
    print("  02_before_tap.png - 点击任务图标前")
    print("  02_before_tap_annotated.png - 标注金色元素")
    print("  03_after_tap_860_80.png - 点击任务图标后")
    print("  03_after_tap_860_80_annotated.png - 标注金色元素")
    print("  04_after_back.png - 按返回后")
    print("  05_after_tap_menu.png - 点击菜单后")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
