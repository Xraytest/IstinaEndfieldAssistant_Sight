#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
楂樼簿搴︽爣鍑嗘祦楠岃瘉鑴氭湰

闂璇婃柇锛?1. 閫€鍑哄璇濇"鍙栨秷"鎸夐挳鍧愭爣 (600, 750) 鏄惁鍑嗙‘锛?2. 椤甸潰绫诲瀷鍒ゆ柇閫昏緫鏄惁姝ｇ‘锛?3. 鏍囧噯娴佸疄闄呮墽琛屾槸鍚︽垚鍔燂紵

鏂规硶锛?1. 閫氳繃鍍忕礌宸紓鍒嗘瀽绮剧‘瀹氫綅"鍙栨秷"鎸夐挳
2. 閲囬泦瀹為檯椤甸潰鏍锋湰楠岃瘉閲戣壊鍏冪礌闃堝€?3. 杩愯鏍囧噯娴佸苟璇︾粏璁板綍姣忎竴姝ョ殑鐘舵€?"""

import subprocess, time, cv2, numpy as np, os, json, sys
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

PROJECT = Path(__file__).resolve().parent.parent
ADB = str(PROJECT / '3rd-part' / 'adb' / 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = PROJECT / 'cache' / 'high_precision_verify'
CACHE.mkdir(exist_ok=True)


def tap(x, y):
    """ADB tap"""
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True, timeout=10)

def back():
    """ADB back"""
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], capture_output=True, timeout=5)

def screencap():
    """鎴浘鍒板唴瀛?""
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       capture_output=True, timeout=15)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def save_img(img, path):
    """淇濆瓨鍥剧墖"""
    if img is not None:
        cv2.imwrite(str(path), img)
        return True
    return False

def screen_diff(img1, img2):
    """璁＄畻涓ゅ紶鍥剧墖鐨勫樊寮?""
    if img1 is None or img2 is None:
        return 0, 0
    d = cv2.absdiff(img1, img2)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t), g.mean()


def detect_golden_elements(img):
    """妫€娴嬮噾鑹插厓绱狅紙涓?ScreenAnalyzer 涓€鑷达級"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    ranges = [
        ("浜噾", np.array([15, 80, 150]), np.array([35, 255, 255])),
        ("鏆楅噾", np.array([15, 50, 80]), np.array([35, 255, 200])),
        ("鏆栭噾", np.array([10, 60, 100]), np.array([40, 255, 255])),
    ]
    all_elems = []
    for name, lower, upper in ranges:
        mask = cv2.inRange(hsv, lower, upper)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 30:
                x, y, bw, bh = cv2.boundingRect(cnt)
                all_elems.append({
                    "cx": x + bw // 2, "cy": y + bh // 2,
                    "w": bw, "h": bh, "area": area, "range": name
                })
    unique = []
    for elem in sorted(all_elems, key=lambda e: e["area"], reverse=True):
        if not any(abs(elem["cx"] - u["cx"]) < 20 and abs(elem["cy"] - u["cy"]) < 20 for u in unique):
            unique.append(elem)
    return unique


