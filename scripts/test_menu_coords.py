#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""娴嬭瘯 world鈫抦enu 杞崲鍜岃彍鍗曞唴鍧愭爣"""
import subprocess, time, cv2, numpy as np, sys
from pathlib import Path
from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path; ensure_path()
from core.service.page_analyzer import HighPrecisionPageAnalyzer

ADB = Path(__file__).resolve().parent.parent / '3rd-part' / 'adb' / 'adb.exe'
a = HighPrecisionPageAnalyzer()

def sc():
    r = subprocess.run([str(ADB),'-s','localhost:16512','exec-out','screencap','-p'],capture_output=True,timeout=10)
    return cv2.imdecode(np.frombuffer(r.stdout,np.uint8),cv2.IMREAD_COLOR)
def tap(x,y):
    subprocess.run([str(ADB),'-s','localhost:16512','shell','input','tap',str(x),str(y)],capture_output=True,timeout=5)
def key(k):
    subprocess.run([str(ADB),'-s','localhost:16512','shell','input','keyevent',str(k)],capture_output=True,timeout=5)

# 杩斿洖world
print('杩斿洖world...')
for _ in range(5):
    key(4); time.sleep(0.8)
img = sc()
r = a.analyze(img)
print(f'褰撳墠: {r["page_type"]} conf={r["confidence"]:.2f}')

# 娴嬭瘯 menu_icon
print('\n娴嬭瘯1: tap menu_icon (1392,79)...')
tap(1392, 79); time.sleep(3)
img = sc()
r = a.analyze(img)
print(f'鑿滃崟: {r["page_type"]} conf={r["confidence"]:.2f}')
print(f'  bottom_nav={r["features"]["bottom_nav_brightness"]:.0f} dialog_gold={r["features"]["dialog_gold_pixels"]:.0f}')

# 娴嬭瘯 base_entry_menu (960,400)
print('\n娴嬭瘯2: tap base_entry_menu (960,400)...')
tap(960, 400); time.sleep(3)
img = sc()
r = a.analyze(img)
print(f'鍩哄缓鍚? {r["page_type"]} conf={r["confidence"]:.2f} left_bar={r["features"]["left_bar_brightness"]:.0f}')

# 杩斿洖
key(4); time.sleep(1)

# 閲嶆柊寮€鑿滃崟
print('\n娴嬭瘯3: 閲嶆柊寮€鑿滃崟...')
key(4); time.sleep(0.5)
tap(1392, 79); time.sleep(3)

# 娴嬭瘯 char_entry_menu (1200,330)
print('娴嬭瘯4: tap char_entry_menu (1200,330)...')
tap(1200, 330); time.sleep(3)
img = sc()
r = a.analyze(img)
print(f'瑙掕壊鍚? {r["page_type"]} conf={r["confidence"]:.2f} left_bar={r["features"]["left_bar_brightness"]:.0f}')

# 杩斿洖world
for _ in range(5):
    key(4); time.sleep(0.5)

print('\n[瀹屾垚]')

