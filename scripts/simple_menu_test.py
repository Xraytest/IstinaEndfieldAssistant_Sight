"""简化版 - 重启后打开menu + 简单金色检测 + 测试按钮"""
import subprocess, time, os, cv2, numpy as np, json

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

def pixel_diff(a, b):
    if a is None or b is None:
        return 0
    d = cv2.absdiff(a, b)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)

def detect_golden_simple(img):
    """Simple golden element detection using HSV"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # Golden range
    lower = np.array([15, 30, 80])
    upper = np.array([45, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    
    # Find contours
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

# ====== MAIN ======
print("=" * 50, flush=True)
print("Simple menu button test", flush=True)
print("=" * 50, flush=True)

# Wait for game to be ready (assumes restart_game.py already ran)
print("\nWaiting for game...", flush=True)
for i in range(40):
    img = cap()
    if img is not None:
        m = img.mean()
        if m > 80 and img.std() > 50:
            print(f"  Ready: mean={m:.1f}", flush=True)
            break
    time.sleep(3)
else:
    print("ERROR: Game not ready", flush=True)
    exit(1)

# Check world
before = cap()
tap(300, 80)
time.sleep(2.5)
after = cap()
d = pixel_diff(before, after)
print(f"World check: diff={d:,}", flush=True)
for _ in range(5):
    back()
    time.sleep(0.5)

world = cap()
print(f"World mean={world.mean():.1f}", flush=True)
cv2.imwrite(os.path.join(CACHE, 'simple_world.png'), world)

# Open menu
print("\nOpen menu (1392, 79)...", flush=True)
tap(1392, 79)
time.sleep(3)
menu = cap()
print(f"Menu mean={menu.mean():.1f}", flush=True)
cv2.imwrite(os.path.join(CACHE, 'simple_menu.png'), menu)

# Detect golden
print("\nGolden detection...", flush=True)
golden = detect_golden_simple(menu)
print(f"Found {len(golden)} golden elements", flush=True)
for g in golden[:25]:
    region = "T" if g['cy'] < 200 else ("B" if g['cy'] > 800 else ("M" if g['cy'] > 400 else "MT"))
    print(f"  ({g['cx']:>4},{g['cy']:>4}) {g['w']:>4}x{g['h']:>4} area={g['area']:>8.0f} [{region}]", flush=True)

# Test top golden elements
print("\nTesting golden buttons...", flush=True)
results = []
for g in golden[:12]:
    x, y = g['cx'], g['cy']
    
    before = cap()
    if before is None:
        continue
    
    tap(x, y)
    time.sleep(2.5)
    
    after = cap()
    if after is None:
        continue
    
    d = pixel_diff(before, after)
    tag = "BIG" if d > 800000 else ("MID" if d > 200000 else "low")
    
    print(f"  [{tag}] ({x:>4},{y:>4}) area={g['area']:.0f} diff={d:>10,}", flush=True)
    
    if d > 500000:
        cv2.imwrite(os.path.join(CACHE, f'simple_btn_{x}_{y}.png'), after)
    
    results.append({"x": x, "y": y, "area": float(g['area']), "diff": int(d)})
    
    # Back to menu
    for _ in range(3):
        back()
        time.sleep(0.5)

# Test specific coordinates from flows_config (on menu)
print("\nTesting flows_config coords ON MENU...", flush=True)
menu_coords = [
    ("base_997_85", 997, 85),
    ("base_665_57", 665, 57),
    ("char_800_220", 800, 220),
    ("char_1200_330", 1200, 330),
    ("center_960_540", 960, 540),
    ("left_400_400", 400, 400),
]

for name, x, y in menu_coords:
    before = cap()
    if before is None:
        continue
    
    tap(x, y)
    time.sleep(2.5)
    
    after = cap()
    if after is None:
        continue
    
    d = pixel_diff(before, after)
    tag = "BIG" if d > 800000 else ("MID" if d > 200000 else "low")
    print(f"  [{tag}] ({x:>4},{y:>4}) {name:20s} diff={d:>10,}", flush=True)
    
    if d > 500000:
        cv2.imwrite(os.path.join(CACHE, f'simple_flow_{name}.png'), after)
    
    results.append({"name": name, "x": x, "y": y, "diff": int(d), "area": 0})
    
    for _ in range(3):
        back()
        time.sleep(0.5)

# Save
out = os.path.join(CACHE, 'simple_menu_results.json')
with open(out, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\nSaved: {out}", flush=True)
print("Done", flush=True)
