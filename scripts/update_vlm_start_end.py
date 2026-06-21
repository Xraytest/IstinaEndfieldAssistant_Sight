#!/usr/bin/env python3
"""
更新标准流配置 - VLM 判定行为的起末

根据 Stop hook 条件："修正流程，一个行为的起末由 vlm 判定"

更新内容:
1. 为 tap 步骤添加 vlm_verify 字段（动作后验证）
2. 更新 vlm_prompt 为动作前确认提示
3. 添加 vlm_verify_prompt 为动作后验证提示
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"

def update_vlm_start_end():
    # 读取配置
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    updated_count = 0
    
    # 更新 daily_quest 和 weekly_quest 的 tap 步骤
    for flow_name in ["daily_quest", "weekly_quest"]:
        if flow_name not in config["flows"]:
            continue
            
        steps = config["flows"][flow_name]["steps"]
        for step in steps:
            if step.get("action") == "tap" and step.get("vlm_confirm"):
                # 添加动作后验证配置
                coords_str = str(step.get("coords", ""))
                
                # 根据坐标类型设置验证提示
                if "quest_icon" in coords_str:
                    step["vlm_verify"] = True
                    step["vlm_verify_prompt"] = "验证任务面板已打开（画面中有任务列表或任务相关 UI 元素）"
                elif "weekly_tab" in coords_str:
                    step["vlm_verify"] = True
                    step["vlm_verify_prompt"] = "验证已切换到周常标签页（画面中显示周常/每周任务列表）"
                else:
                    step["vlm_verify"] = True
                    step["vlm_verify_prompt"] = "验证点击操作已成功执行（画面有相应变化或目标页面已打开）"
                
                updated_count += 1
                print(f"  [{flow_name}] {step.get('id')}: 添加 vlm_verify")
    
    # 更新 execution 配置
    config["execution"]["vlm_start_end_mode"] = "enabled"
    config["execution"]["_vlm_start_end_note"] = "行为的起始和结束均由 VLM 判定"
    
    # 保存配置
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 标准流配置已更新：{updated_count} 个 tap 步骤添加 vlm_verify")
    print("   - 行为起始：vlm_confirm (动作前确认)")
    print("   - 行为结束：vlm_verify (动作后验证)")

if __name__ == "__main__":
    update_vlm_start_end()
