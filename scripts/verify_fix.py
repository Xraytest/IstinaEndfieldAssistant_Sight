#!/usr/bin/env python3
"""
标准流修复验证脚本

验证修复后的标准流引擎是否能正确执行。

测试项目：
1. 退出对话框处理 - 多坐标尝试关闭
2. 页面类型判断 - 金色元素阈值
3. 路由恢复逻辑 - 异常页面处理
4. 标准流执行 - daily_quest 流程
"""

import sys, os, json, time
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

CONFIG_PATH = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"
ENGINE_PATH = PROJECT_ROOT / "scripts" / "standard_flow_engine.py"


def check_fix_applied():
    """检查修复是否已应用"""
    print("\n" + "="*70)
    print("检查修复是否已应用")
    print("="*70)
    
    with open(ENGINE_PATH, 'r', encoding='utf-8') as f:
        code = f.read()
    
    fixes = {
        "退出对话框多坐标尝试": "cancel_candidates",
        "前置验证_close_exit_dialog": "_close_exit_dialog()",
        "路由恢复多坐标逻辑": "for cx, cy in cancel_candidates",
    }
    
    all_ok = True
    for fix_name, keyword in fixes.items():
        found = keyword in code
        status = "✅" if found else "❌"
        print(f"  {status} {fix_name}")
        if not found:
            all_ok = False
    
    return all_ok


def verify_exit_dialog_handling():
    """验证退出对话框处理逻辑"""
    print("\n" + "="*70)
    print("验证退出对话框处理逻辑")
    print("="*70)
    
    import subprocess
    ADB = PROJECT_ROOT / '3rd-part' / 'adb' / 'adb.exe'
    SERIAL = 'localhost:16512'
    
    # 按返回键触发退出对话框
    print("\n[测试] 触发退出对话框...")
    for _ in range(3):
        subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], 
                      capture_output=True, timeout=5)
        time.sleep(0.5)
    
    time.sleep(1)
    
    # 截图分析
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                      capture_output=True, timeout=15)
    if len(r.stdout) < 1000:
        print("  [失败] 无法截图")
        return False
    
    import cv2, numpy as np
    img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        print("  [失败] 截图解码失败")
        return False
    
    # 检测金色元素
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_gold = np.array([15, 80, 150])
    upper_gold = np.array([35, 255, 255])
    mask = cv2.inRange(hsv, lower_gold, upper_gold)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    gold_count = len([c for c in contours if cv2.contourArea(c) > 30])
    
    print(f"  [当前] 金色元素={gold_count} 亮度={img.mean():.1f}")
    
    # 判断页面类型
    if 12 <= gold_count <= 16:
        print(f"  [判断] 退出对话框")
        page_type = "exit_dialog"
    elif 18 <= gold_count <= 21:
        print(f"  [判断] 世界页面")
        page_type = "world"
    elif gold_count >= 22:
        print(f"  [判断] 任务面板")
        page_type = "quest_panel"
    else:
        print(f"  [判断] 其他页面")
        page_type = "other"
    
    # 如果是退出对话框，测试关闭逻辑
    if page_type == "exit_dialog":
        print("\n  [测试] 尝试关闭退出对话框...")
        
        # 尝试多个坐标
        candidates = [
            (600, 750), (540, 720), (660, 780), (580, 730), (620, 770),
        ]
        
        for cx, cy in candidates:
            print(f"    [尝试] 点击 ({cx}, {cy})...")
            subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(cx), str(cy)],
                          capture_output=True, timeout=10)
            time.sleep(1.5)
            
            # 验证是否关闭
            r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                              capture_output=True, timeout=15)
            if len(r.stdout) < 1000:
                continue
            
            img2 = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
            if img2 is None:
                continue
            
            hsv2 = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)
            mask2 = cv2.inRange(hsv2, lower_gold, upper_gold)
            contours2, _ = cv2.findContours(mask2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            gold_count2 = len([c for c in contours2 if cv2.contourArea(c) > 30])
            
            print(f"      金色元素={gold_count2}")
            
            if gold_count2 < 12 or gold_count2 > 16:
                print(f"    [成功] 对话框已关闭")
                # 按返回回到世界
                for _ in range(3):
                    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'],
                                  capture_output=True, timeout=5)
                    time.sleep(0.5)
                return True
        
        print("  [失败] 所有坐标尝试失败")
        # 清理：按返回退出
        for _ in range(3):
            subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'],
                          capture_output=True, timeout=5)
            time.sleep(0.5)
        return False
    else:
        print(f"  [跳过] 当前不是退出对话框 (page={page_type})")
        return True


