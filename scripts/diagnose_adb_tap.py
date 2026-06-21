#!/usr/bin/env python3
"""
ADB 点击诊断脚本

检查 ADB tap 命令是否正确执行，以及坐标是否准确
"""

import subprocess, time, cv2, numpy as np, sys, os
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ADB = str(PROJECT / '3rd-party' / 'adb' / 'adb.exe')
SERIAL = 'localhost:16512'

def tap(x, y):
    """执行 ADB tap 命令"""
    cmd = [ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))]
    print(f"  [CMD] {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, timeout=10)
    if r.returncode != 0:
        print(f"  [错误] tap 命令返回码：{r.returncode}")
        if r.stderr:
            print(f"  [STDERR] {r.stderr.decode('utf-8', errors='ignore')}")
    return r.returncode == 0

def back():
    """执行 ADB back 命令"""
    cmd = [ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4']
    r = subprocess.run(cmd, capture_output=True, timeout=5)
    return r.returncode == 0

def screencap():
    """执行 ADB screencap 命令"""
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       capture_output=True, timeout=15)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def screen_diff(img1, img2):
    """计算两张图片的差异像素数"""
    if img1 is None or img2 is None:
        return 0
    d = cv2.absdiff(img1, img2)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)

def detect_golden(img):
    """检测金色元素数量"""
    if img is None:
        return 0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower = np.array([15, 80, 150])
    upper = np.array([35, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return len([c for c in contours if cv2.contourArea(c) > 30])

def test_tap_response():
    """测试 tap 命令是否产生画面变化"""
    print("\n" + "="*70)
    print("测试 1: ADB tap 响应测试")
    print("="*70)
    
    # 确保在世界页面
    print("\n[准备] 确保在世界页面...")
    for i in range(5):
        back()
        time.sleep(0.5)
    time.sleep(1)
    
    # 截图
    img1 = screencap()
    if img1 is None:
        print("[失败] 无法截图")
        return False
    
    gold1 = detect_golden(img1)
    print(f"[初始] 金色元素={gold1}")
    
    # 测试多个坐标
    test_coords = [
        (860, 80, "任务图标"),
        (928, 53, "活动图标"),
        (1392, 79, "菜单图标"),
        (150, 150, "城市地图"),
        (960, 540, "屏幕中心"),
    ]
    
    results = []
    
    for x, y, name in test_coords:
        print(f"\n[测试] {name} ({x}, {y})...")
        
        # 截图前
        before = screencap()
        if before is None:
            print(f"  [失败] 截图失败")
            continue
        
        gold_before = detect_golden(before)
        
        # 点击
        success = tap(x, y)
        if not success:
            print(f"  [失败] tap 命令执行失败")
            results.append((name, x, y, False, 0, "command_failed"))
            continue
        
        time.sleep(2)
        
        # 截图后
        after = screencap()
        if after is None:
            print(f"  [失败] 截图失败")
            continue
        
        gold_after = detect_golden(after)
        diff = screen_diff(before, after)
        
        print(f"  [结果] diff={diff:,} 金色={gold_before}->{gold_after}")
        
        # 判断是否有效
        if diff > 500000:
            status = "有效 (大变化)"
            effective = True
        elif diff > 200000:
            status = "可能有效 (中变化)"
            effective = True
        elif gold_after != gold_before:
            status = "有效 (金色变化)"
            effective = True
        else:
            status = "无效 (无变化)"
            effective = False
        
        results.append((name, x, y, effective, diff, status))
        print(f"  [判定] {status}")
        
        # 恢复：按返回
        if gold_after > gold_before or diff > 200000:
            print(f"  [恢复] 按返回键...")
            back()
            time.sleep(1)
    
    # 统计
    print("\n" + "="*70)
    print("测试结果统计")
    print("="*70)
    
    for name, x, y, effective, diff, status in results:
        marker = "✓" if effective else "✗"
        print(f"  [{marker}] {name:12} ({x:4}, {y:4}) diff={diff:>8,} {status}")
    
    effective_count = sum(1 for _, _, _, effective, _, _ in results if effective)
    print(f"\n有效点击：{effective_count}/{len(results)}")
    
    return effective_count > 0

def test_quest_icon_detailed():
    """详细测试任务图标点击"""
    print("\n" + "="*70)
    print("测试 2: 任务图标详细测试")
    print("="*70)
    
    # 确保在世界页面
    print("\n[准备] 确保在世界页面...")
    for i in range(5):
        back()
        time.sleep(0.5)
    time.sleep(1)
    
    # 截图
    img = screencap()
    if img is None:
        print("[失败] 无法截图")
        return False
    
    gold = detect_golden(img)
    print(f"[初始] 金色元素={gold}")
    
    if gold < 18 or gold > 21:
        print(f"[警告] 金色元素={gold}，可能不在世界页面")
    
    # 多次点击测试
    for attempt in range(3):
        print(f"\n[尝试 {attempt+1}/3] 点击任务图标 (860, 80)...")
        
        before = screencap()
        gold_before = detect_golden(before)
        
        tap(860, 80)
        time.sleep(3)
        
        after = screencap()
        gold_after = detect_golden(after)
        diff = screen_diff(before, after)
        
        print(f"  [结果] diff={diff:,} 金色={gold_before}->{gold_after}")
        
        if diff > 500000 or gold_after > gold_before + 2:
            print(f"  [成功] 面板已打开")
            
            # 保存截图
            cv2.imwrite(str(PROJECT / 'cache' / 'quest_panel_open.png'), after)
            print(f"  [保存] 截图已保存到 cache/quest_panel_open.png")
            
            # 恢复
            back()
            time.sleep(1)
            return True
        else:
            print(f"  [失败] 面板未打开")
            
            # 尝试按返回恢复
            back()
            time.sleep(0.5)
    
    print("\n[结论] 任务图标点击无效，可能原因：")
    print("  1. 坐标不正确")
    print("  2. ADB 连接问题")
    print("  3. 模拟器状态异常")
    print("  4. 游戏已在任务面板中")
    
    return False

def main():
    print("\n" + "="*70)
    print("ADB 点击诊断")
    print("="*70)
    
    result1 = test_tap_response()
    result2 = test_quest_icon_detailed()
    
    print("\n" + "="*70)
    print("总结")
    print("="*70)
    
    if result1 and result2:
        print("[✓] ADB tap 命令工作正常")
        return 0
    else:
        print("[✗] ADB tap 命令存在问题")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
