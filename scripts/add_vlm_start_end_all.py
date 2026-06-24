#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
涓烘墍鏈夋爣鍑嗘祦鐨勫叧閿?tap 姝ラ娣诲姞 VLM 璧锋湯鍒ゅ畾

鏍规嵁 Stop hook 鏉′欢锛?淇娴佺▼锛屼竴涓涓虹殑璧锋湯鐢?vlm 鍒ゅ畾"

绛栫暐:
1. 鎵€鏈変粠 world 椤甸潰鎵撳紑闈㈡澘鐨?tap 閮芥坊鍔?VLM 璧锋湯鍒ゅ畾
2. 闈㈡澘鍐呯殑 tap 鏆備笉娣诲姞锛堝緟鍧愭爣楠岃瘉鍚庯級
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"

def add_vlm_start_end_to_all_flows():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 瀹氫箟鍏抽敭瀵艰埅鍧愭爣鍙婂叾 VLM 鎻愮ず璇?    nav_vlm_config = {
        "quest_icon": {
            "vlm_prompt": "纭鐢婚潰鍙充笂瑙掓湁浠诲姟鍥炬爣 (榛勮壊鎰熷徆鍙锋垨浠诲姟鎸夐挳)",
            "vlm_verify_prompt": "楠岃瘉浠诲姟闈㈡澘宸叉墦寮€锛堢敾闈腑鏈変换鍔″垪琛ㄦ垨浠诲姟鐩稿叧 UI 鍏冪礌锛?
        },
        "event_icon": {
            "vlm_prompt": "纭鐢婚潰鍙充笂瑙掓湁娲诲姩鍥炬爣",
            "vlm_verify_prompt": "楠岃瘉娲诲姩闈㈡澘宸叉墦寮€锛堢敾闈腑鏈夋椿鍔ㄧ浉鍏?UI 鍏冪礌锛?
        },
        "menu_icon": {
            "vlm_prompt": "纭鐢婚潰鍙充笂瑙掓湁鑿滃崟鍥炬爣 (涓夋潯妯嚎鎴栨眽鍫¤彍鍗?",
            "vlm_verify_prompt": "楠岃瘉绯荤粺鑿滃崟宸叉墦寮€锛堢敾闈腑鏈夎彍鍗曢€夐」鍒楄〃锛?
        },
        "city_map": {
            "vlm_prompt": "纭鐢婚潰宸︿笂瑙掓湁鍩庡競鍦板浘鎸夐挳",
            "vlm_verify_prompt": "楠岃瘉鍩庡競鍦板浘宸叉墦寮€锛堢敾闈腑鏄剧ず鍦板浘鐣岄潰锛?
        },
        "weekly_tab": {
            "vlm_prompt": "纭浠诲姟闈㈡澘鍐呮湁鍛ㄥ父/姣忓懆浜嬪姟鏍囩椤?,
            "vlm_verify_prompt": "楠岃瘉宸插垏鎹㈠埌鍛ㄥ父鏍囩椤碉紙鐢婚潰涓樉绀哄懆甯镐换鍔″垪琛級"
        }
    }
    
    updated_count = 0
    
    # 閬嶅巻鎵€鏈夋祦绋?    for flow_name, flow_cfg in config["flows"].items():
        if not flow_cfg.get("enabled", True):
            continue
            
        print(f"\n[{flow_name}]")
        for step in flow_cfg["steps"]:
            if step.get("action") != "tap":
                continue
            
            coords_str = str(step.get("coords", ""))
            
            # 妫€鏌ユ槸鍚︿娇鐢ㄥ凡瀹氫箟鐨勫鑸潗鏍?            for nav_key, vlm_cfg in nav_vlm_config.items():
                if nav_key in coords_str:
                    # 娣诲姞 VLM 璧锋湯鍒ゅ畾
                    step["vlm_confirm"] = True
                    step["vlm_prompt"] = vlm_cfg["vlm_prompt"]
                    step["vlm_verify"] = True
                    step["vlm_verify_prompt"] = vlm_cfg["vlm_verify_prompt"]
                    
                    print(f"  鉁?{step.get('id')}: 娣诲姞 VLM 璧锋湯鍒ゅ畾 ({nav_key})")
                    updated_count += 1
                    break
    
    # 鏇存柊 execution 閰嶇疆璇存槑
    config["execution"]["_vlm_start_end_note"] = "鎵€鏈夊叧閿鑸?tap 鍔ㄤ綔鐨勮捣濮嬪拰缁撴潫鍧囩敱 VLM 鍒ゅ畾"
    
    # 淇濆瓨閰嶇疆
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"鉁?瀹屾垚锛歿updated_count} 涓?tap 姝ラ娣诲姞 VLM 璧锋湯鍒ゅ畾")
    print(f"   瑕嗙洊娴佺▼锛歞aily_quest, weekly_quest, resource_collection,")
    print(f"            base_management, character_ascension, weapon_crafting,")
    print(f"            event_rewards, delivery_mission, dungeon_grinding")

if __name__ == "__main__":
    add_vlm_start_end_to_all_flows()

