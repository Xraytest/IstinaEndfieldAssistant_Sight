#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
ADB 鐐瑰嚮璇婃柇鑴氭湰

妫€鏌?ADB tap 鍛戒护鏄惁姝ｇ‘鎵ц锛屼互鍙婂潗鏍囨槸鍚﹀噯纭?"""

import subprocess, time, cv2, numpy as np, sys, os
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ADB = str(PROJECT / '3rd-part' / 'adb' / 'adb.exe')
SERIAL = 'localhost:16512'

def tap(x, y):
    """鎵ц ADB tap 鍛戒护"""
    cmd = [ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))]
    print(f"  [CMD] {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, timeout=10)
    if r.returncode != 0:
        print(f"  [閿欒] tap 鍛戒护杩斿洖鐮侊細{r.returncode}")
        if r.stderr:
            print(f"  [STDERR] {r.stderr.decode('utf-8', errors='ignore')}")
    return r.returncode == 0

def back():
    """鎵ц ADB back 鍛戒护"""
    cmd = [ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4']
    r = subprocess.run(cmd, capture_output=True, timeout=5)
    return r.returncode == 0

def screencap():
    """鎵ц ADB screencap 鍛戒护"""
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

def test_tap_response():
    """娴嬭瘯 tap 鍛戒护鏄惁浜х敓鐢婚潰鍙樺寲"""
    print("\n" + "="*70)
    print("娴嬭瘯 1: ADB tap 鍝嶅簲娴嬭瘯")
    print("="*70)
    
    # 纭繚鍦ㄤ笘鐣岄〉闈?    print("\n[鍑嗗] 纭繚鍦ㄤ笘鐣岄〉闈?..")
    for i in range(5):
        back()
        time.sleep(0.5)
    time.sleep(1)
    
    # 鎴浘
    img1 = screencap()
    if img1 is None:
        print("[澶辫触] 鏃犳硶鎴浘")
        return False
    
    gold1 = detect_golden(img1)
    print(f"[鍒濆] 閲戣壊鍏冪礌={gold1}")
    
    # 娴嬭瘯澶氫釜鍧愭爣
    test_coords = [
        (860, 80, "浠诲姟鍥炬爣"),
        (928, 53, "娲诲姩鍥炬爣"),
        (1392, 79, "鑿滃崟鍥炬爣"),
        (150, 150, "鍩庡競鍦板浘"),
        (960, 540, "灞忓箷涓績"),
    ]
    
    results = []
    
    for x, y, name in test_coords:
        print(f"\n[娴嬭瘯] {name} ({x}, {y})...")
        
        # 鎴浘鍓?        before = screencap()
        if before is None:
            print(f"  [澶辫触] 鎴浘澶辫触")
            continue
        
        gold_before = detect_golden(before)
        
        # 鐐瑰嚮
        success = tap(x, y)
        if not success:
            print(f"  [澶辫触] tap 鍛戒护鎵ц澶辫触")
            results.append((name, x, y, False, 0, "command_failed"))
            continue
        
        time.sleep(2)
        
        # 鎴浘鍚?        after = screencap()
        if after is None:
            print(f"  [澶辫触] 鎴浘澶辫触")
            continue
        
        gold_after = detect_golden(after)
        diff = screen_diff(before, after)
        
        print(f"  [缁撴灉] diff={diff:,} 閲戣壊={gold_before}->{gold_after}")
        
        # 鍒ゆ柇鏄惁鏈夋晥
        if diff > 500000:
            status = "鏈夋晥 (澶у彉鍖?"
            effective = True
        elif diff > 200000:
            status = "鍙兘鏈夋晥 (涓彉鍖?"
            effective = True
        elif gold_after != gold_before:
            status = "鏈夋晥 (閲戣壊鍙樺寲)"
            effective = True
        else:
            status = "鏃犳晥 (鏃犲彉鍖?"
            effective = False
        
        results.append((name, x, y, effective, diff, status))
        print(f"  [鍒ゅ畾] {status}")
        
        # 鎭㈠锛氭寜杩斿洖
        if gold_after > gold_before or diff > 200000:
            print(f"  [鎭㈠] 鎸夎繑鍥為敭...")
            back()
            time.sleep(1)
    
    # 缁熻
    print("\n" + "="*70)
    print("娴嬭瘯缁撴灉缁熻")
    print("="*70)
    
    for name, x, y, effective, diff, status in results:
        marker = "鉁? if effective else "鉁?
        print(f"  [{marker}] {name:12} ({x:4}, {y:4}) diff={diff:>8,} {status}")
    
    effective_count = sum(1 for _, _, _, effective, _, _ in results if effective)
    print(f"\n鏈夋晥鐐瑰嚮锛歿effective_count}/{len(results)}")
    
    return effective_count > 0

def test_quest_icon_detailed():
    """璇︾粏娴嬭瘯浠诲姟鍥炬爣鐐瑰嚮"""
    print("\n" + "="*70)
    print("娴嬭瘯 2: 浠诲姟鍥炬爣璇︾粏娴嬭瘯")
    print("="*70)
    
    # 纭繚鍦ㄤ笘鐣岄〉闈?    print("\n[鍑嗗] 纭繚鍦ㄤ笘鐣岄〉闈?..")
    for i in range(5):
        back()
        time.sleep(0.5)
    time.sleep(1)
    
    # 鎴浘
    img = screencap()
    if img is None:
        print("[澶辫触] 鏃犳硶鎴浘")
        return False
    
    gold = detect_golden(img)
    print(f"[鍒濆] 閲戣壊鍏冪礌={gold}")
    
    if gold < 18 or gold > 21:
        print(f"[璀﹀憡] 閲戣壊鍏冪礌={gold}锛屽彲鑳戒笉鍦ㄤ笘鐣岄〉闈?)
    
    # 澶氭鐐瑰嚮娴嬭瘯
    for attempt in range(3):
        print(f"\n[灏濊瘯 {attempt+1}/3] 鐐瑰嚮浠诲姟鍥炬爣 (860, 80)...")
        
        before = screencap()
        gold_before = detect_golden(before)
        
        tap(860, 80)
        time.sleep(3)
        
        after = screencap()
        gold_after = detect_golden(after)
        diff = screen_diff(before, after)
        
        print(f"  [缁撴灉] diff={diff:,} 閲戣壊={gold_before}->{gold_after}")
        
        if diff > 500000 or gold_after > gold_before + 2:
            print(f"  [鎴愬姛] 闈㈡澘宸叉墦寮€")
            
            # 淇濆瓨鎴浘
            cv2.imwrite(str(PROJECT / 'cache' / 'quest_panel_open.png'), after)
            print(f"  [淇濆瓨] 鎴浘宸蹭繚瀛樺埌 cache/quest_panel_open.png")
            
            # 鎭㈠
            back()
            time.sleep(1)
            return True
        else:
            print(f"  [澶辫触] 闈㈡澘鏈墦寮€")
            
            # 灏濊瘯鎸夎繑鍥炴仮澶?            back()
            time.sleep(0.5)
    
    print("\n[缁撹] 浠诲姟鍥炬爣鐐瑰嚮鏃犳晥锛屽彲鑳藉師鍥狅細")
    print("  1. 鍧愭爣涓嶆纭?)
    print("  2. ADB 杩炴帴闂")
    print("  3. 妯℃嫙鍣ㄧ姸鎬佸紓甯?)
    print("  4. 娓告垙宸插湪浠诲姟闈㈡澘涓?)
    
    return False

def main():
    print("\n" + "="*70)
    print("ADB 鐐瑰嚮璇婃柇")
    print("="*70)
    
    result1 = test_tap_response()
    result2 = test_quest_icon_detailed()
    
    print("\n" + "="*70)
    print("鎬荤粨")
    print("="*70)
    
    if result1 and result2:
        print("[鉁揮 ADB tap 鍛戒护宸ヤ綔姝ｅ父")
        return 0
    else:
        print("[鉁梋 ADB tap 鍛戒护瀛樺湪闂")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[閿欒] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

