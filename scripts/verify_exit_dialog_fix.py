#!/usr/bin/env python3
"""
验证 exit_dialog 修复效果 — 基于 MaaEnd 的 CancelButton 思路

测试方法：
1. 触发退出对话框
2. 使用多坐标尝试关闭
3. 通过画面变化验证是否成功
4. 统计成功率

参考：MaaEnd 的 CancelButton 节点（全屏模板匹配）
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

def classify_by_gold(gold_count):
    """基于金色元素数量判断页面类型"""
    if 12 <= gold_count <= 16:
        return "exit_dialog"
    elif 18 <= gold_count <= 21:
        return "world"
    elif gold_count >= 22:
        return "quest_panel"
    else:
        return "other"

def close_with_multi_coords():
    """
    多坐标尝试关闭退出对话框
    
    返回：(success, best_coord, best_diff)
    """
    # 候选坐标：基于 1920x1080 分辨率，覆盖取消按钮的可能位置
    cancel_candidates = [
        (600, 750),   # 默认估计
        (550, 730),   # 偏左上
        (650, 770),   # 偏右下
        (580, 740),   # 偏左
        (620, 760),   # 偏右
        (540, 720),   # 更左上
        (660, 780),   # 更右下
        (560, 750),   # 左中
        (640, 750),   # 右中
        (600, 730),   # 中上
        (600, 770),   # 中下
    ]
    
    best_coord = None
    best_diff = 0
    
    for i, (cx, cy) in enumerate(cancel_candidates):
        # 截图
        before = screencap()
        if before is None:
            continue
        
        gold_before = detect_golden(before)
        page_before = classify_by_gold(gold_before)
        
        if page_before != "exit_dialog":
            return True, best_coord, best_diff  # 已经不在退出对话框
        
        # 点击
        tap(cx, cy)
        time.sleep(1.5)
        
        # 截图验证
        after = screencap()
        if after is None:
            continue
        
        # 计算画面变化
        diff = screen_diff(before, after)
        gold_after = detect_golden(after)
        page_after = classify_by_gold(gold_after)
        
        # 记录最佳坐标
        if diff > best_diff:
            best_diff = diff
            best_coord = (cx, cy)
        
        # 判断是否成功关闭
        if diff > 500000 and page_after != "exit_dialog":
            print(f"  [成功] ({cx}, {cy}) diff={diff:,} {page_before}->{page_after}")
            return True, (cx, cy), diff
        elif diff > 200000 and gold_after < 12:
            print(f"  [可能成功] ({cx}, {cy}) diff={diff:,} 金色减少")
            return True, (cx, cy), diff
        
        # 恢复退出对话框状态（按返回）
        back()
        time.sleep(1)
    
    return False, best_coord, best_diff

def close_with_back():
    """使用 back 键关闭退出对话框"""
    before = screencap()
    back()
    time.sleep(1.5)
    after = screencap()
    
    if before is not None and after is not None:
        diff = screen_diff(before, after)
        gold_after = detect_golden(after)
        page_after = classify_by_gold(gold_after)
        
        print(f"  [back] diff={diff:,} 页面={page_after} (金色={gold_after})")
        
        if page_after != "exit_dialog":
            return True, None, diff
    
    return False, None, 0

def run_test_round(round_num, total_rounds):
    """运行一轮测试"""
    print(f"\n{'='*60}")
    print(f"测试轮次 {round_num}/{total_rounds}")
    print("="*60)
    
    # 确保在世界页面
    print("[准备] 确保在世界页面...")
    for _ in range(5):
        back()
        time.sleep(0.5)
    time.sleep(1)
    
    # 触发退出对话框
    print("[触发] 按返回键触发退出对话框...")
    back()
    time.sleep(2)
    
    # 验证是否出现退出对话框
    img = screencap()
    gold = detect_golden(img)
    page = classify_by_gold(gold)
    
    print(f"[当前] 页面={page} (金色={gold})")
    
    if page != "exit_dialog":
        print(f"[跳过] 未检测到退出对话框")
        return None
    
    # 方法 1：多坐标尝试
    print("\n[方法 1] 多坐标尝试...")
    success1, coord1, diff1 = close_with_multi_coords()
    
    # 验证结果
    time.sleep(1)
    img = screencap()
    gold = detect_golden(img)
    page = classify_by_gold(gold)
    
    if page != "exit_dialog":
        print(f"[结果] 方法 1 成功，当前页面={page}")
        return {"method": "multi_coords", "coord": coord1, "diff": diff1, "success": True}
    
    # 方法 2：back 键
    print("\n[方法 2] back 键...")
    success2, coord2, diff2 = close_with_back()
    
    time.sleep(1)
    img = screencap()
    gold = detect_golden(img)
    page = classify_by_gold(gold)
    
    if page != "exit_dialog":
        print(f"[结果] 方法 2 成功，当前页面={page}")
        return {"method": "back", "coord": coord2, "diff": diff2, "success": True}
    
    print("[结果] 所有方法失败")
    return {"method": "none", "coord": None, "diff": 0, "success": False}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=3, help="测试轮次数")
    parser.add_argument("--single", action="store_true", help="单轮测试")
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("Exit Dialog 修复验证")
    print("="*70)
    
    if args.single:
        result = run_test_round(1, 1)
        if result:
            print(f"\n结果：{result}")
        return 0
    
    # 多轮测试
    results = []
    for i in range(args.rounds):
        result = run_test_round(i + 1, args.rounds)
        if result:
            results.append(result)
        time.sleep(2)
    
    # 统计
    print("\n" + "="*70)
    print("统计结果")
    print("="*70)
    
    success_count = sum(1 for r in results if r["success"])
    print(f"\n总轮次：{len(results)}")
    print(f"成功：{success_count}")
    print(f"失败：{len(results) - success_count}")
    print(f"成功率：{success_count/len(results)*100:.1f}%" if results else "N/A")
    
    # 方法分布
    methods = {}
    for r in results:
        method = r["method"]
        if method not in methods:
            methods[method] = 0
        methods[method] += 1
    
    print("\n方法分布:")
    for method, count in methods.items():
        print(f"  {method}: {count}")
    
    # 最佳坐标
    coords = [r["coord"] for r in results if r["coord"]]
    if coords:
        from collections import Counter
        coord_counts = Counter(str(c) for c in coords)
        print("\n最佳坐标分布:")
        for coord_str, count in coord_counts.most_common(3):
            print(f"  {coord_str}: {count}次")
    
    return 0 if success_count > 0 else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
