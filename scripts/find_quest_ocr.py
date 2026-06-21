"""逐一测试X位置并用OCR检查打开了什么"""
import subprocess, time, os, sys, cv2

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
ADB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
from standard_flow_engine import ScreenAnalyzer

def screencap(path):
    with open(path, 'wb') as f:
        subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], stdout=f, timeout=15)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(x), str(y)], timeout=10)

def go_back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5)
    time.sleep(2)

analyzer = ScreenAnalyzer()
output = []
test_positions = [(720, 33), (810, 33), (855, 33), (900, 33), (990, 33)]

for x, y in test_positions:
    # 确保在世界
    go_back()
    time.sleep(1)
    
    # 截图前
    before_path = os.path.join(CACHE, f'ocr_test_{x}.png')
    screencap(before_path)
    img_before = cv2.imread(before_path)
    r_before = analyzer.analyze(img_before)
    
    # 点击
    tap(x, y)
    time.sleep(2.5)
    
    # 截图后
    after_path = os.path.join(CACHE, f'ocr_test_{x}_after.png')
    screencap(after_path)
    img_after = cv2.imread(after_path)
    r_after = analyzer.analyze(img_after)
    
    output.append(f'X={x}: before={r_before["page_type"]} after={r_after["page_type"]}')
    output.append(f'  OCR before: {r_before["ocr_text"][:100]}')
    output.append(f'  OCR after:  {r_after["ocr_text"][:100]}')
    output.append('')
    
    go_back()
    time.sleep(2)

result = '\n'.join(output)
print(result)
open(os.path.join(CACHE, 'quest_scan_ocr.txt'), 'w', encoding='utf-8').write(result)
