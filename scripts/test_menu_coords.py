#!/usr/bin/env python3
"""测试 world→menu 转换和菜单内坐标"""
import subprocess, time, cv2, numpy as np, sys
from pathlib import Path
from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path; ensure_path()
from core.page_analyzer import HighPrecisionPageAnalyzer

ADB = Path(__file__).resolve().parent.parent / '3rd-party' / 'adb' / 'adb.exe'
a = HighPrecisionPageAnalyzer()

def sc():
    r = subprocess.run([str(ADB),'-s','localhost:16512','exec-out','screencap','-p'],capture_output=True,timeout=10)
    return cv2.imdecode(np.frombuffer(r.stdout,np.uint8),cv2.IMREAD_COLOR)
def tap(x,y):
    subprocess.run([str(ADB),'-s','localhost:16512','shell','input','tap',str(x),str(y)],capture_output=True,timeout=5)
def key(k):
    subprocess.run([str(ADB),'-s','localhost:16512','shell','input','keyevent',str(k)],capture_output=True,timeout=5)

# 返回world
print('返回world...')
for _ in range(5):
    key(4); time.sleep(0.8)
img = sc()
r = a.analyze(img)
print(f'当前: {r["page_type"]} conf={r["confidence"]:.2f}')

# 测试 menu_icon
print('\n测试1: tap menu_icon (1392,79)...')
tap(1392, 79); time.sleep(3)
img = sc()
r = a.analyze(img)
print(f'菜单: {r["page_type"]} conf={r["confidence"]:.2f}')
print(f'  bottom_nav={r["features"]["bottom_nav_brightness"]:.0f} dialog_gold={r["features"]["dialog_gold_pixels"]:.0f}')

# 测试 base_entry_menu (960,400)
print('\n测试2: tap base_entry_menu (960,400)...')
tap(960, 400); time.sleep(3)
img = sc()
r = a.analyze(img)
print(f'基建后: {r["page_type"]} conf={r["confidence"]:.2f} left_bar={r["features"]["left_bar_brightness"]:.0f}')

# 返回
key(4); time.sleep(1)

# 重新开菜单
print('\n测试3: 重新开菜单...')
key(4); time.sleep(0.5)
tap(1392, 79); time.sleep(3)

# 测试 char_entry_menu (1200,330)
print('测试4: tap char_entry_menu (1200,330)...')
tap(1200, 330); time.sleep(3)
img = sc()
r = a.analyze(img)
print(f'角色后: {r["page_type"]} conf={r["confidence"]:.2f} left_bar={r["features"]["left_bar_brightness"]:.0f}')

# 返回world
for _ in range(5):
    key(4); time.sleep(0.5)

print('\n[完成]')
