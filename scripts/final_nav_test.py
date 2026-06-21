"""最终导航按钮验证 - 正确处理退出对话框 + 测试全屏关键区域"""
import subprocess, time, os, sys, cv2, numpy as np

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJECT, 'cache')
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
os.makedirs(CACHE, exist_ok=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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

def close_dialog_hard():
    """强力关闭任何对话框 - 按取消+ESC+返回"""
    for method in range(5):
        img = screencap(os.path.join(CACHE, 'fn_check.png'))
        if img is None or not is_dialog(img):
            return True
        if method == 0:
            tap(834, 717)  # cancel button in 1080p
        elif method == 1:
            back()
        elif method == 2:
            tap(834, 717)
            time.sleep(0.3)
            back()
        elif method == 3:
            # tap far corner to dismiss
            tap(1800, 100)
        elif method == 4:
            back()
            back()
        time.sleep(1.5)
    return False

def go_to_world():
    """强力返回世界画面"""
    for _ in range(4):
        back()
        time.sleep(0.5)
    time.sleep(1)
    close_dialog_hard()
    time.sleep(1)

# ── 测试集 ──
# 包含flows_config中的key坐标，加上我们实证找到的坐标
tests = [
    # Top bar coordinates (from flows_config & game_coords)
    ("quest_icon_1", 855, 33, "nav_coords quest_icon"),
    ("quest_icon_2", 855, 50, "quest slightly lower"),
    ("quest_icon_3", 860, 70, "quest even lower"),
    ("menu_icon_1", 1392, 79, "nav_coords menu_icon"),
    ("menu_icon_2", 1390, 100, "menu slightly lower"),
    ("event_icon_1", 928, 53, "nav_coords event_icon"),
    ("event_icon_2", 930, 80, "event slightly lower"),
    ("base_entry_1", 997, 85, "nav_coords base_entry"),
    ("base_entry_2", 998, 110, "base slightly lower"),
    
    # Already confirmed working
    ("industry_panel", 300, 80, "opens 武陵工业计划"),
    ("region_build", 400, 35, "opens 地区建设"),
    ("city_map", 150, 150, "opens 武陵城地图"),
    ("production_report", 90, 120, "opens 工业简报"),
    
    # Right-side edge gestures
    ("bottom_menu_1", 1800, 990, "bottom right corner"),
    ("bottom_menu_2", 1320, 990, "bottom mid-right"),
    
    # Screen edges
    ("top_edge_right", 1800, 5, "top right edge"),
    ("top_edge_mid", 960, 5, "top center edge"),
    ("bottom_edge_mid", 960, 1075, "bottom center edge"),
    ("bottom_edge_right", 1800, 1075, "bottom right edge"),
    ("right_edge_mid", 1915, 540, "right edge center"),
    ("left_edge_mid", 5, 540, "left edge center"),
]

print("Phase 0: 准备回到世界...")
go_to_world()

results_ok = []
results_fail = []
img_count = 0

for tag, x, y, desc in tests:
    # 确保在世界
    if not close_dialog_hard():
        print(f"  WARN: 无法关闭对话框，跳过 {tag}")
        continue
    
    before_p = os.path.join(CACHE, f'fn_before_{tag}.png')
    img_before = screencap(before_p)
    if img_before is None:
        print(f"  {tag}: SKIP (before failed)")
        continue
    img_count += 1
    
    tap(x, y)
    time.sleep(2.5)
    
    after_p = os.path.join(CACHE, f'fn_after_{tag}.png')
    img_after = screencap(after_p)
    if img_after is None:
        print(f"  {tag}: SKIP (after failed)")
        back()
        time.sleep(1)
        continue
    
    diff = full_diff(img_before, img_after)
    
    # 简单判断：大diff = 面板打开
    is_big = diff > 300000
    
    # VLM分析（仅对big diff）
    if is_big:
        r = analyzer.analyze(img_after)
        ptype = r['page_type']
        ocr = r['ocr_text'][:150].replace('\n', ' | ')
        print(f"  ✅ {tag} ({x},{y}) [{desc}]: diff={diff:,} type={ptype}")
        print(f"     OCR: {ocr}")
        results_ok.append((tag, x, y, diff, ptype, ocr))
        
        # 面板内点击后直接返回
        back()
        time.sleep(1.5)
        close_dialog_hard()
    else:
        print(f"  ❌ {tag} ({x},{y}) [{desc}]: diff={diff:,} (no UI)")
        results_fail.append((tag, x, y, diff))
    
    # 限制截图数量，避免VLM过载
    if img_count > 15 and is_big:
        break

# ── 汇总 ──
print(f"\n{'='*60}")
print(f"=== 结果 ===")
print(f"\n✅ 有效面板 ({len(results_ok)}):")
for tag, x, y, diff, ptype, ocr in results_ok:
    print(f"  ({x},{y}) {tag}: {diff:,} type={ptype}")
    print(f"    {ocr[:100]}")

print(f"\n❌ 未触发UI ({len(results_fail)}):")
for tag, x, y, diff in results_fail:
    print(f"  ({x},{y}) {tag}: {diff:,}")

print("\nDone!")
