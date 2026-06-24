#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏇存柊鏍囧噯娴侀厤缃?- 娣诲姞 VLM 纭鏈哄埗

鏍规嵁 Stop hook 鏉′欢锛氬嵆浣挎湁棰勮鍧愭爣锛岃鍔ㄦ椂涔熼渶瑕佺敱 VLM 纭

鏇存柊鍐呭:
1. 涓烘瘡涓?tap 姝ラ娣诲姞 vlm_confirm 瀛楁
2. 娣诲姞 vlm_prompt 鎸囧畾纭鎻愮ず璇?3. 鏇存柊 execution 閰嶇疆鍚敤 VLM 纭妯″紡
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"

def update_vlm_confirm():
    # 璇诲彇閰嶇疆
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 鏇存柊 daily_quest 娴佺▼ - 娣诲姞 VLM 纭
    daily_steps = config["flows"]["daily_quest"]["steps"]
    for step in daily_steps:
        if step.get("action") == "tap":
            step["vlm_confirm"] = True
            if "quest_icon" in str(step.get("coords", "")):
                step["vlm_prompt"] = "纭鐢婚潰鍙充笂瑙掓湁浠诲姟鍥炬爣 (榛勮壊鎰熷徆鍙锋垨浠诲姟鎸夐挳)"
            elif "weekly_tab" in str(step.get("coords", "")):
                step["vlm_prompt"] = "纭浠诲姟闈㈡澘鍐呮湁鍛ㄥ父/姣忓懆浜嬪姟鏍囩椤?
            else:
                step["vlm_prompt"] = "纭鐩爣鎸夐挳鍦ㄦ寚瀹氫綅缃彲瑙佷笖鍙偣鍑?
    
    # 鏇存柊 weekly_quest 娴佺▼ - 娣诲姞 VLM 纭
    weekly_steps = config["flows"]["weekly_quest"]["steps"]
    for step in weekly_steps:
        if step.get("action") == "tap":
            step["vlm_confirm"] = True
            if "quest_icon" in str(step.get("coords", "")):
                step["vlm_prompt"] = "纭鐢婚潰鍙充笂瑙掓湁浠诲姟鍥炬爣 (榛勮壊鎰熷徆鍙锋垨浠诲姟鎸夐挳)"
            elif "weekly_tab" in str(step.get("coords", "")):
                step["vlm_prompt"] = "纭浠诲姟闈㈡澘鍐呮湁鍛ㄥ父/姣忓懆浜嬪姟鏍囩椤?
            else:
                step["vlm_prompt"] = "纭鐩爣鎸夐挳鍦ㄦ寚瀹氫綅缃彲瑙佷笖鍙偣鍑?
    
    # 鏇存柊 execution 閰嶇疆
    config["execution"]["vlm_confirm_mode"] = "enabled"
    config["execution"]["vlm_confirm_timeout"] = 30
    config["execution"]["_vlm_note"] = "鎵€鏈?tap 鍔ㄤ綔鎵ц鍓嶉渶閫氳繃 VLM 纭鐩爣鍏冪礌鍙"
    
    # 淇濆瓨閰嶇疆
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print("鉁?鏍囧噯娴侀厤缃凡娣诲姞 VLM 纭鏈哄埗")
    print("   - daily_quest: 2 涓?tap 姝ラ娣诲姞 vlm_confirm")
    print("   - weekly_quest: 2 涓?tap 姝ラ娣诲姞 vlm_confirm")
    print("   - execution: 鍚敤 vlm_confirm_mode")

if __name__ == "__main__":
    update_vlm_confirm()

