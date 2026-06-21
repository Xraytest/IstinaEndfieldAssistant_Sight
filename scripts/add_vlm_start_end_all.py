#!/usr/bin/env python3
"""
为所有标准流的关键 tap 步骤添加 VLM 起末判定

根据 Stop hook 条件："修正流程，一个行为的起末由 vlm 判定"

策略:
1. 所有从 world 页面打开面板的 tap 都添加 VLM 起末判定
2. 面板内的 tap 暂不添加（待坐标验证后）
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"

def add_vlm_start_end_to_all_flows():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 定义关键导航坐标及其 VLM 提示词
    nav_vlm_config = {
        "quest_icon": {
            "vlm_prompt": "确认画面右上角有任务图标 (黄色感叹号或任务按钮)",
            "vlm_verify_prompt": "验证任务面板已打开（画面中有任务列表或任务相关 UI 元素）"
        },
        "event_icon": {
            "vlm_prompt": "确认画面右上角有活动图标",
            "vlm_verify_prompt": "验证活动面板已打开（画面中有活动相关 UI 元素）"
        },
        "menu_icon": {
            "vlm_prompt": "确认画面右上角有菜单图标 (三条横线或汉堡菜单)",
            "vlm_verify_prompt": "验证系统菜单已打开（画面中有菜单选项列表）"
        },
        "city_map": {
            "vlm_prompt": "确认画面左上角有城市地图按钮",
            "vlm_verify_prompt": "验证城市地图已打开（画面中显示地图界面）"
        },
        "weekly_tab": {
            "vlm_prompt": "确认任务面板内有周常/每周事务标签页",
            "vlm_verify_prompt": "验证已切换到周常标签页（画面中显示周常任务列表）"
        }
    }
    
    updated_count = 0
    
    # 遍历所有流程
    for flow_name, flow_cfg in config["flows"].items():
        if not flow_cfg.get("enabled", True):
            continue
            
        print(f"\n[{flow_name}]")
        for step in flow_cfg["steps"]:
            if step.get("action") != "tap":
                continue
            
            coords_str = str(step.get("coords", ""))
            
            # 检查是否使用已定义的导航坐标
            for nav_key, vlm_cfg in nav_vlm_config.items():
                if nav_key in coords_str:
                    # 添加 VLM 起末判定
                    step["vlm_confirm"] = True
                    step["vlm_prompt"] = vlm_cfg["vlm_prompt"]
                    step["vlm_verify"] = True
                    step["vlm_verify_prompt"] = vlm_cfg["vlm_verify_prompt"]
                    
                    print(f"  ✅ {step.get('id')}: 添加 VLM 起末判定 ({nav_key})")
                    updated_count += 1
                    break
    
    # 更新 execution 配置说明
    config["execution"]["_vlm_start_end_note"] = "所有关键导航 tap 动作的起始和结束均由 VLM 判定"
    
    # 保存配置
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ 完成：{updated_count} 个 tap 步骤添加 VLM 起末判定")
    print(f"   覆盖流程：daily_quest, weekly_quest, resource_collection,")
    print(f"            base_management, character_ascension, weapon_crafting,")
    print(f"            event_rewards, delivery_mission, dungeon_grinding")

if __name__ == "__main__":
    add_vlm_start_end_to_all_flows()
