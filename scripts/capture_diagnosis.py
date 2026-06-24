#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鎵嬪姩鎴浘璇婃柇 - 淇濆瓨褰撳墠鐢婚潰浠ヤ究浜哄伐鍒嗘瀽
"""

import subprocess, time, cv2, numpy as np, sys, os
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ADB = str(PROJECT / '3rd-part' / 'adb' / 'adb.exe')
SERIAL = 'localhost:16512'
OUTPUT_DIR = PROJECT / 'cache' / 'diagnosis'
OUTPUT_DIR.mkdir(exist_ok=True)

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

def detect_golden(img):
    if img is None:
        return 0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower = np.array([15, 80, 150])
    upper = np.array([35, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    golden = [c for c in contours if cv2.contourArea(c) > 30]
    return len(golden), golden

def main():
    print("\n" + "="*70)
    print("鎵嬪姩鎴浘璇婃柇")
    print("="*70)
    
    # 纭繚鍦ㄤ笘鐣岄〉闈?    print("\n[鍑嗗] 鎸夎繑鍥為敭鍥炲埌鍩虹鐘舵€?..")
    for i in range(10):
        back()
        time.sleep(0.5)
    time.sleep(1)
    
    # 鎴浘 1锛氬垵濮嬬姸鎬?    print("\n[鎴浘 1] 鍒濆鐘舵€?..")
    img1 = screencap()
    gold1, _ = detect_golden(img1)
    print(f"  閲戣壊鍏冪礌锛歿gold1}")
    cv2.imwrite(str(OUTPUT_DIR / '01_initial.png'), img1)
    
    # 鎴浘 2锛氱偣鍑讳换鍔″浘鏍囧墠
    print("\n[鎴浘 2] 鐐瑰嚮浠诲姟鍥炬爣鍓?..")
    time.sleep(0.5)
    img2 = screencap()
    gold2, golden2 = detect_golden(img2)
    print(f"  閲戣壊鍏冪礌锛歿gold2}")
    cv2.imwrite(str(OUTPUT_DIR / '02_before_tap.png'), img2)
    
    # 鍦ㄦ埅鍥句笂鏍囨敞閲戣壊鍏冪礌浣嶇疆
    img2_annotated = img2.copy()
    for i, cnt in enumerate(golden2):
        M = cv2.moments(cnt)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            cv2.circle(img2_annotated, (cx, cy), 5, (255, 0, 0), -1)
    cv2.imwrite(str(OUTPUT_DIR / '02_before_tap_annotated.png'), img2_annotated)
    
    # 鐐瑰嚮浠诲姟鍥炬爣
    print("\n[鎿嶄綔] 鐐瑰嚮浠诲姟鍥炬爣 (860, 80)...")
    tap(860, 80)
    time.sleep(3)
    
    # 鎴浘 3锛氱偣鍑诲悗
    print("\n[鎴浘 3] 鐐瑰嚮浠诲姟鍥炬爣鍚?..")
    img3 = screencap()
    gold3, golden3 = detect_golden(img3)
    print(f"  閲戣壊鍏冪礌锛歿gold3}")
    cv2.imwrite(str(OUTPUT_DIR / '03_after_tap_860_80.png'), img3)
    
    # 鏍囨敞
    img3_annotated = img3.copy()
    for i, cnt in enumerate(golden3):
        M = cv2.moments(cnt)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            cv2.circle(img3_annotated, (cx, cy), 5, (0, 255, 0), -1)
    cv2.imwrite(str(OUTPUT_DIR / '03_after_tap_860_80_annotated.png'), img3_annotated)
    
    # 鎸夎繑鍥?    print("\n[鎿嶄綔] 鎸夎繑鍥為敭...")
    back()
    time.sleep(1)
    
    # 鎴浘 4锛氳繑鍥炲悗
    print("\n[鎴浘 4] 鎸夎繑鍥炲悗...")
    img4 = screencap()
    gold4, _ = detect_golden(img4)
    print(f"  閲戣壊鍏冪礌锛歿gold4}")
    cv2.imwrite(str(OUTPUT_DIR / '04_after_back.png'), img4)
    
    # 灏濊瘯鐐瑰嚮鍏朵粬浣嶇疆
    print("\n[鎿嶄綔] 鐐瑰嚮鑿滃崟鍥炬爣 (1392, 79)...")
    tap(1392, 79)
    time.sleep(3)
    
    # 鎴浘 5锛氱偣鍑昏彍鍗曞悗
    print("\n[鎴浘 5] 鐐瑰嚮鑿滃崟鍥炬爣鍚?..")
    img5 = screencap()
    gold5, _ = detect_golden(img5)
    print(f"  閲戣壊鍏冪礌锛歿gold5}")
    cv2.imwrite(str(OUTPUT_DIR / '05_after_tap_menu.png'), img5)
    
    print("\n" + "="*70)
    print("鎴浘瀹屾垚")
    print("="*70)
    print(f"\n鎴浘淇濆瓨鍦細{OUTPUT_DIR}")
    print("\n璇锋鏌ヤ互涓嬫埅鍥撅細")
    print("  01_initial.png - 鍒濆鐘舵€?)
    print("  02_before_tap.png - 鐐瑰嚮浠诲姟鍥炬爣鍓?)
    print("  02_before_tap_annotated.png - 鏍囨敞閲戣壊鍏冪礌")
    print("  03_after_tap_860_80.png - 鐐瑰嚮浠诲姟鍥炬爣鍚?)
    print("  03_after_tap_860_80_annotated.png - 鏍囨敞閲戣壊鍏冪礌")
    print("  04_after_back.png - 鎸夎繑鍥炲悗")
    print("  05_after_tap_menu.png - 鐐瑰嚮鑿滃崟鍚?)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[閿欒] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

