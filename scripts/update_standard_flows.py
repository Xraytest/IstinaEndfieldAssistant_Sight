#!/usr/bin/env python3
"""
更新标准流配置 - 基于 MaaEnd 设计模式完善 daily_quest 和 weekly_quest 流程

参考 MaaEnd 设计模式:
1. DijiangRewards: Navigation(导航)→StatusCheck(状态检测)→Claim(领取)→Back(返回)
2. BAKER: SwitchTab(切换标签)→SwipeFilter(滑动筛选)→FilterUnread(查找可领取)→Claim(领取)
3. GrowthChamber: TargetNotFound 时滑动查找
4. Common/Button: ClickKey(key=4) 通用返回
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"

def update_flows():
    # 读取配置
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 更新 daily_quest 流程
    config["flows"]["daily_quest"] = {
        "enabled": True,
        "description": "完成每日任务并领取奖励（参考 MaaEnd DijiangRewards 导航模式）",
        "_status": "基于 MaaEnd 设计模式完善：导航分离 + 状态检测 + 滑动查找 + 错误恢复",
        "_design": "MaaEnd 模式：Navigation(打开面板)→StatusCheck(确认页面)→ScrollFind(滑动查找)→Claim(领取)→Back(返回)",
        "steps": [
            {
                "id": "ensure_world",
                "action": "check",
                "expect": "world",
                "desc": "确保在探索界面（世界地图）"
            },
            {
                "id": "open_quest_panel",
                "action": "tap",
                "coords": "{{nav_coords.quest_icon}}",
                "wait": 4,
                "desc": "打开任务面板 (860,80) ✓ 已验证"
            },
            {
                "id": "verify_quest_panel",
                "action": "check",
                "expect": "quest_panel",
                "desc": "验证任务面板已打开（金色元素≥22）"
            },
            {
                "id": "scroll_daily_tasks",
                "action": "swipe",
                "start": [540, 800],
                "end": [540, 400],
                "duration": 500,
                "desc": "滑动查找每日任务（参考 MaaEnd GrowthChamberTargetNotFound）"
            },
            {
                "id": "check_daily_status",
                "action": "check",
                "desc": "检查每日任务状态（可领取/进行中/已完成）"
            },
            {
                "id": "claim_daily_rewards",
                "action": "claim",
                "target": "claim_all",
                "desc": "一键领取每日任务奖励"
            },
            {
                "id": "verify_claim",
                "action": "wait",
                "wait": 2,
                "desc": "等待领取动画完成"
            },
            {
                "id": "close_quest_panel",
                "action": "back",
                "wait": 2,
                "desc": "返回探索界面（参考 MaaEnd ClickKey key=4）"
            },
            {
                "id": "verify_world_return",
                "action": "check",
                "expect": "world",
                "desc": "验证已返回世界地图"
            }
        ]
    }
    
    # 更新 weekly_quest 流程
    config["flows"]["weekly_quest"] = {
        "enabled": True,
        "description": "完成周常任务并领取奖励（参考 MaaEnd BAKER 筛选模式）",
        "_status": "基于 MaaEnd BAKER 设计：Tab 切换→滑动查找→筛选未读→领取",
        "_design": "MaaEnd BAKER 模式：SwitchTab(切换标签)→SwipeFilter(滑动筛选)→FilterUnread(查找可领取)→Claim(领取)",
        "steps": [
            {
                "id": "ensure_world",
                "action": "check",
                "expect": "world",
                "desc": "确保在探索界面"
            },
            {
                "id": "open_quest_panel",
                "action": "tap",
                "coords": "{{nav_coords.quest_icon}}",
                "wait": 4,
                "desc": "打开任务面板 (860,80) ✓"
            },
            {
                "id": "verify_quest_panel",
                "action": "check",
                "expect": "quest_panel",
                "desc": "验证任务面板已打开"
            },
            {
                "id": "switch_to_weekly",
                "action": "tap",
                "coords": "{{nav_coords.weekly_tab}}",
                "wait": 3,
                "desc": "切换到周常标签页 (810,300)"
            },
            {
                "id": "scroll_weekly_list",
                "action": "swipe",
                "start": [540, 900],
                "end": [540, 500],
                "duration": 600,
                "desc": "滑动查找周常任务列表（参考 MaaEnd BakerSwipeFilter）"
            },
            {
                "id": "check_weekly_status",
                "action": "check",
                "desc": "检查周常任务状态（参考 MaaEnd BakerFilterUnread）"
            },
            {
                "id": "claim_weekly_rewards",
                "action": "claim",
                "target": "claim_all",
                "desc": "一键领取周常任务奖励"
            },
            {
                "id": "verify_claim",
                "action": "wait",
                "wait": 2,
                "desc": "等待领取动画完成"
            },
            {
                "id": "return_world",
                "action": "back",
                "wait": 2,
                "desc": "返回探索界面"
            },
            {
                "id": "verify_world_return",
                "action": "check",
                "expect": "world",
                "desc": "验证已返回世界地图"
            }
        ]
    }
    
    # 保存配置
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print("✅ 标准流配置已更新")
    print(f"   - daily_quest: 9 个步骤 (MaaEnd DijiangRewards 模式)")
    print(f"   - weekly_quest: 11 个步骤 (MaaEnd BAKER 模式)")

if __name__ == "__main__":
    update_flows()
