"""测试探索引擎找到的按钮坐标"""
import subprocess, time, os, cv2

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
ADB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'

def screencap(path):
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       timeout=15, capture_output=True)
    open(path, 'wb').write(r.stdout)
    return cv2.imread(path)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(x), str(y)],
                   timeout=10, capture_output=True)

def go_back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'],
                   timeout=5, capture_output=True)
    time.sleep(2)

def pixel_diff(img_a, img_b, roi=None):
    if roi:
        y1, y2, x1, x2 = roi
        a, b = img_a[y1:y2, x1:x2], img_b[y1:y2, x1:x2]
    else:
        a, b = img_a, img_b
    diff = cv2.absdiff(a, b)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(thresh)

# 确保回到世界
for _ in range(3):
    go_back()
tap(960, 717)
time.sleep(1)

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
from standard_flow_engine import ScreenAnalyzer
analyzer = ScreenAnalyzer()

# 探索引擎找到的坐标
tests = [
    ("task_button", 163, 51),
    ("mail_button", 252, 47),
]

output = []
for name, x, y in tests:
    go_back()
    tap(960, 717)
    time.sleep(1)
    go_back()
    time.sleep(1.5)
    
    before_path = os.path.join(CACHE, f'explore_{name}_before.png')
    screencap(before_path)
    img_before = cv2.imread(before_path)
    
    tap(x, y)
    time.sleep(2.5)
    
    after_path = os.path.join(CACHE, f'explore_{name}_after.png')
    screencap(after_path)
    img_after = cv2.imread(after_path)
    
    center_change = pixel_diff(img_before, img_after, (80, 650, 100, 1180))
    global_change = pixel_diff(img_before, img_after)
    
    r = analyzer.analyze(img_after)
    line = f'{name} ({x},{y}): center_diff={center_change:,} global_diff={global_change:,} page={r["page_type"]}'
    output.append(line)
    output.append(f'  OCR: {r["ocr_text"][:120]}')
    print(line)
    print(f'  OCR: {r["ocr_text"][:120]}')

result = '\n'.join(output)
with open(os.path.join(CACHE, 'explore_coords_test.txt'), 'w', encoding='utf-8') as f:
    f.write(result)
print('\nDONE')
