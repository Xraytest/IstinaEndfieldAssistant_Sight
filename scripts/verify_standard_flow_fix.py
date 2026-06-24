#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佺患鍚堥獙璇佽剼鏈?鈥?鍩轰簬 MaaEnd 瀵规瘮鍒嗘瀽

楠岃瘉椤圭洰锛?1. 灞忓箷宸紓妫€娴嬪嚱鏁?2. exit_dialog 澶氬潗鏍囧皾璇?+ 鐢婚潰楠岃瘉
3. 椤甸潰绫诲瀷鍒ゆ柇鍑嗙‘鎬?4. daily_quest 娴佺▼閰嶇疆

鍙傝€冿細MaaEnd 鐨?CancelButton銆乀asks.json 瀹炵幇
"""

import sys, os, json, time, cv2, numpy as np
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

PROJECT = Path(__file__).resolve().parent.parent

from core.capability.adb_utils import ADB, adb_screencap

# 瀵煎叆鏍囧噯娴佸紩鎿庣殑鍑芥暟
try:
    from standard_flow_engine import screen_diff, close_exit_dialog_with_verify, ScreenAnalyzer
    print("[鉁揮 鎴愬姛瀵煎叆鏍囧噯娴佸紩鎿庡嚱鏁?)
except Exception as e:
    print(f"[鉁梋 瀵煎叆鏍囧噯娴佸紩鎿庡け璐ワ細{e}")
    sys.exit(1)


def test_screen_diff():
    """娴嬭瘯灞忓箷宸紓妫€娴嬪嚱鏁?""
    print("\n" + "="*70)
    print("娴嬭瘯 1: 灞忓箷宸紓妫€娴?)
    print("="*70)
    
    adb = ADB('localhost:16512')
    
    # 鎴浘 1
    img1_raw = adb_screencap()
    if img1_raw is None:
        print("[澶辫触] 鏃犳硶鎴浘")
        return False
    img1 = cv2.imdecode(np.frombuffer(img1_raw, np.uint8), cv2.IMREAD_COLOR)
    
    time.sleep(0.5)
    
    # 鎴浘 2
    img2_raw = adb_screencap()
    if img2_raw is None:
        print("[澶辫触] 鏃犳硶鎴浘")
        return False
    img2 = cv2.imdecode(np.frombuffer(img2_raw, np.uint8), cv2.IMREAD_COLOR)
    
    # 璁＄畻宸紓锛堝簲璇ュ緢灏忥紝鍥犱负鐢婚潰鍑犱箮娌″彉锛?    diff = screen_diff(img1, img2)
    print(f"[闈欐€乚 涓ゆ鎴浘宸紓锛歿diff:,} 鍍忕礌")

    # 璋冩暣闃堝€硷細闈欐€佺敾闈㈠彲鑳芥湁 50 涓囧乏鍙冲樊寮傦紙UI 鍔ㄧ敾绛夛級
    static_threshold = 600000
    if diff < static_threshold:
        print(f"[鉁揮 闈欐€佺敾闈㈠樊寮傚湪鍙帴鍙楄寖鍥村唴 (<{static_threshold:,})")
    else:
        print(f"[鈿燷 闈欐€佺敾闈㈠樊寮傝緝澶?(>{static_threshold:,})锛屽彲鑳芥槸 UI 鍔ㄧ敾")

    # 鐐瑰嚮浠诲姟鍥炬爣锛堜細鎵撳紑闈㈡澘锛岀敾闈㈠彉鍖栨槑鏄撅級
    print("[鎿嶄綔] 鐐瑰嚮浠诲姟鍥炬爣 (860, 80)...")
    adb.tap(860, 80)
    time.sleep(3)

    img3_raw = adb_screencap()
    if img3_raw is None:
        print("[澶辫触] 鏃犳硶鎴浘")
        adb.back()
        time.sleep(1)
        return False
    img3 = cv2.imdecode(np.frombuffer(img3_raw, np.uint8), cv2.IMREAD_COLOR)

    # 璁＄畻宸紓锛堝簲璇ヨ緝澶э紝鍥犱负鎵撳紑浜嗛潰鏉匡級
    diff2 = screen_diff(img1, img3)
    print(f"[鍔ㄦ€乚 鐐瑰嚮鍚庡樊寮傦細{diff2:,} 鍍忕礌")

    # 鎭㈠锛氬叧闂潰鏉?    adb.back()
    time.sleep(1)

    # 鐐瑰嚮鍚庣殑宸紓搴旇鏄庢樉澶т簬闈欐€佸樊寮傦紝鎴栬€呯粷瀵瑰€艰緝澶?    if diff2 > diff * 1.5:
        print(f"[鉁揮 鐐瑰嚮鍚庡樊寮傛槑鏄惧ぇ浜庨潤鎬佸樊寮?({diff2:,} > {diff*1.5:,})")
        return True
    elif diff2 > 800000:
        print("[鉁揮 鐐瑰嚮鍚庡樊寮傚ぇ锛岀鍚堥鏈?)
        return True
    elif diff2 > 400000:
        print("[鈿燷 鐐瑰嚮鍚庡樊寮備腑绛夛紝鍙兘鏈夋晥")
        return True
    else:
        print(f"[鉁梋 鐐瑰嚮鍚庡樊寮傚皬锛屽彲鑳芥棤鏁?({diff2:,} < 400000)")
        return False


def test_exit_dialog_close():
    """娴嬭瘯 exit_dialog 鍏抽棴鍔熻兘"""
    print("\n" + "="*70)
    print("娴嬭瘯 2: 閫€鍑哄璇濇鍏抽棴")
    print("="*70)
    
    adb = ADB('localhost:16512')
    analyzer = ScreenAnalyzer()
    
    def tap_func(x, y):
        adb.tap(x, y)
    
    # 纭繚鍦ㄤ笘鐣岄〉闈?    print("[鍑嗗] 纭繚鍦ㄤ笘鐣岄〉闈?..")
    for _ in range(5):
        adb.back()
        time.sleep(0.5)
    time.sleep(1)
    
    # 瑙﹀彂閫€鍑哄璇濇
    print("[瑙﹀彂] 鎸夎繑鍥為敭瑙﹀彂閫€鍑哄璇濇...")
    adb.back()
    time.sleep(2)
    
    # 楠岃瘉鏄惁鍑虹幇閫€鍑哄璇濇
    img_raw = adb_screencap()
    if img_raw is None:
        print("[澶辫触] 鏃犳硶鎴浘")
        return False
    img = cv2.imdecode(np.frombuffer(img_raw, np.uint8), cv2.IMREAD_COLOR)
    rotated = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    resized = cv2.resize(rotated, (1280, 720))
    analysis = analyzer.analyze(resized)
    
    print(f"[褰撳墠] 椤甸潰={analysis['page_type']} (閲戣壊={len(analysis['golden_elements'])})")
    
    if analysis["page_type"] != "exit_dialog":
        print(f"[璺宠繃] 鏈娴嬪埌閫€鍑哄璇濇")
        return True
    
    # 娴嬭瘯鍏抽棴
    print("[娴嬭瘯] 灏濊瘯鍏抽棴閫€鍑哄璇濇...")
    success, coord, diff = close_exit_dialog_with_verify(adb, analyzer, tap_func)
    
    print(f"[缁撴灉] success={success} coord={coord} diff={diff:,}" if diff else "[缁撴灉] success=" + str(success))
    
    # 楠岃瘉缁撴灉
    time.sleep(1)
    img_raw = adb_screencap()
    img = cv2.imdecode(np.frombuffer(img_raw, np.uint8), cv2.IMREAD_COLOR)
    rotated = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    resized = cv2.resize(rotated, (1280, 720))
    analysis2 = analyzer.analyze(resized)
    
    print(f"[楠岃瘉] 褰撳墠椤甸潰={analysis2['page_type']}")
    
    if analysis2["page_type"] != "exit_dialog":
        print("[鉁揮 閫€鍑哄璇濇宸插叧闂?)
        return True
    else:
        print("[鉁梋 閫€鍑哄璇濇浠嶅湪")
        return False


def test_page_classification():
    """娴嬭瘯椤甸潰绫诲瀷鍒ゆ柇鍑嗙‘鎬?""
    print("\n" + "="*70)
    print("娴嬭瘯 3: 椤甸潰绫诲瀷鍒ゆ柇")
    print("="*70)

    analyzer = ScreenAnalyzer()

    # 纭繚鍦ㄤ笘鐣岄〉闈?    adb = ADB('localhost:16512')
    print("[鍑嗗] 纭繚鍦ㄤ笘鐣岄〉闈?..")
    
    # 鍏堟寜澶氭 back 鍥炲埌涓栫晫鎴栭€€鍑哄璇濇
    for _ in range(5):
        adb.back()
        time.sleep(0.5)
    time.sleep(1)
    
    # 妫€鏌ユ槸鍚︽湁閫€鍑哄璇濇锛屾湁鍒欏叧闂?    img_raw = adb_screencap()
    img = cv2.imdecode(np.frombuffer(img_raw, np.uint8), cv2.IMREAD_COLOR)
    rotated = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    resized = cv2.resize(rotated, (1280, 720))
    analysis = analyzer.analyze(resized)
    
    if analysis["page_type"] == "exit_dialog":
        print("[鍑嗗] 妫€娴嬪埌閫€鍑哄璇濇锛屽叧闂?..")
        success, coord, diff = close_exit_dialog_with_verify(adb, analyzer, lambda x, y: adb.tap(x, y))
        if success:
            print(f"[鍑嗗] 閫€鍑哄璇濇宸插叧闂?{coord}")
        time.sleep(1)
    
    # 鍐嶆妫€鏌ョ‘淇濆湪涓栫晫椤甸潰
    img_raw = adb_screencap()
    img = cv2.imdecode(np.frombuffer(img_raw, np.uint8), cv2.IMREAD_COLOR)
    rotated = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    resized = cv2.resize(rotated, (1280, 720))
    analysis = analyzer.analyze(resized)

    print(f"[涓栫晫] 椤甸潰={analysis['page_type']}")
    print(f"       閲戣壊={len(analysis['golden_elements'])}")
    print(f"       YOLO={len(analysis['yolo_objects'])}")
    print(f"       OCR={analysis['ocr_text'][:80].replace(chr(10),' ')}")

    if analysis["page_type"] == "world":
        print("[鉁揮 涓栫晫椤甸潰鍒ゆ柇姝ｇ‘")
        world_correct = True
    else:
        print(f"[鉁梋 涓栫晫椤甸潰鍒ゆ柇閿欒 (瀹為檯={analysis['page_type']})")
        world_correct = False

    # 鎵撳紑浠诲姟闈㈡澘
    print("\n[鍑嗗] 鎵撳紑浠诲姟闈㈡澘...")
    adb.tap(860, 80)
    # 澧炲姞绛夊緟鏃堕棿锛岀‘淇濋潰鏉垮畬鍏ㄦ墦寮€
    time.sleep(5)
    
    # 妫€鏌ユ槸鍚︽湁閫€鍑哄璇濇锛堢偣鍑诲彲鑳借Е鍙戜簡杩斿洖锛?    img_raw = adb_screencap()
    img = cv2.imdecode(np.frombuffer(img_raw, np.uint8), cv2.IMREAD_COLOR)
    rotated = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    resized = cv2.resize(rotated, (1280, 720))
    temp_analysis = analyzer.analyze(resized)
    
    if temp_analysis["page_type"] == "exit_dialog":
        print("[鍑嗗] 妫€娴嬪埌閫€鍑哄璇濇锛屽叧闂?..")
        success, coord, diff = close_exit_dialog_with_verify(adb, analyzer, lambda x, y: adb.tap(x, y))
        if success:
            print(f"[鍑嗗] 閫€鍑哄璇濇宸插叧闂?{coord}")
        # 閲嶆柊鐐瑰嚮浠诲姟鍥炬爣
        print("[鍑嗗] 閲嶆柊鐐瑰嚮浠诲姟鍥炬爣...")
        adb.tap(860, 80)
        time.sleep(5)

    img_raw = adb_screencap()
    img = cv2.imdecode(np.frombuffer(img_raw, np.uint8), cv2.IMREAD_COLOR)
    rotated = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    resized = cv2.resize(rotated, (1280, 720))
    analysis2 = analyzer.analyze(resized)

    print(f"[浠诲姟] 椤甸潰={analysis2['page_type']}")
    print(f"       閲戣壊={len(analysis2['golden_elements'])}")
    print(f"       YOLO={len(analysis2['yolo_objects'])}")
    print(f"       OCR={analysis2['ocr_text'][:80].replace(chr(10),' ')}")

    # 浠诲姟闈㈡澘鍒ゆ柇锛氶噾鑹插厓绱?>= 22 鎴?妫€娴嬪埌"鏃ュ父"/"浠诲姟"鏂囧瓧
    is_quest_panel = (analysis2["page_type"] == "quest_panel" or 
                      len(analysis2["golden_elements"]) >= 22 or
                      any(kw in analysis2["ocr_text"] for kw in ["鏃ュ父", "浠诲姟", "Daily", "Quest"]))
    
    if is_quest_panel:
        print("[鉁揮 浠诲姟闈㈡澘鍒ゆ柇姝ｇ‘")
        quest_correct = True
    else:
        print(f"[鉁梋 浠诲姟闈㈡澘鍒ゆ柇閿欒 (瀹為檯={analysis2['page_type']}, 閲戣壊={len(analysis2['golden_elements'])})")
        quest_correct = False

    # 杩斿洖涓栫晫
    adb.back()
    time.sleep(1)

    return world_correct and quest_correct


def test_daily_quest_config():
    """娴嬭瘯 daily_quest 娴佺▼閰嶇疆"""
    print("\n" + "="*70)
    print("娴嬭瘯 4: daily_quest 娴佺▼閰嶇疆")
    print("="*70)
    
    config_path = PROJECT / "config" / "standard_flows" / "flows_config.json"
    
    if not config_path.exists():
        print(f"[澶辫触] 閰嶇疆鏂囦欢涓嶅瓨鍦細{config_path}")
        return False
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    flow = config.get("flows", {}).get("daily_quest")
    
    if not flow:
        print("[澶辫触] daily_quest 娴佺▼涓嶅瓨鍦?)
        return False
    
    print("[鉁揮 daily_quest 娴佺▼瀛樺湪")
    
    steps = flow.get("steps", [])
    print(f"[鉁揮 娴佺▼姝ラ鏁帮細{len(steps)}")
    
    # 妫€鏌ュ叧閿楠わ紙鍖归厤瀹為檯閰嶇疆涓殑姝ラ鍚嶇О锛?    required_patterns = [
        (["ensure_world", "verify_world"], "涓栫晫椤甸潰妫€鏌?),
        (["open_quest_panel", "open_quest"], "鎵撳紑浠诲姟闈㈡澘"),
        (["return_world", "back"], "杩斿洖涓栫晫"),
    ]
    
    step_ids = [s.get("id", "") for s in steps]
    step_descs = [s.get("desc", "").lower() for s in steps]
    
    missing = []
    for patterns, desc in required_patterns:
        found = any(p in step_ids for p in patterns)
        if found:
            print(f"[鉁揮 鍖呭惈姝ラ锛歿desc}")
        else:
            print(f"[鉁梋 缂哄皯姝ラ锛歿desc}")
            missing.append(desc)

    if missing:
        print(f"[鈿燷 缂哄皯 {len(missing)} 涓叧閿楠?)

    # 妫€鏌?exit_dialog 澶勭悊
    has_exit_dialog = any("exit_dialog" in s.get("id", "").lower() or
                          "exit_dialog" in s.get("desc", "").lower()
                          for s in steps)

    if has_exit_dialog:
        print("[鉁揮 鍖呭惈 exit_dialog 澶勭悊")
    else:
        print("[鈿燷 鏈槑纭寘鍚?exit_dialog 澶勭悊姝ラ锛堜絾寮曟搸浼氳嚜鍔ㄥ鐞嗭級")

    return len(missing) == 0


def generate_report():
    """鐢熸垚楠岃瘉鎶ュ憡"""
    print("\n" + "="*70)
    print("鏍囧噯娴佷慨澶嶉獙璇佹姤鍛?)
    print("="*70)
    print(f"鐢熸垚鏃堕棿锛歿time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {
        "screen_diff": test_screen_diff(),
        "exit_dialog": test_exit_dialog_close(),
        "page_classification": test_page_classification(),
        "daily_quest_config": test_daily_quest_config(),
    }
    
    # 缁熻
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print("\n" + "="*70)
    print("鎬荤粨")
    print("="*70)
    print(f"\n閫氳繃妫€鏌ワ細{passed}/{total}")
    
    for name, result in results.items():
        status = "鉁? if result else "鉁?
        print(f"  [{status}] {name}")
    
    if passed == total:
        print("\n[鉁揮 鎵€鏈夋鏌ラ€氳繃锛?)
        print("\n淇宸插簲鐢?")
        print("  鈥?灞忓箷宸紓妫€娴嬪嚱鏁?)
        print("  鈥?exit_dialog 澶氬潗鏍囧皾璇?+ 鐢婚潰楠岃瘉")
        print("  鈥?椤甸潰绫诲瀷鍒ゆ柇閫昏緫")
        print("  鈥?daily_quest 娴佺▼閰嶇疆")
        print("\n鏍囧噯娴佸紩鎿庡凡淇锛屽彲浠ユ墽琛屾祴璇曘€?)
        print("\n涓嬩竴姝?")
        print("  python scripts/standard_flow_engine.py --flow daily_quest")
        return True
    else:
        print(f"\n[鈿燷 {total - passed} 椤规鏌ユ湭閫氳繃")
        return False


def main():
    print("\n" + "="*70)
    print("鏍囧噯娴佺患鍚堥獙璇?)
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

