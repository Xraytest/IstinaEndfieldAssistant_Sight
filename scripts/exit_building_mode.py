"""退出建造模式，回到正常探索世界"""
import subprocess, time, os, sys, cv2

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJECT, 'cache')
ADB = os.path.join(PROJECT, '3rd-part', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
os.makedirs(CACHE, exist_ok=True)
from standard_flow_engine import ScreenAnalyzer
analyzer = ScreenAnalyzer()

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   timeout=10, capture_output=True)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5, capture_output=True)

def screencap():
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], timeout=15, capture_output=True)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

import numpy as np

def is_exit_dialog(img):
    if img is None:
        return False
    mid = img[300:700, 500:1400, :]
    return mid.mean() < 80

def analyze_state(img):
    r = analyzer.analyze(img)
    ocr = r['ocr_text']
    return {
        'is_exit': '是否退出游戏' in ocr,
        'is_building': '建造状态' in ocr or '放置预览' in ocr,
        'ocr': ocr[:200]
    }

# 1. 先看当前状态
img = screencap()
state = analyze_state(img)
print(f"初始状态: exit={state['is_exit']} building={state['is_building']}")
print(f"OCR: {state['ocr']}")

# 2. 退出building mode: 按"取消"按钮
# building的取消按钮和exit的取消按钮可能在不同位置
# 先尝试右下方区域
attempt = 0
for attempt in range(10):
    img = screencap()
    if img is None:
        continue
    state = analyze_state(img)
    
    if not state['is_exit'] and not state['is_building']:
        print(f"\n✅ 已退出建造/退出模式!")
        print(f"最终OCR: {state['ocr']}")
        break
    
    print(f"\n[Attempt {attempt+1}] exit={state['is_exit']} building={state['is_building']}")
    
    if state['is_exit']:
        # 关闭退出对话框
        print(f"  关闭退出对话框...")
        tap(834, 717)  # cancel button (556,478)*1.5
        time.sleep(2)
    elif state['is_building']:
        # 取消建造
        print(f"  取消建造...")
        # 尝试多个可能的取消按钮位置
        cancel_candidates = [
            (1319, 49),   # top-right close X (golden element)
            (1749, 721),  # right-side golden element
            (1456, 912),  # bottom-right golden element
            (834, 717),   # generic cancel
            (500, 900),   # bottom-left cancel
        ]
        for cx, cy in cancel_candidates:
            tap(cx, cy)
            time.sleep(1.5)
            img2 = screencap()
            if img2 is not None:
                st2 = analyze_state(img2)
                if not st2['is_building'] and not st2['is_exit']:
                    print(f"  ✅ ({cx},{cy}) 成功退出建造模式!")
                    img = img2
                    break
                if not st2['is_building']:
                    print(f"  ({cx},{cy}) 退出建造，但进入: {st2['ocr'][:80]}")
                    break
    else:
        back()
        time.sleep(1)

# 3. 最终确认
print(f"\n最终状态:")
img = screencap()
if img is not None:
    r = analyzer.analyze(img)
    print(f"  type: {r['page_type']}")
    print(f"  OCR: {r['ocr_text'][:300]}")
    print(f"  VLM: {r['vlm_judgment'][:200]}")
    cv2.imwrite(os.path.join(CACHE, 'cs_final_world.png'), img)