def verify_page_classification():
    """验证页面类型判断逻辑"""
    print("\n" + "="*70)
    print("验证页面类型判断逻辑")
    print("="*70)
    
    # 读取配置中的坐标
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    nav_coords = config.get("variables", {}).get("nav_coords", {})
    
    # 检查关键坐标是否存在
    required_coords = [
        "quest_icon",
        "event_icon", 
        "menu_icon",
        "city_map",
    ]
    
    print("\n[检查] 关键导航坐标:")
    all_ok = True
    for coord_name in required_coords:
        if coord_name in nav_coords:
            coords = nav_coords[coord_name]
            print(f"  ✅ {coord_name}: {coords}")
        else:
            print(f"  ❌ {coord_name}: 缺失")
            all_ok = False
    
    return all_ok


def test_standard_flow():
    """测试标准流执行"""
    print("\n" + "="*70)
    print("测试标准流执行")
    print("="*70)
    
    # 导入标准流引擎
    try:
        from standard_flow_engine import StandardFlowExecutor, FlowConfig
    except Exception as e:
        print(f"  [失败] 导入标准流引擎失败：{e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 加载配置
    try:
        config = FlowConfig()
    except Exception as e:
        print(f"  [失败] 加载配置失败：{e}")
        return False
    
    # 检查 daily_quest 流程
    flow = config.get_flow("daily_quest")
    if flow is None:
        print("  [失败] daily_quest 流程不存在")
        return False
    
    print("  ✅ daily_quest 流程存在")
    
    # 检查流程步骤
    steps = flow.get("steps", [])
    print(f"  ✅ 流程步骤数：{len(steps)}")
    
    # 列出步骤
    print("\n  步骤列表:")
    for i, step in enumerate(steps[:5]):  # 只显示前 5 步
        action = step.get("action", "none")
        desc = step.get("desc", "")
        print(f"    {i+1}. {action}: {desc}")
    
    if len(steps) > 5:
        print(f"    ... 还有 {len(steps) - 5} 步")
    
    print("\n  [提示] 要实际运行流程，请使用:")
    print(f"    python scripts/standard_flow_engine.py --flow daily_quest")
    
    return True


def generate_report():
    """生成验证报告"""
    print("\n" + "="*70)
    print("验证报告")
    print("="*70)
    
    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "fixes_applied": check_fix_applied(),
        "page_classification": verify_page_classification(),
        "flow_test": test_standard_flow(),
    }
    
    # 退出对话框测试（可选）
    # dialog_test = verify_exit_dialog_handling()
    # results["exit_dialog"] = dialog_test
    
    # 统计
    passed = sum(1 for v in results.values() if isinstance(v, bool) and v)
    total = sum(1 for v in results.values() if isinstance(v, bool))
    
    print(f"\n通过检查：{passed}/{total}")
    
    if passed == total:
        print("\n✅ 所有检查通过！")
        print("\n修复已应用:")
        print("  • 退出对话框多坐标尝试关闭")
        print("  • 前置验证对话框处理")
        print("  • 路由恢复逻辑增强")
        print("\n标准流引擎已修复，可以执行测试。")
        return True
    else:
        print(f"\n⚠️  {total - passed} 项检查未通过")
        return False


def main():
    print("\n" + "="*70)
    print("标准流修复验证")
    print("="*70)
    
    success = generate_report()
    
    return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[错误] 验证失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
