"""导航按钮定位 Phase 3 - 扫描底部栏 + 左侧全区域 + 世界传送点"""
import subprocess, time, os, sys, cv2, numpy as np, json

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJECT, 'cache')
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
os.makedirs(CACHE, exist_ok=True)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   timeout=10, capture_output=True)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5, capture_output=True)

def screencap(path):
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       timeout=15, capture_output=True)
    if len(r.stdout) < 1000:
        return None
    with open(path, 'wb') as f:
        f.write(r.stdout)
    return cv2.imread(path)

def full_diff(img_a, img_b):
    if img_a is None or img_b is None:
        return 0
    diff = cv2.absdiff(img_a, img_b)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(thresh)

def is_dialog(img):
    if img is None:
        return True
    mid = img[300:700, 500:1400, :]
    return mid.mean() < 80

# 准备
print("Phase 0: 准备...")
for _ in range(3):
    back()
    time.sleep(0.8)
time.sleep(1)

check_path = os.path.join(CACHE, 'h3_check.png')
for i in range(5):
    img = screencap(check_path)
    if not is_dialog(img):
        break
    tap(834, 717)
    time.sleep(1)
time.sleep(1)

baseline = screencap(os.path.join(CACHE, 'h3_baseline.png'))
h, w = baseline.shape[:2]
print(f"分辨率: {w}x{h}")

# ── Phase 1: 底部栏扫描 (Y=980-1060, X=0-1920, step=40) ──
print(f"\nPhase 1: 底部栏扫描 (Y=990-1050, step=80)")
results_bottom = []

for y in [990, 1020, 1050]:
    for x in range(40, 1900, 80):
        img = screencap(check_path)
        if is_dialog(img):
            tap(834, 717)
            time.sleep(1)
        
        img_before = screencap(os.path.join(CACHE, 'h3_dummy.png'))
        if img_before is None:
            continue
        
        tap(x, y)
        time.sleep(1.8)
        
        img_after = screencap(os.path.join(CACHE, 'h3_dummy.png'))
        if img_after is None:
            continue
        
        fc = full_diff(img_before, img_after)
        results_bottom.append({'x': x, 'y': y, 'full': int(fc)})
        
        sig = ' ⭐' if fc > 200000 else ''
        if fc > 200000:
            print(f'  ({x},{y}): full={fc:>10,}{sig}')
        
        back()
        time.sleep(1.2)

results_bottom.sort(key=lambda r: r['full'], reverse=True)
print(f'\n底部栏 TOP 10:')
for r in results_bottom[:10]:
    print(f"  ({r['x']},{r['y']}): {r['full']:>10,}")

# ── Phase 2: 左侧全区域扫描 (X=0-540, Y=0-1080, coarse) ──
print(f"\nPhase 2: 左侧全区域扫描 (X=30-510, Y=80-900)")
results_left = []

for y in [80, 200, 350, 500, 650, 800]:
    for x in [30, 120, 210, 300, 390, 480]:
        img = screencap(check_path)
        if is_dialog(img):
            tap(834, 717)
            time.sleep(1)
        
        img_before = screencap(os.path.join(CACHE, 'h3_dummy.png'))
        if img_before is None:
            continue
        
        tap(x, y)
        time.sleep(1.8)
        
        img_after = screencap(os.path.join(CACHE, 'h3_dummy.png'))
        if img_after is None:
            continue
        
        fc = full_diff(img_before, img_after)
        results_left.append({'x': x, 'y': y, 'full': int(fc)})
        
        sig = ' ⭐' if fc > 200000 else ''
        if fc > 200000:
            print(f'  ({x},{y}): full={fc:>10,}{sig}')
        
        back()
        time.sleep(1.2)

results_left.sort(key=lambda r: r['full'], reverse=True)
print(f'\n左侧 TOP 10:')
for r in results_left[:10]:
    print(f"  ({r['x']},{r['y']}): {r['full']:>10,}")

# ── Phase 3: 用 ScreenAnalyzer 分析世界截图 OCR ──
print(f"\nPhase 3: OCR 分析世界画面...")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from standard_flow_engine import ScreenAnalyzer
analyzer = ScreenAnalyzer()

world_img = screencap(os.path.join(CACHE, 'h3_world.png'))
if world_img is not None:
    r = analyzer.analyze(world_img)
    print(f"  page_type: {r['page_type']}")
    print(f"  OCR: {r['ocr_text'][:300]}")
    print(f"  YOLO: {r['yolo_objects']}")
    print(f"  VLM: {r['vlm_judgment'][:200]}")
else:
    print("  ERROR: 截图失败")

# 保存所有结果
all_results = {
    'bottom': results_bottom[:20],
    'left': results_left[:20],
}
with open(os.path.join(CACHE, 'h3_results.json'), 'w') as f:
    json.dump(all_results, f, indent=2)
print('\nDone!')
