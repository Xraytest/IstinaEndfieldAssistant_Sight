"""验证 flows_config.json 中所有导航坐标是否正确触发目标页面"""
import subprocess, time, os, sys, cv2, numpy as np, json

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJECT, 'cache')
ADB = os.path.join(PROJECT, '3rd-part', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
os.makedirs(CACHE, exist_ok=True)

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

def full_diff(img_a, img_b):
    if img_a is None or img_b is None:
        return 0
    diff = cv2.absdiff(img_a, img_b)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(thresh)

def is_dialog(img):
    """检测是否在退出对话框中"""
    if img is None:
        return True
    mid = img[300:700, 500:1400, :]
    return mid.mean() < 80

def is_exit_dialog(img):
    if img is None:
        return False
    mid = img[300:700, 500:1400, :]
    return mid.mean() < 80

def ensure_world():
    """确保回到世界画面，处理退出对话框"""
    for attempt in range(8):
        img = screencap(os.path.join(CACHE, 'va_check.png'))
        if img is None:
            time.sleep(1)
            continue
        if not is_dialog(img):
            return True
        # 在退出对话框中：按"取消" (用像素坐标约 556, 478 in 720p → scaled)
        # 根据游戏画面，对话框的"取消"按钮在左侧
        print(f"  [ensure] 检测到退出对话框，按取消...")
        tap(810, 1035)  # flows_config confirm 坐标... 实际上应该是 cancel
        time.sleep(1.5)
        # 如果 cancel 没效果，试试 back
        img2 = screencap(os.path.join(CACHE, 'va_check2.png'))
        if img2 is not None and is_dialog(img2):
            tap(550, 720)  # cancel area
            time.sleep(1)
    return True

# ── 测试坐标列表 ──
test_coords = [
    # flows_config.json nav_coords + 实际测试中发现的坐标
    (855, 33, "quest_icon", "任务图标"),
    (1392, 79, "menu_icon", "系统菜单"),
    (997, 85, "base_entry", "基建入口"),
    (120, 180, "minimap", "小地图"),
    (90, 120, "back", "返回按钮"),
    (150, 150, "explore", "探索模式"),
    (1200, 330, "char_portrait", "角色头像"),
    (928, 53, "event_icon", "活动图标"),         # from event_rewards
    (800, 220, "char_panel", "角色面板"),          # from character_ascension
    (665, 57, "base_alt", "基建备选"),              # from base_management
    (30, 80, "industry_panel", "工业面板左上"),     # 实证命中
    (400, 35, "industry_actual", "工业面板实际"),   # 实证命中
    (300, 80, "menu_trigger", "菜单触发"),          # 触发退出对话框
]

print("Phase 0: 准备...")
for _ in range(3):
    back()
    time.sleep(0.6)
time.sleep(1)

hits = []
fails = []

for x, y, tag, desc in test_coords:
    print(f"\n--- {tag} ({x},{y}) {desc} ---")
    
    # 确保在世界
    ensure_world()
    time.sleep(0.5)
    
    # 截图前
    before_p = os.path.join(CACHE, f'va_before_{tag}.png')
    img_before = screencap(before_p)
    if img_before is None:
        print(f"  FAIL: 截图失败")
        fails.append((tag, "screenshot failed"))
        continue
    
    # 点击
    tap(x, y)
    time.sleep(2.5)
    
    # 截图后
    after_p = os.path.join(CACHE, f'va_after_{tag}.png')
    img_after = screencap(after_p)
    if img_after is None:
        print(f"  FAIL: 截图失败")
        fails.append((tag, "after screenshot failed"))
        back()
        time.sleep(1)
        continue
    
    diff = full_diff(img_before, img_after)
    
    # VLM 分析
    r = analyzer.analyze(img_after)
    page_type = r['page_type']
    ocr = r['ocr_text'][:120].replace('\n', ' | ')
    vlm = r['vlm_judgment'][:100]
    
    print(f"  diff={diff:>10,} type={page_type}")
    print(f"  OCR: {ocr}")
    print(f"  VLM: {vlm}")
    
    if page_type != 'world' and page_type != 'unknown' or diff > 500000:
        hits.append((tag, desc, (x, y), diff, page_type, ocr))
        print(f"  >>> HIT! <<<")
    else:
        fails.append((tag, desc, diff, ocr))
    
    # 返回世界
    back()
    time.sleep(1.5)

# ── 汇总 ──
print(f"\n{'='*60}")
print(f"=== 结果汇总 ===")
print(f"\n✅ 命中 ({len(hits)}个):")
for tag, desc, coords, diff, ptype, ocr in hits:
    print(f"  {tag} {coords} diff={diff:,} type={ptype}")
    print(f"    OCR: {ocr[:80]}")

print(f"\n❌ 未命中 ({len(fails)}个):")
for item in fails:
    if len(item) == 4:
        tag, desc, diff, ocr = item
        print(f"  {tag} {desc} diff={diff:,}")
    else:
        print(f"  {item[0]} {item[1]}")

print("\nDone!")
