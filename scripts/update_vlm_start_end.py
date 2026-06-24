#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏇存柊鏍囧噯娴侀厤缃?- VLM 鍒ゅ畾琛屼负鐨勮捣鏈?
鏍规嵁 Stop hook 鏉′欢锛?淇娴佺▼锛屼竴涓涓虹殑璧锋湯鐢?vlm 鍒ゅ畾"

鏇存柊鍐呭:
1. 涓?tap 姝ラ娣诲姞 vlm_verify 瀛楁锛堝姩浣滃悗楠岃瘉锛?2. 鏇存柊 vlm_prompt 涓哄姩浣滃墠纭鎻愮ず
3. 娣诲姞 vlm_verify_prompt 涓哄姩浣滃悗楠岃瘉鎻愮ず
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"

def update_vlm_start_end():
    # 璇诲彇閰嶇疆
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    updated_count = 0
    
    # 鏇存柊 daily_quest 鍜?weekly_quest 鐨?tap 姝ラ
    for flow_name in ["daily_quest", "weekly_quest"]:
        if flow_name not in config["flows"]:
            continue
            
        steps = config["flows"][flow_name]["steps"]
        for step in steps:
            if step.get("action") == "tap" and step.get("vlm_confirm"):
                # 娣诲姞鍔ㄤ綔鍚庨獙璇侀厤缃?                coords_str = str(step.get("coords", ""))
                
                # 鏍规嵁鍧愭爣绫诲瀷璁剧疆楠岃瘉鎻愮ず
                if "quest_icon" in coords_str:
                    step["vlm_verify"] = True
                    step["vlm_verify_prompt"] = "楠岃瘉浠诲姟闈㈡澘宸叉墦寮€锛堢敾闈腑鏈変换鍔″垪琛ㄦ垨浠诲姟鐩稿叧 UI 鍏冪礌锛?
                elif "weekly_tab" in coords_str:
                    step["vlm_verify"] = True
                    step["vlm_verify_prompt"] = "楠岃瘉宸插垏鎹㈠埌鍛ㄥ父鏍囩椤碉紙鐢婚潰涓樉绀哄懆甯?姣忓懆浠诲姟鍒楄〃锛?
                else:
                    step["vlm_verify"] = True
                    step["vlm_verify_prompt"] = "楠岃瘉鐐瑰嚮鎿嶄綔宸叉垚鍔熸墽琛岋紙鐢婚潰鏈夌浉搴斿彉鍖栨垨鐩爣椤甸潰宸叉墦寮€锛?
                
                updated_count += 1
                print(f"  [{flow_name}] {step.get('id')}: 娣诲姞 vlm_verify")
    
    # 鏇存柊 execution 閰嶇疆
    config["execution"]["vlm_start_end_mode"] = "enabled"
    config["execution"]["_vlm_start_end_note"] = "琛屼负鐨勮捣濮嬪拰缁撴潫鍧囩敱 VLM 鍒ゅ畾"
    
    # 淇濆瓨閰嶇疆
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"\n鉁?鏍囧噯娴侀厤缃凡鏇存柊锛歿updated_count} 涓?tap 姝ラ娣诲姞 vlm_verify")
    print("   - 琛屼负璧峰锛歷lm_confirm (鍔ㄤ綔鍓嶇‘璁?")
    print("   - 琛屼负缁撴潫锛歷lm_verify (鍔ㄤ綔鍚庨獙璇?")

if __name__ == "__main__":
    update_vlm_start_end()

