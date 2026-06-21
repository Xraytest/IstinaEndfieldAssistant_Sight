"""重启到world -> 打开menu -> 金色检测找base/character按钮"""
import subprocess, time, os, cv2, numpy as np, json, sys

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(PROJECT, 'cache')
os.makedirs(CACHE, exist_ok=True)
from standard_flow_engine import ScreenAnalyzer

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

def restart_to_world():
    """Force restart and reach world"""
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'force-stop', 'com.hypergryph.endfield'],
                   capture_output=True, timeout=10)
    time.sleep(3)
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'start', '-n',
                    'com.hypergryph.endfield/com.u8.sdk.U8UnityContext'],
                   capture_output=True, timeout=10)
    
    # Wait for title screen
    for i in range(20):
        time.sleep(3)
        img = cap()
        if img is not None and img.mean() > 50 and img.std() > 30:
            break
    
    # Tap to enter
    for _ in range(5):
        tap(960, 540)
        time.sleep(4)
    
    # Wait for world
    for i in range(25):
        time.sleep(3)
        img = cap()
        if img is not None:
            m = img.mean()
            if m > 80 and img.std() > 50:
                # Verify world
                before = cap()
                tap(300, 80)
                time.sleep(2.5)
                after = cap()
                d = diff(before, after)
                if d > 500000:
                    for _ in range(5):
                        back()
                        time.sleep(0.5)
                    return True
    
    return False


print("=" * 60, flush=True)
print("Find menu buttons", flush=True)
print("=" * 60, flush=True)

# Step 1: Restart to world
print("\nStep 1: Restart to world...", flush=True)
if not restart_to_world():
    print("ERROR: Cannot reach world", flush=True)
    sys.exit(1)

world = cap()
print(f"World: mean={world.mean():.1f}", flush=True)
cv2.imwrite(os.path.join(CACHE, 'menu_world_before.png'), world)

# Step 2: Open menu
print("\nStep 2: Open menu (1392, 79)...", flush=True)
tap(1392, 79)
time.sleep(3)

menu = cap()
print(f"Menu: mean={menu.mean():.1f}", flush=True)
cv2.imwrite(os.path.join(CACHE, 'menu_panel.png'), menu)

# Step 3: Golden element detection on menu
print("\nStep 3: Golden detection on menu...", flush=True)
analyzer = ScreenAnalyzer()
golden = analyzer._detect_golden(menu)

print(f"Golden elements: {len(golden)}", flush=True)
# Sort by area descending
golden.sort(key=lambda g: g['area'], reverse=True)

print("\nTop golden elements:", flush=True)
for g in golden[:20]:
    region = ""
    if g['cy'] < 200:
        region = "[TOP]"
    elif g['cy'] > 800:
        region = "[BTM]"
    elif g['cy'] > 500:
        region = "[MID-BTM]"
    elif g['cy'] > 200:
        region = "[MID]"
    print(f"  ({g['cx']:>4},{g['cy']:>4}) {g['w']:>4}x{g['h']:>4} area={g['area']:>8.1f} {g['range']} {region}", flush=True)

# Step 4: Test each promising golden element
print("\nStep 4: Test golden buttons...", flush=True)

# Filter for likely button-sized elements (area > 200, w*h reasonable)
button_candidates = [g for g in golden if g['area'] > 500 and 20 < g['w'] < 400 and 20 < g['h'] < 200]

# Also include specific regions of interest
interesting_regions = {
    "left_mid": lambda g: g['cx'] < 600 and 200 < g['cy'] < 600,
    "center": lambda g: 600 < g['cx'] < 1300 and 200 < g['cy'] < 600,
    "right_mid": lambda g: g['cx'] > 1300 and 200 < g['cy'] < 600,
    "bottom": lambda g: g['cy'] > 700,
}

results = []
for g in button_candidates[:15]:
    x, y = g['cx'], g['cy']
    
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
        cv2.imwrite(os.path.join(CACHE, f'menu_btn_{g[\"cx\"]}_{g[\"cy\"]}_after.png'), after)
    
    results.append({"x": x, "y": y, "area": g['area'], "diff": int(d), "range": g['range']})
    
    # Back to menu
    for _ in range(3):
        back()
        time.sleep(0.5)

# Also test bottom bar positions from world
print("\nStep 5: Close menu and test bottom bar...", flush=True)
for _ in range(5):
    back()
    time.sleep(0.5)

world2 = cap()
print(f"Back to world: mean={world2.mean():.1f}" if world2 is not None else "Failed", flush=True)

# Test bottom bar with finer granularity
print("\nBottom bar fine scan (Y=930, step=60)...", flush=True)
for x in range(300, 1800, 60):
    before = cap()
    if before is None:
        continue
    
    tap(x, 930)
    time.sleep(2.5)
    
    after = cap()
    if after is None:
        continue
    
    d = diff(before, after)
    
    if d > 300000:
        tag = f"[BIG:{d//1000}k]" if d > 800000 else f"[MID:{d//1000}k]"
        print(f"  {tag} ({x:>4},930) diff={d:>10,}", flush=True)
        if d > 500000:
            cv2.imwrite(os.path.join(CACHE, f'btm_fine_x{x}.png'), after)
        results.append({"x": x, "y": 930, "diff": int(d), "area": 0, "range": "bottom_bar"})
    
    for _ in range(4):
        back()
        time.sleep(0.3)

# Save results
out = os.path.join(CACHE, 'find_menu_buttons.json')
with open(out, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\nSaved: {out}", flush=True)
print("Done", flush=True)
