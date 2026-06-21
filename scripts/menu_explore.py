"""一体化: 重启到world -> 打开menu -> 金色检测 -> 测试按钮 -> 底部栏"""
import subprocess, time, os, cv2, numpy as np, json, sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(PROJECT, 'cache')
os.makedirs(CACHE, exist_ok=True)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True, timeout=10)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], capture_output=True, timeout=5)

def cap():
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], capture_output=True, timeout=15)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def diff(a, b):
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
    """重启并到达world，返回world截图"""
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'force-stop', 'com.hypergryph.endfield'],
                   capture_output=True, timeout=10)
    time.sleep(3)
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'start', '-n',
                    'com.hypergryph.endfield/com.u8.sdk.U8UnityContext'],
                   capture_output=True, timeout=10)

    # 等待标题画面
    for i in range(15):
        time.sleep(3)
        img = cap()
        if img is not None and img.mean() > 50 and img.std() > 30:
            print(f"  Title screen at {i*3}s: mean={img.mean():.0f}", flush=True)
            break

    # 点击进入游戏
    for _ in range(5):
        tap(960, 540)
        time.sleep(4)

    # 等待world
    for i in range(20):
        time.sleep(3)
        img = cap()
        if img is not None:
            m = img.mean()
            if m > 80 and img.std() > 50:
                before = cap()
                tap(300, 80)
                time.sleep(2.5)
                after = cap()
                d = diff(before, after)
                if d > 500000:
                    print(f"  World at {i*3}s: diff={d:,}", flush=True)
                    for _ in range(5):
                        back()
                        time.sleep(0.5)
                    time.sleep(2)
                    return cap()
    print("  ERROR: Cannot reach world", flush=True)
    return None

# ====== MAIN ======
print("=" * 60, flush=True)
print("Menu Explorer - 一体化菜单面板分析", flush=True)
print("=" * 60, flush=True)

# Phase 1: 重启到world
print("\n[Phase 1] Restart to world...", flush=True)
world = restart_to_world()
if world is None:
    sys.exit(1)
print(f"World: mean={world.mean():.1f}", flush=True)
cv2.imwrite(os.path.join(CACHE, 'mexp_world.png'), world)

# Phase 2: 打开菜单
print("\n[Phase 2] Open menu (1392, 79)...", flush=True)
tap(1392, 79)
time.sleep(3)
menu = cap()
if menu is None:
    print("ERROR: menu screenshot failed", flush=True)
    sys.exit(1)
print(f"Menu: mean={menu.mean():.1f}", flush=True)
cv2.imwrite(os.path.join(CACHE, 'mexp_menu.png'), menu)

# Phase 3: 金色检测
print("\n[Phase 3] Golden element detection...", flush=True)
golden = detect_golden(menu)
print(f"Found {len(golden)} golden elements", flush=True)
for g in golden[:30]:
    region = "TOP" if g['cy'] < 200 else ("BTM" if g['cy'] > 800 else ("MID-BTM" if g['cy'] > 500 else "MID"))
    print(f"  ({g['cx']:>4},{g['cy']:>4}) {g['w']:>4}x{g['h']:>4} area={g['area']:>8.0f} [{region}]", flush=True)

