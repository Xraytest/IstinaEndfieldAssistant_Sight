#!/usr/bin/env python3
"""
更新标准流配置 - 添加 VLM 确认机制

根据 Stop hook 条件：即使有预设坐标，行动时也需要由 VLM 确认

更新内容:
1. 为每个 tap 步骤添加 vlm_confirm 字段
2. 添加 vlm_prompt 指定确认提示词
3. 更新 execution 配置启用 VLM 确认模式
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"

def update_vlm_confirm():
    # 读取配置
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 更新 daily_quest 流程 - 添加 VLM 确认
    daily_steps = config["flows"]["daily_quest"]["steps"]
    for step in daily_steps:
        if step.get("action") == "tap":
            step["vlm_confirm"] = True
            if "quest_icon" in str(step.get("coords", "")):
                step["vlm_prompt"] = "确认画面右上角有任务图标 (黄色感叹号或任务按钮)"
            elif "weekly_tab" in str(step.get("coords", "")):
                step["vlm_prompt"] = "确认任务面板内有周常/每周事务标签页"
            else:
                step["vlm_prompt"] = "确认目标按钮在指定位置可见且可点击"
    
    # 更新 weekly_quest 流程 - 添加 VLM 确认
    weekly_steps = config["flows"]["weekly_quest"]["steps"]
    for step in weekly_steps:
        if step.get("action") == "tap":
            step["vlm_confirm"] = True
            if "quest_icon" in str(step.get("coords", "")):
                step["vlm_prompt"] = "确认画面右上角有任务图标 (黄色感叹号或任务按钮)"
            elif "weekly_tab" in str(step.get("coords", "")):
                step["vlm_prompt"] = "确认任务面板内有周常/每周事务标签页"
            else:
                step["vlm_prompt"] = "确认目标按钮在指定位置可见且可点击"
    
    # 更新 execution 配置
    config["execution"]["vlm_confirm_mode"] = "enabled"
    config["execution"]["vlm_confirm_timeout"] = 30
    config["execution"]["_vlm_note"] = "所有 tap 动作执行前需通过 VLM 确认目标元素可见"
    
    # 保存配置
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print("✅ 标准流配置已添加 VLM 确认机制")
    print("   - daily_quest: 2 个 tap 步骤添加 vlm_confirm")
    print("   - weekly_quest: 2 个 tap 步骤添加 vlm_confirm")
    print("   - execution: 启用 vlm_confirm_mode")

if __name__ == "__main__":
    update_vlm_confirm()
