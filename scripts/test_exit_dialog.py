#!/usr/bin/env python3
"""测试退出对话框特征检测"""
import subprocess, time, cv2, numpy as np, sys
from pathlib import Path
from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path; ensure_path()
from core.service.page_analyzer import HighPrecisionPageAnalyzer

ADB = Path(__file__).resolve().parent.parent / '3rd-part' / 'adb' / 'adb.exe'
SER = 'localhost:16512'

def sc():
    r = subprocess.run([str(ADB), '-s', SER, 'exec-out', 'screencap', '-p'],
                      capture_output=True, timeout=10)
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def key(k):
    subprocess.run([str(ADB), '-s', SER, 'shell', 'input', 'keyevent', str(k)],
                  capture_output=True, timeout=5)
    time.sleep(0.5)

a = HighPrecisionPageAnalyzer()

def tap(x, y):
    subprocess.run([str(ADB), '-s', SER, 'shell', 'input', 'tap', str(x), str(y)],
                  capture_output=True, timeout=5)
    time.sleep(0.5)

# 策略1: 快速连按返回（间隔短，模拟正常操作）
print('快速连按返回...', flush=True)
for i in range(5):
    img = sc()
    if img is not None:
        r = a.analyze(img)
        lt = r["features"]["left_bar_brightness"]
        print(f'{i}: {r["page_type"]} left_bar={lt:.0f} green={r["features"]["green_pixels_top_right"]:.0f}', flush=True)
        if r['page_type'] == 'world':
            print('✅ 到达世界！', flush=True)
            break
    key(4)
    time.sleep(1.5)  # 稍长等待

# 如果还是任务面板，尝试退出游戏重启
img = sc()
if img is not None:
    r = a.analyze(img)
    if r['page_type'] != 'world':
        print('仍在任务面板，尝试强制返回桌面...', flush=True)
        key(3)  # HOME
        time.sleep(2)
        subprocess.run([str(ADB), '-s', SER, 'shell', 'am', 'start', '-n',
                       'com.hypergryph.endfield/.MainActivity'],
                      capture_output=True, timeout=10)
        time.sleep(15)
        
        img = sc()
        if img is not None:
            r = a.analyze(img)
            print(f'重启后: {r["page_type"]} left_bar={r["features"]["left_bar_brightness"]:.0f}', flush=True)

# 触发退出对话框
time.sleep(1)
key(4)
time.sleep(2)

img = sc()
r = a.analyze(img)
print(f'\n对话框后: {r["page_type"]} conf={r["confidence"]:.2f}', flush=True)
for k, v in r['features'].items():
    print(f'  {k}: {v:.2f}', flush=True)
