#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""娴嬭瘯閫€鍑哄璇濇鐗瑰緛妫€娴?""
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

# 绛栫暐1: 蹇€熻繛鎸夎繑鍥烇紙闂撮殧鐭紝妯℃嫙姝ｅ父鎿嶄綔锛?
print('蹇€熻繛鎸夎繑鍥?..', flush=True)
for i in range(5):
    img = sc()
    if img is not None:
        r = a.analyze(img)
        lt = r["features"]["left_bar_brightness"]
        print(f'{i}: {r["page_type"]} left_bar={lt:.0f} green={r["features"]["green_pixels_top_right"]:.0f}', flush=True)
        if r['page_type'] == 'world':
            print('鉁?鍒拌揪涓栫晫锛?, flush=True)
            break
    key(4)
    time.sleep(1.5)  # 绋嶉暱绛夊緟

# 濡傛灉杩樻槸浠诲姟闈㈡澘锛屽皾璇曢€€鍑烘父鎴忛噸鍚?
img = sc()
if img is not None:
    r = a.analyze(img)
    if r['page_type'] != 'world':
        print('浠嶅湪浠诲姟闈㈡澘锛屽皾璇曞己鍒惰繑鍥炴闈?..', flush=True)
        key(3)  # HOME
        time.sleep(2)
        subprocess.run([str(ADB), '-s', SER, 'shell', 'am', 'start', '-n',
                       'com.hypergryph.endfield/.MainActivity'],
                      capture_output=True, timeout=10)
        time.sleep(15)
        
        img = sc()
        if img is not None:
            r = a.analyze(img)
            print(f'閲嶅惎鍚? {r["page_type"]} left_bar={r["features"]["left_bar_brightness"]:.0f}', flush=True)

# 瑙﹀彂閫€鍑哄璇濇
time.sleep(1)
key(4)
time.sleep(2)

img = sc()
r = a.analyze(img)
print(f'\n瀵硅瘽妗嗗悗: {r["page_type"]} conf={r["confidence"]:.2f}', flush=True)
for k, v in r['features'].items():
    print(f'  {k}: {v:.2f}', flush=True)

