"""验证菜单面板内的坐标 - 先打开menu再测试base/character等"""
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
    d = cv2.absdiff(a, b)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)

# ====== TEST FLOW ======
# 1. Open menu (confirmed working)
# 2. Test base/character/inventory buttons on menu screen
# 3. After each test, close with back

# Menu panel coordinates to test (guesses based on typical UI layout)
menu_test_coords = [
    # Base/industry related
    ("base_entry", 997, 85, "基建入口 menu上"),
    ("base_alt", 665, 57, "基建备用 menu上"),
    ("base_mid", 960, 400, "基建中 menu上"),
    ("base_left", 400, 400, "基建左 menu上"),
    # Character
    ("char_portrait", 1200, 330, "角色 menu上"),
    ("char_alt", 800, 220, "角色备用 menu上"),
    ("char_mid", 640, 500, "角色中 menu上"),
    # Inventory/backpack
    ("inventory", 585, 22, "背包 menu上"),
    # Settings
    ("settings", 1200, 800, "设置 menu上"),
    # Quest
    ("quest_mid", 960, 300, "任务中 menu上"),
    # Events
    ("event_mid", 960, 500, "活动中 menu上"),
]

print("=" * 60, flush=True)
print("Verify menu panel coords", flush=True)
print("=" * 60, flush=True)

# Ensure in world
for attempt in range(5):
    img = cap()
    if img is None:
        print("ERROR: cant screenshot", flush=True)
        sys.exit(1)
    
    m = img.mean()
    print(f"Current mean={m:.1f}", flush=True)
    
    before = cap()
    tap(300, 80)
    time.sleep(2.5)
    after = cap()
    d = diff(before, after)
    
    if d > 500000:
        print(f"  World: diff={d:,}", flush=True)
        for _ in range(5):
            back()
            time.sleep(0.5)
        break
    else:
        print(f"  Not world diff={d:,}, back...", flush=True)
        for _ in range(8):
            back()
            time.sleep(0.3)
else:
    print("Force restart...", flush=True)
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'force-stop', 'com.hypergryph.endfield'],
                   capture_output=True, timeout=10)
    time.sleep(3)
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'start', '-n',
                    'com.hypergryph.endfield/com.u8.sdk.U8UnityContext'],
                   capture_output=True, timeout=10)
    time.sleep(35)
    for _ in range(5):
        tap(960, 540)
        time.sleep(4)
    time.sleep(25)

# ====== Phase 1: Open menu, test coords ======
results = []
MENU_X, MENU_Y = 1392, 79  # Confirmed menu button

for name, x, y, desc in menu_test_coords:
    # Step 1: Open menu
    print(f"\n[Open menu] ({MENU_X},{MENU_Y})", flush=True)
    tap(MENU_X, MENU_Y)
    time.sleep(3)
    
    menu_screen = cap()
    if menu_screen is None:
        continue
    menu_mean = menu_screen.mean()
    print(f"  Menu mean={menu_mean:.1f}", flush=True)
    cv2.imwrite(os.path.join(CACHE, f'menu_panel_{name}.png'), menu_screen)
    
    # Step 2: Test coordinate on menu
    before = cap()
    tap(x, y)
    time.sleep(2.5)
    after = cap()
    
    if before is None or after is None:
        # Go back to world
        for _ in range(3):
            back()
            time.sleep(1)
        continue
    
    d = diff(before, after)
    bm = before.mean()
    am = after.mean()
    
    tag = "BIG" if d > 800000 else ("MID" if d > 200000 else "low")
    
    print(f"  [{tag}] ({x:>4},{y:>3}) {name:20s} diff={d:>10,}  mean: {bm:.0f}->{am:.0f}  {desc}", flush=True)
    
    if d > 500000:
        cv2.imwrite(os.path.join(CACHE, f'menu_test_{name}_after.png'), after)
    
    results.append({
        "name": name, "x": x, "y": y, "diff": int(d),
        "before_mean": float(bm), "after_mean": float(am),
        "on_menu": True, "desc": desc
    })
    
    # Step 3: Back to world (multiple backs to exit menu)
    for _ in range(6):
        back()
        time.sleep(0.5)
    time.sleep(1)
    
    # Verify back to world
    check = cap()
    if check is not None:
        print(f"  After back: mean={check.mean():.1f}", flush=True)

# ====== Phase 2: Test bottom bar coords from world ======
print(f"\n\n{'='*40}", flush=True)
print("Phase 2: Bottom bar test (from world)", flush=True)
print(f"{'='*40}", flush=True)

bottom_coords = [
    ("btm_char1", 480, 930, "底部左1"),
    ("btm_char2", 640, 930, "底部左2"),
    ("btm_char3", 800, 930, "底部左3"),
    ("btm_char4", 960, 930, "底部中"),
    ("btm_char5", 1120, 930, "底部中右"),
    ("btm_char6", 1280, 930, "底部右1"),
    ("btm_char7", 1440, 930, "底部右2"),
    ("btm_char8", 1600, 930, "底部右3"),
]

for name, x, y, desc in bottom_coords:
    before = cap()
    if before is None:
        continue
    
    tap(x, y)
    time.sleep(2.5)
    
    after = cap()
    if after is None:
        continue
    
    d = diff(before, after)
    bm = before.mean()
    am = after.mean()
    
    tag = "BIG" if d > 800000 else ("MID" if d > 200000 else "low")
    
    print(f"[{tag}] ({x:>4},{y:>3}) {name:20s} diff={d:>10,}  mean: {bm:.0f}->{am:.0f}  {desc}", flush=True)
    
    if d > 500000:
        cv2.imwrite(os.path.join(CACHE, f'btm_test_{name}_after.png'), after)
    
    results.append({
        "name": name, "x": x, "y": y, "diff": int(d),
        "before_mean": float(bm), "after_mean": float(am),
        "on_menu": False, "desc": desc
    })
    
    for _ in range(6):
        back()
        time.sleep(0.5)
    time.sleep(1)

# Save
out = os.path.join(CACHE, 'verify_menu_coords.json')
with open(out, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n\nSaved: {out}", flush=True)

print("\n=== BIG results ===", flush=True)
for r in results:
    if r['diff'] > 800000:
        print(f"  [{r['diff']//1000}k] ({r['x']},{r['y']}) {r['name']} {r['desc']}", flush=True)

print("\nDone", flush=True)
