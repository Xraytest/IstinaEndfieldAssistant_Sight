#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""鎵弿浠诲姟鍥炬爣浣嶇疆 - 浣跨敤 ADB tap + 鍍忕礌宸紓娉?""
import subprocess, time, cv2, numpy as np, sys

PROJECT_ROOT = r'C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight'
ADB = f"{PROJECT_ROOT}\\3rd-part\\adb\\adb.exe"
DEVICE = "localhost:16512"

def adb_tap(x, y):
    subprocess.run([ADB, "-s", DEVICE, "shell", "input", "tap", str(int(x)), str(int(y))], 
                   capture_output=True, timeout=5)

def adb_back():
    subprocess.run([ADB, "-s", DEVICE, "shell", "input", "keyevent", "4"], capture_output=True)

def adb_screencap():
    r = subprocess.run([ADB, "-s", DEVICE, "exec-out", "screencap", "-p"], 
                       capture_output=True, timeout=10)
    if r.returncode == 0 and len(r.stdout) > 1000:
        return cv2.imdecode(np.frombuffer(r.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
    return None

# 鍥炲埌涓栫晫
print("[鍓嶇疆] 鍥炲埌涓栫晫...")
for _ in range(8):
    adb_back()
    time.sleep(0.3)
time.sleep(2)

# 鍩哄噯鎴浘
img_base = adb_screencap()
if img_base is None:
    print("[ERROR] 鍩哄噯鎴浘澶辫触")
    sys.exit(1)
print(f"[鍩哄噯] 鍒嗚鲸鐜囷細{img_base.shape[1]}x{img_base.shape[0]}")

# 鏃嬭浆鍩哄噯鍥惧埌妯睆鍒嗘瀽
img_base_rot = cv2.rotate(img_base, cv2.ROTATE_90_COUNTERCLOCKWISE)
img_base_resized = cv2.resize(img_base_rot, (1280, 720))

# 鎵弿 x 鍧愭爣鑼冨洿 (浠诲姟鍥炬爣搴旇鍦ㄩ《閮ㄥ鑸爮)
# 鍩轰簬涔嬪墠鐨勬祴璇曪細(855, 60) 鑳芥墦寮€闈㈡澘
# 鎵弿 x: 800-900, y: 40-80
print("\n[鎵弿] 浠诲姟鍥炬爣浣嶇疆 (ADB tap 鍧愭爣)")
print("="*70)

results = []
for x in range(800, 920, 20):
    for y in range(40, 90, 10):
        adb_tap(x, y)
        time.sleep(2.5)
        
        img = adb_screencap()
        if img is None:
            adb_back()
            time.sleep(1)
            continue
        
        # 鏃嬭浆鍒版í灞忔瘮杈?        img_rot = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        img_resized = cv2.resize(img_rot, (1280, 720))
        
        # 鍍忕礌宸紓
        diff = cv2.absdiff(img_base_resized, img_resized)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
        changed = cv2.countNonZero(thresh)
        rate = changed / (1280 * 720) * 100
        
        results.append({'x': x, 'y': y, 'changed': changed, 'rate': rate})
        
        status = "鉁? if rate > 40 else ("鈿狅笍" if rate > 15 else " ")
        print(f"{status} ({x:4d}, {y:3d}): {changed:8d} px ({rate:5.1f}%)")
        
        adb_back()
        time.sleep(0.5)

print("\n" + "="*70)
if results:
    best = max(results, key=lambda r: r['rate'])
    print(f"[鏈€浣砞 ({best['x']:4d}, {best['y']:3d}): {best['changed']:8d} px ({best['rate']:5.1f}%)")
    if best['rate'] > 40:
        print("[缁撹] 鉁?鎵惧埌浠诲姟鍥炬爣浣嶇疆")
    else:
        print("[缁撹] 鉂?鏈壘鍒版湁鏁堜綅缃紝鍙兘闇€瑕佹墿澶ф壂鎻忚寖鍥?)

