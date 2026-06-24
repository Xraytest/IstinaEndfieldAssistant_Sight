#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鐘舵€佹仮澶嶈剼鏈?- 鎵惧埌骞剁‘璁や笘鐣岄〉闈㈢姸鎬?"""

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

def home():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '3'], 
                   capture_output=True, timeout=5)

def screencap():
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       capture_output=True, timeout=15)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def detect_golden(img):
    if img is None:
        return 0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower = np.array([15, 80, 150])
    upper = np.array([35, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return len([c for c in contours if cv2.contourArea(c) > 30])

def classify_page(gold_count):
    """鍩轰簬閲戣壊鍏冪礌鏁伴噺鍒ゆ柇椤甸潰绫诲瀷"""
    if gold_count < 10:
        return "unknown_low"
    elif 10 <= gold_count <= 18:
        return "exit_dialog"
    elif 16 <= gold_count <= 24:
        return "world"
    elif gold_count > 30:
        return "menu_or_panel"
    else:
        return "other"

def find_world_state(max_attempts=30):
    """
    灏濊瘯鎵惧埌涓栫晫椤甸潰鐘舵€?    
    绛栫暐锛?    1. 杩炵画鎸夎繑鍥為敭锛岀洃鎺ч噾鑹插厓绱犲彉鍖?    2. 涓€鏃﹂噾鑹插湪 16-24 鑼冨洿鍐咃紝纭涓轰笘鐣岄〉闈?    3. 濡傛灉閲戣壊>30锛岃鏄庡湪鑿滃崟/闈㈡澘涓紝缁х画鎸夎繑鍥?    4. 濡傛灉閲戣壊<10锛岃鏄庡湪寮傚父鐘舵€侊紝缁х画鎸夎繑鍥?    """
    print("\n" + "="*70)
    print("鐘舵€佹仮澶嶏細瀵绘壘涓栫晫椤甸潰")
    print("="*70)
    
    history = []
    
    for i in range(max_attempts):
        # 鎴浘
        img = screencap()
        if img is None:
            print(f"[{i:2d}] 鎴浘澶辫触")
            continue
        
        gold = detect_golden(img)
        page = classify_page(gold)
        
        history.append((i, gold, page))
        marker = "鈽? if page == "world" else " "
        print(f"{marker} [{i:2d}] 閲戣壊={gold:3d} 鈫?{page}")
        
        # 鎵惧埌涓栫晫椤甸潰
        if page == "world":
            print(f"\n[鎴愬姛] 鍦ㄧ{i+1}娆″皾璇曞悗鎵惧埌涓栫晫椤甸潰")
            return True, i, gold, img
        
        # 鍐冲畾涓嬩竴姝ユ搷浣?        if gold > 30:
            # 鍦ㄨ彍鍗?闈㈡澘涓紝鎸夎繑鍥?            print(f"       鈫?鎸夎繑鍥?(鍦ㄨ彍鍗?闈㈡澘涓?")
            back()
            time.sleep(0.5)
        elif gold < 10:
            # 寮傚父鐘舵€侊紝鎸夎繑鍥?            print(f"       鈫?鎸夎繑鍥?(寮傚父鐘舵€?")
            back()
            time.sleep(0.5)
        elif page == "exit_dialog":
            # 閫€鍑哄璇濇锛岀偣鍑诲彇娑堟寜閽?            print(f"       鈫?鐐瑰嚮鍙栨秷鎸夐挳 (閫€鍑哄璇濇)")
            tap(600, 750)
            time.sleep(1.5)
        else:
            # 鍏朵粬鐘舵€侊紝鎸夎繑鍥?            print(f"       鈫?鎸夎繑鍥?)
            back()
            time.sleep(0.5)
    
    print(f"\n[澶辫触] {max_attempts}娆″皾璇曞悗浠嶆湭鎵惧埌涓栫晫椤甸潰")
    print("\n鍘嗗彶:")
    for idx, gold, page in history[-10:]:
        print(f"  [{idx:2d}] 閲戣壊={gold:3d} 鈫?{page}")
    
    return False, max_attempts, history[-1][1] if history else 0, None

def verify_world_state(img):
    """楠岃瘉鏄惁鐪熺殑鏄笘鐣岄〉闈?""
    if img is None:
        return False
    
    gold = detect_golden(img)
    
    # 涓栫晫椤甸潰鐗瑰緛锛?    # 1. 閲戣壊鍏冪礌 16-24 涓?    # 2. 鐐瑰嚮鍙充笂瑙掍换鍔″浘鏍囧簲璇ユ墦寮€闈㈡澘锛堥噾鑹插鍔狅級
    
    print(f"\n[楠岃瘉] 褰撳墠閲戣壊={gold}")
    
    if not (16 <= gold <= 24):
        print(f"[楠岃瘉澶辫触] 閲戣壊{gold}涓嶅湪涓栫晫椤甸潰鑼冨洿 (16-24)")
        return False
    
    # 灏濊瘯鐐瑰嚮浠诲姟鍥炬爣
    print("[楠岃瘉] 鐐瑰嚮浠诲姟鍥炬爣 (860, 80)...")
    before = img
    tap(860, 80)
    time.sleep(2)
    
    after = screencap()
    if after is None:
        print("[楠岃瘉澶辫触] 鎴浘澶辫触")
        return False
    
    gold_after = detect_golden(after)
    print(f"[楠岃瘉] 鐐瑰嚮鍚庨噾鑹?{gold_after} (鍙樺寲={gold_after-gold:+d})")
    
    # 鎭㈠
    back()
    time.sleep(0.5)
    
    # 鍒ゆ柇锛氬鏋滈噾鑹插鍔?=3锛岃鏄庢墦寮€浜嗛潰鏉?    if gold_after - gold >= 3:
        print("[楠岃瘉閫氳繃] 浠诲姟鍥炬爣鐐瑰嚮鏈夋晥")
        return True
    else:
        print(f"[楠岃瘉璀﹀憡] 浠诲姟鍥炬爣鐐瑰嚮鍚庨噾鑹插彉鍖栧皬 ({gold_after-gold:+d})")
        return False

def main():
    print("\n" + "="*70)
    print("鐘舵€佹仮澶嶈瘖鏂?)
    print("="*70)
    
    # 瀵绘壘涓栫晫椤甸潰
    success, attempts, gold, img = find_world_state()
    
    if success:
        # 楠岃瘉
        is_valid = verify_world_state(img)
        
        if is_valid:
            print(f"\n[鉁揮 鎴愬姛鎵惧埌骞堕獙璇佷笘鐣岄〉闈?)
            print(f"    灏濊瘯娆℃暟锛歿attempts}")
            print(f"    閲戣壊鍏冪礌锛歿gold}")
            return 0
        else:
            print(f"\n[鈿燷 鎵惧埌鐤戜技涓栫晫椤甸潰锛屼絾楠岃瘉鏈€氳繃")
            return 1
    else:
        print(f"\n[鉁梋 鏃犳硶鎵惧埌涓栫晫椤甸潰")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[閿欒] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

