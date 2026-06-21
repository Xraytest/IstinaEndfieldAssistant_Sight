"""精准定位: world上的quest/event图标 + 菜单上的大金色元素"""
import subprocess, time, cv2, numpy as np, os, json, sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(PROJECT, 'cache')
os.makedirs(CACHE, exist_ok=True)

T1 = os.path.join(CACHE, '_p1.png')
T2 = os.path.join(CACHE, '_p2.png')

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True, timeout=10)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], capture_output=True, timeout=5)

def cap(path):
    with open(path, 'wb') as f:
        subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       stdout=f, stderr=subprocess.PIPE, timeout=15)
    img = cv2.imread(path)
    return img if (img is not None and img.mean() > 0.5) else None

def diff_files(a_path, b_path):
    a = cv2.imread(a_path)
    b = cv2.imread(b_path)
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
        if area < 50:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        cx, cy = x + w//2, y + h//2
        elements.append({'cx': cx, 'cy': cy, 'w': w, 'h': h, 'area': area})
    elements.sort(key=lambda e: e['area'], reverse=True)
    return elements

def restart_to_world():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'force-stop', 'com.hypergryph.endfield'],
                   capture_output=True, timeout=10)
    time.sleep(3)
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'start', '-n',
                    'com.hypergryph.endfield/com.u8.sdk.U8UnityContext'],
                   capture_output=True, timeout=10)
    
    for i in range(20):
        time.sleep(3)
        img = cap(T1)
        if img is not None and img.mean() > 50 and img.std() > 30:
            break
    
    for _ in range(5):
        tap(960, 540)
        time.sleep(4)
    
    for i in range(25):
        time.sleep(3)
        img = cap(T1)
        if img is not None and img.mean() > 80 and img.std() > 50:
            before = cap(T1)
            if before is None:
                continue
            tap(300, 80)
            time.sleep(2.5)
            after = cap(T2)
            if after is None:
                continue
            d = diff_files(T1, T2)
            if d > 500000:
                for _ in range(5):
                    back()
                    time.sleep(0.5)
                time.sleep(2)
                return cap(T1)
    return None

def ensure_world():
    """确保在world，如果不是则back尝试返回"""
    for attempt in range(5):
        img = cap(T1)
        if img is None:
            continue
        if img.mean() > 50 and img.mean() < 130:
            # 验证是否world
            before = cap(T1)
            if before is None:
                continue
            tap(300, 80)
            time.sleep(2.5)
            after = cap(T2)
            if after is None:
                continue
            d = diff_files(T1, T2)
            if d > 500000:
                for _ in range(5):
                    back()
                    time.sleep(0.5)
                time.sleep(1)
                return True
        # 不在world，back尝试
        for _ in range(5):
            back()
            time.sleep(0.5)
    return False

def ensure_on_menu():
    """确保在菜单上"""
    for attempt in range(5):
        img = cap(T1)
        if img is None:
            continue
        m = img.mean()
        if 100 < m < 200:
            return img, m
        for _ in range(3):
            back()
            time.sleep(0.5)
        tap(1392, 79)
        time.sleep(3)
    return None, 0

# ====== MAIN ======
print("=" * 60, flush=True)
print("Precision Navigation Test", flush=True)
print("=" * 60, flush=True)

results = []

# Phase 1: 重启到world
print("\n[P1] Restart to world...", flush=True)
world = restart_to_world()
if world is None:
    print("FATAL", flush=True)
    sys.exit(1)
print(f"World: mean={world.mean():.1f}", flush=True)
cv2.imwrite(os.path.join(CACHE, 'prec_world.png'), world)

# Phase 2: 精确定位quest图标 (在855,33附近细扫)
print("\n[P2] Fine scan quest icon area...", flush=True)
# quest_icon was (855,33) with ~250k MID
# Let's scan X:830-890, Y:25-55 with fine step
for x in range(830, 891, 10):
    for y in range(25, 56, 8):
        if not ensure_world():
            world = restart_to_world()
            if world is None:
                continue
        
        before = cap(T1)
        if before is None:
            continue
        
        tap(x, y)
        time.sleep(2.5)
        
        after = cap(T2)
        if after is None:
            for _ in range(3):
                back()
                time.sleep(0.5)
            continue
        
        d = diff_files(T1, T2)
        
        if d > 300000:
            tag = "BIG" if d > 800000 else "MID"
            print(f"  [{tag}] ({x:>4},{y:>3}) quest diff={d:>10,}", flush=True)
            if d > 500000:
                cv2.imwrite(os.path.join(CACHE, f'prec_quest_{x}_{y}.png'), after)
                results.append({"type": "quest", "x": x, "y": y, "diff": int(d), "tag": tag})
        
        # 返回world
        for _ in range(4):
            back()
            time.sleep(0.3)
        time.sleep(0.5)

