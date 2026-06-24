#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
楠岃瘉 exit_dialog 淇鏁堟灉 鈥?鍩轰簬 MaaEnd 鐨?CancelButton 鎬濊矾

娴嬭瘯鏂规硶锛?1. 瑙﹀彂閫€鍑哄璇濇
2. 浣跨敤澶氬潗鏍囧皾璇曞叧闂?3. 閫氳繃鐢婚潰鍙樺寲楠岃瘉鏄惁鎴愬姛
4. 缁熻鎴愬姛鐜?
鍙傝€冿細MaaEnd 鐨?CancelButton 鑺傜偣锛堝叏灞忔ā鏉垮尮閰嶏級
"""

import subprocess, time, cv2, numpy as np, sys, os
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ADB = str(PROJECT / '3rd-part' / 'adb' / 'adb.exe')
SERIAL = 'localhost:16512'

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True, timeout=10)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], 
                   capture_output=True, timeout=5)

def screencap():
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       capture_output=True, timeout=15)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def screen_diff(img1, img2):
    """璁＄畻涓ゅ紶鍥剧墖鐨勫樊寮傚儚绱犳暟"""
    if img1 is None or img2 is None:
        return 0
    d = cv2.absdiff(img1, img2)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)

def detect_golden(img):
    """妫€娴嬮噾鑹插厓绱犳暟閲?""
    if img is None:
        return 0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower = np.array([15, 80, 150])
    upper = np.array([35, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return len([c for c in contours if cv2.contourArea(c) > 30])

def classify_by_gold(gold_count):
    """鍩轰簬閲戣壊鍏冪礌鏁伴噺鍒ゆ柇椤甸潰绫诲瀷"""
    if 12 <= gold_count <= 16:
        return "exit_dialog"
    elif 18 <= gold_count <= 21:
        return "world"
    elif gold_count >= 22:
        return "quest_panel"
    else:
        return "other"

def close_with_multi_coords():
    """
    澶氬潗鏍囧皾璇曞叧闂€€鍑哄璇濇
    
    杩斿洖锛?success, best_coord, best_diff)
    """
    # 鍊欓€夊潗鏍囷細鍩轰簬 1920x1080 鍒嗚鲸鐜囷紝瑕嗙洊鍙栨秷鎸夐挳鐨勫彲鑳戒綅缃?    cancel_candidates = [
        (600, 750),   # 榛樿浼拌
        (550, 730),   # 鍋忓乏涓?        (650, 770),   # 鍋忓彸涓?        (580, 740),   # 鍋忓乏
        (620, 760),   # 鍋忓彸
        (540, 720),   # 鏇村乏涓?        (660, 780),   # 鏇村彸涓?        (560, 750),   # 宸︿腑
        (640, 750),   # 鍙充腑
        (600, 730),   # 涓笂
        (600, 770),   # 涓笅
    ]
    
    best_coord = None
    best_diff = 0
    
    for i, (cx, cy) in enumerate(cancel_candidates):
        # 鎴浘
        before = screencap()
        if before is None:
            continue
        
        gold_before = detect_golden(before)
        page_before = classify_by_gold(gold_before)
        
        if page_before != "exit_dialog":
            return True, best_coord, best_diff  # 宸茬粡涓嶅湪閫€鍑哄璇濇
        
        # 鐐瑰嚮
        tap(cx, cy)
        time.sleep(1.5)
        
        # 鎴浘楠岃瘉
        after = screencap()
        if after is None:
            continue
        
        # 璁＄畻鐢婚潰鍙樺寲
        diff = screen_diff(before, after)
        gold_after = detect_golden(after)
        page_after = classify_by_gold(gold_after)
        
        # 璁板綍鏈€浣冲潗鏍?        if diff > best_diff:
            best_diff = diff
            best_coord = (cx, cy)
        
        # 鍒ゆ柇鏄惁鎴愬姛鍏抽棴
        if diff > 500000 and page_after != "exit_dialog":
            print(f"  [鎴愬姛] ({cx}, {cy}) diff={diff:,} {page_before}->{page_after}")
            return True, (cx, cy), diff
        elif diff > 200000 and gold_after < 12:
            print(f"  [鍙兘鎴愬姛] ({cx}, {cy}) diff={diff:,} 閲戣壊鍑忓皯")
            return True, (cx, cy), diff
        
        # 鎭㈠閫€鍑哄璇濇鐘舵€侊紙鎸夎繑鍥烇級
        back()
        time.sleep(1)
    
    return False, best_coord, best_diff

def close_with_back():
    """浣跨敤 back 閿叧闂€€鍑哄璇濇"""
    before = screencap()
    back()
    time.sleep(1.5)
    after = screencap()
    
    if before is not None and after is not None:
        diff = screen_diff(before, after)
        gold_after = detect_golden(after)
        page_after = classify_by_gold(gold_after)
        
        print(f"  [back] diff={diff:,} 椤甸潰={page_after} (閲戣壊={gold_after})")
        
        if page_after != "exit_dialog":
            return True, None, diff
    
    return False, None, 0

def run_test_round(round_num, total_rounds):
    """杩愯涓€杞祴璇?""
    print(f"\n{'='*60}")
    print(f"娴嬭瘯杞 {round_num}/{total_rounds}")
    print("="*60)
    
    # 纭繚鍦ㄤ笘鐣岄〉闈?    print("[鍑嗗] 纭繚鍦ㄤ笘鐣岄〉闈?..")
    for _ in range(5):
        back()
        time.sleep(0.5)
    time.sleep(1)
    
    # 瑙﹀彂閫€鍑哄璇濇
    print("[瑙﹀彂] 鎸夎繑鍥為敭瑙﹀彂閫€鍑哄璇濇...")
    back()
    time.sleep(2)
    
    # 楠岃瘉鏄惁鍑虹幇閫€鍑哄璇濇
    img = screencap()
    gold = detect_golden(img)
    page = classify_by_gold(gold)
    
    print(f"[褰撳墠] 椤甸潰={page} (閲戣壊={gold})")
    
    if page != "exit_dialog":
        print(f"[璺宠繃] 鏈娴嬪埌閫€鍑哄璇濇")
        return None
    
    # 鏂规硶 1锛氬鍧愭爣灏濊瘯
    print("\n[鏂规硶 1] 澶氬潗鏍囧皾璇?..")
    success1, coord1, diff1 = close_with_multi_coords()
    
    # 楠岃瘉缁撴灉
    time.sleep(1)
    img = screencap()
    gold = detect_golden(img)
    page = classify_by_gold(gold)
    
    if page != "exit_dialog":
        print(f"[缁撴灉] 鏂规硶 1 鎴愬姛锛屽綋鍓嶉〉闈?{page}")
        return {"method": "multi_coords", "coord": coord1, "diff": diff1, "success": True}
    
    # 鏂规硶 2锛歜ack 閿?    print("\n[鏂规硶 2] back 閿?..")
    success2, coord2, diff2 = close_with_back()
    
    time.sleep(1)
    img = screencap()
    gold = detect_golden(img)
    page = classify_by_gold(gold)
    
    if page != "exit_dialog":
        print(f"[缁撴灉] 鏂规硶 2 鎴愬姛锛屽綋鍓嶉〉闈?{page}")
        return {"method": "back", "coord": coord2, "diff": diff2, "success": True}
    
    print("[缁撴灉] 鎵€鏈夋柟娉曞け璐?)
    return {"method": "none", "coord": None, "diff": 0, "success": False}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=3, help="娴嬭瘯杞鏁?)
    parser.add_argument("--single", action="store_true", help="鍗曡疆娴嬭瘯")
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("Exit Dialog 淇楠岃瘉")
    print("="*70)
    
    if args.single:
        result = run_test_round(1, 1)
        if result:
            print(f"\n缁撴灉锛歿result}")
        return 0
    
    # 澶氳疆娴嬭瘯
    results = []
    for i in range(args.rounds):
        result = run_test_round(i + 1, args.rounds)
        if result:
            results.append(result)
        time.sleep(2)
    
    # 缁熻
    print("\n" + "="*70)
    print("缁熻缁撴灉")
    print("="*70)
    
    success_count = sum(1 for r in results if r["success"])
    print(f"\n鎬昏疆娆★細{len(results)}")
    print(f"鎴愬姛锛歿success_count}")
    print(f"澶辫触锛歿len(results) - success_count}")
    print(f"鎴愬姛鐜囷細{success_count/len(results)*100:.1f}%" if results else "N/A")
    
    # 鏂规硶鍒嗗竷
    methods = {}
    for r in results:
        method = r["method"]
        if method not in methods:
            methods[method] = 0
        methods[method] += 1
    
    print("\n鏂规硶鍒嗗竷:")
    for method, count in methods.items():
        print(f"  {method}: {count}")
    
    # 鏈€浣冲潗鏍?    coords = [r["coord"] for r in results if r["coord"]]
    if coords:
        from collections import Counter
        coord_counts = Counter(str(c) for c in coords)
        print("\n鏈€浣冲潗鏍囧垎甯?")
        for coord_str, count in coord_counts.most_common(3):
            print(f"  {coord_str}: {count}娆?)
    
    return 0 if success_count > 0 else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[閿欒] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

