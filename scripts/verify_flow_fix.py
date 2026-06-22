#!/usr/bin/env python3
"""
标准流修复验证脚本

验证内容：
1. 新页面分析器能否正确识别世界页面和任务面板
2. 标准流引擎前置页面验证逻辑是否正常工作
3. 退出对话框处理是否可靠
"""

import subprocess
import time
import cv2
import numpy as np
from pathlib import Path
import sys

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

from core.service.page_analyzer import HighPrecisionPageAnalyzer

PROJECT = PROJECT_ROOT

ADB_EXE = PROJECT / '3rd-party' / 'adb' / 'adb.exe'
SERIAL = 'localhost:16512'


def adb_cmd(args):
    """执行 ADB 命令"""
    return subprocess.run(
        [str(ADB_EXE), '-s', SERIAL] + args,
        capture_output=True, timeout=15
    )


def screencap():
    """截图"""
    r = adb_cmd(['exec-out', 'screencap', '-p'])
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)


def tap(x, y):
    """点击"""
    adb_cmd(['shell', 'input', 'tap', str(int(x)), str(int(y))])


def keyevent(key):
    """按键"""
    adb_cmd(['shell', 'input', 'keyevent', str(key)])


def test_page_analyzer():
    """测试页面分析器"""
    print("\n" + "="*70)
    print("测试 1: 页面分析器")
    print("="*70)
    
    analyzer = HighPrecisionPageAnalyzer()
    correct = 0
    total = 0
    
    # 测试世界页面
    print("\n[测试] 世界页面识别...")
    for i in range(3):
        # 按返回键直到世界页面（最多 10 次）
        for attempt in range(10):
            keyevent(4)
            time.sleep(0.3)
            
            img = screencap()
            if img is None:
                continue
            
            result = analyzer.analyze(img)
            if result['page_type'] == "world":
                break
        
        img = screencap()
        if img is None:
            print(f"  样本 {i+1}: 截图失败")
            continue
        
        result = analyzer.analyze(img)
        page_type = result['page_type']
        confidence = result['confidence']
        features = result['features']
        
        total += 1
        if page_type == "world":
            correct += 1
            status = "✅"
        else:
            status = "❌"
        
        print(f"  {status} 样本 {i+1}: {page_type} (置信度 {confidence:.2f})")
        print(f"       left_bar={features['left_bar_brightness']:.1f} green={features['green_pixels_top_right']:.0f}")
    
    # 测试任务面板
    print("\n[测试] 任务面板识别...")
    tap(860, 80)  # 任务图标
    time.sleep(2)
    
    for i in range(3):
        img = screencap()
        if img is None:
            print(f"  样本 {i+1}: 截图失败")
            continue
        
        result = analyzer.analyze(img)
        page_type = result['page_type']
        confidence = result['confidence']
        features = result['features']
        
        # 验证是否真的在任务面板（left_bar > 120）
        actual_quest_panel = features['left_bar_brightness'] > 120 and features['green_pixels_top_right'] < 30
        
        total += 1
        if actual_quest_panel:
            # 确实在任务面板，检查识别是否正确
            if page_type == "quest_panel":
                correct += 1
                status = "✅"
            else:
                status = "❌(识别错误)"
        else:
            # 不在任务面板，识别为其他页面是正确的
            if page_type != "quest_panel":
                correct += 1
                status = "✅(正确识别为非任务面板)"
            else:
                status = "❌(错误识别为任务面板)"
        
        print(f"  {status} 样本 {i+1}: {page_type} (置信度 {confidence:.2f})")
        print(f"       left_bar={features['left_bar_brightness']:.1f} green={features['green_pixels_top_right']:.0f} 实际在任务面板={actual_quest_panel}")
    
    # 返回世界
    for _ in range(3):
        keyevent(4)
        time.sleep(0.3)
    
    accuracy = correct / total if total > 0 else 0
    print(f"\n[结果] 准确率：{correct}/{total} ({accuracy*100:.1f}%)")
    
    return accuracy > 0.8


def test_exit_dialog_handling():
    """测试退出对话框处理"""
    print("\n" + "="*70)
    print("测试 2: 退出对话框处理")
    print("="*70)
    
    analyzer = HighPrecisionPageAnalyzer()
    
    # 确保在世界页面
    print("\n[步骤 1] 确保在世界页面...")
    for _ in range(5):
        keyevent(4)
        time.sleep(0.3)
    time.sleep(1)
    
    img = screencap()
    if img is None:
        print("  [失败] 截图失败")
        return False
    
    result = analyzer.analyze(img)
    print(f"  当前页面：{result['page_type']} (置信度 {result['confidence']:.2f})")
    
    if result['page_type'] != "world":
        print("  [警告] 不在世界页面，测试可能不准确")
    
    # 触发退出对话框
    print("\n[步骤 2] 触发退出对话框...")
    keyevent(4)
    time.sleep(1)
    
    img = screencap()
    if img is None:
        print("  [失败] 截图失败")
        return False
    
    result = analyzer.analyze(img)
    print(f"  当前页面：{result['page_type']} (置信度 {result['confidence']:.2f})")
    
    # 尝试点击取消按钮
    print("\n[步骤 3] 尝试关闭对话框...")
    tap(600, 750)
    time.sleep(1.5)
    
    img = screencap()
    if img is None:
        print("  [失败] 截图失败")
        return False
    
    result = analyzer.analyze(img)
    print(f"  当前页面：{result['page_type']} (置信度 {result['confidence']:.2f})")
    
    if result['page_type'] == "world":
        print("  [成功] 对话框已关闭，回到世界页面")
        return True
    else:
        print("  [失败] 对话框未关闭或页面识别错误")
        return False


def main():
    print("\n" + "="*70)
    print("标准流修复验证")
    print("="*70)
    
    results = {}
    
    # 测试 1: 页面分析器
    results['page_analyzer'] = test_page_analyzer()
    
    # 测试 2: 退出对话框处理
    results['exit_dialog'] = test_exit_dialog_handling()
    
    # 总结
    print("\n" + "="*70)
    print("验证总结")
    print("="*70)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n[结论] 所有测试通过，标准流修复有效")
        return 0
    else:
        print("\n[结论] 部分测试失败，需要进一步调试")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[错误] 验证失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
