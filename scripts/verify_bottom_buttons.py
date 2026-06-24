"""验证底部命中点——用ScreenAnalyzer识别面板内容"""
import subprocess, time, os, sys, cv2, numpy as np

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJECT, 'cache')
ADB = os.path.join(PROJECT, '3rd-part', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
os.makedirs(CACHE, exist_ok=True)

def full_diff(img_a, img_b):
    if img_a is None or img_b is None:
        return 0
    diff = cv2.absdiff(img_a, img_b)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(thresh)

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

from standard_flow_engine import ScreenAnalyzer

analyzer = ScreenAnalyzer()

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   timeout=10, capture_output=True)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5, capture_output=True)

def screencap(path):
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], timeout=15, capture_output=True)
    if len(r.stdout) < 1000:
        return None
    with open(path, 'wb') as f:
        f.write(r.stdout)
    return cv2.imread(path)

# ── 测试目标点 ──
test_points = [
    # 底部栏命中点
    (1320, 990, "bottom_mid_right"),
    (1800, 990, "bottom_far_right"),
    (1800, 1020, "bottom_far_right_low"),
    # 左侧命中点
    (30, 80, "left_top"),
    (300, 80, "mid_top"),
    (210, 200, "left_mid_upper"),
    (390, 200, "left_mid"),
    # 底部栏精细扫描 Y=990, X=1240-1880 step=40
    (1240, 990, "bot_x1240"),
    (1280, 990, "bot_x1280"),
    (1360, 990, "bot_x1360"),
    (1400, 990, "bot_x1400"),
    (1440, 990, "bot_x1440"),
    (1480, 990, "bot_x1480"),
    (1520, 990, "bot_x1520"),
    (1560, 990, "bot_x1560"),
    (1600, 990, "bot_x1600"),
    (1640, 990, "bot_x1640"),
    (1680, 990, "bot_x1680"),
    (1720, 990, "bot_x1720"),
    (1760, 990, "bot_x1760"),
    (1840, 990, "bot_x1840"),
    (1880, 990, "bot_x1880"),
]

for x, y, label in test_points:
    # 确保在世界
    for _ in range(3):
        back()
        time.sleep(0.6)
    time.sleep(1)
    
    # 截图前
    before_p = os.path.join(CACHE, f'vfy_before_{label}.png')
    img_before = screencap(before_p)
    if img_before is None:
        print(f'  {label} ({x},{y}): SKIP (screenshot failed)')
        continue
    
    tap(x, y)
    time.sleep(2.5)
    
    after_p = os.path.join(CACHE, f'vfy_after_{label}.png')
    img_after = screencap(after_p)
    if img_after is None:
        print(f'  {label} ({x},{y}): SKIP (after failed)')
        continue
    
    diff = full_diff(img_before, img_after)
    
    # VLM分析
    r = analyzer.analyze(img_after)
    ocr_short = r['ocr_text'][:100].replace('\n', ' | ')
    print(f'  {label} ({x},{y}): diff={diff:>10,} type={r["page_type"]} OCR={ocr_short}')
    
    back()
    time.sleep(1.5)

print('\nDone!')
