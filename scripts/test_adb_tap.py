#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""娴嬭瘯 ADB tap 鐐瑰嚮浠诲姟鍥炬爣"""
import subprocess, time

ADB = r"C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\adb\adb.exe"
DEVICE = "localhost:16512"

def adb_tap(x, y):
    r = subprocess.run([ADB, "-s", DEVICE, "shell", "input", "tap", str(x), str(y)], capture_output=True, timeout=5)
    return r.returncode == 0

def adb_back():
    subprocess.run([ADB, "-s", DEVICE, "shell", "input", "keyevent", "4"], capture_output=True)

# 鍏堟寜杩斿洖鍥炲埌涓栫晫
print("[鍓嶇疆] 鍥炲埌涓栫晫...")
for _ in range(6):
    adb_back()
    time.sleep(0.3)
time.sleep(2)

# 娴嬭瘯澶氫釜鍧愭爣
# MaaFw 鎵弿纭 y=40 鏈夋晥 (MaaFw 1280x720 妯睆)
# 鍋囪 ADB 涔熸槸 1280x720 妯睆绌洪棿
test_coords = [
    (570, 40),   # MaaFw 鏈€浣?    (570, 28),   # MaaFw 鏈夋晥
    (855, 60),   # 鍘熼厤缃?(鍋囪 1080x1920)
    (855, 40),   # 娣峰悎
    (40, 570),   # 鏃嬭浆锛?]

print("\n[娴嬭瘯] ADB tap 鐐瑰嚮")
for x, y in test_coords:
    print(f"\n鐐瑰嚮 ({x}, {y})...")
    adb_tap(x, y)
    time.sleep(3)
    
    # 鎴浘妫€鏌?    r = subprocess.run([ADB, "-s", DEVICE, "exec-out", "screencap", "-p"], capture_output=True, timeout=10)
    if r.returncode == 0 and len(r.stdout) > 1000:
        print(f"  鎴浘鎴愬姛锛歿len(r.stdout)} bytes")
    else:
        print(f"  鎴浘澶辫触")
    
    # 鎸夎繑鍥?    adb_back()
    time.sleep(1)

print("\n[瀹屾垚]")

