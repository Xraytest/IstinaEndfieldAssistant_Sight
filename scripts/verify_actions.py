#!/usr/bin/env python3
"""
标准流动作类型验证脚本

验证标准流引擎是否支持所有需要的动作类型。

用法:
    python scripts/verify_actions.py
"""

import sys, os, json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"
ENGINE_PATH = PROJECT_ROOT / "scripts" / "standard_flow_engine.py"


# 标准流引擎支持的动作类型
SUPPORTED_ACTIONS = {
    "tap": "点击指定坐标",
    "swipe": "滑动/移动",
    "back": "返回键",
    "check": "多源视觉分析确认",
    "claim": "一键领取",
    "navigate": "精确坐标导航",
    "wait": "等待指定时间",
    "long_press": "长按",
}


def check_config_actions():
    """检查配置文件中使用的动作类型"""
    print("\n" + "="*60)
    print("检查配置文件中使用的动作类型")
    print("="*60)
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    flows = config.get("flows", {})
    used_actions = {}
    
    for flow_name, flow_config in flows.items():
        steps = flow_config.get("steps", [])
        for step in steps:
            action = step.get("action", "")
            if action:
                if action not in used_actions:
                    used_actions[action] = []
                used_actions[action].append(flow_name)
    
    print("\n配置中使用的动作类型:")
    for action, flows_list in used_actions.items():
        status = "✅" if action in SUPPORTED_ACTIONS else "❌"
        desc = SUPPORTED_ACTIONS.get(action, "未知")
        print(f"  {status} {action:15} {desc:20} 用于：{', '.join(set(flows_list))}")
    
    return used_actions


def check_engine_implementation():
    """检查引擎中实现的動作类型"""
    print("\n" + "="*60)
    print("检查引擎中实现的動作类型")
    print("="*60)
    
    with open(ENGINE_PATH, 'r', encoding='utf-8') as f:
        engine_code = f.read()
    
    implemented = {}
    for action in SUPPORTED_ACTIONS.keys():
        # 检查是否有对应的处理逻辑
        patterns = [
            f'step_action == "{action}"',
            f'elif step_action == "{action}"',
            f'if action == "{action}"',
            f'elif action == "{action}"',
        ]
        found = any(p in engine_code for p in patterns)
        implemented[action] = found
        status = "✅" if found else "❌"
        desc = SUPPORTED_ACTIONS[action]
        print(f"  {status} {action:15} {desc}")
    
    return implemented


def check_missing_actions(used_actions, implemented):
    """检查缺失的动作类型"""
    print("\n" + "="*60)
    print("缺失的动作类型")
    print("="*60)
    
    missing = []
    for action in used_actions.keys():
        if action not in SUPPORTED_ACTIONS:
            missing.append(action)
        elif not implemented.get(action, False):
            missing.append(action)
    
    if missing:
        print("\n以下动作类型未在引擎中实现:")
        for action in missing:
            flows_list = used_actions[action]
            print(f"  ❌ {action:15} 用于：{', '.join(set(flows_list))}")
        return False
    else:
        print("\n✅ 所有使用的动作类型均已实现")
        return True


def check_action_coverage():
    """检查动作类型覆盖情况"""
    print("\n" + "="*60)
    print("动作类型覆盖情况")
    print("="*60)
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    flows = config.get("flows", {})
    action_stats = {}
    
    for flow_name, flow_config in flows.items():
        steps = flow_config.get("steps", [])
        for step in steps:
            action = step.get("action", "")
            if action:
                if action not in action_stats:
                    action_stats[action] = 0
                action_stats[action] += 1
    
    print("\n动作类型使用统计:")
    total = sum(action_stats.values())
    for action, count in sorted(action_stats.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        print(f"  {action:15} {count:3} 次 ({pct:5.1f}%)")
    
    return action_stats


def generate_report(used_actions, implemented, action_stats):
    """生成验证报告"""
    print("\n" + "="*60)
    print("验证报告")
    print("="*60)
    
    # 统计
    total_actions = len(SUPPORTED_ACTIONS)
    impl_actions = sum(1 for v in implemented.values() if v)
    used_action_count = len(used_actions)
    
    print(f"\n引擎支持的动作类型：{impl_actions}/{total_actions}")
    print(f"配置使用的动作类型：{used_action_count}")
    
    # 检查
    all_ok = True
    for action in used_actions.keys():
        if not implemented.get(action, False):
            print(f"❌ 缺失动作类型：{action}")
            all_ok = False
    
    if all_ok:
        print("\n✅ 所有检查通过")
        print("\n标准流引擎已支持所有需要的动作类型:")
        for action in used_actions.keys():
            desc = SUPPORTED_ACTIONS.get(action, "未知")
            count = action_stats.get(action, 0)
            print(f"  ✅ {action:15} {desc:20} ({count} 次)")
    
    return all_ok


def main():
    print("\n" + "="*60)
    print("标准流动作类型验证")
    print("="*60)
    
    # 检查
    used_actions = check_config_actions()
    implemented = check_engine_implementation()
    missing_ok = check_missing_actions(used_actions, implemented)
    action_stats = check_action_coverage()
    
    # 报告
    success = generate_report(used_actions, implemented, action_stats)
    
    if not missing_ok:
        print("\n⚠️  存在缺失的动作类型，请在标准流引擎中添加支持")
    
    return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[错误] 验证失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
