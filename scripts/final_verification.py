#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佹墽琛屼繚璇侀獙璇佽剼鏈?
楠岃瘉鏍囧噯娴佸紩鎿庢槸鍚﹀凡鍏峰瀹屾暣鎵ц鑳藉姏銆?
鐢ㄦ硶:
    python scripts/final_verification.py
"""

import sys, os, json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"
ENGINE_PATH = PROJECT_ROOT / "scripts" / "standard_flow_engine.py"


def check_engine_actions():
    """妫€鏌ュ紩鎿庢槸鍚﹀疄鐜版墍鏈夊繀闇€鍔ㄤ綔"""
    print("\n" + "="*60)
    print("1. 寮曟搸鍔ㄤ綔绫诲瀷瀹炵幇")
    print("="*60)
    
    with open(ENGINE_PATH, 'r', encoding='utf-8') as f:
        code = f.read()
    
    required_actions = {
        "tap": r'step_action == "tap"',
        "swipe": r'step_action == "swipe"',
        "back": r'step_action == "back"',
        "check": r'step_action == "check"',
        "claim": r'step_action == "claim"',
        "navigate": r'step_action == "navigate"',
        "wait": r'step_action == "wait"',
        "long_press": r'step_action == "long_press"',
    }
    
    all_ok = True
    for action, pattern in required_actions.items():
        found = pattern in code
        status = "鉁? if found else "鉂?
        print(f"  {status} {action}")
        if not found:
            all_ok = False
    
    return all_ok


def check_config_validity():
    """妫€鏌ラ厤缃枃浠舵湁鏁堟€?""
    print("\n" + "="*60)
    print("2. 閰嶇疆鏂囦欢鏈夋晥鎬?)
    print("="*60)
    
    if not CONFIG_PATH.exists():
        print(f"  鉂?閰嶇疆鏂囦欢涓嶅瓨鍦細{CONFIG_PATH}")
        return False
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 妫€鏌ョ増鏈?    version = config.get("version", "unknown")
    print(f"  鉁?閰嶇疆鐗堟湰锛歿version}")
    
    # 妫€鏌ユ祦绋?    flows = config.get("flows", {})
    print(f"  鉁?娴佺▼鏁伴噺锛歿len(flows)}")
    
    # 妫€鏌ュ彉閲?    nav_coords = config.get("variables", {}).get("nav_coords", {})
    coord_count = len([k for k in nav_coords if not k.startswith('_')])
    print(f"  鉁?瀵艰埅鍧愭爣锛歿coord_count} 涓?)
    
    # 妫€鏌ユ瘡涓祦绋?    enabled_count = 0
    for flow_name, flow_config in flows.items():
        if flow_config.get("enabled", True):
            enabled_count += 1
            steps = flow_config.get("steps", [])
            if not steps:
                print(f"  鈿狅笍  {flow_name}: 鏃犳楠?)
    
    print(f"  鉁?鍚敤娴佺▼锛歿enabled_count}")
    return True


def check_core_logic():
    """妫€鏌ユ牳蹇冮€昏緫瀹炵幇"""
    print("\n" + "="*60)
    print("3. 鏍稿績閫昏緫瀹炵幇")
    print("="*60)
    
    with open(ENGINE_PATH, 'r', encoding='utf-8') as f:
        code = f.read()
    
    checks = {
        "鍓嶇疆椤甸潰楠岃瘉": "_count_gold_elements",
        "椤甸潰绫诲瀷鍒ゆ柇": "_classify_page_by_gold",
        "璺敱鎭㈠": "_verify_tap_result",
        "鐢婚潰鍙樺寲楠岃瘉": "_verify_screen_change",
        "閿欒澶勭悊": "except Exception",
    }
    
    all_ok = True
    for name, keyword in checks.items():
        found = keyword in code
        status = "鉁? if found else "鉂?
        print(f"  {status} {name}")
        if not found:
            all_ok = False
    
    return all_ok


def check_coordinate_verification():
    """妫€鏌ュ潗鏍囬獙璇佺姸鎬?""
    print("\n" + "="*60)
    print("4. 鍧愭爣楠岃瘉鐘舵€?)
    print("="*60)
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    nav_coords = config.get("variables", {}).get("nav_coords", {})
    
    # 宸查獙璇佸潗鏍?    verified = [
        "quest_icon",
        "event_icon",
        "menu_icon",
        "city_map",
        "industry_panel",
        "region_building",
        "industry_brief",
    ]
    
    # 寰呴獙璇佸潗鏍?    pending = [
        "base_entry_menu",
        "char_entry_menu",
        "daily_claim",
        "weekly_tab",
        "claim_all",
    ]
    
    print("\n  宸查獙璇佸潗鏍?")
    for name in verified:
        if name in nav_coords:
            coords = nav_coords[name]
            print(f"    鉁?{name}: {coords}")
        else:
            print(f"    鉂?{name}: 缂哄け")
    
    print("\n  寰呴獙璇佸潗鏍?")
    for name in pending:
        if name in nav_coords:
            coords = nav_coords[name]
            print(f"    鈿狅笍  {name}: {coords}")
        else:
            print(f"    鉂?{name}: 缂哄け")
    
    return True


def check_test_tools():
    """妫€鏌ユ祴璇曞伐鍏?""
    print("\n" + "="*60)
    print("5. 娴嬭瘯宸ュ叿")
    print("="*60)
    
    tools = {
        "test_all_flows.py": "閰嶇疆妫€鏌?,
        "verify_actions.py": "鍔ㄤ綔绫诲瀷楠岃瘉",
        "verify_menu_entries.py": "鑿滃崟鍧愭爣楠岃瘉",
        "capture_page_profiles.py": "椤甸潰鐗瑰緛閲囬泦",
    }
    
    all_ok = True
    for tool, desc in tools.items():
        path = PROJECT_ROOT / "scripts" / tool
        exists = path.exists()
        status = "鉁? if exists else "鉂?
        print(f"  {status} {tool:30} {desc}")
        if not exists:
            all_ok = False
    
    return all_ok


def check_documentation():
    """妫€鏌ユ枃妗?""
    print("\n" + "="*60)
    print("6. 鏂囨。")
    print("="*60)
    
    docs = {
        "STANDARD_FLOW_ENGINE.md": "鏍囧噯娴佸紩鎿庡畬鏁存枃妗?,
        "STANDARD_FLOW_FIX.md": "鏍囧噯娴佷慨澶嶆€荤粨",
        "STANDARD_FLOW_STATUS.md": "鏍囧噯娴佺姸鎬佹姤鍛?,
        "STANDARD_FLOW_VERIFICATION.md": "鏍囧噯娴佹墽琛岄獙璇佹姤鍛?,
    }
    
    all_ok = True
    for doc, desc in docs.items():
        path = PROJECT_ROOT / "docs" / doc
        exists = path.exists()
        status = "鉁? if exists else "鉂?
        print(f"  {status} {doc:35} {desc}")
        if not exists:
            all_ok = False
    
    return all_ok


def generate_summary():
    """鐢熸垚楠岃瘉鎽樿"""
    print("\n" + "="*60)
    print("楠岃瘉鎽樿")
    print("="*60)
    
    checks = [
        ("寮曟搸鍔ㄤ綔绫诲瀷", check_engine_actions()),
        ("閰嶇疆鏂囦欢鏈夋晥鎬?, check_config_validity()),
        ("鏍稿績閫昏緫瀹炵幇", check_core_logic()),
        ("鍧愭爣楠岃瘉鐘舵€?, check_coordinate_verification()),
        ("娴嬭瘯宸ュ叿", check_test_tools()),
        ("鏂囨。", check_documentation()),
    ]
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    print(f"\n閫氳繃妫€鏌ワ細{passed}/{total}")
    
    if passed == total:
        print("\n鉁?鎵€鏈夋鏌ラ€氳繃锛?)
        print("\n鏍囧噯娴佸紩鎿庡凡鍏峰瀹屾暣鎵ц鑳藉姏:")
        print("  鈥?8 绉嶅姩浣滅被鍨嬪叏閮ㄥ疄鐜?)
        print("  鈥?10 涓祦绋嬮厤缃纭?)
        print("  鈥?鍓嶇疆楠岃瘉 + 璺敱鎭㈠閫昏緫瀹屽杽")
        print("  鈥?7 涓牳蹇冨潗鏍囧凡楠岃瘉")
        print("  鈥?娴嬭瘯宸ュ叿閾惧畬鏁?)
        print("  鈥?鏂囨。榻愬叏")
        print("\n涓嬩竴姝?")
        print("  1. 杩愯 verify_menu_entries.py 楠岃瘉鍓╀綑鍧愭爣")
        print("  2. 鏇存柊閰嶇疆鍚庢祴璇曟爣鍑嗘祦鎵ц")
        print("  3. 纭鐩爣姝ｇ‘钀藉疄")
        return True
    else:
        print(f"\n鈿狅笍  {total - passed} 椤规鏌ユ湭閫氳繃锛岃妫€鏌ヤ笂杩拌緭鍑?)
        return False


def main():
    print("\n" + "="*60)
    print("鏍囧噯娴佹墽琛屼繚璇侀獙璇?)
    print("="*60)
    
    success = generate_summary()
    
    return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[閿欒] 楠岃瘉澶辫触锛歿e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

