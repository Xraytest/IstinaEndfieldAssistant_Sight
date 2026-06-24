#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏇存柊鏍囧噯娴侀厤缃?- 鍩轰簬 MaaEnd 璁捐妯″紡瀹屽杽 daily_quest 鍜?weekly_quest 娴佺▼

鍙傝€?MaaEnd 璁捐妯″紡:
1. DijiangRewards: Navigation(瀵艰埅)鈫扴tatusCheck(鐘舵€佹娴?鈫扖laim(棰嗗彇)鈫払ack(杩斿洖)
2. BAKER: SwitchTab(鍒囨崲鏍囩)鈫扴wipeFilter(婊戝姩绛涢€?鈫扚ilterUnread(鏌ユ壘鍙鍙?鈫扖laim(棰嗗彇)
3. GrowthChamber: TargetNotFound 鏃舵粦鍔ㄦ煡鎵?4. Common/Button: ClickKey(key=4) 閫氱敤杩斿洖
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"

def update_flows():
    # 璇诲彇閰嶇疆
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 鏇存柊 daily_quest 娴佺▼
    config["flows"]["daily_quest"] = {
        "enabled": True,
        "description": "瀹屾垚姣忔棩浠诲姟骞堕鍙栧鍔憋紙鍙傝€?MaaEnd DijiangRewards 瀵艰埅妯″紡锛?,
        "_status": "鍩轰簬 MaaEnd 璁捐妯″紡瀹屽杽锛氬鑸垎绂?+ 鐘舵€佹娴?+ 婊戝姩鏌ユ壘 + 閿欒鎭㈠",
        "_design": "MaaEnd 妯″紡锛歂avigation(鎵撳紑闈㈡澘)鈫扴tatusCheck(纭椤甸潰)鈫扴crollFind(婊戝姩鏌ユ壘)鈫扖laim(棰嗗彇)鈫払ack(杩斿洖)",
        "steps": [
            {
                "id": "ensure_world",
                "action": "check",
                "expect": "world",
                "desc": "纭繚鍦ㄦ帰绱㈢晫闈紙涓栫晫鍦板浘锛?
            },
            {
                "id": "open_quest_panel",
                "action": "tap",
                "coords": "{{nav_coords.quest_icon}}",
                "wait": 4,
                "desc": "鎵撳紑浠诲姟闈㈡澘 (860,80) 鉁?宸查獙璇?
            },
            {
                "id": "verify_quest_panel",
                "action": "check",
                "expect": "quest_panel",
                "desc": "楠岃瘉浠诲姟闈㈡澘宸叉墦寮€锛堥噾鑹插厓绱犫墺22锛?
            },
            {
                "id": "scroll_daily_tasks",
                "action": "swipe",
                "start": [540, 800],
                "end": [540, 400],
                "duration": 500,
                "desc": "婊戝姩鏌ユ壘姣忔棩浠诲姟锛堝弬鑰?MaaEnd GrowthChamberTargetNotFound锛?
            },
            {
                "id": "check_daily_status",
                "action": "check",
                "desc": "妫€鏌ユ瘡鏃ヤ换鍔＄姸鎬侊紙鍙鍙?杩涜涓?宸插畬鎴愶級"
            },
            {
                "id": "claim_daily_rewards",
                "action": "claim",
                "target": "claim_all",
                "desc": "涓€閿鍙栨瘡鏃ヤ换鍔″鍔?
            },
            {
                "id": "verify_claim",
                "action": "wait",
                "wait": 2,
                "desc": "绛夊緟棰嗗彇鍔ㄧ敾瀹屾垚"
            },
            {
                "id": "close_quest_panel",
                "action": "back",
                "wait": 2,
                "desc": "杩斿洖鎺㈢储鐣岄潰锛堝弬鑰?MaaEnd ClickKey key=4锛?
            },
            {
                "id": "verify_world_return",
                "action": "check",
                "expect": "world",
                "desc": "楠岃瘉宸茶繑鍥炰笘鐣屽湴鍥?
            }
        ]
    }
    
    # 鏇存柊 weekly_quest 娴佺▼
    config["flows"]["weekly_quest"] = {
        "enabled": True,
        "description": "瀹屾垚鍛ㄥ父浠诲姟骞堕鍙栧鍔憋紙鍙傝€?MaaEnd BAKER 绛涢€夋ā寮忥級",
        "_status": "鍩轰簬 MaaEnd BAKER 璁捐锛歍ab 鍒囨崲鈫掓粦鍔ㄦ煡鎵锯啋绛涢€夋湭璇烩啋棰嗗彇",
        "_design": "MaaEnd BAKER 妯″紡锛歋witchTab(鍒囨崲鏍囩)鈫扴wipeFilter(婊戝姩绛涢€?鈫扚ilterUnread(鏌ユ壘鍙鍙?鈫扖laim(棰嗗彇)",
        "steps": [
            {
                "id": "ensure_world",
                "action": "check",
                "expect": "world",
                "desc": "纭繚鍦ㄦ帰绱㈢晫闈?
            },
            {
                "id": "open_quest_panel",
                "action": "tap",
                "coords": "{{nav_coords.quest_icon}}",
                "wait": 4,
                "desc": "鎵撳紑浠诲姟闈㈡澘 (860,80) 鉁?
            },
            {
                "id": "verify_quest_panel",
                "action": "check",
                "expect": "quest_panel",
                "desc": "楠岃瘉浠诲姟闈㈡澘宸叉墦寮€"
            },
            {
                "id": "switch_to_weekly",
                "action": "tap",
                "coords": "{{nav_coords.weekly_tab}}",
                "wait": 3,
                "desc": "鍒囨崲鍒板懆甯告爣绛鹃〉 (810,300)"
            },
            {
                "id": "scroll_weekly_list",
                "action": "swipe",
                "start": [540, 900],
                "end": [540, 500],
                "duration": 600,
                "desc": "婊戝姩鏌ユ壘鍛ㄥ父浠诲姟鍒楄〃锛堝弬鑰?MaaEnd BakerSwipeFilter锛?
            },
            {
                "id": "check_weekly_status",
                "action": "check",
                "desc": "妫€鏌ュ懆甯镐换鍔＄姸鎬侊紙鍙傝€?MaaEnd BakerFilterUnread锛?
            },
            {
                "id": "claim_weekly_rewards",
                "action": "claim",
                "target": "claim_all",
                "desc": "涓€閿鍙栧懆甯镐换鍔″鍔?
            },
            {
                "id": "verify_claim",
                "action": "wait",
                "wait": 2,
                "desc": "绛夊緟棰嗗彇鍔ㄧ敾瀹屾垚"
            },
            {
                "id": "return_world",
                "action": "back",
                "wait": 2,
                "desc": "杩斿洖鎺㈢储鐣岄潰"
            },
            {
                "id": "verify_world_return",
                "action": "check",
                "expect": "world",
                "desc": "楠岃瘉宸茶繑鍥炰笘鐣屽湴鍥?
            }
        ]
    }
    
    # 淇濆瓨閰嶇疆
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print("鉁?鏍囧噯娴侀厤缃凡鏇存柊")
    print(f"   - daily_quest: 9 涓楠?(MaaEnd DijiangRewards 妯″紡)")
    print(f"   - weekly_quest: 11 涓楠?(MaaEnd BAKER 妯″紡)")

if __name__ == "__main__":
    update_flows()

