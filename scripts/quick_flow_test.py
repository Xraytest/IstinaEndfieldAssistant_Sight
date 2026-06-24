#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
蹇€熸祦娴嬭瘯 鈥?浠庡綋鍓嶆父鎴忕姸鎬佺洿鎺ユ墽琛屾祦姝ラ锛堣烦杩?preamble锛?

鐢ㄦ硶: python scripts/quick_flow_test.py daily_quest
"""

import sys, time, json
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT / "scripts"))

from core.capability.adb_utils import ADB, adb_screencap
from core.service.page_analyzer import HighPrecisionPageAnalyzer
from core.service.gui_client import GUIClient
import cv2, numpy as np


def load_flow(flow_name):
    path = PROJECT / "config" / "standard_flows" / "flows_config.json"
    with open(path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    flow = config.get("flows", {}).get(flow_name)
    nav = config.get("variables", {}).get("nav_coords", {})
    if not flow:
        print(f"鏈壘鍒版祦绋? {flow_name}")
        sys.exit(1)
    return flow, nav


def resolve_coords(raw, nav_coords):
    """瑙ｆ瀽鍧愭爣锛堟敮鎸?{{nav_coords.xxx}} 寮曠敤锛?""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and "{{" in raw:
        key = raw.strip("{}").strip()
        parts = key.split(".")
        if parts[0] == "nav_coords" and len(parts) == 2:
            return nav_coords.get(parts[1])
    return None


def run_flow(flow_name: str):
    flow, nav = load_flow(flow_name)
    steps = flow.get("steps", [])
    adb = ADB()
    analyzer = HighPrecisionPageAnalyzer()
    vlm = GUIClient({"vlm_mode": "local"})

    print(f"\n{'='*60}")
    print(f"鎵ц: {flow_name} ({flow.get('description','')})")
    print(f"姝ラ: {len(steps)}")
    print(f"{'='*60}")

    for i, step in enumerate(steps):
        sid = step.get("id", f"step_{i}")
        action = step.get("action", "none")
        desc = step.get("desc", sid)
        wait_s = step.get("wait", 2)

        print(f"\n[姝ラ {i+1}/{len(steps)}] {desc}")

        # 鎴浘鍒嗘瀽褰撳墠椤甸潰
        img_bytes = adb_screencap()
        if not img_bytes:
            print("  鎴浘澶辫触")
            continue
        cv_img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        page_result = analyzer.analyze(cv_img)
        pt = page_result["page_type"]
        conf = page_result["confidence"]

        print(f"  褰撳墠椤甸潰: {pt} (缃俊搴?{conf:.2f})")

        # 鑷姩澶勭悊閫€鍑哄璇濇
        if pt == "exit_dialog":
            print(f"  [AUTO] 妫€娴嬪埌閫€鍑哄璇濇锛岃嚜鍔ㄥ叧闂?..")
            closed = False
            for cx, cy in [(600, 750), (540, 720), (660, 780), (580, 730), (620, 770)]:
                adb.tap(cx, cy)
                time.sleep(1.5)
                img_bytes2 = adb_screencap()
                cv_img2 = cv2.imdecode(np.frombuffer(img_bytes2, np.uint8), cv2.IMREAD_COLOR)
                r2 = analyzer.analyze(cv_img2)
                if r2["page_type"] != "exit_dialog":
                    print(f"  [OK] 瀵硅瘽妗嗗凡鍏抽棴锛屽綋鍓?{r2['page_type']}")
                    r = r2
                    pt = r["page_type"]
                    conf = r["confidence"]
                    closed = True
                    break
            if not closed:
                print(f"  [WARN] 鏃犳硶鍏抽棴閫€鍑哄璇濇锛屾寜杩斿洖")
                adb.back()
                time.sleep(1)
                continue

        # Check for special screen and handle
        if pt in ("enter_game_prompt", "title"):
            print(f"  [INFO] {pt} 鐢婚潰锛岀偣鍑讳腑澶繘鍏ユ父鎴?)
            adb.tap(960, 540)
            time.sleep(3)
            continue

        if pt == "menu":
            print(f"  [INFO] 鑿滃崟椤甸潰锛宭eft_bar={r['features'].get('left_bar_brightness',0):.0f}")

        # 澶勭悊 actions
        if action == "tap":
            coords = resolve_coords(step.get("coords"), nav)
            if coords and len(coords) == 2:
                print(f"  [TAP] ({coords[0]}, {coords[1]})")
                adb.tap(coords[0], coords[1])
                time.sleep(wait_s)
            else:
                print(f"  [WARN] 鏃犳湁鏁堝潗鏍?)

        elif action == "back":
            print(f"  [BACK]")
            adb.back()
            time.sleep(wait_s)

        elif action == "check":
            expect = step.get("expect", "")
            if expect:
                if pt == expect:
                    print(f"  [OK] 椤甸潰鍖归厤棰勬湡: {expect}")
                elif expect == "world" and pt in ("world", "world_transition"):
                    print(f"  [OK] 椤甸潰鍖归厤棰勬湡 (world)")
                else:
                    print(f"  [WARN] 棰勬湡={expect} 瀹為檯={pt}")

        elif action == "claim":
            coords = nav.get("claim_all", [810, 900])
            print(f"  [CLAIM] ({coords[0]}, {coords[1]})")
            adb.tap(coords[0], coords[1])
            time.sleep(wait_s)

        elif action == "swipe":
            start = step.get("start", [200, 1700])
            end = step.get("end", [200, 1400])
            dur = step.get("duration", 1000)
            print(f"  [SWIPE] {start} -> {end} ({dur}ms)")
            adb.swipe(start[0], start[1], end[0], end[1], dur)
            time.sleep(wait_s)

        elif action == "navigate":
            target = step.get("target", "world")
            print(f"  [NAV] 瀵艰埅鍒?{target}")
            for _ in range(6):
                adb.back()
                time.sleep(0.5)
            time.sleep(wait_s)

        elif action == "wait":
            print(f"  [WAIT] {wait_s}s")
            time.sleep(wait_s)

    # 鏈€缁堢姸鎬?
    img_bytes = adb_screencap()
    cv_img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    final = analyzer.analyze(cv_img)
    print(f"\n鏈€缁堥〉闈? {final['page_type']} (缃俊搴?{final['confidence']:.2f})")


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "daily_quest"
    run_flow(name)

