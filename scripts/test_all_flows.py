#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佺患鍚堟祴璇曡剼鏈?
娴嬭瘯鎵€鏈夋爣鍑嗘祦鐨勯厤缃纭€у拰鍙墽琛屾€с€?
鐢ㄦ硶:
    python scripts/test_all_flows.py
"""

import sys, os, json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"


def check_config():
    """妫€鏌ラ厤缃枃浠?""
    print("\n" + "="*60)
    print("妫€鏌ラ厤缃枃浠?)
    print("="*60)
    
    if not CONFIG_PATH.exists():
        print(f"[閿欒] 閰嶇疆鏂囦欢涓嶅瓨鍦細{CONFIG_PATH}")
        return False
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 妫€鏌ョ増鏈?    version = config.get("version", "unknown")
    print(f"[閰嶇疆] 鐗堟湰锛歿version}")
    
    # 妫€鏌ュ彉閲?    nav_coords = config.get("variables", {}).get("nav_coords", {})
    print(f"[鍙橀噺] 瀵艰埅鍧愭爣鏁帮細{len([k for k in nav_coords if not k.startswith('_')])}")
    
    # 妫€鏌ユ祦绋?    flows = config.get("flows", {})
    print(f"[娴佺▼] 鎬绘暟锛歿len(flows)}")
    
    enabled_count = sum(1 for f in flows.values() if f.get("enabled", True))
    print(f"[娴佺▼] 鍚敤锛歿enabled_count}")
    
    # 妫€鏌ュ緟楠岃瘉椤?    todo = config.get("execution", {}).get("_verification_todo", [])
    if todo:
        print(f"\n[寰呴獙璇乚 {len(todo)} 椤?")
        for t in todo:
            print(f"  - {t}")
    
    return True


def check_flow_steps(flow_name, flow_config):
    """妫€鏌ュ崟涓祦绋嬬殑姝ラ"""
    print(f"\n[娴佺▼] {flow_name}")
    print("-" * 40)
    
    steps = flow_config.get("steps", [])
    print(f"  姝ラ鏁帮細{len(steps)}")
    
    # 妫€鏌ユ瘡涓楠?    issues = []
    for i, step in enumerate(steps):
        step_id = step.get("id", f"step_{i}")
        action = step.get("action", "")
        
        # 妫€鏌ュ潗鏍囧紩鐢?        if "coords" in step:
            coords = step["coords"]
            if isinstance(coords, str) and coords.startswith("{{"):
                # 鍙橀噺寮曠敤
                var_name = coords[2:-1].strip()
                if not var_name:
                    issues.append(f"  [姝ラ {step_id}] 绌哄彉閲忓紩鐢?)
            elif isinstance(coords, list) and len(coords) == 2:
                # 鐩存帴鍧愭爣
                x, y = coords
                if x < 0 or x > 1920 or y < 0 or y > 1080:
                    issues.append(f"  [姝ラ {step_id}] 鍧愭爣瓒呭嚭鑼冨洿锛?{x}, {y})")
        
        # 妫€鏌?action 绫诲瀷
        valid_actions = ["tap", "swipe", "back", "check", "claim", "navigate", "wait"]
        if action and action not in valid_actions:
            issues.append(f"  [姝ラ {step_id}] 鏈煡 action: {action}")
    
    if issues:
        for issue in issues:
            print(issue)
    else:
        print("  鉁?姝ラ妫€鏌ラ€氳繃")
    
    return len(issues) == 0


def check_verified_coords():
    """妫€鏌ュ凡楠岃瘉鐨勫潗鏍?""
    print("\n" + "="*60)
    print("宸查獙璇佸潗鏍囩姸鎬?)
    print("="*60)
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    nav_coords = config.get("variables", {}).get("nav_coords", {})
    
    # 宸查獙璇佺殑鍧愭爣
    verified = [
        "quest_icon",
        "event_icon",
        "menu_icon",
        "city_map",
        "industry_panel",
        "region_building",
        "industry_brief",
    ]
    
    # 寰呴獙璇佺殑鍧愭爣
    pending = [
        "base_entry_menu",
        "char_entry_menu",
        "daily_claim",
        "weekly_tab",
        "claim_all",
        "event_sub",
        "mid_action",
        "production_btn",
        "confirm_btn",
        "confirm_dialog",
        "exit_cancel",
    ]
    
    print("\n宸查獙璇佸潗鏍?")
    for name in verified:
        if name in nav_coords:
            coords = nav_coords[name]
            print(f"  鉁?{name}: {coords}")
    
    print("\n寰呴獙璇佸潗鏍?")
    for name in pending:
        if name in nav_coords:
            coords = nav_coords[name]
            print(f"  鈿狅笍  {name}: {coords} (寰呯‘璁?")
    
    return True


def check_flow_dependencies():
    """妫€鏌ユ祦绋嬩緷璧栧叧绯?""
    print("\n" + "="*60)
    print("娴佺▼渚濊禆鍏崇郴")
    print("="*60)
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    flows = config.get("flows", {})
    
    # 鍒嗘瀽姣忎釜娴佺▼鐨勯〉闈㈡祦杞?    for flow_name, flow_config in flows.items():
        if not flow_config.get("enabled", True):
            continue
        
        steps = flow_config.get("steps", [])
        pages = []
        
        for step in steps:
            expect = step.get("expect", "")
            if expect:
                pages.append(expect)
        
        if pages:
            print(f"\n{flow_name}:")
            print(f"  椤甸潰娴佽浆锛歿' 鈫?'.join(pages)}")
    
    return True


def run_tests():
    """杩愯鎵€鏈夋祴璇?""
    print("\n" + "="*60)
    print("鏍囧噯娴佺患鍚堟祴璇?)
    print("="*60)
    
    # 1. 妫€鏌ラ厤缃?    if not check_config():
        print("\n[閿欒] 閰嶇疆妫€鏌ュけ璐?)
        return False
    
    # 2. 妫€鏌ュ凡楠岃瘉鍧愭爣
    check_verified_coords()
    
    # 3. 妫€鏌ユ祦绋嬩緷璧?    check_flow_dependencies()
    
    # 4. 妫€鏌ユ瘡涓祦绋?    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    flows = config.get("flows", {})
    all_passed = True
    
    for flow_name, flow_config in flows.items():
        if not check_flow_steps(flow_name, flow_config):
            all_passed = False
    
    # 鎬荤粨
    print("\n" + "="*60)
    print("娴嬭瘯鎬荤粨")
    print("="*60)
    
    if all_passed:
        print("鉁?鎵€鏈夋鏌ラ€氳繃")
    else:
        print("鈿狅笍  瀛樺湪涓€浜涢棶棰橈紝璇锋鏌ヤ笂杩拌緭鍑?)
    
    print("\n涓嬩竴姝?")
    print("  1. 杩愯 verify_menu_entries.py 楠岃瘉鑿滃崟鍐呭潗鏍?)
    print("  2. 鏇存柊 flows_config.json 涓殑寰呴獙璇佸潗鏍?)
    print("  3. 杩愯鏍囧噯娴佸紩鎿庢祴璇?")
    print("     python scripts/standard_flow_engine.py --flow daily_quest")
    
    return all_passed


if __name__ == "__main__":
    try:
        success = run_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[閿欒] 娴嬭瘯澶辫触锛歿e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

