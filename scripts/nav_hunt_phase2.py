"""导航按钮定位 Phase 2 - 聚焦右侧已知命中 + 细粒度扫描 + VLM 面板识别"""
import subprocess, time, os, sys, cv2, numpy as np, json

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJECT, 'cache')
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
os.makedirs(CACHE, exist_ok=True)

from standard_flow_engine import ScreenAnalyzer

analyzer = ScreenAnalyzer()

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

def pixel_diff(img_a, img_b, y1, y2, x1, x2):
    if img_a is None or img_b is None:
        return 0
    diff = cv2.absdiff(img_a[y1:y2, x1:x2], img_b[y1:y2, x1:x2])
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(thresh)

def is_dialog(img):
    if img is None:
        return True
    mid = img[300:700, 500:1400, :]
    return mid.mean() < 80

# 关闭对话框
print("Phase 0: 准备...")
for _ in range(3):
    back()
    time.sleep(0.8)
time.sleep(1)

check_path = os.path.join(CACHE, 'h2_check.png')
for i in range(5):
    img = screencap(check_path)
    if not is_dialog(img):
        break
    tap(834, 717)
    time.sleep(1)
time.sleep(1)

baseline = screencap(os.path.join(CACHE, 'h2_baseline.png'))
h, w = baseline.shape[:2]
print(f"分辨率: {w}x{h}")

# ── Phase 1: 验证 (1025, 35) 并分析面板内容 ──
print("\nPhase 1: 验证已知命中点 (1025, 35)...")

# 先截图before
tap(1025, 35)
time.sleep(2.5)
panel_img = screencap(os.path.join(CACHE, 'h2_panel_1025_35.png'))

# VLM分析
print("  VLM分析面板...")
r = analyzer.analyze(panel_img)
print(f"  类型: {r['page_type']}")
print(f"  OCR: {r['ocr_text'][:300]}")
print(f"  VLM: {r['vlm_judgment'][:200]}")

# 返回
back()
time.sleep(1.5)

# ── Phase 2: 细粒度扫描 X=840-1060, Y=25-55 (step=10) ──
# Scale: 720p→1080p = 1.5x
# Tasks(540-600,22)→(810-900,33), Inventory(570-630,22)→(855-945,33), Settings(630-690,22)→(945-1035,33)
# Y扫描 28, 33, 38, 43, 48, 53
print(f"\n{'='*60}")
print("Phase 2: 细粒度扫描右侧按钮区 (X=840-1060, Y=28-53, step=10)")

results = []
hit_count = 0

for y in [28, 33, 38, 43, 48, 53]:
    for x in range(840, 1060, 10):
        img = screencap(check_path)
        if is_dialog(img):
            tap(834, 717)
            time.sleep(1)
        
        before_path = os.path.join(CACHE, f'h2_before_{x}_{y}.png')
        img_before = screencap(before_path)
        if img_before is None:
            continue
        
        tap(x, y)
        time.sleep(2.0)  # 缩短等待
        
        after_path = os.path.join(CACHE, f'h2_after_{x}_{y}.png')
        img_after = screencap(after_path)
        if img_after is None:
            back()
            time.sleep(1)
            continue
        
        full_c = full_diff(img_before, img_after)
        center_c = pixel_diff(img_before, img_after, 80, min(650, h), 100, min(1180, w))
        
        results.append({'x': x, 'y': y, 'full': int(full_c), 'center': int(center_c)})
        
        sig = ' ⭐ HIT!' if center_c > 100000 else ''
        if center_c > 100000:
            hit_count += 1
        print(f'  ({x},{y}): full={full_c:>10,} center={center_c:>10,}{sig}')
        
        back()
        time.sleep(1.2)

print(f'\n找到 {hit_count} 个命中点')

# 保存
results.sort(key=lambda r: r['center'], reverse=True)
with open(os.path.join(CACHE, 'h2_results.json'), 'w') as f:
    json.dump(results, f, indent=2)

print(f'\nTOP 15:')
for r in results[:15]:
    print(f"  ({r['x']},{r['y']}): full={r['full']:>10,} center={r['center']:>10,}")

# ── Phase 3: 对命中点逐一用 VLM 识别面板 ──
print(f'\n{"="*60}')
print('Phase 3: VLM 识别各命中面板...')

# 重新按世界，逐个验证top hits
top_hits = [r for r in results if r['center'] > 100000][:5]
for hit in top_hits:
    x, y = hit['x'], hit['y']
    
    # 确保在世界
    for _ in range(2):
        back()
        time.sleep(0.8)
    time.sleep(1)
    
    tap(x, y)
    time.sleep(2.5)
    panel_img = screencap(os.path.join(CACHE, f'h2_panel_{x}_{y}.png'))
    
    r = analyzer.analyze(panel_img)
    label = r['ocr_text'][:80].replace('\n', ' | ')
    print(f'  ({x},{y}): type={r["page_type"]} OCR={label}')
    
    back()
    time.sleep(1.5)

print('\nDone!')
