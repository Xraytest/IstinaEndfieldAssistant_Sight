#!/usr/bin/env python3
"""
更新标准流配置头部注释和 execution TODO 列表
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"

def update_config_header():
    # 读取配置
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 更新头部注释
    config["_note"] = "2026-06-14 基于 MaaEnd 设计模式完善。✓=world 验证有效 ?=面板内未验证 →=需通过菜单间接到达"
    
    # 更新 execution 部分的 TODO
    config["execution"]["_verification_todo"] = [
        "✅ COMPLETED: daily_quest 基于 MaaEnd DijiangRewards 模式完善 (9 步骤)",
        "✅ COMPLETED: weekly_quest 基于 MaaEnd BAKER 模式完善 (11 步骤)",
        "TODO: 运行 verify_menu_entries.py 验证菜单内 base/character 精确坐标",
        "TODO: 确认 claim_all (810,900) 在各面板内有效",
        "TODO: 菜单内 base_entry_menu 当前用 (960,400) 估计值，需精确验证",
        "TODO: 菜单内 char_entry_menu 当前用 (1200,330) 估计值，需精确验证",
        "TODO: 参考 MaaEnd AutoCollect 模式完善 resource_collection 流程",
        "TODO: 参考 MaaEnd DeliveryJobs 模式完善 delivery_mission 流程"
    ]
    
    # 保存配置
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print("✅ 配置头部注释和 TODO 列表已更新")

if __name__ == "__main__":
    update_config_header()
