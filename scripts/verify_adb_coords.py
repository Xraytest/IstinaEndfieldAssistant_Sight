#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""楠岃瘉 ADB tap 鍧愭爣 - 鐩存帴娴嬭瘯 (860, 80)"""
import subprocess, time, cv2, numpy as np, sys

PROJECT_ROOT = r'C:\Users\xray\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant'
ADB = f"{PROJECT_ROOT}\\3rd-part\\adb\\adb.exe"
DEVICE = "localhost:16512"

def adb_tap(x, y):
    r = subprocess.run([ADB, "-s", DEVICE, "shell", "input", "tap", str(int(x)), str(int(y))], 
                       capture_output=True, timeout=5)
    print(f"  ADB tap ({x}, {y}): {r.returncode}")
    return r.returncode == 0

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

# 娴嬭瘯鍧愭爣
test_coords = [
    ("閰嶇疆鏂?, 860, 80),
    ("閰嶇疆鏃?, 820, 40),
    ("鎵弿鏈€浣?, 860, 80),
    ("涓ぎ", 960, 540),
]

print("\n[娴嬭瘯] ADB tap 鍧愭爣楠岃瘉")
print("="*70)

for name, x, y in test_coords:
    print(f"\n{name}: ({x}, {y})")
    adb_tap(x, y)
    time.sleep(3)
    
    img = adb_screencap()
    if img is None:
        print(f"  鎴浘澶辫触")
        adb_back()
        time.sleep(1)
        continue
    
    # 鍍忕礌宸紓
    diff = cv2.absdiff(img_base, img)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    changed = cv2.countNonZero(thresh)
    rate = changed / (thresh.shape[0] * thresh.shape[1]) * 100
    
    status = "鉁? if rate > 30 else ("鈿狅笍" if rate > 10 else "鉂?)
    print(f"  {status} 鍙樺寲锛歿changed:8d} px ({rate:5.1f}%)")
    
    # 鎸夎繑鍥?    adb_back()
    time.sleep(1)

print("\n[缁撹] >30% 琛ㄧず闈㈡澘鎵撳紑锛?10% 琛ㄧず鏃犲彉鍖?)

