#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
绂荤嚎鍏ㄦ爣鍑嗘祦娴嬭瘯 鈥?浣跨敤缂撳瓨鎴浘楠岃瘉鍒嗘瀽鍣ㄥ拰寮曟搸閫昏緫

涓嶄緷璧栧湪绾胯澶囥€備娇鐢ㄥ凡鐭ラ〉闈㈡埅鍥炬祴璇曪細
- cache/test_recognition/world_*.png 鈫?棰勬湡 world
- cache/test_recognition/quest_*.png 鈫?棰勬湡 quest_panel
- cache/test_recognition/dialog_*.png 鈫?棰勬湡 exit_dialog
- cache/menu_screen.png 鈫?棰勬湡 menu
"""

import sys, json, cv2
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path; ensure_path()

from core.service.page_analyzer import HighPrecisionPageAnalyzer
from core.capability.recognition import RecognitionEngine, PREDEFINED_STATES

analyzer = HighPrecisionPageAnalyzer()
engine = RecognitionEngine()


def test_page_classification():
    """娴嬭瘯椤甸潰鍒嗙被鍣ㄥ湪鎵€鏈夊凡鐭ユ埅鍥句笂鐨勫噯纭€?""
    print("=" * 60)
    print("Test 1: Page Classifier Accuracy (offline)")
    print("=" * 60)

    test_cases = [
        # (path, expected_page)
        ("world_1.png", "world"),
        ("world_2.png", "world"),
        ("world_3.png", "world"),
        ("quest_1.png", "quest_panel"),
        ("quest_2.png", "quest_panel"),
        ("quest_3.png", "quest_panel"),
        ("dialog_1.png", "exit_dialog"),
        ("dialog_2.png", "exit_dialog"),
        ("dialog_3.png", "exit_dialog"),
    ]

    base = PROJECT / "cache" / "test_recognition"
    correct = 0

    for fname, expected in test_cases:
        path = base / fname
        if not path.exists():
            print(f"  SKIP {fname}: not found")
            continue

        img = cv2.imread(str(path))
        if img is None:
            print(f"  SKIP {fname}: unreadable")
            continue

        result = analyzer.analyze(img)
        page_type = result["page_type"]
        confidence = result["confidence"]
        detail = result.get("detail", {})

        ok = page_type == expected
        if ok:
            correct += 1
            status = "PASS"
        else:
            status = "FAIL"

        print(f"  [{status}] {fname} 鈫?{page_type} (c={confidence:.2f}) "
              f"detail={detail.get('method','?')}")

    accuracy = correct / len(test_cases) * 100 if test_cases else 0
    print(f"\n  Accuracy: {correct}/{len(test_cases)} ({accuracy:.1f}%)")
    return correct == len(test_cases)


