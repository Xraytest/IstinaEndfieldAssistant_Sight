"""菜单探索 v2 - 使用shell重定向截图 (可靠) + 去重黑屏"""
import subprocess, time, os, cv2, numpy as np, json, sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(PROJECT, 'cache')
os.makedirs(CACHE, exist_ok=True)

TMP1 = os.path.join(CACHE, '_t1.png')
TMP2 = os.path.join(CACHE, '_t2.png')

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True, timeout=10)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], capture_output=True, timeout=5)

def cap(out_path):
    """使用shell重定向截图 (可靠)"""
    with open(out_path, 'wb') as f:
        subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       stdout=f, timeout=15)
    img = cv2.imread(out_path)
    if img is not None and img.mean() > 0.5:
        return img
    return None

def cap_safe(retries=3):
    """截图并自动重试黑屏"""
    for i in range(retries):
        img = cap(TMP1)
        if img is not None and img.mean() > 0.5:
            return img
        time.sleep(0.5)
    return None

def diff_file(a_path, b_path):
    a = cv2.imread(a_path)
    b = cv2.imread(b_path)
    if a is None or b is None:
        return 0
    d = cv2.absdiff(a, b)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)

def diff_img(a, b):
    if a is None or b is None:
        return 0
    d = cv2.absdiff(a, b)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)

def detect_golden(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower = np.array([15, 30, 80])
    upper = np.array([45, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    elements = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 30:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        cx, cy = x + w//2, y + h//2
        elements.append({'cx': cx, 'cy': cy, 'w': w, 'h': h, 'area': area})
    elements.sort(key=lambda e: e['area'], reverse=True)
    return elements

def restart_to_world():
    """重启并到达world"""
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'force-stop', 'com.hypergryph.endfield'],
                   capture_output=True, timeout=10)
    time.sleep(3)
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'start', '-n',
                    'com.hypergryph.endfield/com.u8.sdk.U8UnityContext'],
                   capture_output=True, timeout=10)
    
    for i in range(20):
        time.sleep(3)
        img = cap_safe()
        if img is not None and img.mean() > 50 and img.std() > 30:
            print(f"  Title at {i*3}s: mean={img.mean():.0f}", flush=True)
            break
    
    for _ in range(5):
        tap(960, 540)
        time.sleep(4)
    
    for i in range(25):
        time.sleep(3)
        img = cap_safe()
        if img is not None:
            m = img.mean()
            if m > 80 and img.std() > 50:
                # Verify world
                before = cap_safe()
                if before is None:
                    continue
                cv2.imwrite(TMP2, before)
                tap(300, 80)
                time.sleep(2.5)
                after = cap_safe()
                if after is None:
                    continue
                d = diff_img(before, after)
                if d > 500000:
                    print(f"  World at {i*3}s: diff={d:,}", flush=True)
                    for _ in range(5):
                        back()
                        time.sleep(0.5)
                    time.sleep(2)
                    world = cap_safe()
                    return world
    return None

def ensure_on_menu(menu_mean, menu_std):
    """确保在菜单面板上，如偏离则重新打开"""
    for attempt in range(3):
        check = cap_safe()
        if check is None:
            continue
        m = check.mean()
        # 如果均值与menu基线接近，认为在menu
        if abs(m - menu_mean) < 30 and check.std() > 30:
            return check
        # 否则back后重新打开menu
        print(f"  [RECOVER] mean={m:.0f} != menu({menu_mean:.0f}), reopen...", flush=True)
        for _ in range(3):
            back()
            time.sleep(0.5)
        tap(1392, 79)
        time.sleep(3)
    return cap_safe()

# ====== MAIN ======
print("=" * 60, flush=True)
print("Menu Explorer v2 - shell redirect capt + black retry", flush=True)
print("=" * 60, flush=True)

# Phase 1: 重启到world
print("\n[P1] Restart to world...", flush=True)
world = restart_to_world()
if world is None:
    print("FATAL: Cannot reach world", flush=True)
    sys.exit(1)
world_mean = world.mean()
world_std = world.std()
print(f"World: mean={world_mean:.1f} std={world_std:.1f}", flush=True)
cv2.imwrite(os.path.join(CACHE, 'mev2_world.png'), world)

