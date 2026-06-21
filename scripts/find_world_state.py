#!/usr/bin/env python3
"""
状态恢复脚本 - 找到并确认世界页面状态
"""

import subprocess, time, cv2, numpy as np, sys, os
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ADB = str(PROJECT / '3rd-party' / 'adb' / 'adb.exe')
SERIAL = 'localhost:16512'

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True, timeout=10)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], 
                   capture_output=True, timeout=5)

def home():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '3'], 
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
    return len([c for c in contours if cv2.contourArea(c) > 30])

def classify_page(gold_count):
    """基于金色元素数量判断页面类型"""
    if gold_count < 10:
        return "unknown_low"
    elif 10 <= gold_count <= 18:
        return "exit_dialog"
    elif 16 <= gold_count <= 24:
        return "world"
    elif gold_count > 30:
        return "menu_or_panel"
    else:
        return "other"

def find_world_state(max_attempts=30):
    """
    尝试找到世界页面状态
    
    策略：
    1. 连续按返回键，监控金色元素变化
    2. 一旦金色在 16-24 范围内，确认为世界页面
    3. 如果金色>30，说明在菜单/面板中，继续按返回
    4. 如果金色<10，说明在异常状态，继续按返回
    """
    print("\n" + "="*70)
    print("状态恢复：寻找世界页面")
    print("="*70)
    
    history = []
    
    for i in range(max_attempts):
        # 截图
        img = screencap()
        if img is None:
            print(f"[{i:2d}] 截图失败")
            continue
        
        gold = detect_golden(img)
        page = classify_page(gold)
        
        history.append((i, gold, page))
        marker = "★" if page == "world" else " "
        print(f"{marker} [{i:2d}] 金色={gold:3d} → {page}")
        
        # 找到世界页面
        if page == "world":
            print(f"\n[成功] 在第{i+1}次尝试后找到世界页面")
            return True, i, gold, img
        
        # 决定下一步操作
        if gold > 30:
            # 在菜单/面板中，按返回
            print(f"       → 按返回 (在菜单/面板中)")
            back()
            time.sleep(0.5)
        elif gold < 10:
            # 异常状态，按返回
            print(f"       → 按返回 (异常状态)")
            back()
            time.sleep(0.5)
        elif page == "exit_dialog":
            # 退出对话框，点击取消按钮
            print(f"       → 点击取消按钮 (退出对话框)")
            tap(600, 750)
            time.sleep(1.5)
        else:
            # 其他状态，按返回
            print(f"       → 按返回")
            back()
            time.sleep(0.5)
    
    print(f"\n[失败] {max_attempts}次尝试后仍未找到世界页面")
    print("\n历史:")
    for idx, gold, page in history[-10:]:
        print(f"  [{idx:2d}] 金色={gold:3d} → {page}")
    
    return False, max_attempts, history[-1][1] if history else 0, None

def verify_world_state(img):
    """验证是否真的是世界页面"""
    if img is None:
        return False
    
    gold = detect_golden(img)
    
    # 世界页面特征：
    # 1. 金色元素 16-24 个
    # 2. 点击右上角任务图标应该打开面板（金色增加）
    
    print(f"\n[验证] 当前金色={gold}")
    
    if not (16 <= gold <= 24):
        print(f"[验证失败] 金色{gold}不在世界页面范围 (16-24)")
        return False
    
    # 尝试点击任务图标
    print("[验证] 点击任务图标 (860, 80)...")
    before = img
    tap(860, 80)
    time.sleep(2)
    
    after = screencap()
    if after is None:
        print("[验证失败] 截图失败")
        return False
    
    gold_after = detect_golden(after)
    print(f"[验证] 点击后金色={gold_after} (变化={gold_after-gold:+d})")
    
    # 恢复
    back()
    time.sleep(0.5)
    
    # 判断：如果金色增加>=3，说明打开了面板
    if gold_after - gold >= 3:
        print("[验证通过] 任务图标点击有效")
        return True
    else:
        print(f"[验证警告] 任务图标点击后金色变化小 ({gold_after-gold:+d})")
        return False

def main():
    print("\n" + "="*70)
    print("状态恢复诊断")
    print("="*70)
    
    # 寻找世界页面
    success, attempts, gold, img = find_world_state()
    
    if success:
        # 验证
        is_valid = verify_world_state(img)
        
        if is_valid:
            print(f"\n[✓] 成功找到并验证世界页面")
            print(f"    尝试次数：{attempts}")
            print(f"    金色元素：{gold}")
            return 0
        else:
            print(f"\n[⚠] 找到疑似世界页面，但验证未通过")
            return 1
    else:
        print(f"\n[✗] 无法找到世界页面")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
