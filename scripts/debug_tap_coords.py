#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""璋冭瘯 tap 鍧愭爣瀵规瘮锛氭壂鎻忚剼鏈?vs 鏍囧噯娴佸紩鎿?""
import subprocess, time, cv2, numpy as np, sys, os
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

ADB_PATH = f"{PROJECT_ROOT}\\3rd-part\\adb\\adb.exe"
DEVICE = "localhost:16512"

# 娴嬭瘯鍧愭爣锛氭壂鎻忚剼鏈獙璇佹湁鏁堢殑鍧愭爣
TEST_X, TEST_Y = 860, 80

def adb_screencap():
    """鎴浘"""
    r = subprocess.run([ADB_PATH, "-s", DEVICE, "exec-out", "screencap", "-p"],
                       capture_output=True, timeout=10)
    if r.returncode == 0 and len(r.stdout) > 1000:
        return cv2.imdecode(np.frombuffer(r.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
    return None

def count_gold_elements(img):
    """璁＄畻閲戣壊鍏冪礌鏁伴噺锛堥〉闈㈢壒寰侊級"""
    if img is None:
        return 0
    # 鏃嬭浆鍒版í灞?    img_rot = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    img_resized = cv2.resize(img_rot, (1280, 720))
    
    hsv = cv2.cvtColor(img_resized, cv2.COLOR_BGR2HSV)
    lower_gold = np.array([25, 100, 100])
    upper_gold = np.array([35, 255, 255])
    mask = cv2.inRange(hsv, lower_gold, upper_gold)
    
    kernel = np.ones((3,3),np.uint8)
    dilated_mask = cv2.dilate(mask, kernel, iterations=2)
    eroded_mask = cv2.erode(dilated_mask, kernel, iterations=1)
    
    contours, _ = cv2.findContours(eroded_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_contours = [c for c in contours if cv2.contourArea(c) > 50]
    return len(valid_contours)

def adb_back():
    """鎸夎繑鍥為敭"""
    subprocess.run([ADB_PATH, "-s", DEVICE, "shell", "input", "keyevent", "4"], 
                   capture_output=True, timeout=5)

def test_scan_script_tap():
    """娴嬭瘯鎵弿鑴氭湰鏂瑰紡鐨?tap"""
    print("\n[娴嬭瘯 1] 鎵弿鑴氭湰鏂瑰紡锛歴ubprocess.run([... 'input', 'tap', '860', '80'])")
    result = subprocess.run(
        [ADB_PATH, "-s", DEVICE, "shell", "input", "tap", "860", "80"],
        capture_output=True, timeout=5
    )
    return result.returncode == 0

def test_adb_utils_tap():
    """娴嬭瘯 adb_utils 鏂瑰紡鐨?tap"""
    print("\n[娴嬭瘯 2] adb_utils 鏂瑰紡锛欰DB().tap(860, 80)")
    from core.capability.adb_utils import ADB
    adb = ADB()
    return adb.tap(860, 80)

def test_adb_utils_tap_direct():
    """娴嬭瘯 adb_utils 搴曞眰鍑芥暟鐨?tap"""
    print("\n[娴嬭瘯 3] adb_utils 搴曞眰锛歛db_tap(860, 80)")
    from core.capability.adb_utils import adb_tap
    return adb_tap(860, 80)

def main():
    # 鍥炲埌涓栫晫
    print("[鍓嶇疆] 鍥炲埌涓栫晫...")
    for i in range(8):
        adb_back()
        time.sleep(0.3)
    time.sleep(2)
    
    # 鍩哄噯鎴浘
    img_base = adb_screencap()
    if img_base is None:
        print("[ERROR] 鍩哄噯鎴浘澶辫触")
        sys.exit(1)
    
    gold_base = count_gold_elements(img_base)
    print(f"[鍩哄噯] 鍒嗚鲸鐜囷細{img_base.shape[1]}x{img_base.shape[0]}")
    print(f"[鍩哄噯] 閲戣壊鍏冪礌锛歿gold_base}")
    
    if gold_base < 15:
        print("[璀﹀憡] 閲戣壊鍏冪礌鏁伴噺杈冨皯锛屽彲鑳戒笉鍦ㄤ笘鐣岄〉闈?)
    elif gold_base > 20:
        print("[鎻愮ず] 閲戣壊鍏冪礌鏁伴噺杈冨锛屽彲鑳藉湪浠诲姟闈㈡澘椤甸潰")
    else:
        print("[鎻愮ず] 閲戣壊鍏冪礌鏁伴噺姝ｅ父锛屽簲鍦ㄤ笘鐣岄〉闈?)
    
    # 娴嬭瘯涓夌 tap 鏂瑰紡
    tests = [
        ("鎵弿鑴氭湰鏂瑰紡", test_scan_script_tap),
        ("ADB().tap()", test_adb_utils_tap),
        ("adb_tap()", test_adb_utils_tap_direct),
    ]
    
    for name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"[娴嬭瘯] {name}")
        print(f"{'='*60}")
        
        # 纭繚鍥炲埌涓栫晫
        print("[鍑嗗] 鍥炲埌涓栫晫...")
        for _ in range(5):
            adb_back()
            time.sleep(0.3)
        time.sleep(1)
        
        img_before = adb_screencap()
        gold_before = count_gold_elements(img_before)
        print(f"[鐐瑰嚮鍓峕 閲戣壊鍏冪礌锛歿gold_before}")
        
        # 鎵ц tap
        success = test_func()
        print(f"[鐐瑰嚮] input tap 860 80 {'鎴愬姛' if success else '澶辫触'}")
        
        # 绛夊緟骞舵埅鍥?        time.sleep(3)
        img_after = adb_screencap()
        gold_after = count_gold_elements(img_after)
        print(f"[鐐瑰嚮鍚嶿 閲戣壊鍏冪礌锛歿gold_after}")
        
        # 鍒ゆ柇缁撴灉
        if gold_after > gold_before + 5:
            print(f"[缁撴灉] 鉁?闈㈡澘宸叉墦寮€ (閲戣壊 +{gold_after - gold_before})")
        elif gold_after < gold_before - 5:
            print(f"[缁撴灉] 鉂?閲戣壊娑堝け (閲戣壊 -{gold_before - gold_after})")
        else:
            print(f"[缁撴灉] 鈿狅笍  鏃犳槑鏄惧彉鍖?(閲戣壊 {gold_after - gold_before:+d})")
        
        # 杩斿洖
        print("[鎭㈠] 鎸夎繑鍥為敭...")
        for _ in range(3):
            adb_back()
            time.sleep(0.3)
        time.sleep(1)

if __name__ == "__main__":
    main()

