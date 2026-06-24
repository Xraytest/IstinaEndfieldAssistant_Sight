#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""楠岃瘉鑿滃崟鍏ュ彛鍧愭爣鍜岃彍鍗曞唴鍏冪礌浣嶇疆"""
import subprocess, time, cv2, numpy as np, sys, json
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

from core.service.page_analyzer import HighPrecisionPageAnalyzer

PROJECT = Path(__file__).resolve().parent.parent
ADB = PROJECT / '3rd-part' / 'adb' / 'adb.exe'
SER = 'localhost:16512'

def sc():
    r = subprocess.run([str(ADB),'-s',SER,'exec-out','screencap','-p'],capture_output=True,timeout=10)
    return cv2.imdecode(np.frombuffer(r.stdout,np.uint8),cv2.IMREAD_COLOR)

def tap(x,y):
    subprocess.run([str(ADB),'-s',SER,'shell','input','tap',str(int(x)),str(int(y))],capture_output=True,timeout=5)

def key(k):
    subprocess.run([str(ADB),'-s',SER,'shell','input','keyevent',str(k)],capture_output=True,timeout=5)

CFG = json.load(open(PROJECT / "config" / "standard_flows" / "flows_config.json", 'r', encoding='utf-8'))
NAV = CFG["variables"]["nav_coords"]
a = HighPrecisionPageAnalyzer()

# 纭繚鍦╳orld
print('纭繚鍦╳orld...')
for _ in range(5):
    key(4); time.sleep(0.5)
img = sc()
r = a.analyze(img)
print(f'  褰撳墠: {r["page_type"]} left_bar={r["features"]["left_bar_brightness"]:.0f} green={r["features"]["green_pixels_top_right"]:.0f}')

# 娴嬭瘯 menu_icon
print(f'\n娴嬭瘯1: menu_icon ({NAV["menu_icon"]}) 鎵撳紑绯荤粺鑿滃崟...')
tap(*NAV["menu_icon"])
time.sleep(3)
img = sc()
r = a.analyze(img)
print(f'  鑿滃崟鍚? {r["page_type"]} conf={r["confidence"]:.2f}')
features = r["features"]
print(f'  left_bar={features["left_bar_brightness"]:.0f} green={features["green_pixels_top_right"]:.0f}')
print(f'  full_bright={features["full_brightness"]:.0f} center_edge={features["center_edge_density"]:.1f}%')
print(f'  top_left_bright={features["top_left_brightness"]:.0f}')
cv2.imwrite(str(PROJECT / 'cache' / 'menu_screen.png'), img)
print(f'  鎴浘淇濆瓨: cache/menu_screen.png')

# 娴嬭瘯 event_icon
print(f'\n娴嬭瘯2: event_icon ({NAV["event_icon"]}) 鎵撳紑娲诲姩闈㈡澘...')
# 鍏堣繑鍥瀢orld
for _ in range(5):
    key(4); time.sleep(0.5)
tap(*NAV["event_icon"])
time.sleep(3)
img = sc()
r = a.analyze(img)
print(f'  娲诲姩鍚? {r["page_type"]} conf={r["confidence"]:.2f} left_bar={r["features"]["left_bar_brightness"]:.0f}')

# 娴嬭瘯 city_map
print(f'\n娴嬭瘯3: city_map ({NAV["city_map"]}) 鎵撳紑鍦板浘...')
for _ in range(5):
    key(4); time.sleep(0.5)
tap(*NAV["city_map"])
time.sleep(3)
img = sc()
r = a.analyze(img)
print(f'  鍦板浘鍚? {r["page_type"]} conf={r["confidence"]:.2f} left_bar={r["features"]["left_bar_brightness"]:.0f}')

# 杩斿洖world
for _ in range(5):
    key(4); time.sleep(0.5)

print('\n[瀹屾垚] 鏌ョ湅 cache/menu_screen.png 纭鑿滃崟甯冨眬')

