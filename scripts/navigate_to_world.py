#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""鍒嗘瀽褰撳墠椤甸潰骞跺鑸埌涓栫晫"""
import subprocess, time, cv2, numpy as np, sys
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

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

def get_brightness(img):
    """鑾峰彇鐢婚潰骞冲潎浜害"""
    if img is None:
        return 0
    img_rot = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    img_resized = cv2.resize(img_rot, (1280, 720))
    return np.mean(cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY))

def check_text_ocr(img, keywords):
    """绠€鍗?OCR 妫€鏌ュ叧閿瘝锛堜娇鐢ㄦā鏉垮尮閰嶄唬鏇匡級"""
    # 杩欓噷绠€鍖栧鐞嗭紝浠呰繑鍥?None 琛ㄧず闇€瑕?VLM 鍒嗘瀽
    return None

# 鎴浘鍒嗘瀽
print("[鍒嗘瀽] 鑾峰彇褰撳墠鐢婚潰...")
img = adb_screencap()
if img is None:
    print("[ERROR] 鎴浘澶辫触")
    sys.exit(1)

gold = count_gold(img)
brightness = get_brightness(img)

print(f"\n[鐢婚潰淇℃伅]")
print(f"  鍒嗚鲸鐜囷細{img.shape[1]}x{img.shape[0]} (绔栧睆)")
print(f"  閲戣壊鍏冪礌锛歿gold}")
print(f"  骞冲潎浜害锛歿brightness:.1f}")

# 椤甸潰鍒ゆ柇
if brightness < 30:
    page_type = "black_screen (榛戝睆)"
elif gold >= 20:
    page_type = "quest_panel (浠诲姟闈㈡澘)"
elif gold >= 18:
    page_type = "world (涓栫晫)"
elif gold >= 12:
    page_type = "exit_dialog (閫€鍑哄璇濇)"
elif gold >= 8:
    page_type = "menu/menu_dialog (鑿滃崟/瀵硅瘽妗?"
else:
    page_type = "loading/other (鍔犺浇/鍏朵粬)"

print(f"\n[椤甸潰绫诲瀷]: {page_type}")

# 瀵艰埅鍒颁笘鐣?print(f"\n[瀵艰埅] 灏濊瘯瀵艰埅鍒颁笘鐣岄〉闈?..")

if "black_screen" in page_type:
    print("[鎿嶄綔] 榛戝睆锛岀偣鍑讳腑澶敜閱?)
    adb_tap(540, 960)
    time.sleep(3)
    
elif "exit_dialog" in page_type or "menu_dialog" in page_type:
    print("[鎿嶄綔] 妫€娴嬪埌瀵硅瘽妗嗭紝鐐瑰嚮鍙栨秷鎸夐挳")
    # 鍙栨秷鎸夐挳閫氬父鍦ㄥ簳閮?    adb_tap(600, 750)
    time.sleep(2)
    
    # 濡傛灉杩樻湁瀵硅瘽妗嗭紝鎸夎繑鍥?    img2 = adb_screencap()
    gold2 = count_gold(img2)
    if gold2 >= 12:
        print("[鎿嶄綔] 浠嶆湁瀵硅瘽妗嗭紝鎸夎繑鍥為敭")
        adb_back()
        time.sleep(2)

elif "quest_panel" in page_type:
    print("[鎿嶄綔] 宸插湪浠诲姟闈㈡澘锛屾寜杩斿洖鍒颁笘鐣?)
    adb_back()
    time.sleep(2)

elif "loading" in page_type:
    print("[鎿嶄綔] 鍔犺浇涓紝绛夊緟 30 绉?)
    time.sleep(30)

else:
    # 鏈煡椤甸潰锛屽皾璇曢€氱敤瀵艰埅
    print("[鎿嶄綔] 鏈煡椤甸潰锛屽皾璇曟寜杩斿洖閿鑸?)
    for i in range(5):
        adb_back()
        time.sleep(0.5)
    
    # 妫€鏌ユ槸鍚﹂渶瑕佺偣鍑讳腑澶?    img2 = adb_screencap()
    gold2 = count_gold(img2)
    brightness2 = get_brightness(img2)
    
    if brightness2 < 50 or gold2 < 10:
        print("[鎿嶄綔] 鐐瑰嚮涓ぎ杩涘叆")
        adb_tap(540, 960)
        time.sleep(5)

# 楠岃瘉缁撴灉
print(f"\n[楠岃瘉] 妫€鏌ュ鑸粨鏋?..")
img_final = adb_screencap()
gold_final = count_gold(img_final)
brightness_final = get_brightness(img_final)

print(f"  閲戣壊鍏冪礌锛歿gold_final}")
print(f"  骞冲潎浜害锛歿brightness_final:.1f}")

if gold_final >= 18 and gold_final <= 22:
    print(f"\n[缁撴灉] 鉁?鎴愬姛杩涘叆涓栫晫椤甸潰")
elif gold_final >= 20:
    print(f"\n[缁撴灉] 鈿狅笍  鍙兘鍦ㄤ换鍔￠潰鏉块〉闈?)
elif gold_final >= 12:
    print(f"\n[缁撴灉] 鈿狅笍  鍙兘鏈夐€€鍑哄璇濇")
else:
    print(f"\n[缁撴灉] 鉂?鏈繘鍏ヤ笘鐣岄〉闈紝璇锋墜鍔ㄦ搷浣?)

# 淇濆瓨鎴浘渚涘垎鏋?img_final_rot = cv2.rotate(img_final, cv2.ROTATE_90_COUNTERCLOCKWISE)
cv2.imwrite(str(PROJECT_ROOT / "data" / "analysis" / "current_page.png"), img_final_rot)
print(f"\n[淇濆瓨] 鎴浘宸蹭繚瀛樺埌 data/analysis/current_page.png")