# Phase 4: 测试金色按钮（大区域优先）
results = []
print("\n[Phase 4] Test golden buttons on menu...", flush=True)
tested = set()
for g in golden[:15]:
    x, y = g['cx'], g['cy']
    # 去重（相近坐标）
    key = (x // 30, y // 30)
    if key in tested:
        continue
    tested.add(key)

    # 确保还在menu上
    check = cap()
    if check is None or abs(check.mean() - menu.mean()) > 25:
        print(f"  [RECOVER] menu偏离, 重新打开...", flush=True)
        for _ in range(3):
            back()
            time.sleep(0.5)
        tap(1392, 79)
        time.sleep(3)

    before = cap()
    if before is None:
        continue

    tap(x, y)
    time.sleep(2.5)

    after = cap()
    if after is None:
        continue

    d = diff(before, after)
    tag = "BIG" if d > 800000 else ("MID" if d > 200000 else "low")

    print(f"  [{tag}] ({x:>4},{y:>4}) area={g['area']:.0f} diff={d:>10,}", flush=True)

    if d > 500000:
        cv2.imwrite(os.path.join(CACHE, f'mexp_golden_{x}_{y}.png'), after)
        results.append({"source": "golden", "x": x, "y": y, "area": float(g['area']), "diff": int(d), "tag": tag})

    # 返回menu
    for _ in range(4):
        back()
        time.sleep(0.5)
    time.sleep(1)

# Phase 5: 测试flows_config中的坐标（在menu上）
print("\n[Phase 5] Test flows_config coords on menu...", flush=True)
flow_coords = [
    ("base_entry", 997, 85),
    ("base_alt", 665, 57),
    ("char_portrait", 1200, 330),
    ("char_alt", 800, 220),
    ("center", 960, 540),
    ("left_mid", 400, 400),
    ("right_mid", 1400, 400),
    ("inventory", 585, 22),
]

for name, x, y in flow_coords:
    check = cap()
    if check is None or abs(check.mean() - menu.mean()) > 25:
        for _ in range(3):
            back()
            time.sleep(0.5)
        tap(1392, 79)
        time.sleep(3)

    before = cap()
    if before is None:
        continue

    tap(x, y)
    time.sleep(2.5)

    after = cap()
    if after is None:
        continue

    d = diff(before, after)
    tag = "BIG" if d > 800000 else ("MID" if d > 200000 else "low")

    print(f"  [{tag}] ({x:>4},{y:>4}) {name:20s} diff={d:>10,}", flush=True)

    if d > 500000:
        cv2.imwrite(os.path.join(CACHE, f'mexp_flow_{name}.png'), after)
        results.append({"source": "flow_config", "name": name, "x": x, "y": y, "diff": int(d), "tag": tag})

    for _ in range(4):
        back()
        time.sleep(0.5)
    time.sleep(1)

# Phase 6: 关闭menu，测试底部栏
print("\n[Phase 6] Close menu, test bottom bar from world...", flush=True)
for _ in range(5):
    back()
    time.sleep(0.5)
time.sleep(2)

world2 = cap()
world_mean = world2.mean() if world2 is not None else 0
print(f"Back to world: mean={world_mean:.1f}", flush=True)

print("Testing bottom bar Y=930...", flush=True)
for x in range(240, 1800, 60):
    before = cap()
    if before is None:
        continue

    tap(x, 930)
    time.sleep(2.5)

    after = cap()
    if after is None:
        continue

    d = diff(before, after)

    if d > 200000:
        tag = "BIG" if d > 800000 else "MID"
        print(f"  [{tag}] ({x:>4},930) diff={d:>10,}", flush=True)
        if d > 500000:
            cv2.imwrite(os.path.join(CACHE, f'mexp_btm_x{x}.png'), after)
            results.append({"source": "bottom_bar", "x": x, "y": 930, "diff": int(d), "tag": tag})

    for _ in range(4):
        back()
        time.sleep(0.3)
    time.sleep(0.5)

# Phase 7: 从world测试quest/event图标
print("\n[Phase 7] Test quest/event icons from world...", flush=True)
world_coords = [
    ("quest_icon", 855, 33),
    ("quest_y40", 855, 40),
    ("quest_y50", 855, 50),
    ("quest_y60", 855, 60),
    ("event_icon", 928, 53),
    ("event_y40", 928, 40),
    ("event_y60", 928, 60),
    ("event_y70", 928, 70),
]

for name, x, y in world_coords:
    before = cap()
    if before is None:
        continue

    tap(x, y)
    time.sleep(2.5)

    after = cap()
    if after is None:
        continue

    d = diff(before, after)
    tag = "BIG" if d > 800000 else ("MID" if d > 200000 else "low")

    print(f"  [{tag}] ({x:>4},{y:>4}) {name:20s} diff={d:>10,}", flush=True)

    if d > 500000:
        cv2.imwrite(os.path.join(CACHE, f'mexp_world_{name}.png'), after)
        results.append({"source": "world_icon", "name": name, "x": x, "y": y, "diff": int(d), "tag": tag})

    for _ in range(5):
        back()
        time.sleep(0.3)
    time.sleep(1)

# Save
out = os.path.join(CACHE, 'menu_explore.json')
with open(out, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n{'='*60}", flush=True)
print(f"Results saved: {out}", flush=True)
print(f"\nBIG results (>{800000:,} diff):", flush=True)
for r in results:
    if r.get('diff', 0) > 800000:
        src = r.get('source', '?')
        name = r.get('name', '')
        print(f"  [{r['diff']//1000}k] ({r['x']},{r['y']}) {src} {name}", flush=True)

print(f"\nMID results (200k-800k diff):", flush=True)
for r in results:
    d = r.get('diff', 0)
    if 200000 < d <= 800000:
        src = r.get('source', '?')
        name = r.get('name', '')
        print(f"  [{d//1000}k] ({r['x']},{r['y']}) {src} {name}", flush=True)

print("\nDone", flush=True)