def classify_page_by_gold(gold_count, img_mean):
    """鍩轰簬閲戣壊鍏冪礌鏁伴噺鍜岀敾闈寒搴﹀垽鏂〉闈㈢被鍨?""
    # 閫€鍑哄璇濇锛?2-16 涓噾鑹插厓绱?+ 杈冩殫鑳屾櫙
    if 12 <= gold_count <= 16 and img_mean < 100:
        return "exit_dialog"
    # 浠诲姟闈㈡澘锛氣墺22 涓噾鑹插厓绱?    if gold_count >= 22:
        return "quest_panel"
    # 涓栫晫椤甸潰锛?8-21 涓噾鑹插厓绱?    if 18 <= gold_count <= 21:
        return "world"
    # 鑿滃崟锛?-11 涓噾鑹插厓绱?    if 8 <= gold_count <= 11:
        return "menu"
    # 涓栫晫锛堜綆閲戣壊锛夛細15-17 涓?    if 15 <= gold_count <= 17:
        return "world_low_gold"
    return "other"


def find_exit_dialog_cancel_button(img):
    """
    閫氳繃鍍忕礌宸紓鍒嗘瀽绮剧‘瀹氫綅閫€鍑哄璇濇"鍙栨秷"鎸夐挳
    
    鏂规硶锛?    1. 妫€娴嬮€€鍑哄璇濇鍖哄煙锛堥€氬父鍦ㄧ敾闈腑澶級
    2. 鍦ㄥ璇濇搴曢儴瀵绘壘涓や釜鎸夐挳
    3. 宸︿晶涓?鍙栨秷"锛屽彸渚т负"纭"
    """
    print("\n[鍒嗘瀽] 妫€娴嬮€€鍑哄璇濇鎸夐挳浣嶇疆...")
    
    if img is None:
        return None
    
    h, w = img.shape[:2]  # 1080x1920 绔栧睆
    
    # 閫€鍑哄璇濇閫氬父鍦ㄤ腑澶尯鍩?    # 鎸夐挳鍦ㄥ璇濇搴曢儴锛屽ぇ绾﹀湪 (600-800, 700-900) 鑼冨洿
    
    # 妫€娴嬪簳閮ㄥ尯鍩熺殑閲戣壊/浜壊鍏冪礌锛堟寜閽級
    bottom_region = img[600:900, 400:1200]  # 搴曢儴涓ぎ鍖哄煙
    
    golden = detect_golden_elements(bottom_region)
    
    # 绛涢€夋寜閽ぇ灏忕殑鍏冪礌锛堝搴?80-200锛岄珮搴?40-80锛?    buttons = []
    for g in golden:
        adjusted_cx = g["cx"] + 400  # 璋冩暣鍒板師鍥惧潗鏍?        adjusted_cy = g["cy"] + 600
        if 80 <= g["w"] <= 200 and 40 <= g["h"] <= 80:
            buttons.append({
                "cx": adjusted_cx, "cy": adjusted_cy,
                "w": g["w"], "h": g["h"], "area": g["area"]
            })
    
    # 鎸?x 鍧愭爣鎺掑簭锛屽乏渚т负"鍙栨秷"
    buttons.sort(key=lambda b: b["cx"])
    
    if len(buttons) >= 2:
        cancel_btn = buttons[0]
        confirm_btn = buttons[1]
        print(f"  [鍙戠幇] 鍙栨秷鎸夐挳锛?{cancel_btn['cx']}, {cancel_btn['cy']}) {cancel_btn['w']}x{cancel_btn['h']}")
        print(f"  [鍙戠幇] 纭鎸夐挳锛?{confirm_btn['cx']}, {confirm_btn['cy']}) {confirm_btn['w']}x{confirm_btn['h']}")
        return cancel_btn
    elif len(buttons) == 1:
        print(f"  [璀﹀憡] 鍙壘鍒?1 涓寜閽細({buttons[0]['cx']}, {buttons[0]['cy']})")
        return buttons[0]
    else:
        print(f"  [璀﹀憡] 鏈壘鍒版寜閽紝浣跨敤榛樿鍧愭爣 (600, 750)")
        return {"cx": 600, "cy": 750, "w": 100, "h": 60}


def verify_cancel_button_coords():
    """
    楠岃瘉閫€鍑哄璇濇"鍙栨秷"鎸夐挳鍧愭爣
    
    姝ラ锛?    1. 瑙﹀彂閫€鍑哄璇濇
    2. 鎴浘鍒嗘瀽鎸夐挳浣嶇疆
    3. 娴嬭瘯澶氫釜鍊欓€夊潗鏍?    4. 閫氳繃鐢婚潰鍙樺寲纭鍝釜鍧愭爣鏈夋晥
    """
    print("\n" + "="*70)
    print("楠岃瘉閫€鍑哄璇濇'鍙栨秷'鎸夐挳鍧愭爣")
    print("="*70)
    
    # 姝ラ 1: 纭繚鍦ㄤ笘鐣岄〉闈?    print("\n[姝ラ 1] 纭繚鍦ㄤ笘鐣岄〉闈?..")
    for _ in range(5):
        back()
        time.sleep(0.5)
    
    time.sleep(1)
    world_img = screencap()
    if world_img is None:
        print("  [澶辫触] 鏃犳硶鎴浘")
        return False
    
    world_gold = len(detect_golden_elements(world_img))
    world_page = classify_page_by_gold(world_gold, world_img.mean())
    print(f"  [褰撳墠] 椤甸潰={world_page} 閲戣壊={world_gold} 浜害={world_img.mean():.1f}")
    
    # 姝ラ 2: 瑙﹀彂閫€鍑哄璇濇锛堟寜杩斿洖閿級
    print("\n[姝ラ 2] 瑙﹀彂閫€鍑哄璇濇...")
    back()
    time.sleep(2)
    
    dialog_img = screencap()
    if dialog_img is None:
        print("  [澶辫触] 鏃犳硶鎴浘")
        return False
    
    dialog_gold = len(detect_golden_elements(dialog_img))
    dialog_page = classify_page_by_gold(dialog_gold, dialog_img.mean())
    print(f"  [褰撳墠] 椤甸潰={dialog_page} 閲戣壊={dialog_gold} 浜害={dialog_img.mean():.1f}")
    
    if dialog_page != "exit_dialog":
        print(f"  [璀﹀憡] 鏈娴嬪埌閫€鍑哄璇濇锛屽綋鍓嶉〉闈?{dialog_page}")
        # 缁х画娴嬭瘯锛屼絾鏍囪涓哄紓甯?    else:
        print(f"  [鎴愬姛] 妫€娴嬪埌閫€鍑哄璇濇")
    
    save_img(dialog_img, CACHE / 'exit_dialog.png')
    
    # 姝ラ 3: 鍒嗘瀽鎸夐挳浣嶇疆
    print("\n[姝ラ 3] 鍒嗘瀽鎸夐挳浣嶇疆...")
    cancel_btn = find_exit_dialog_cancel_button(dialog_img)
    
    # 姝ラ 4: 娴嬭瘯鍊欓€夊潗鏍?    print("\n[姝ラ 4] 娴嬭瘯鍊欓€夊潗鏍?..")
    
    # 鍊欓€夊潗鏍囷細鍒嗘瀽寰楀埌鐨?+ 榛樿 (600, 750) + 闄勮繎鍖哄煙
    candidates = [
        (cancel_btn["cx"], cancel_btn["cy"], "鍒嗘瀽寰楀埌"),
        (600, 750, "榛樿鍧愭爣"),
        (540, 720, "闄勮繎 1"),
        (660, 780, "闄勮繎 2"),
    ]
    
    best_coord = None
    best_diff = 0
    
    for cx, cy, desc in candidates:
        # 閲嶆柊瑙﹀彂閫€鍑哄璇濇
        back()
        time.sleep(2)
        
        before = screencap()
        if before is None:
            continue
        
        # 鐐瑰嚮鍊欓€夊潗鏍?        print(f"  [娴嬭瘯] {desc}: ({cx}, {cy})", end=" ")
        tap(cx, cy)
        time.sleep(2)
        
        after = screencap()
        if after is None:
            print("鎴浘澶辫触")
            continue
        
        # 璁＄畻鐢婚潰鍙樺寲
        diff, mean_diff = screen_diff(before, after)
        
        # 妫€鏌ユ槸鍚﹀洖鍒颁笘鐣岄〉闈?        after_gold = len(detect_golden_elements(after))
        after_page = classify_page_by_gold(after_gold, after.mean())
        
        print(f"diff={diff:,} mean={mean_diff:.1f} 椤甸潰={after_page}")
        
        # 濡傛灉鐢婚潰鍙樺寲澶т笖鍥炲埌涓栫晫椤甸潰锛岃鏄庡潗鏍囨湁鏁?        if diff > best_diff and after_page in ("world", "world_low_gold"):
            best_diff = diff
            best_coord = (cx, cy, desc)
            print(f"    [鏈夋晥] 鎴愬姛鍏抽棴瀵硅瘽妗嗭紝鍥炲埌{after_page}")
    
    if best_coord:
        print(f"\n[缁撹] 鏈€浣冲潗鏍囷細{best_coord[0]}, {best_coord[1]} ({best_coord[2]})")
        return best_coord
    else:
        print(f"\n[缁撹] 鏈壘鍒版湁鏁堝潗鏍囷紝寤鸿浣跨敤榛樿 (600, 750)")
        return (600, 750, "榛樿")


def verify_page_classification():
    """
    楠岃瘉椤甸潰绫诲瀷鍒ゆ柇閫昏緫
    
    閲囬泦鍚勯〉闈㈢殑瀹為檯鏍锋湰锛岄獙璇侀噾鑹插厓绱犻槇鍊兼槸鍚﹀噯纭?    """
    print("\n" + "="*70)
    print("楠岃瘉椤甸潰绫诲瀷鍒ゆ柇閫昏緫")
    print("="*70)
    
    samples = {}
    
    # 閲囬泦涓栫晫椤甸潰鏍锋湰
    print("\n[閲囬泦] 涓栫晫椤甸潰鏍锋湰...")
    for i in range(5):
        for _ in range(3):
            back()
            time.sleep(0.5)
        time.sleep(1)
        
        img = screencap()
        if img is None:
            continue
        
        gold = len(detect_golden_elements(img))
        mean = img.mean()
        page = classify_page_by_gold(gold, mean)
        
        print(f"  [鏍锋湰 {i+1}] 閲戣壊={gold} 浜害={mean:.1f} 鍒ゆ柇={page}")
        
        if "world" not in samples:
            samples["world"] = []
        samples["world"].append({"gold": gold, "mean": mean, "page": page})
        
        save_img(img, CACHE / f'world_sample_{i+1}.png')
        time.sleep(0.5)
    
    # 閲囬泦浠诲姟闈㈡澘鏍锋湰
    print("\n[閲囬泦] 浠诲姟闈㈡澘鏍锋湰...")
    tap(860, 80)  # 浠诲姟鍥炬爣
    time.sleep(2)
    
    for i in range(3):
        img = screencap()
        if img is None:
            continue
        
        gold = len(detect_golden_elements(img))
        mean = img.mean()
        page = classify_page_by_gold(gold, mean)
        
        print(f"  [鏍锋湰 {i+1}] 閲戣壊={gold} 浜害={mean:.1f} 鍒ゆ柇={page}")
        
        if "quest_panel" not in samples:
            samples["quest_panel"] = []
        samples["quest_panel"].append({"gold": gold, "mean": mean, "page": page})
        
        save_img(img, CACHE / f'quest_panel_sample_{i+1}.png')
        time.sleep(0.5)
    
    # 鎸夎繑鍥為€€鍑轰换鍔￠潰鏉?    for _ in range(3):
        back()
        time.sleep(0.5)
    
    # 缁熻缁撴灉
    print("\n[缁熻] 椤甸潰绫诲瀷鍒ゆ柇鍑嗙‘鎬?..")
    for page_type, page_samples in samples.items():
        if not page_samples:
            continue
        
        golds = [s["gold"] for s in page_samples]
        means = [s["mean"] for s in page_samples]
        correct = sum(1 for s in page_samples if page_type in s["page"])
        
        print(f"\n  {page_type}:")
        print(f"    閲戣壊鍏冪礌锛歮in={min(golds)} max={max(golds)} avg={sum(golds)/len(golds):.1f}")
        print(f"    鐢婚潰浜害锛歮in={min(means):.1f} max={max(means):.1f} avg={sum(means)/len(means):.1f}")
        print(f"    鍒ゆ柇鍑嗙‘锛歿correct}/{len(page_samples)}")
    
    # 淇濆瓨缁熻缁撴灉
    result = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "samples": {}
    }
    for page_type, page_samples in samples.items():
        if page_samples:
            golds = [s["gold"] for s in page_samples]
            means = [s["mean"] for s in page_samples]
            result["samples"][page_type] = {
                "gold_range": [min(golds), max(golds)],
                "gold_avg": sum(golds) / len(golds),
                "mean_range": [min(means), max(means)],
                "mean_avg": sum(means) / len(means),
                "count": len(page_samples)
            }
    
    with open(CACHE / 'page_classification_stats.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n[淇濆瓨] 缁熻缁撴灉锛歿CACHE / 'page_classification_stats.json'}")
    
    return result


def run_standard_flow_test(flow_name="daily_quest"):
    """
    杩愯鏍囧噯娴佹祴璇?    
    璇︾粏璁板綍姣忎竴姝ョ殑鐘舵€侊紝楠岃瘉鏄惁鑳芥纭墽琛?    """
    print("\n" + "="*70)
    print(f"杩愯鏍囧噯娴佹祴璇曪細{flow_name}")
    print("="*70)
    
    # 瀵煎叆鏍囧噯娴佸紩鎿?    try:
        from scripts.standard_flow_engine import StandardFlowExecutor, load_config
    except Exception as e:
        print(f"[澶辫触] 瀵煎叆鏍囧噯娴佸紩鎿庡け璐ワ細{e}")
        return False
    
    # 鍔犺浇閰嶇疆
    config = load_config()
    
    # 妫€鏌ユ祦绋嬫槸鍚﹀瓨鍦?    if not config.is_flow_exists(flow_name):
        print(f"[澶辫触] 娴佺▼涓嶅瓨鍦細{flow_name}")
        return False
    
    # 鍒涘缓鎵ц鍣?    executor = StandardFlowExecutor(config)
    
    # 鎵ц娴佺▼
    print(f"\n[鎵ц] 寮€濮嬫墽琛?{flow_name}...")
    success = executor.execute_flow(flow_name)
    
    print(f"\n[缁撴灉] {'鎴愬姛' if success else '鏈夊け璐ユ楠?}")
    
    return success


def main():
    print("\n" + "="*70)
    print("楂樼簿搴︽爣鍑嗘祦楠岃瘉")
    print("="*70)
    
    results = {}
    
    # 1. 楠岃瘉閫€鍑哄璇濇鍧愭爣
    cancel_coord = verify_cancel_button_coords()
    results["cancel_button"] = cancel_coord
    
    # 2. 楠岃瘉椤甸潰绫诲瀷鍒ゆ柇
    page_stats = verify_page_classification()
    results["page_classification"] = page_stats
    
    # 3. 杩愯鏍囧噯娴佹祴璇?    # flow_success = run_standard_flow_test("daily_quest")
    # results["flow_test"] = flow_success
    
    # 淇濆瓨缁撴灉
    with open(CACHE / 'verification_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # 鎬荤粨
    print("\n" + "="*70)
    print("楠岃瘉鎬荤粨")
    print("="*70)
    
    print(f"\n1. 閫€鍑哄璇濇'鍙栨秷'鎸夐挳鍧愭爣锛歿cancel_coord[0]}, {cancel_coord[1]} ({cancel_coord[2]})")
    
    if page_stats and "samples" in page_stats:
        for page_type, stats in page_stats["samples"].items():
            print(f"2. {page_type} 椤甸潰:")
            print(f"   閲戣壊鍏冪礌鑼冨洿锛歔{stats['gold_range'][0]}, {stats['gold_range'][1]}]")
            print(f"   骞冲潎閲戣壊鍏冪礌锛歿stats['gold_avg']:.1f}")
    
    print(f"\n璇︾粏缁撴灉宸蹭繚瀛橈細{CACHE / 'verification_results.json'}")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[閿欒] 楠岃瘉澶辫触锛歿e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

