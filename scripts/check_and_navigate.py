#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佸墠缃鏌ワ細楠岃瘉椤甸潰鐘舵€佸苟瀵艰埅鍒颁笘鐣?鐢ㄦ硶锛歱ython scripts/check_and_navigate.py
"""
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

def get_brightness(img):
    if img is None:
        return 0
    img_rot = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    img_resized = cv2.resize(img_rot, (1280, 720))
    return np.mean(cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY))

def classify_page(gold, brightness):
    """鍩轰簬閲戣壊鍏冪礌鍜屼寒搴﹀垽鏂〉闈㈢被鍨?""
    if brightness < 30:
        return "black_screen"
    elif gold >= 22:
        return "quest_panel"
    elif gold >= 18:
        return "world"
    elif gold >= 15:
        return "world_low_gold"  # 涓栫晫椤甸潰浣嗛噾鑹茶緝灏?    elif gold >= 12:
        return "exit_dialog"
    elif gold >= 8:
        return "menu"
    elif brightness > 150:
        return "loading"
    else:
        return "other"

def navigate_to_world(max_attempts=3):
    """灏濊瘯瀵艰埅鍒颁笘鐣岄〉闈?""
    for attempt in range(max_attempts):
        print(f"\n[灏濊瘯 {attempt+1}/{max_attempts}] 妫€鏌ュ綋鍓嶉〉闈?..")
        
        img = adb_screencap()
        if img is None:
            print("[ERROR] 鎴浘澶辫触")
            continue
        
        gold = count_gold(img)
        brightness = get_brightness(img)
        page_type = classify_page(gold, brightness)
        
        print(f"  閲戣壊鍏冪礌锛歿gold}, 浜害锛歿brightness:.1f}, 绫诲瀷锛歿page_type}")
        
        if page_type == "world" or page_type == "world_low_gold":
            print(f"\n[鎴愬姛] 宸茬‘璁ゅ湪涓栫晫椤甸潰")
            return True
        
        elif page_type == "black_screen":
            print("[鎿嶄綔] 榛戝睆锛岀偣鍑讳腑澶?)
            adb_tap(540, 960)
            time.sleep(3)
        
        elif page_type == "exit_dialog":
            print("[鎿嶄綔] 閫€鍑哄璇濇锛岀偣鍑诲彇娑?)
            adb_tap(600, 750)
            time.sleep(2)
        
        elif page_type == "quest_panel":
            print("[鎿嶄綔] 浠诲姟闈㈡澘锛屾寜杩斿洖")
            adb_back()
            time.sleep(2)
        
        elif page_type == "menu":
            print("[鎿嶄綔] 鑿滃崟椤甸潰锛屾寜杩斿洖")
            adb_back()
            time.sleep(1)
        
        elif page_type == "loading":
            print("[鎿嶄綔] 鍔犺浇涓紝绛夊緟 15 绉?)
            time.sleep(15)
        
        else:
            print("[鎿嶄綔] 鏈煡椤甸潰锛屾寜杩斿洖骞剁偣鍑讳腑澶?)
            adb_back()
            time.sleep(0.5)
            adb_tap(540, 960)
            time.sleep(3)
    
    print(f"\n[澶辫触] {max_attempts} 娆″皾璇曞悗浠嶆湭杩涘叆涓栫晫椤甸潰")
    return False

def main():
    print("="*60)
    print("鏍囧噯娴佸墠缃鏌ワ細瀵艰埅鍒颁笘鐣岄〉闈?)
    print("="*60)
    
    # 鍏堟寜鍑犳杩斿洖纭繚涓嶅湪娣卞眰鑿滃崟
    print("\n[鍓嶇疆] 鎸夎繑鍥為敭閫€鍑烘繁灞傝彍鍗?..")
    for i in range(5):
        adb_back()
        time.sleep(0.3)
    time.sleep(1)
    
    # 瀵艰埅鍒颁笘鐣?    success = navigate_to_world(max_attempts=5)
    
    if success:
        # 淇濆瓨涓栫晫椤甸潰鎴浘
        img = adb_screencap()
        if img is not None:
            img_rot = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            cv2.imwrite(str(PROJECT_ROOT / "data" / "analysis" / "world_page_reference.png"), img_rot)
            print(f"\n[淇濆瓨] 涓栫晫椤甸潰鍙傝€冩埅鍥惧凡淇濆瓨")
        
        print(f"\n{'='*60}")
        print("[灏辩华] 鍙互杩愯鏍囧噯娴侊細python scripts/standard_flow_engine.py --flow daily_quest")
        print(f"{'='*60}")
        return 0
    else:
        print(f"\n{'='*60}")
        print("[鎻愮ず] 璇锋墜鍔ㄨ繘鍏ユ父鎴忎笘鐣岄〉闈㈠悗閲嶆柊杩愯")
        print(f"{'='*60}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

