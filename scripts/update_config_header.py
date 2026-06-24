#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏇存柊鏍囧噯娴侀厤缃ご閮ㄦ敞閲婂拰 execution TODO 鍒楄〃
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"

def update_config_header():
    # 璇诲彇閰嶇疆
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 鏇存柊澶撮儴娉ㄩ噴
    config["_note"] = "2026-06-14 鍩轰簬 MaaEnd 璁捐妯″紡瀹屽杽銆傗湏=world 楠岃瘉鏈夋晥 ?=闈㈡澘鍐呮湭楠岃瘉 鈫?闇€閫氳繃鑿滃崟闂存帴鍒拌揪"
    
    # 鏇存柊 execution 閮ㄥ垎鐨?TODO
    config["execution"]["_verification_todo"] = [
        "鉁?COMPLETED: daily_quest 鍩轰簬 MaaEnd DijiangRewards 妯″紡瀹屽杽 (9 姝ラ)",
        "鉁?COMPLETED: weekly_quest 鍩轰簬 MaaEnd BAKER 妯″紡瀹屽杽 (11 姝ラ)",
        "TODO: 杩愯 verify_menu_entries.py 楠岃瘉鑿滃崟鍐?base/character 绮剧‘鍧愭爣",
        "TODO: 纭 claim_all (810,900) 鍦ㄥ悇闈㈡澘鍐呮湁鏁?,
        "TODO: 鑿滃崟鍐?base_entry_menu 褰撳墠鐢?(960,400) 浼拌鍊硷紝闇€绮剧‘楠岃瘉",
        "TODO: 鑿滃崟鍐?char_entry_menu 褰撳墠鐢?(1200,330) 浼拌鍊硷紝闇€绮剧‘楠岃瘉",
        "TODO: 鍙傝€?MaaEnd AutoCollect 妯″紡瀹屽杽 resource_collection 娴佺▼",
        "TODO: 鍙傝€?MaaEnd DeliveryJobs 妯″紡瀹屽杽 delivery_mission 娴佺▼"
    ]
    
    # 淇濆瓨閰嶇疆
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print("鉁?閰嶇疆澶撮儴娉ㄩ噴鍜?TODO 鍒楄〃宸叉洿鏂?)

if __name__ == "__main__":
    update_config_header()

