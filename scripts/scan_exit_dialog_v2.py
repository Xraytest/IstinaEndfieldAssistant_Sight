#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""鎵弿閫€鍑哄璇濇鐨勫彇娑堟寜閽綅缃?- 浼樺寲鐗?""
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

# 鍏堝洖鍒颁笘鐣?print("[鍓嶇疆] 鍥炲埌涓栫晫...")
for _ in range(8):
    adb_back()
    time.sleep(0.3)
time.sleep(2)

# 瑙﹀彂閫€鍑哄璇濇锛氭寜 Home 閿?print("[瑙﹀彂] 鎸?Home 閿Е鍙戦€€鍑哄璇濇...")
subprocess.run([ADB, "-s", DEVICE, "shell", "input", "keyevent", "3"], capture_output=True)
time.sleep(3)

# 鍩哄噯鎴浘锛堝簲璇ユ湁閫€鍑哄璇濇锛?img_base = adb_screencap()
if img_base is None:
    print("[ERROR] 鎴浘澶辫触")
    sys.exit(1)
print(f"[鍩哄噯] 鍒嗚鲸鐜囷細{img_base.shape[1]}x{img_base.shape[0]}")

# 閫€鍑哄璇濇閫氬父鍦ㄤ腑澶紝鍙栨秷/纭鎸夐挳鍦ㄥ簳閮?# 缂╁皬鎵弿鑼冨洿锛氬簳閮ㄥ尯鍩?y: 600-900, x: 400-1000
print("\n[鎵弿] 閫€鍑哄璇濇鎸夐挳 (搴曢儴鍖哄煙)")
print("="*70)

results = []
# 鎵弿搴曢儴鎸夐挳鍖哄煙
for x in range(400, 1000, 80):
    for y in range(600, 900, 60):
        adb_tap(x, y)
        time.sleep(1.5)
        
        img = adb_screencap()
        if img is None:
            continue
        
        # 鍍忕礌宸紓
        diff = cv2.absdiff(img_base, img)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
        changed = cv2.countNonZero(thresh)
        rate = changed / (img.shape[0] * img.shape[1]) * 100
        
        results.append({'x': x, 'y': y, 'changed': changed, 'rate': rate})
        
        # 瀵硅瘽妗嗗叧闂細鏈夎緝澶у彉鍖?(>15%)
        if rate > 15:
            print(f"鉁?({x:4d}, {y:4d}): {changed:8d} px ({rate:5.1f}%)")
        elif rate > 5:
            print(f"鈿狅笍 ({x:4d}, {y:4d}): {changed:8d} px ({rate:5.1f}%)")

print("\n" + "="*70)
if results:
    best = max(results, key=lambda r: r['rate'])
    print(f"[鏈€浣砞 ({best['x']:4d}, {best['y']:4d}): {best['changed']:8d} px ({best['rate']:5.1f}%)")
    if best['rate'] > 15:
        print("[缁撹] 鉁?鎵惧埌鎸夐挳浣嶇疆")
    else:
        print("[缁撹] 鉂?鏈壘鍒帮紝瀵硅瘽妗嗗彲鑳芥湭鏄剧ず")

# 鎭㈠锛氬娆℃寜杩斿洖
print("\n[鎭㈠] 鎸夎繑鍥炲叧闂?..")
for _ in range(3):
    adb_back()
    time.sleep(0.5)

