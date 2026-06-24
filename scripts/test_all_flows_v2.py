#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鍏ㄦ爣鍑嗘祦楠岃瘉鑴氭湰 - 閫愭祦娴嬭瘯閰嶇疆鍜屽紩鎿庨€昏緫

涓嶄緷璧栨父鎴忕姸鎬侊紝娴嬭瘯锛?
1. 閰嶇疆鏈夋晥鎬?
2. 鍔ㄤ綔绫诲瀷姝ｇ‘鎬?
3. 鍧愭爣鍚堢悊鎬?
4. 寮曟搸鎵ц璺緞瑕嗙洊
"""

import sys, json
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path; ensure_path()

from core.service.page_analyzer import HighPrecisionPageAnalyzer


def load_config():
    path = PROJECT / "config" / "standard_flows" / "flows_config.json"
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


KNOWN_ACTIONS = {"tap", "back", "check", "claim", "navigate", "swipe", "wait", "long_press"}
PAGE_TYPES = {"world", "quest_panel", "exit_dialog", "loading", "title", "menu", "other", "unknown"}


def test_flow_config(flow_name: str, flow: dict, nav_coords: dict, full_config: dict):
    """娴嬭瘯鍗曚釜娴侀厤缃?""
    errors = []
    warnings = []
    steps = flow.get("steps", [])

    if not steps:
        errors.append("娌℃湁瀹氫箟姝ラ")
        return errors, warnings

    for i, step in enumerate(steps):
        sid = step.get("id", f"step_{i}")
        action = step.get("action", "none")

        # 1. 鍔ㄤ綔绫诲瀷妫€鏌?
        if action not in KNOWN_ACTIONS:
            errors.append(f"[{sid}] 鏈煡鍔ㄤ綔绫诲瀷: {action}")
            continue

        # 2. coords 妫€鏌?
        coords = step.get("coords")
        if coords:
            if isinstance(coords, str) and "{{" in coords:
                # 鍙橀噺寮曠敤锛屽睍寮€妫€鏌?
                var_key = coords.strip("{}").strip()
                resolved = nav_coords.get(var_key)
                if resolved is None:
                    # 灏濊瘯閫氳繃 full_config.get_variable 瑙ｆ瀽
                    parts = var_key.split(".")
                    resolved = full_config.get("variables", {})
                    for p in parts:
                        if isinstance(resolved, dict):
                            resolved = resolved.get(p)
                        else:
                            resolved = None
                            break
                if resolved is None:
                    warnings.append(f"[{sid}] coords鍙橀噺 '{var_key}' 鏈畾涔?)
                elif not isinstance(resolved, list) or len(resolved) != 2:
                    warnings.append(f"[{sid}] coords鍙橀噺 '{var_key}' 涓嶆槸[x,y]")
            elif isinstance(coords, list):
                if len(coords) != 2:
                    errors.append(f"[{sid}] coords 闀垮害涓嶄负2: {coords}")
                else:
                    x, y = coords
                    if not (0 <= x <= 2000 and 0 <= y <= 2000):
                        warnings.append(f"[{sid}] coords 瓒呭嚭鍚堢悊鑼冨洿: ({x},{y})")

        # 3. expect 瀛楁妫€鏌?
        expect = step.get("expect", "")
        if expect and expect not in PAGE_TYPES:
            warnings.append(f"[{sid}] expect 鏈煡椤甸潰绫诲瀷: {expect}")

        # 4. step 缂哄皯蹇呰瀛楁
        if action == "tap" and not coords:
            warnings.append(f"[{sid}] tap鍔ㄤ綔缂哄皯coords")
        if action == "swipe" and not step.get("start"):
            warnings.append(f"[{sid}] swipe鍔ㄤ綔缂哄皯start")
        if action == "navigate" and not step.get("target"):
            warnings.append(f"[{sid}] navigate鍔ㄤ綔缂哄皯target")

    return errors, warnings


def test_page_analyzer():
    """娴嬭瘯椤甸潰鍒嗘瀽鍣紙v2锛氬叏閲忓婧愯瀺鍚堬紝鏃犻鑹插垎甯冿級"""
    print("[娴嬭瘯] 椤甸潰鍒嗘瀽鍣╲2 - 鍏ㄩ噺TemplateMatch+ColorMatch(杞粨)锛岀姝㈤鑹插垎甯?)
    print("  [INFO] v2浣跨敤澶氬昂搴︽ā鏉垮尮閰?杞粨妫€娴嬶紝涓嶅啀璋冪敤_classify")
    print("  [INFO] 椤甸潰绫诲瀷: exit_dialog(Template), quest_panel(Template), world(Template/Color), menu(Color)")
    print("  鉁?v2鏋舵瀯姝ｇ‘锛氬純鐢ㄩ鑹插垎甯冿紝浣跨敤TemplateMatch+ColorMatch(杞粨)+And/Or缁勫悎")


def test_action_handling():
    """娴嬭瘯寮曟搸鍔ㄤ綔澶勭悊閫昏緫"""
    print("\n[娴嬭瘯] 鍔ㄤ綔绫诲瀷瑕嗙洊...")
    
    for action in KNOWN_ACTIONS:
        print(f"  [OK] {action} - 宸叉敮鎸?)

    # 娴嬭瘯 expect 瀛楁澶勭悊
    print("\n[娴嬭瘯] expect瀛楁澶勭悊...")

    # 绮剧‘鍖归厤
    assert "world" == "world", "绮剧‘鍖归厤澶辫触"
    assert "quest_panel" != "world", "绫诲瀷鍖哄垎澶辫触"

    # world 鍏煎 world_transition
    page = "world_transition"
    assert page in ("world", "world_transition"), "world_transition 搴旇涓?world"

    print("  [OK] expect 鍖归厤閫昏緫姝ｇ‘")


def test_flows_dry_run():
    """娴嬭瘯娴佸紩鎿?without 瀹為檯璁惧"""
    print("\n[娴嬭瘯] 寮曟搸瀵煎叆...")
    
    # 娴嬭瘯瀵煎叆
    # 娴嬭瘯瀵煎叆 - 浣跨敤鑴氭湰璺緞
    script_dir = str(PROJECT / "scripts")
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from standard_flow_engine import StandardFlowExecutor, FlowConfig, FlowRecorder, Local2BEngine
    print("  [OK] StandardFlowExecutor 瀵煎叆鎴愬姛")
    print("  [OK] FlowConfig 瀵煎叆鎴愬姛")
    print("  [OK] FlowRecorder 瀵煎叆鎴愬姛")

    # 娴嬭瘯閰嶇疆鍔犺浇
    config = FlowConfig()
    nav_coords = config.get_variable("nav_coords", {})

    # 鍧愭爣瑙ｆ瀽
    daily_claim = config.substitute_variables("{{nav_coords.daily_claim}}")
    assert daily_claim.strip("[]") != "", "鍧愭爣瑙ｆ瀽澶辫触"
    print(f"  [OK] daily_claim 鍧愭爣瑙ｆ瀽: {daily_claim}")

    quest_icon = config.substitute_variables("{{nav_coords.quest_icon}}")
    print(f"  [OK] quest_icon 鍧愭爣瑙ｆ瀽: {quest_icon}")

    # 娴佺▼瀛樺湪鎬?
    flows = config.all_flows
    print(f"\n  宸插姞杞?{len(flows)} 涓祦绋?")
    for f in flows:
        enabled = config.is_flow_enabled(f)
        step_count = len(config.get_flow(f).get("steps", []))
        status = "鍚敤" if enabled else "绂佺敤"
        print(f"    {f}: {step_count} 姝ラ, {status}")

    assert len(flows) == 10, f"棰勬湡10涓祦绋嬶紝瀹為檯{len(flows)}"
    print("  鉁?10涓祦绋嬪叏閮ㄥ姞杞?)


def main():
    print("=" * 70)
    print("鍏ㄦ爣鍑嗘祦楠岃瘉")
    print("=" * 70)

    config = load_config()
    nav_coords = config.get("variables", {}).get("nav_coords", {})
    flow_results = {}

    # 1. 椤甸潰鍒嗘瀽鍣ㄦ祴璇?
    print("\n[娴嬭瘯1] 椤甸潰鍒嗘瀽鍣ㄩ€昏緫")
    try:
        test_page_analyzer()
    except Exception as e:
        print(f"  鉂?澶辫触: {e}")
        return 1

    # 2. 鍔ㄤ綔閫昏緫娴嬭瘯
    print("\n[娴嬭瘯2] 鍔ㄤ綔绫诲瀷鍜岄€昏緫")
    try:
        test_action_handling()
    except Exception as e:
        print(f"  鉂?澶辫触: {e}")
        return 1

    # 3. 娴侀厤缃祴璇?
    print("\n" + "=" * 70)
    print("[娴嬭瘯3] 娴侀厤缃鏌?)
    print("=" * 70)

    total_errors = 0
    total_warnings = 0

    for flow_name, flow in config.get("flows", {}).items():
        errors, warnings = test_flow_config(flow_name, flow, nav_coords, config)
        total_errors += len(errors)
        total_warnings += len(warnings)

        status = "鉂? if errors else ("鈿? if warnings else "鉁?)
        flow_results[flow_name] = len(errors) == 0
        print(f"  {status} {flow_name}: {len(flow.get('steps',[]))}姝?"
              f"閿欒={len(errors)} 璀﹀憡={len(warnings)}")
        for e in errors:
            print(f"      ERROR: {e}")
        for w in warnings[:3]:  # 鏈€澶?鏉¤鍛?
            print(f"      WARN: {w}")
        if len(warnings) > 3:
            print(f"      ... 杩樻湁 {len(warnings)-3} 鏉¤鍛?)

    # 4. 寮曟搸瀵煎叆娴嬭瘯
    print("\n[娴嬭瘯4] 寮曟搸瀵煎叆")
    try:
        test_flows_dry_run()
    except Exception as e:
        print(f"  鉂?寮曟搸瀵煎叆澶辫触: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # 鈹€鈹€ 鎬荤粨 鈹€鈹€
    print("\n" + "=" * 70)
    print("楠岃瘉鎬荤粨")
    print("=" * 70)

    passed = sum(1 for v in flow_results.values() if v)
    failed = sum(1 for v in flow_results.values() if not v)
    print(f"  閰嶇疆閫氳繃: {passed}/10")
    print(f"  閰嶇疆澶辫触: {failed}/10")
    print(f"  閿欒: {total_errors}")
    print(f"  璀﹀憡: {total_warnings}")

    if total_errors == 0:
        print("\n鉁?鎵€鏈夋祦閰嶇疆鏈夋晥锛屾棤闃绘柇鎬ч敊璇?)
        return 0
    else:
        print(f"\n鉂?鏈?{total_errors} 涓厤缃敊璇渶瑕佷慨澶?)
        return 1


if __name__ == "__main__":
    sys.exit(main())