def test_template_matching():
    """娴嬭瘯鎵€鏈夐瀹氫箟妯℃澘鍦ㄥ綋鍓嶆埅鍥句笂鐨勮〃鐜?""
    print("\n" + "=" * 60)
    print("Test 2: Template Matching (SIFT)")
    print("=" * 60)

    test_files = [
        ("cache/test_recognition/world_2.png", "World page"),
        ("cache/test_recognition/quest_2.png", "Quest panel"),
        ("cache/test_recognition/dialog_2.png", "Exit dialog"),
        ("cache/menu_screen.png", "Menu screen"),
    ]

    for path, desc in test_files:
        full_path = PROJECT / path
        if not full_path.exists():
            print(f"  SKIP {desc}: no screenshot")
            continue

        img = cv2.imread(str(full_path))
        if img is None:
            continue

        print(f"\n  {desc} ({path}):")
        for node_name in ["CancelButton", "InWorld", "TaskIcon", "YellowConfirmButton"]:
            node = PREDEFINED_STATES[node_name]
            ok, result = engine.recognize(img, node)
            if ok:
                info = f"loc={result.get('location','?')} matches={result.get('matches','?')}"
                print(f"    [{node_name}] FOUND: {info}")
            else:
                print(f"    [{node_name}] not found")


def test_flow_configs():
    """楠岃瘉鍏ㄩ儴娴侀厤缃?""
    print("\n" + "=" * 60)
    print("Test 3: Flow Config Validation")
    print("=" * 60)

    path = PROJECT / "config" / "standard_flows" / "flows_config.json"
    with open(path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    flows = cfg.get("flows", {})
    nav = cfg.get("variables", {}).get("nav_coords", {})
    errors = []

    ACTIONS = {"tap", "back", "check", "claim", "navigate", "swipe", "wait", "long_press"}

    for fname, flow in flows.items():
        steps = flow.get("steps", [])
        for i, step in enumerate(steps):
            sid = step.get("id", f"step{i}")
            action = step.get("action", "none")

            if action not in ACTIONS:
                errors.append(f"{fname}/{sid}: unknown action '{action}'")

            coords = step.get("coords")
            if coords:
                if isinstance(coords, str) and "{{" in coords:
                    key = coords.strip("{}").split(".")[-1]
                    if key not in nav:
                        errors.append(f"{fname}/{sid}: var '{key}' not defined")

    if errors:
        print("  FAIL:")
        for e in errors:
            print(f"    - {e}")
    else:
        print(f"  PASS: {len(flows)} flows, 0 errors")

    return len(errors) == 0


def test_all_actions():
    """楠岃瘉寮曟搸鏀寔鎵€鏈夊姩浣滅被鍨?""
    print("\n" + "=" * 60)
    print("Test 4: Action Type Coverage")
    print("=" * 60)

    path = PROJECT / "config" / "standard_flows" / "flows_config.json"
    with open(path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    used_actions = set()
    for flow in cfg.get("flows", {}).values():
        for step in flow.get("steps", []):
            used_actions.add(step.get("action", "none"))

    expected = {"tap", "back", "check", "claim", "navigate", "swipe", "wait", "long_press"}
    missing = expected - used_actions
    extra = used_actions - expected

    for a in sorted(expected):
        status = "used" if a in used_actions else "MISSING"
        print(f"  [{status}] {a}")

    if missing:
        print(f"  Missing: {missing}")
    if extra:
        print(f"  Extra: {extra}")

    return len(missing) == 0


def test_sift_match_accuracy():
    """SIFT鍖归厤鍦ㄥ凡鐭ユ埅鍥句笂鐨勫噯纭€?""
    print("\n" + "=" * 60)
    print("Test 5: SIFT Match on Known Screenshots")
    print("=" * 60)

    # Test CancelButton on dialog screenshots
    dialog_path = PROJECT / "cache/test_recognition/dialog_2.png"
    if dialog_path.exists():
        img = cv2.imread(str(dialog_path))
        ok, r = engine.recognize(img, {
            "type": "TemplateMatch",
            "template": "Common/Button/CancelButtonType1.png",
            "roi": [200, 500, 700, 500],
            "threshold": 4
        })
        if ok:
            pos = r.get("location", (0,0))
            matches = r.get("matches", 0)
            print(f"  [PASS] CancelButton on exit_dialog: pos=({pos[0]},{pos[1]}) matches={matches}")
        else:
            matches = r.get("matches", 0)
            print(f"  [FAIL] CancelButton on exit_dialog: matches={matches} (need 4)")
    else:
        print("  SKIP: no dialog screenshot")

    # Test WorldMenu on world screenshots
    world_path = PROJECT / "cache/test_recognition/world_2.png"
    if world_path.exists():
        img = cv2.imread(str(world_path))
        ok, r = engine.recognize(img, {
            "type": "TemplateMatch",
            "template": "SceneManager/WorldMenu.png",
            "roi": [0, 0, 200, 200],
            "threshold": 4
        })
        matches = r.get("matches", 0)
        print(f"  WorldMenu on world: matches={matches} {'(PASS)' if ok else ''}")


def main():
    results = {}

    # Test 1
    results["page_classification"] = test_page_classification()

    # Test 2
    test_template_matching()

    # Test 3
    results["flow_configs"] = test_flow_configs()

    # Test 4
    results["action_coverage"] = test_all_actions()

    # Test 5
    test_sift_match_accuracy()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for v in results.values() if v)
    for name, ok in results.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n  {passed}/{len(results)} tests passed")

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())