# Phase 2: 打开菜单
print("\n[P2] Open menu (1392, 79)...", flush=True)
tap(1392, 79)
time.sleep(3)
menu = cap_safe()
if menu is None:
    print("FATAL: Menu screenshot failed", flush=True)
    sys.exit(1)
menu_mean = menu.mean()
menu_std = menu.std()
print(f"Menu: mean={menu_mean:.1f} std={menu_std:.1f}", flush=True)
cv2.imwrite(os.path.join(CACHE, 'mev2_menu.png'), menu)

# Phase 3: 金色检测
print("\n[P3] Golden element detection...", flush=True)
golden = detect_golden(menu)
print(f"Found {len(golden)} golden elements", flush=True)
for g in golden[:30]:
    region = "TOP" if g['cy'] < 200 else ("BTM" if g['cy'] > 800 else ("MID-BTM" if g['cy'] > 500 else "MID"))
    print(f"  ({g['cx']:>4},{g['cy']:>4}) {g['w']:>4}x{g['h']:>4} area={g['area']:>8.0f} [{region}]", flush=True)

# Phase 4: 测试金色按钮
results = []
print("\n[P4] Test golden buttons...", flush=True)
tested = set()
for g in golden[:20]:
    x, y = g['cx'], g['cy']
    key = (x // 40, y // 40)
    if key in tested:
        continue
    tested.add(key)
    
    # 确保在menu上
    ensure_on_menu(menu_mean, menu_std)
    
    before = cap_safe()
    if before is None:
        continue
    cv2.imwrite(TMP1, before)
    
    tap(x, y)
    time.sleep(2.5)
    
    after = cap_safe()
    if after is None:
        continue
    cv2.imwrite(TMP2, after)
    
    # 验证before/after都不是黑屏
    if before.mean() < 0.5:
        print(f"  [SKIP] before black", flush=True)
        continue
    if after.mean() < 0.5:
        print(f"  [SKIP] after black", flush=True)
        continue
    
    d = diff_file(TMP1, TMP2)
    tag = "BIG" if d > 800000 else ("MID" if d > 200000 else "low")
    
    print(f"  [{tag}] ({x:>4},{y:>4}) area={g['area']:.0f} diff={d:>10,}  bm={before.mean():.0f}->am={after.mean():.0f}", flush=True)
    
    if d > 500000:
        cv2.imwrite(os.path.join(CACHE, f'mev2_golden_{x}_{y}.png'), after)
        results.append({"source": "golden", "x": x, "y": y, "area": float(g['area']), "diff": int(d), "tag": tag})
    
    for _ in range(3):
        back()
        time.sleep(0.5)
    time.sleep(1)

# Phase 5: 测试flows_config坐标 (menu上)
print("\n[P5] Test flows_config coords ON MENU...", flush=True)
flow_coords = [
    ("base_entry", 997, 85),
    ("base_665_57", 665, 57),
    ("base_700_80", 700, 80),
    ("base_800_100", 800, 100),
    ("base_900_60", 900, 60),
    ("char_portrait", 1200, 330),
    ("char_800_220", 800, 220),
    ("char_1000_220", 1000, 220),
    ("char_600_400", 600, 400),
    ("char_800_400", 800, 400),
    ("inventory_585", 585, 22),
    ("inventory_500_40", 500, 40),
    ("settings_1800_50", 1800, 50),
    ("settings_1700_50", 1700, 50),
]

for name, x, y in flow_coords:
    ensure_on_menu(menu_mean, menu_std)
    
    before = cap_safe()
    if before is None:
        continue
    cv2.imwrite(TMP1, before)
    
    tap(x, y)
    time.sleep(2.5)
    
    after = cap_safe()
    if after is None:
        continue
    cv2.imwrite(TMP2, after)
    
    if before.mean() < 0.5 or after.mean() < 0.5:
        print(f"  [SKIP] {name} black screen", flush=True)
        continue
    
    d = diff_file(TMP1, TMP2)
    tag = "BIG" if d > 800000 else ("MID" if d > 200000 else "low")
    
    print(f"  [{tag}] ({x:>4},{y:>4}) {name:22s} diff={d:>10,}  bm={before.mean():.0f}->am={after.mean():.0f}", flush=True)
    
    if d > 300000:
        cv2.imwrite(os.path.join(CACHE, f'mev2_flow_{name}.png'), after)
        results.append({"source": "flow_config", "name": name, "x": x, "y": y, "diff": int(d), "tag": tag})
    
    for _ in range(3):
        back()
        time.sleep(0.5)
    time.sleep(1)

# Phase 6: 关闭menu, 测试world上的quest/event
print("\n[P6] Back to world, test quest/event...", flush=True)
for _ in range(10):
    back()
    time.sleep(0.5)
time.sleep(2)

world2 = cap_safe()
if world2 is not None:
    w2_mean = world2.mean()
    print(f"After back: mean={w2_mean:.1f}", flush=True)
    
    # 验证是否在world
    before = cap_safe()
    if before is not None:
        cv2.imwrite(TMP1, before)
        tap(300, 80)
        time.sleep(2.5)
        after = cap_safe()
        if after is not None:
            cv2.imwrite(TMP2, after)
            d = diff_file(TMP1, TMP2)
            if d > 500000:
                print(f"  World confirmed: diff={d:,}", flush=True)
                for _ in range(5):
                    back()
                    time.sleep(0.5)
                time.sleep(1)
            else:
                print(f"  NOT world (diff={d:,}), restarting...", flush=True)
                world2 = restart_to_world()
                if world2 is None:
                    print("FATAL", flush=True)
                    sys.exit(1)
    
    # Test quest/event
    world_icons = [
        ("quest_icon", 855, 33),
        ("quest_855_40", 855, 40),
        ("quest_860_35", 860, 35),
        ("quest_850_35", 850, 35),
        ("event_icon", 928, 53),
        ("event_928_45", 928, 45),
        ("event_928_60", 928, 60),
        ("event_935_55", 935, 55),
        ("event_920_50", 920, 50),
    ]
    
    for name, x, y in world_icons:
        before = cap_safe()
        if before is None:
            continue
        cv2.imwrite(TMP1, before)
        
        tap(x, y)
        time.sleep(2.5)
        
        after = cap_safe()
        if after is None:
            continue
        cv2.imwrite(TMP2, after)
        
        if before.mean() < 0.5 or after.mean() < 0.5:
            continue
        
        d = diff_file(TMP1, TMP2)
        tag = "BIG" if d > 800000 else ("MID" if d > 200000 else "low")
        
        print(f"  [{tag}] ({x:>4},{y:>4}) {name:22s} diff={d:>10,}  bm={before.mean():.0f}->am={after.mean():.0f}", flush=True)
        
        if d > 300000:
            cv2.imwrite(os.path.join(CACHE, f'mev2_icon_{name}.png'), after)
            results.append({"source": "world_icon", "name": name, "x": x, "y": y, "diff": int(d), "tag": tag})
        
        for _ in range(4):
            back()
            time.sleep(0.3)
        time.sleep(1)

# Save
out = os.path.join(CACHE, 'menu_explore_v2.json')
with open(out, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n{'='*60}", flush=True)
print(f"Results: {out}", flush=True)
print(f"\nBIG >800k:", flush=True)
big = [r for r in results if r.get('diff', 0) > 800000]
if big:
    for r in sorted(big, key=lambda x: x['diff'], reverse=True):
        print(f"  [{r['diff']//1000}k] ({r.get('x','?')},{r.get('y','?')}) {r.get('source','?')} {r.get('name','?')}", flush=True)
else:
    print("  (none)", flush=True)

print(f"\nMID 200-800k:", flush=True)
mid = [r for r in results if 200000 < r.get('diff', 0) <= 800000]
if mid:
    for r in sorted(mid, key=lambda x: x['diff'], reverse=True):
        print(f"  [{r['diff']//1000}k] ({r.get('x','?')},{r.get('y','?')}) {r.get('source','?')} {r.get('name','?')}", flush=True)
else:
    print("  (none)", flush=True)

print("\nDone", flush=True)
