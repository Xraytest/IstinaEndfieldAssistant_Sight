"""测试修正Y坐标的按钮位置"""
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
tap(960, 717)  # 取消可能存在的对话框
time.sleep(1)
go_back()
time.sleep(1.5)

# 基准截图
base_path = os.path.join(CACHE, 'test_y33_base.png')
img_base = screencap(base_path)
print(f"基准截图: {img_base.shape[1]}x{img_base.shape[0]}")

# 测试坐标 (1280x720 → 1920x1080 缩放)
# Coords: tasks=(570,22) event=(510,22) back=(450,22) shop=(480,22) signin=(525,22) inventory=(585,22) settings=(645,22)
tests = [
    ("exploration", 75, 33),    # mode_switch (75,21) * 1.5
    ("back",        450*1.5, 33),
    ("shop",        480*1.5, 33),
    ("event",       510*1.5, 33),
    ("signin",      525*1.5, 33),
    ("tasks",       570*1.5, 33),
    ("inventory",   585*1.5, 33),
    ("settings",    645*1.5, 33),
]

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
from standard_flow_engine import ScreenAnalyzer
analyzer = ScreenAnalyzer()

output = []
for name, x, y in tests:
    x, y = int(x), int(y)
    
    # 回到主世界
    go_back()
    tap(960, 717)
    time.sleep(0.5)
    go_back()
    time.sleep(1.5)
    
    # 截图前
    before_path = os.path.join(CACHE, f'y33_{name}_before.png')
    screencap(before_path)
    img_before = cv2.imread(before_path)
    
    # 点击
    tap(x, y)
    time.sleep(2.5)
    
    # 截图后
    after_path = os.path.join(CACHE, f'y33_{name}_after.png')
    screencap(after_path)
    img_after = cv2.imread(after_path)
    
    # 像素差异分析
    center_change = pixel_diff(img_before, img_after, (80, 650, 100, 1180))
    global_change = pixel_diff(img_before, img_after)
    
    # OCR分析
    r = analyzer.analyze(img_after)
    page_type = r['page_type']
    ocr = r['ocr_text'][:120]
    
    line = f'{name} ({x},{y}): center_diff={center_change:,} global_diff={global_change:,} page={page_type}'
    output.append(line)
    output.append(f'  OCR: {ocr}')
    print(line)
    print(f'  OCR: {ocr}')

result = '\n'.join(output)
with open(os.path.join(CACHE, 'y33_test_results.txt'), 'w', encoding='utf-8') as f:
    f.write(result)
print('\nDONE')
