"""直接验证VLM识别的按钮是否能打开面板"""
import subprocess, time, os, cv2, sys

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
ADB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

from standard_flow_engine import ScreenAnalyzer
analyzer = ScreenAnalyzer()

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(x), str(y)],
                   timeout=10, capture_output=True)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'],
                   timeout=5, capture_output=True)

def screencap(path):
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       timeout=15, capture_output=True)
    open(path, 'wb').write(r.stdout)
    return cv2.imread(path)

def goto_world():
    for _ in range(4):
        back()
        time.sleep(0.8)
    time.sleep(1)
    for _ in range(3):
        tap(834, 717)
        time.sleep(0.5)

def test_button(name, x, y):
    goto_world()
    time.sleep(1.5)
    
    before_path = os.path.join(CACHE, f'test_{name}_before.png')
    screencap(before_path)
    
    tap(x, y)
    time.sleep(3)
    
    after_path = os.path.join(CACHE, f'test_{name}_after.png')
    img = screencap(after_path)
    
    r = analyzer.analyze(img)
    page_type = r['page_type']
    ocr = r['ocr_text'][:150]
    
    # 检查是否有变化
    img_before = cv2.imread(before_path)
    if img_before is not None:
        diff = cv2.absdiff(img_before[80:650, 100:1180], img[80:650, 100:1180])
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
        change = cv2.countNonZero(thresh)
    else:
        change = 0
    
    changed = '✅ OPENED' if change > 100000 else '❌ NO CHANGE' if change < 10000 else '⚠️ SMALL'
    print(f'[{name}] ({x},{y}): {changed} | center={change:,} | type={page_type} | OCR={ocr[:80]}')
    
    return {'name': name, 'x': x, 'y': y, 'change': change, 'page_type': page_type, 'ocr': ocr}

# VLM 识别的按钮（居中坐标）
buttons = [
    ("探索/模式", 71, 46),
    ("商店(左1)", 166, 51),
    ("活动(左)", 210, 46),
    ("签到(左)", 254, 51),
    ("任务", 660, 42),
    ("商店(右)", 704, 42),
    ("活动(右)", 748, 42),
    ("商店(右2)", 792, 46),
    ("背包", 834, 46),
    ("设置(右1)", 878, 46),
    ("设置(右2)", 922, 46),
    ("设置(右3)", 964, 46),
]

print("开始验证按钮...")
results = []
for name, x, y in buttons:
    try:
        r = test_button(name, x, y)
        results.append(r)
    except Exception as e:
        print(f'[{name}] ERROR: {e}')

print(f'\n=== 验证结果 ===')
for r in results:
    opened = '✅' if r['change'] > 100000 else '❌'
    print(f'{opened} {r["name"]:12s} ({r["x"]},{r["y"]}): center={r["change"]:>8,} | {r["page_type"]:12s} | {r["ocr"][:60]}')
