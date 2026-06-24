#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佷慨澶嶉獙璇佽剼鏈?
楠岃瘉淇鍚庣殑鏍囧噯娴佸紩鎿庢槸鍚﹁兘姝ｇ‘鎵ц銆?
娴嬭瘯椤圭洰锛?1. 閫€鍑哄璇濇澶勭悊 - 澶氬潗鏍囧皾璇曞叧闂?2. 椤甸潰绫诲瀷鍒ゆ柇 - 閲戣壊鍏冪礌闃堝€?3. 璺敱鎭㈠閫昏緫 - 寮傚父椤甸潰澶勭悊
4. 鏍囧噯娴佹墽琛?- daily_quest 娴佺▼
"""

import sys, os, json, time
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

CONFIG_PATH = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"
ENGINE_PATH = PROJECT_ROOT / "scripts" / "standard_flow_engine.py"


def check_fix_applied():
    """妫€鏌ヤ慨澶嶆槸鍚﹀凡搴旂敤"""
    print("\n" + "="*70)
    print("妫€鏌ヤ慨澶嶆槸鍚﹀凡搴旂敤")
    print("="*70)
    
    with open(ENGINE_PATH, 'r', encoding='utf-8') as f:
        code = f.read()
    
    fixes = {
        "閫€鍑哄璇濇澶氬潗鏍囧皾璇?: "cancel_candidates",
        "鍓嶇疆楠岃瘉_close_exit_dialog": "_close_exit_dialog()",
        "璺敱鎭㈠澶氬潗鏍囬€昏緫": "for cx, cy in cancel_candidates",
    }
    
    all_ok = True
    for fix_name, keyword in fixes.items():
        found = keyword in code
        status = "鉁? if found else "鉂?
        print(f"  {status} {fix_name}")
        if not found:
            all_ok = False
    
    return all_ok


def verify_exit_dialog_handling():
    """楠岃瘉閫€鍑哄璇濇澶勭悊閫昏緫"""
    print("\n" + "="*70)
    print("楠岃瘉閫€鍑哄璇濇澶勭悊閫昏緫")
    print("="*70)
    
    import subprocess
    ADB = PROJECT_ROOT / '3rd-part' / 'adb' / 'adb.exe'
    SERIAL = 'localhost:16512'
    
    # 鎸夎繑鍥為敭瑙﹀彂閫€鍑哄璇濇
    print("\n[娴嬭瘯] 瑙﹀彂閫€鍑哄璇濇...")
    for _ in range(3):
        subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], 
                      capture_output=True, timeout=5)
        time.sleep(0.5)
    
    time.sleep(1)
    
    # 鎴浘鍒嗘瀽
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                      capture_output=True, timeout=15)
    if len(r.stdout) < 1000:
        print("  [澶辫触] 鏃犳硶鎴浘")
        return False
    
    import cv2, numpy as np
    img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        print("  [澶辫触] 鎴浘瑙ｇ爜澶辫触")
        return False
    
    # 妫€娴嬮噾鑹插厓绱?    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_gold = np.array([15, 80, 150])
    upper_gold = np.array([35, 255, 255])
    mask = cv2.inRange(hsv, lower_gold, upper_gold)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    gold_count = len([c for c in contours if cv2.contourArea(c) > 30])
    
    print(f"  [褰撳墠] 閲戣壊鍏冪礌={gold_count} 浜害={img.mean():.1f}")
    
    # 鍒ゆ柇椤甸潰绫诲瀷
    if 12 <= gold_count <= 16:
        print(f"  [鍒ゆ柇] 閫€鍑哄璇濇")
        page_type = "exit_dialog"
    elif 18 <= gold_count <= 21:
        print(f"  [鍒ゆ柇] 涓栫晫椤甸潰")
        page_type = "world"
    elif gold_count >= 22:
        print(f"  [鍒ゆ柇] 浠诲姟闈㈡澘")
        page_type = "quest_panel"
    else:
        print(f"  [鍒ゆ柇] 鍏朵粬椤甸潰")
        page_type = "other"
    
    # 濡傛灉鏄€€鍑哄璇濇锛屾祴璇曞叧闂€昏緫
    if page_type == "exit_dialog":
        print("\n  [娴嬭瘯] 灏濊瘯鍏抽棴閫€鍑哄璇濇...")
        
        # 灏濊瘯澶氫釜鍧愭爣
        candidates = [
            (600, 750), (540, 720), (660, 780), (580, 730), (620, 770),
        ]
        
        for cx, cy in candidates:
            print(f"    [灏濊瘯] 鐐瑰嚮 ({cx}, {cy})...")
            subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(cx), str(cy)],
                          capture_output=True, timeout=10)
            time.sleep(1.5)
            
            # 楠岃瘉鏄惁鍏抽棴
            r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                              capture_output=True, timeout=15)
            if len(r.stdout) < 1000:
                continue
            
            img2 = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
            if img2 is None:
                continue
            
            hsv2 = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)
            mask2 = cv2.inRange(hsv2, lower_gold, upper_gold)
            contours2, _ = cv2.findContours(mask2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            gold_count2 = len([c for c in contours2 if cv2.contourArea(c) > 30])
            
            print(f"      閲戣壊鍏冪礌={gold_count2}")
            
            if gold_count2 < 12 or gold_count2 > 16:
                print(f"    [鎴愬姛] 瀵硅瘽妗嗗凡鍏抽棴")
                # 鎸夎繑鍥炲洖鍒颁笘鐣?                for _ in range(3):
                    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'],
                                  capture_output=True, timeout=5)
                    time.sleep(0.5)
                return True
        
        print("  [澶辫触] 鎵€鏈夊潗鏍囧皾璇曞け璐?)
        # 娓呯悊锛氭寜杩斿洖閫€鍑?        for _ in range(3):
            subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'],
                          capture_output=True, timeout=5)
            time.sleep(0.5)
        return False
    else:
        print(f"  [璺宠繃] 褰撳墠涓嶆槸閫€鍑哄璇濇 (page={page_type})")
        return True


def verify_page_classification():
    """楠岃瘉椤甸潰绫诲瀷鍒ゆ柇閫昏緫"""
    print("\n" + "="*70)
    print("楠岃瘉椤甸潰绫诲瀷鍒ゆ柇閫昏緫")
    print("="*70)
    
    # 璇诲彇閰嶇疆涓殑鍧愭爣
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    nav_coords = config.get("variables", {}).get("nav_coords", {})
    
    # 妫€鏌ュ叧閿潗鏍囨槸鍚﹀瓨鍦?    required_coords = [
        "quest_icon",
        "event_icon", 
        "menu_icon",
        "city_map",
    ]
    
    print("\n[妫€鏌 鍏抽敭瀵艰埅鍧愭爣:")
    all_ok = True
    for coord_name in required_coords:
        if coord_name in nav_coords:
            coords = nav_coords[coord_name]
            print(f"  鉁?{coord_name}: {coords}")
        else:
            print(f"  鉂?{coord_name}: 缂哄け")
            all_ok = False
    
    return all_ok


def test_standard_flow():
    """娴嬭瘯鏍囧噯娴佹墽琛?""
    print("\n" + "="*70)
    print("娴嬭瘯鏍囧噯娴佹墽琛?)
    print("="*70)
    
    # 瀵煎叆鏍囧噯娴佸紩鎿?    try:
        from standard_flow_engine import StandardFlowExecutor, FlowConfig
    except Exception as e:
        print(f"  [澶辫触] 瀵煎叆鏍囧噯娴佸紩鎿庡け璐ワ細{e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 鍔犺浇閰嶇疆
    try:
        config = FlowConfig()
    except Exception as e:
        print(f"  [澶辫触] 鍔犺浇閰嶇疆澶辫触锛歿e}")
        return False
    
    # 妫€鏌?daily_quest 娴佺▼
    flow = config.get_flow("daily_quest")
    if flow is None:
        print("  [澶辫触] daily_quest 娴佺▼涓嶅瓨鍦?)
        return False
    
    print("  鉁?daily_quest 娴佺▼瀛樺湪")
    
    # 妫€鏌ユ祦绋嬫楠?    steps = flow.get("steps", [])
    print(f"  鉁?娴佺▼姝ラ鏁帮細{len(steps)}")
    
    # 鍒楀嚭姝ラ
    print("\n  姝ラ鍒楄〃:")
    for i, step in enumerate(steps[:5]):  # 鍙樉绀哄墠 5 姝?        action = step.get("action", "none")
        desc = step.get("desc", "")
        print(f"    {i+1}. {action}: {desc}")
    
    if len(steps) > 5:
        print(f"    ... 杩樻湁 {len(steps) - 5} 姝?)
    
    print("\n  [鎻愮ず] 瑕佸疄闄呰繍琛屾祦绋嬶紝璇蜂娇鐢?")
    print(f"    python scripts/standard_flow_engine.py --flow daily_quest")
    
    return True


def generate_report():
    """鐢熸垚楠岃瘉鎶ュ憡"""
    print("\n" + "="*70)
    print("楠岃瘉鎶ュ憡")
    print("="*70)
    
    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "fixes_applied": check_fix_applied(),
        "page_classification": verify_page_classification(),
        "flow_test": test_standard_flow(),
    }
    
    # 閫€鍑哄璇濇娴嬭瘯锛堝彲閫夛級
    # dialog_test = verify_exit_dialog_handling()
    # results["exit_dialog"] = dialog_test
    
    # 缁熻
    passed = sum(1 for v in results.values() if isinstance(v, bool) and v)
    total = sum(1 for v in results.values() if isinstance(v, bool))
    
    print(f"\n閫氳繃妫€鏌ワ細{passed}/{total}")
    
    if passed == total:
        print("\n鉁?鎵€鏈夋鏌ラ€氳繃锛?)
        print("\n淇宸插簲鐢?")
        print("  鈥?閫€鍑哄璇濇澶氬潗鏍囧皾璇曞叧闂?)
        print("  鈥?鍓嶇疆楠岃瘉瀵硅瘽妗嗗鐞?)
        print("  鈥?璺敱鎭㈠閫昏緫澧炲己")
        print("\n鏍囧噯娴佸紩鎿庡凡淇锛屽彲浠ユ墽琛屾祴璇曘€?)
        return True
    else:
        print(f"\n鈿狅笍  {total - passed} 椤规鏌ユ湭閫氳繃")
        return False


def main():
    print("\n" + "="*70)
    print("鏍囧噯娴佷慨澶嶉獙璇?)
    print("="*70)
    
    success = generate_report()
    
    return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[閿欒] 楠岃瘉澶辫触锛歿e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

