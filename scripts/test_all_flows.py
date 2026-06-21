#!/usr/bin/env python3
"""
标准流综合测试脚本

测试所有标准流的配置正确性和可执行性。

用法:
    python scripts/test_all_flows.py
"""

import sys, os, json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"


def check_config():
    """检查配置文件"""
    print("\n" + "="*60)
    print("检查配置文件")
    print("="*60)
    
    if not CONFIG_PATH.exists():
        print(f"[错误] 配置文件不存在：{CONFIG_PATH}")
        return False
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 检查版本
    version = config.get("version", "unknown")
    print(f"[配置] 版本：{version}")
    
    # 检查变量
    nav_coords = config.get("variables", {}).get("nav_coords", {})
    print(f"[变量] 导航坐标数：{len([k for k in nav_coords if not k.startswith('_')])}")
    
    # 检查流程
    flows = config.get("flows", {})
    print(f"[流程] 总数：{len(flows)}")
    
    enabled_count = sum(1 for f in flows.values() if f.get("enabled", True))
    print(f"[流程] 启用：{enabled_count}")
    
    # 检查待验证项
    todo = config.get("execution", {}).get("_verification_todo", [])
    if todo:
        print(f"\n[待验证] {len(todo)} 项:")
        for t in todo:
            print(f"  - {t}")
    
    return True


def check_flow_steps(flow_name, flow_config):
    """检查单个流程的步骤"""
    print(f"\n[流程] {flow_name}")
    print("-" * 40)
    
    steps = flow_config.get("steps", [])
    print(f"  步骤数：{len(steps)}")
    
    # 检查每个步骤
    issues = []
    for i, step in enumerate(steps):
        step_id = step.get("id", f"step_{i}")
        action = step.get("action", "")
        
        # 检查坐标引用
        if "coords" in step:
            coords = step["coords"]
            if isinstance(coords, str) and coords.startswith("{{"):
                # 变量引用
                var_name = coords[2:-1].strip()
                if not var_name:
                    issues.append(f"  [步骤 {step_id}] 空变量引用")
            elif isinstance(coords, list) and len(coords) == 2:
                # 直接坐标
                x, y = coords
                if x < 0 or x > 1920 or y < 0 or y > 1080:
                    issues.append(f"  [步骤 {step_id}] 坐标超出范围：({x}, {y})")
        
        # 检查 action 类型
        valid_actions = ["tap", "swipe", "back", "check", "claim", "navigate", "wait"]
        if action and action not in valid_actions:
            issues.append(f"  [步骤 {step_id}] 未知 action: {action}")
    
    if issues:
        for issue in issues:
            print(issue)
    else:
        print("  ✅ 步骤检查通过")
    
    return len(issues) == 0


def check_verified_coords():
    """检查已验证的坐标"""
    print("\n" + "="*60)
    print("已验证坐标状态")
    print("="*60)
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    nav_coords = config.get("variables", {}).get("nav_coords", {})
    
    # 已验证的坐标
    verified = [
        "quest_icon",
        "event_icon",
        "menu_icon",
        "city_map",
        "industry_panel",
        "region_building",
        "industry_brief",
    ]
    
    # 待验证的坐标
    pending = [
        "base_entry_menu",
        "char_entry_menu",
        "daily_claim",
        "weekly_tab",
        "claim_all",
        "event_sub",
        "mid_action",
        "production_btn",
        "confirm_btn",
        "confirm_dialog",
        "exit_cancel",
    ]
    
    print("\n已验证坐标:")
    for name in verified:
        if name in nav_coords:
            coords = nav_coords[name]
            print(f"  ✅ {name}: {coords}")
    
    print("\n待验证坐标:")
    for name in pending:
        if name in nav_coords:
            coords = nav_coords[name]
            print(f"  ⚠️  {name}: {coords} (待确认)")
    
    return True


def check_flow_dependencies():
    """检查流程依赖关系"""
    print("\n" + "="*60)
    print("流程依赖关系")
    print("="*60)
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    flows = config.get("flows", {})
    
    # 分析每个流程的页面流转
    for flow_name, flow_config in flows.items():
        if not flow_config.get("enabled", True):
            continue
        
        steps = flow_config.get("steps", [])
        pages = []
        
        for step in steps:
            expect = step.get("expect", "")
            if expect:
                pages.append(expect)
        
        if pages:
            print(f"\n{flow_name}:")
            print(f"  页面流转：{' → '.join(pages)}")
    
    return True


def run_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("标准流综合测试")
    print("="*60)
    
    # 1. 检查配置
    if not check_config():
        print("\n[错误] 配置检查失败")
        return False
    
    # 2. 检查已验证坐标
    check_verified_coords()
    
    # 3. 检查流程依赖
    check_flow_dependencies()
    
    # 4. 检查每个流程
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    flows = config.get("flows", {})
    all_passed = True
    
    for flow_name, flow_config in flows.items():
        if not check_flow_steps(flow_name, flow_config):
            all_passed = False
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    if all_passed:
        print("✅ 所有检查通过")
    else:
        print("⚠️  存在一些问题，请检查上述输出")
    
    print("\n下一步:")
    print("  1. 运行 verify_menu_entries.py 验证菜单内坐标")
    print("  2. 更新 flows_config.json 中的待验证坐标")
    print("  3. 运行标准流引擎测试:")
    print("     python scripts/standard_flow_engine.py --flow daily_quest")
    
    return all_passed


if __name__ == "__main__":
    try:
        success = run_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[错误] 测试失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
