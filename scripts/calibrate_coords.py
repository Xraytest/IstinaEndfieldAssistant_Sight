#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鍧愭爣鏍″噯鑴氭湰

閫氳繃鍍忕礌鎵弿鎵惧嚭浠诲姟鍥炬爣鐨勫噯纭潗鏍?鍙傝€冿細涔嬪墠鍧愭爣鎵弿楠岃瘉缁撴灉 (860,80) 59.9%
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
    if img1 is None or img2 is None:
        return 0
    d = cv2.absdiff(img1, img2)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)

def detect_golden(img):
    if img is None:
        return 0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower = np.array([15, 80, 150])
    upper = np.array([35, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return len([c for c in contours if cv2.contourArea(c) > 30])

def find_icon_by_scanning():
    """
    閫氳繃鎵弿鍙充笂瑙掑尯鍩熸壘鍑轰换鍔″浘鏍囧潗鏍?    
    鍙傝€冧箣鍓嶇殑鎵弿缁撴灉锛?    - 妫嬬洏鏍兼壂鎻忓彂鐜?y=40/60/80 鏈夋晥锛寉=50/70 鏃犳晥
    - 鏈€浣冲潗鏍?(860, 80) 浜х敓 59.9% 鍖归厤搴?    """
    print("\n" + "="*70)
    print("鍧愭爣鎵弿锛氫换鍔″浘鏍?)
    print("="*70)
    
    # 纭繚鍦ㄤ笘鐣岄〉闈紙閲戣壊 18-21锛?    print("\n[鍑嗗] 纭繚鍦ㄤ笘鐣岄〉闈?..")
    for i in range(10):
        back()
        time.sleep(0.5)
    time.sleep(1)
    
    img = screencap()
    gold = detect_golden(img)
    print(f"[褰撳墠] 閲戣壊鍏冪礌={gold}")
    
    if gold < 12 or gold > 25:
        print(f"[璀﹀憡] 閲戣壊={gold}锛屽彲鑳戒笉鍦ㄤ笘鐣岄〉闈紝灏濊瘯鎭㈠...")
        for i in range(5):
            back()
            time.sleep(0.5)
        time.sleep(1)
        img = screencap()
        gold = detect_golden(img)
        print(f"[鎭㈠鍚嶿 閲戣壊鍏冪礌={gold}")
    
    # 鍩哄噯鎴浘
    baseline = screencap()
    baseline_gold = detect_golden(baseline)
    
    # 鎵弿鍖哄煙锛氬彸涓婅 (x: 700-1000, y: 20-120)
    # 鍩轰簬涔嬪墠楠岃瘉锛歽=40/60/80 鏈夋晥
    x_range = range(750, 950, 50)  # 750, 800, 850, 900, 949
    y_range = [40, 60, 80, 100]   # 涔嬪墠楠岃瘉鏈夋晥鐨?y 鍊?    
    best_coord = None
    best_diff = 0
    best_gold_change = 0
    
    print("\n[鎵弿] 鍙充笂瑙掑尯鍩?..")
    results = []
    
    for x in x_range:
        for y in y_range:
            before = screencap()
            before_gold = detect_golden(before)
            
            tap(x, y)
            time.sleep(1.5)
            
            after = screencap()
            after_gold = detect_golden(after)
            diff = screen_diff(before, after)
            gold_change = after_gold - before_gold
            
            results.append((x, y, diff, gold_change))
            
            # 璁板綍鏈€浣?            if diff > best_diff or gold_change > best_gold_change:
                best_diff = diff
                best_gold_change = gold_change
                best_coord = (x, y)
            
            # 鎭㈠
            back()
            time.sleep(0.3)
    
    # 鎺掑簭鏄剧ず鍓?10 涓粨鏋?    results.sort(key=lambda r: (r[2] + r[3]*100000), reverse=True)
    
    print("\n[缁撴灉] 鍓?10 涓渶浣冲潗鏍?")
    for i, (x, y, diff, gold_change) in enumerate(results[:10]):
        marker = "鈽? if (x, y) == best_coord else " "
        print(f"  {marker} ({x:4}, {y:3}) diff={diff:>8,} gold_change={gold_change:+d}")
    
    if best_coord:
        print(f"\n[鏈€浣砞 {best_coord} diff={best_diff:,} gold_change={best_gold_change:+d}")
    
    return best_coord

def verify_coordinate(coord):
    """楠岃瘉缁欏畾鍧愭爣鏄惁鏈夋晥"""
    print("\n" + "="*70)
    print(f"鍧愭爣楠岃瘉锛歿coord}")
    print("="*70)
    
    x, y = coord
    
    # 纭繚鍦ㄤ笘鐣岄〉闈?    print("\n[鍑嗗] 纭繚鍦ㄤ笘鐣岄〉闈?..")
    for i in range(10):
        back()
        time.sleep(0.5)
    time.sleep(1)
    
    img = screencap()
    gold = detect_golden(img)
    print(f"[鍒濆] 閲戣壊鍏冪礌={gold}")
    
    # 澶氭鐐瑰嚮娴嬭瘯
    success_count = 0
    for attempt in range(5):
        print(f"\n[灏濊瘯 {attempt+1}/5] 鐐瑰嚮 {coord}...")
        
        before = screencap()
        before_gold = detect_golden(before)
        
        tap(x, y)
        time.sleep(2)
        
        after = screencap()
        after_gold = detect_golden(after)
        diff = screen_diff(before, after)
        
        print(f"  [缁撴灉] diff={diff:,} 閲戣壊={before_gold}->{after_gold} (鍙樺寲={after_gold-before_gold:+d})")
        
        # 鍒ゆ柇鏄惁鎴愬姛鎵撳紑闈㈡澘锛堥噾鑹插鍔?>= 3 鎴?宸紓 > 500000锛?        if after_gold - before_gold >= 3 or diff > 500000:
            print(f"  [鎴愬姛] 闈㈡澘宸叉墦寮€")
            success_count += 1
            
            # 淇濆瓨鎴浘
            cv2.imwrite(str(PROJECT / 'cache' / f'verify_{x}_{y}.png'), after)
            
            # 鎭㈠
            back()
            time.sleep(1)
        else:
            print(f"  [澶辫触] 闈㈡澘鏈墦寮€")
            back()
            time.sleep(0.5)
    
    print(f"\n[缁熻] 鎴愬姛 {success_count}/5 娆?({success_count*20}%)")
    
    return success_count >= 3

def main():
    print("\n" + "="*70)
    print("鍧愭爣鏍″噯")
    print("="*70)
    
    # 鎵弿鎵惧嚭鏈€浣冲潗鏍?    best_coord = find_icon_by_scanning()
    
    if best_coord:
        # 楠岃瘉鏈€浣冲潗鏍?        success = verify_coordinate(best_coord)
        
        if success:
            print(f"\n[鉁揮 鍧愭爣 {best_coord} 楠岃瘉閫氳繃")
            return 0
        else:
            print(f"\n[鉁梋 鍧愭爣 {best_coord} 楠岃瘉澶辫触")
            return 1
    else:
        print("\n[鉁梋 鏈壘鍒版湁鏁堝潗鏍?)
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[閿欒] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

