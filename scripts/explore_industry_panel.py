"""打开武陵工业计划面板，扫描其内部所有可点击按钮"""
import subprocess, time, os, sys, cv2, numpy as np, json

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

def screencap(path):
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], timeout=15, capture_output=True)
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

def close_exit_dialog():
    """正确关闭退出对话框：game_coords exit_cancel=(556,478) 720p → (834,717) 1080p"""
    for _ in range(3):
        img = screencap(os.path.join(CACHE, 'eip_check.png'))
        if img is None:
            time.sleep(0.5)
            continue
        if not is_dialog(img):
            return True
        # 按取消按钮 (834, 717) in 1080p
        tap(834, 717)
        time.sleep(1.5)
    return False

# ── Phase 1: 打开武陵工业计划面板，完整分析 ──
print("Phase 1: 打开武陵工业计划面板...")
for _ in range(4):
    back()
    time.sleep(0.5)
time.sleep(1)
close_exit_dialog()
time.sleep(1)

# 打开面板
tap(300, 80)
time.sleep(3)

panel_img = screencap(os.path.join(CACHE, 'eip_industry_panel.png'))
if panel_img is None:
    print("ERROR: 截图失败")
    sys.exit(1)

print(f"面板大小: {panel_img.shape[1]}x{panel_img.shape[0]}")

# 完整分析
r = analyzer.analyze(panel_img)
print(f"\n完整OCR:")
print(r['ocr_text'])
print(f"\nVLM判断: {r['vlm_judgment'][:300]}")
print(f"\n金色元素: {len(r['golden_elements'])}个")
for g in r['golden_elements'][:10]:
    print(f"  {g}")
print(f"\nYOLO: {r['yolo_objects'][:10]}")

# ── Phase 2: 扫描面板内可点击区域 ──
print(f"\nPhase 2: 扫描面板内部按钮...")

# 基于OCR识别的内容：原料开采、物流运输、材料加工、战斗辅助、息壤工业、武陵工业二期
# 这些应该是面板内的子模块
# 面板大约在屏幕中央偏左

# 粗扫面板区域 (Y=100-500, X=50-500) 
scan_positions = []
for y in range(100, 500, 50):
    for x in range(50, 500, 60):
        scan_positions.append((x, y))

# 也扫描右下区域（可能有返回/关闭按钮）
for y in [800, 900, 1000]:
    for x in range(1200, 1900, 80):
        scan_positions.append((x, y))

total = len(scan_positions)
print(f"  共 {total} 个扫描点")

results = []
for idx, (x, y) in enumerate(scan_positions):
    # 确保面板还开着
    img_check = screencap(os.path.join(CACHE, 'eip_check.png'))
    if img_check is not None and is_dialog(img_check):
        close_exit_dialog()
        # 重新打开面板
        tap(300, 80)
        time.sleep(2)
    
    before_p = os.path.join(CACHE, 'eip_dummy.png')
    img_before = screencap(before_p)
    if img_before is None:
        continue
    
    tap(x, y)
    time.sleep(2.0)
    
    after_p = os.path.join(CACHE, 'eip_dummy.png')
    img_after = screencap(after_p)
    if img_after is None:
        continue
    
    fc = full_diff(img_before, img_after)
    results.append({'x': x, 'y': y, 'full': int(fc)})
    
    sig = ' ⭐' if fc > 200000 else ''
    if fc > 200000:
        print(f'  [{idx+1}/{total}] ({x},{y}): full={fc:>10,}{sig}')
    
    # 返回（如果在面板内点击可能已跳转）
    back()
    time.sleep(1.2)

results.sort(key=lambda r: r['full'], reverse=True)
print(f'\n面板内 TOP 20:')
for r in results[:20]:
    print(f"  ({r['x']},{r['y']}): {r['full']:>10,}")

with open(os.path.join(CACHE, 'eip_results.json'), 'w') as f:
    json.dump(results, f, indent=2)
print('\nDone!')
