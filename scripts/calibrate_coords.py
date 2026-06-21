#!/usr/bin/env python3
"""
坐标校准脚本

通过像素扫描找出任务图标的准确坐标
参考：之前坐标扫描验证结果 (860,80) 59.9%
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

def screencap():
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       capture_output=True, timeout=15)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def screen_diff(img1, img2):
    if img1 is None or img2 is None:
        return 0
    d = cv2.absdiff(img1, img2)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)

def detect_golden(img):
    if img is None:
        return 0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower = np.array([15, 80, 150])
    upper = np.array([35, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return len([c for c in contours if cv2.contourArea(c) > 30])

def find_icon_by_scanning():
    """
    通过扫描右上角区域找出任务图标坐标
    
    参考之前的扫描结果：
    - 棋盘格扫描发现 y=40/60/80 有效，y=50/70 无效
    - 最佳坐标 (860, 80) 产生 59.9% 匹配度
    """
    print("\n" + "="*70)
    print("坐标扫描：任务图标")
    print("="*70)
    
    # 确保在世界页面（金色 18-21）
    print("\n[准备] 确保在世界页面...")
    for i in range(10):
        back()
        time.sleep(0.5)
    time.sleep(1)
    
    img = screencap()
    gold = detect_golden(img)
    print(f"[当前] 金色元素={gold}")
    
    if gold < 12 or gold > 25:
        print(f"[警告] 金色={gold}，可能不在世界页面，尝试恢复...")
        for i in range(5):
            back()
            time.sleep(0.5)
        time.sleep(1)
        img = screencap()
        gold = detect_golden(img)
        print(f"[恢复后] 金色元素={gold}")
    
    # 基准截图
    baseline = screencap()
    baseline_gold = detect_golden(baseline)
    
    # 扫描区域：右上角 (x: 700-1000, y: 20-120)
    # 基于之前验证：y=40/60/80 有效
    x_range = range(750, 950, 50)  # 750, 800, 850, 900, 949
    y_range = [40, 60, 80, 100]   # 之前验证有效的 y 值
    
    best_coord = None
    best_diff = 0
    best_gold_change = 0
    
    print("\n[扫描] 右上角区域...")
    results = []
    
    for x in x_range:
        for y in y_range:
            before = screencap()
            before_gold = detect_golden(before)
            
            tap(x, y)
            time.sleep(1.5)
            
            after = screencap()
            after_gold = detect_golden(after)
            diff = screen_diff(before, after)
            gold_change = after_gold - before_gold
            
            results.append((x, y, diff, gold_change))
            
            # 记录最佳
            if diff > best_diff or gold_change > best_gold_change:
                best_diff = diff
                best_gold_change = gold_change
                best_coord = (x, y)
            
            # 恢复
            back()
            time.sleep(0.3)
    
    # 排序显示前 10 个结果
    results.sort(key=lambda r: (r[2] + r[3]*100000), reverse=True)
    
    print("\n[结果] 前 10 个最佳坐标:")
    for i, (x, y, diff, gold_change) in enumerate(results[:10]):
        marker = "★" if (x, y) == best_coord else " "
        print(f"  {marker} ({x:4}, {y:3}) diff={diff:>8,} gold_change={gold_change:+d}")
    
    if best_coord:
        print(f"\n[最佳] {best_coord} diff={best_diff:,} gold_change={best_gold_change:+d}")
    
    return best_coord

def verify_coordinate(coord):
    """验证给定坐标是否有效"""
    print("\n" + "="*70)
    print(f"坐标验证：{coord}")
    print("="*70)
    
    x, y = coord
    
    # 确保在世界页面
    print("\n[准备] 确保在世界页面...")
    for i in range(10):
        back()
        time.sleep(0.5)
    time.sleep(1)
    
    img = screencap()
    gold = detect_golden(img)
    print(f"[初始] 金色元素={gold}")
    
    # 多次点击测试
    success_count = 0
    for attempt in range(5):
        print(f"\n[尝试 {attempt+1}/5] 点击 {coord}...")
        
        before = screencap()
        before_gold = detect_golden(before)
        
        tap(x, y)
        time.sleep(2)
        
        after = screencap()
        after_gold = detect_golden(after)
        diff = screen_diff(before, after)
        
        print(f"  [结果] diff={diff:,} 金色={before_gold}->{after_gold} (变化={after_gold-before_gold:+d})")
        
        # 判断是否成功打开面板（金色增加 >= 3 或 差异 > 500000）
        if after_gold - before_gold >= 3 or diff > 500000:
            print(f"  [成功] 面板已打开")
            success_count += 1
            
            # 保存截图
            cv2.imwrite(str(PROJECT / 'cache' / f'verify_{x}_{y}.png'), after)
            
            # 恢复
            back()
            time.sleep(1)
        else:
            print(f"  [失败] 面板未打开")
            back()
            time.sleep(0.5)
    
    print(f"\n[统计] 成功 {success_count}/5 次 ({success_count*20}%)")
    
    return success_count >= 3

def main():
    print("\n" + "="*70)
    print("坐标校准")
    print("="*70)
    
    # 扫描找出最佳坐标
    best_coord = find_icon_by_scanning()
    
    if best_coord:
        # 验证最佳坐标
        success = verify_coordinate(best_coord)
        
        if success:
            print(f"\n[✓] 坐标 {best_coord} 验证通过")
            return 0
        else:
            print(f"\n[✗] 坐标 {best_coord} 验证失败")
            return 1
    else:
        print("\n[✗] 未找到有效坐标")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
