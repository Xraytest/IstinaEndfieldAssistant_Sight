#!/usr/bin/env python3
"""验证菜单入口坐标和菜单内元素位置"""
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

# 确保在world
print('确保在world...')
for _ in range(5):
    key(4); time.sleep(0.5)
img = sc()
r = a.analyze(img)
print(f'  当前: {r["page_type"]} left_bar={r["features"]["left_bar_brightness"]:.0f} green={r["features"]["green_pixels_top_right"]:.0f}')

# 测试 menu_icon
print(f'\n测试1: menu_icon ({NAV["menu_icon"]}) 打开系统菜单...')
tap(*NAV["menu_icon"])
time.sleep(3)
img = sc()
r = a.analyze(img)
print(f'  菜单后: {r["page_type"]} conf={r["confidence"]:.2f}')
features = r["features"]
print(f'  left_bar={features["left_bar_brightness"]:.0f} green={features["green_pixels_top_right"]:.0f}')
print(f'  full_bright={features["full_brightness"]:.0f} center_edge={features["center_edge_density"]:.1f}%')
print(f'  top_left_bright={features["top_left_brightness"]:.0f}')
cv2.imwrite(str(PROJECT / 'cache' / 'menu_screen.png'), img)
print(f'  截图保存: cache/menu_screen.png')

# 测试 event_icon
print(f'\n测试2: event_icon ({NAV["event_icon"]}) 打开活动面板...')
# 先返回world
for _ in range(5):
    key(4); time.sleep(0.5)
tap(*NAV["event_icon"])
time.sleep(3)
img = sc()
r = a.analyze(img)
print(f'  活动后: {r["page_type"]} conf={r["confidence"]:.2f} left_bar={r["features"]["left_bar_brightness"]:.0f}')

# 测试 city_map
print(f'\n测试3: city_map ({NAV["city_map"]}) 打开地图...')
for _ in range(5):
    key(4); time.sleep(0.5)
tap(*NAV["city_map"])
time.sleep(3)
img = sc()
r = a.analyze(img)
print(f'  地图后: {r["page_type"]} conf={r["confidence"]:.2f} left_bar={r["features"]["left_bar_brightness"]:.0f}')

# 返回world
for _ in range(5):
    key(4); time.sleep(0.5)

print('\n[完成] 查看 cache/menu_screen.png 确认菜单布局')
