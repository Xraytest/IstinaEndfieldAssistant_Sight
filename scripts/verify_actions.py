#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佸姩浣滅被鍨嬮獙璇佽剼鏈?
楠岃瘉鏍囧噯娴佸紩鎿庢槸鍚︽敮鎸佹墍鏈夐渶瑕佺殑鍔ㄤ綔绫诲瀷銆?
鐢ㄦ硶:
    python scripts/verify_actions.py
"""

import sys, os, json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"
ENGINE_PATH = PROJECT_ROOT / "scripts" / "standard_flow_engine.py"


# 鏍囧噯娴佸紩鎿庢敮鎸佺殑鍔ㄤ綔绫诲瀷
SUPPORTED_ACTIONS = {
    "tap": "鐐瑰嚮鎸囧畾鍧愭爣",
    "swipe": "婊戝姩/绉诲姩",
    "back": "杩斿洖閿?,
    "check": "澶氭簮瑙嗚鍒嗘瀽纭",
    "claim": "涓€閿鍙?,
    "navigate": "绮剧‘鍧愭爣瀵艰埅",
    "wait": "绛夊緟鎸囧畾鏃堕棿",
    "long_press": "闀挎寜",
}


def check_config_actions():
    """妫€鏌ラ厤缃枃浠朵腑浣跨敤鐨勫姩浣滅被鍨?""
    print("\n" + "="*60)
    print("妫€鏌ラ厤缃枃浠朵腑浣跨敤鐨勫姩浣滅被鍨?)
    print("="*60)
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    flows = config.get("flows", {})
    used_actions = {}
    
    for flow_name, flow_config in flows.items():
        steps = flow_config.get("steps", [])
        for step in steps:
            action = step.get("action", "")
            if action:
                if action not in used_actions:
                    used_actions[action] = []
                used_actions[action].append(flow_name)
    
    print("\n閰嶇疆涓娇鐢ㄧ殑鍔ㄤ綔绫诲瀷:")
    for action, flows_list in used_actions.items():
        status = "鉁? if action in SUPPORTED_ACTIONS else "鉂?
        desc = SUPPORTED_ACTIONS.get(action, "鏈煡")
        print(f"  {status} {action:15} {desc:20} 鐢ㄤ簬锛歿', '.join(set(flows_list))}")
    
    return used_actions


def check_engine_implementation():
    """妫€鏌ュ紩鎿庝腑瀹炵幇鐨勫嫊浣滅被鍨?""
    print("\n" + "="*60)
    print("妫€鏌ュ紩鎿庝腑瀹炵幇鐨勫嫊浣滅被鍨?)
    print("="*60)
    
    with open(ENGINE_PATH, 'r', encoding='utf-8') as f:
        engine_code = f.read()
    
    implemented = {}
    for action in SUPPORTED_ACTIONS.keys():
        # 妫€鏌ユ槸鍚︽湁瀵瑰簲鐨勫鐞嗛€昏緫
        patterns = [
            f'step_action == "{action}"',
            f'elif step_action == "{action}"',
            f'if action == "{action}"',
            f'elif action == "{action}"',
        ]
        found = any(p in engine_code for p in patterns)
        implemented[action] = found
        status = "鉁? if found else "鉂?
        desc = SUPPORTED_ACTIONS[action]
        print(f"  {status} {action:15} {desc}")
    
    return implemented


def check_missing_actions(used_actions, implemented):
    """妫€鏌ョ己澶辩殑鍔ㄤ綔绫诲瀷"""
    print("\n" + "="*60)
    print("缂哄け鐨勫姩浣滅被鍨?)
    print("="*60)
    
    missing = []
    for action in used_actions.keys():
        if action not in SUPPORTED_ACTIONS:
            missing.append(action)
        elif not implemented.get(action, False):
            missing.append(action)
    
    if missing:
        print("\n浠ヤ笅鍔ㄤ綔绫诲瀷鏈湪寮曟搸涓疄鐜?")
        for action in missing:
            flows_list = used_actions[action]
            print(f"  鉂?{action:15} 鐢ㄤ簬锛歿', '.join(set(flows_list))}")
        return False
    else:
        print("\n鉁?鎵€鏈変娇鐢ㄧ殑鍔ㄤ綔绫诲瀷鍧囧凡瀹炵幇")
        return True


def check_action_coverage():
    """妫€鏌ュ姩浣滅被鍨嬭鐩栨儏鍐?""
    print("\n" + "="*60)
    print("鍔ㄤ綔绫诲瀷瑕嗙洊鎯呭喌")
    print("="*60)
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    flows = config.get("flows", {})
    action_stats = {}
    
    for flow_name, flow_config in flows.items():
        steps = flow_config.get("steps", [])
        for step in steps:
            action = step.get("action", "")
            if action:
                if action not in action_stats:
                    action_stats[action] = 0
                action_stats[action] += 1
    
    print("\n鍔ㄤ綔绫诲瀷浣跨敤缁熻:")
    total = sum(action_stats.values())
    for action, count in sorted(action_stats.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        print(f"  {action:15} {count:3} 娆?({pct:5.1f}%)")
    
    return action_stats


def generate_report(used_actions, implemented, action_stats):
    """鐢熸垚楠岃瘉鎶ュ憡"""
    print("\n" + "="*60)
    print("楠岃瘉鎶ュ憡")
    print("="*60)
    
    # 缁熻
    total_actions = len(SUPPORTED_ACTIONS)
    impl_actions = sum(1 for v in implemented.values() if v)
    used_action_count = len(used_actions)
    
    print(f"\n寮曟搸鏀寔鐨勫姩浣滅被鍨嬶細{impl_actions}/{total_actions}")
    print(f"閰嶇疆浣跨敤鐨勫姩浣滅被鍨嬶細{used_action_count}")
    
    # 妫€鏌?    all_ok = True
    for action in used_actions.keys():
        if not implemented.get(action, False):
            print(f"鉂?缂哄け鍔ㄤ綔绫诲瀷锛歿action}")
            all_ok = False
    
    if all_ok:
        print("\n鉁?鎵€鏈夋鏌ラ€氳繃")
        print("\n鏍囧噯娴佸紩鎿庡凡鏀寔鎵€鏈夐渶瑕佺殑鍔ㄤ綔绫诲瀷:")
        for action in used_actions.keys():
            desc = SUPPORTED_ACTIONS.get(action, "鏈煡")
            count = action_stats.get(action, 0)
            print(f"  鉁?{action:15} {desc:20} ({count} 娆?")
    
    return all_ok


def main():
    print("\n" + "="*60)
    print("鏍囧噯娴佸姩浣滅被鍨嬮獙璇?)
    print("="*60)
    
    # 妫€鏌?    used_actions = check_config_actions()
    implemented = check_engine_implementation()
    missing_ok = check_missing_actions(used_actions, implemented)
    action_stats = check_action_coverage()
    
    # 鎶ュ憡
    success = generate_report(used_actions, implemented, action_stats)
    
    if not missing_ok:
        print("\n鈿狅笍  瀛樺湪缂哄け鐨勫姩浣滅被鍨嬶紝璇峰湪鏍囧噯娴佸紩鎿庝腑娣诲姞鏀寔")
    
    return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[閿欒] 楠岃瘉澶辫触锛歿e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