# Phase 3: 精确定位event图标 (在928,53附近细扫)
print("\n[P3] Fine scan event icon area...", flush=True)
for x in range(910, 951, 8):
    for y in range(40, 71, 8):
        if not ensure_world():
            world = restart_to_world()
            if world is None:
                continue
        
        before = cap(T1)
        if before is None:
            continue
        
        tap(x, y)
        time.sleep(2.5)
        
        after = cap(T2)
        if after is None:
            for _ in range(3):
                back()
                time.sleep(0.5)
            continue
        
        d = diff_files(T1, T2)
        
        if d > 300000:
            tag = "BIG" if d > 800000 else "MID"
            print(f"  [{tag}] ({x:>4},{y:>3}) event diff={d:>10,}", flush=True)
            if d > 500000:
                cv2.imwrite(os.path.join(CACHE, f'prec_event_{x}_{y}.png'), after)
                results.append({"type": "event", "x": x, "y": y, "diff": int(d), "tag": tag})
        
        for _ in range(4):
            back()
            time.sleep(0.3)
        time.sleep(0.5)

# Phase 4: 打开菜单，测试大金色元素
print("\n[P4] Open menu and test large golden elements...", flush=True)
tap(1392, 79)
time.sleep(3)
menu, menu_mean = ensure_on_menu()
if menu is None:
    print("FATAL: Cannot open menu", flush=True)
    sys.exit(1)
print(f"Menu: mean={menu_mean:.1f}", flush=True)

golden = detect_golden(menu)
print(f"Golden elements: {len(golden)}", flush=True)

# Test top 12 golden elements (sorted by area)
# Focus on elements that are likely UI buttons (not the huge decorative elements)
# Filter: ignore elements with extreme w>500 or h>150 unless they're in key areas
for g in golden[:12]:
    x, y = g['cx'], g['cy']
    area = g['area']
    w, h = g['w'], g['h']
    
    # Re-ensure menu
    ensure_on_menu()
    
    before = cap(T1)
    if before is None:
        continue
    
    tap(x, y)
    time.sleep(2.5)
    
    after = cap(T2)
    if after is None:
        for _ in range(3):
            back()
            time.sleep(0.5)
        continue
    
    d = diff_files(T1, T2)
    tag = "BIG" if d > 800000 else ("MID" if d > 200000 else "low")
    
    print(f"  [{tag}] ({x:>4},{y:>4}) {w}x{h} area={area:.0f} diff={d:>10,}", flush=True)
    
    if d > 300000:
        cv2.imwrite(os.path.join(CACHE, f'prec_golden_{x}_{y}.png'), after)
        results.append({"type": "menu_golden", "x": x, "y": y, "w": w, "h": h, "area": float(area), "diff": int(d), "tag": tag})
    
    # Return to menu
    for _ in range(3):
        back()
        time.sleep(0.5)
    time.sleep(1)
    ensure_on_menu()

# Phase 5: 测试menu上的关键坐标 (基于金色元素推断)
print("\n[P5] Test specific menu positions...", flush=True)
menu_test_points = [
    # 基于 golden 元素分布推测的菜单按钮
    ("mid_left_1", 400, 267),   # 靠近 (272,267) 大金色元素
    ("mid_left_2", 500, 267),
    ("mid_left_3", 350, 400),   # 靠近 (637,402)
    ("mid_left_4", 500, 400),
    ("mid_left_5", 650, 400),
    ("top_mid", 769, 78),       # (769,78) 金色元素
    ("mid_right", 1435, 311),   # (1435,311) 巨大金色条
    ("bottom", 1562, 1065),     # (1562,1065) 底部金色条
]

for name, x, y in menu_test_points:
    ensure_on_menu()
    
    before = cap(T1)
    if before is None:
        continue
    
    tap(x, y)
    time.sleep(2.5)
    
    after = cap(T2)
    if after is None:
        for _ in range(3):
            back()
            time.sleep(0.5)
        continue
    
    d = diff_files(T1, T2)
    tag = "BIG" if d > 800000 else ("MID" if d > 200000 else "low")
    
    print(f"  [{tag}] ({x:>4},{y:>4}) {name:20s} diff={d:>10,}", flush=True)
    
    if d > 300000:
        cv2.imwrite(os.path.join(CACHE, f'prec_menu_{name}.png'), after)
        results.append({"type": "menu_position", "name": name, "x": x, "y": y, "diff": int(d), "tag": tag})
    
    for _ in range(3):
        back()
        time.sleep(0.5)
    time.sleep(1)

# Save
out = os.path.join(CACHE, 'precision_results.json')
with open(out, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n{'='*60}", flush=True)
print(f"Results: {out}", flush=True)
print(f"\nBIG hits (>800k):", flush=True)
big = [r for r in results if r.get('diff', 0) > 800000]
for r in sorted(big, key=lambda x: x['diff'], reverse=True):
    print(f"  [{r['diff']//1000}k] ({r.get('x','?')},{r.get('y','?')}) {r.get('type','?')} {r.get('name','?')}", flush=True)

print(f"\nMID hits (300-800k):", flush=True)
mid = [r for r in results if 300000 < r.get('diff', 0) <= 800000]
for r in sorted(mid, key=lambda x: x['diff'], reverse=True):
    print(f"  [{r['diff']//1000}k] ({r.get('x','?')},{r.get('y','?')}) {r.get('type','?')} {r.get('name','?')}", flush=True)

print("\nDone", flush=True)
