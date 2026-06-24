#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""閲嶆柊鎵弿浠诲姟鍥炬爣 - 鍏堢‘璁ら〉闈㈢姸鎬?""
import subprocess, time, cv2, numpy as np, sys
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight')
ADB_PATH = f"{PROJECT_ROOT}\\3rd-part\\adb\\adb.exe"
DEVICE = "localhost:16512"

def adb_cmd(args):
    r = subprocess.run([ADB_PATH, "-s", DEVICE] + args, capture_output=True, timeout=10)
    return r

def adb_tap(x, y):
    adb_cmd(["shell", "input", "tap", str(int(x)), str(int(y))])

def adb_back():
    adb_cmd(["shell", "input", "keyevent", "4"])

def adb_screencap():
    r = adb_cmd(["exec-out", "screencap", "-p"])
    if r.returncode == 0 and len(r.stdout) > 1000:
        return cv2.imdecode(np.frombuffer(r.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
    return None

def count_gold(img):
    if img is None:
        return 0
    img_rot = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    img_resized = cv2.resize(img_rot, (1280, 720))
    hsv = cv2.cvtColor(img_resized, cv2.COLOR_BGR2HSV)
    lower_gold = np.array([25, 100, 100])
    upper_gold = np.array([35, 255, 255])
    mask = cv2.inRange(hsv, lower_gold, upper_gold)
    kernel = np.ones((3,3),np.uint8)
    dilated_mask = cv2.dilate(mask, kernel, iterations=2)
    eroded_mask = cv2.erode(dilated_mask, kernel, iterations=1)
    contours, _ = cv2.findContours(eroded_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return len([c for c in contours if cv2.contourArea(c) > 50])

def classify_page(gold_count):
    if gold_count >= 20:
        return "quest_panel (浠诲姟闈㈡澘)"
    elif gold_count >= 18:
        return "world (涓栫晫)"
    elif gold_count >= 12:
        return "exit_dialog (閫€鍑哄璇濇)"
    else:
        return "other (鍏朵粬椤甸潰)"

# 鍥炲埌涓荤晫闈?print("[鍓嶇疆] 杩斿洖閿?x10 鍥炲埌涓荤晫闈?..")
for i in range(10):
    adb_back()
    time.sleep(0.3)
time.sleep(2)

# 妫€鏌ラ〉闈?img = adb_screencap()
if img is None:
    print("[ERROR] 鎴浘澶辫触")
    sys.exit(1)

gold = count_gold(img)
page = classify_page(gold)
print(f"\n[褰撳墠椤甸潰] 鍒嗚鲸鐜囷細{img.shape[1]}x{img.shape[0]}")
print(f"[褰撳墠椤甸潰] 閲戣壊鍏冪礌锛歿gold}")
print(f"[褰撳墠椤甸潰] 绫诲瀷锛歿page}")

# 濡傛灉涓嶅湪涓栫晫椤甸潰锛屽皾璇曠偣鍑诲睆骞曚腑澶繘鍏?if gold < 15:
    print("\n[鎻愮ず] 涓嶅湪涓栫晫椤甸潰锛屽皾璇曠偣鍑讳腑澶繘鍏?..")
    # 妯睆涓ぎ绾?(640, 360)锛屽搴旂珫灞忓潗鏍囬渶瑕佽浆鎹?    # 绔栧睆 1920x1080锛屾í灞忓唴瀹瑰湪涓ぎ鍖哄煙
    adb_tap(540, 960)  # 绔栧睆涓ぎ鍋忎笅
    time.sleep(3)
    
    img2 = adb_screencap()
    gold2 = count_gold(img2)
    page2 = classify_page(gold2)
    print(f"[鐐瑰嚮鍚嶿 閲戣壊鍏冪礌锛歿gold2}, 绫诲瀷锛歿page2}")

# 鍐嶆妫€鏌?img = adb_screencap()
gold = count_gold(img)
page = classify_page(gold)
print(f"\n[鏈€缁堥〉闈 閲戣壊鍏冪礌锛歿gold}, 绫诲瀷锛歿page}")

# 鎵弿瀵艰埅鏍忓尯鍩?if gold >= 15:
    print("\n" + "="*70)
    print("[鎵弿] 瀵艰埅鏍忓浘鏍?(x: 700-1000, y: 30-100)")
    print("="*70)
    
    img_base = adb_screencap()
    img_base_rot = cv2.rotate(img_base, cv2.ROTATE_90_COUNTERCLOCKWISE)
    img_base_resized = cv2.resize(img_base_rot, (1280, 720))
    
    best_result = None
    best_rate = 0
    
    for x in range(700, 1020, 30):
        for y in range(30, 100, 15):
            adb_tap(x, y)
            time.sleep(2.5)
            
            img = adb_screencap()
            if img is not None:
                img_rot = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
                img_resized = cv2.resize(img_rot, (1280, 720))
                
                diff = cv2.absdiff(img_base_resized, img_resized)
                gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
                _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
                changed = cv2.countNonZero(thresh)
                rate = changed / (1280 * 720) * 100
                
                if rate > best_rate:
                    best_rate = rate
                    best_result = (x, y, rate)
                
                status = "鉁? if rate > 40 else ("鈿狅笍" if rate > 20 else " ")
                if rate > 20:
                    print(f"{status} ({x:4d}, {y:3d}): {rate:5.1f}%")
            
            adb_back()
            time.sleep(0.5)
    
    print("\n" + "="*70)
    if best_result and best_rate > 40:
        print(f"[鏈€浣砞 ({best_result[0]}, {best_result[1]}): {best_rate:.1f}%")
        print("[缁撹] 鉁?鎵惧埌鏈夋晥鍧愭爣")
    else:
        print(f"[鏈€浣砞 ({best_result[0] if best_result else 'N/A'}, {best_result[1] if best_result else 'N/A'}): {best_rate:.1f}%")
        print("[缁撹] 鉂?鏈壘鍒版湁鏁堝潗鏍?)
else:
    print("\n[璺宠繃] 涓嶅湪涓栫晫椤甸潰锛屾棤娉曟壂鎻忎换鍔″浘鏍?)
    print("[鎻愮ず] 璇峰厛鎵嬪姩杩涘叆娓告垙涓栫晫椤甸潰鍚庨噸鏂拌繍琛?)

