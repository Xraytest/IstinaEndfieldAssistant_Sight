"""测试菜单金色元素 v2 - 正确管理menu开关状态"""
import subprocess, time, cv2, numpy as np, os, json

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(PROJECT, 'cache')
os.makedirs(CACHE, exist_ok=True)

T1 = os.path.join(CACHE, '_gv1.png')
T2 = os.path.join(CACHE, '_gv2.png')

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

def diff_files(a, b):
    da = cv2.imread(a)
    db = cv2.imread(b)
    if da is None or db is None:
        return 0
    d = cv2.absdiff(da, db)
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

def is_menu(img):
    """Check if image is menu (mean 120-160)"""
    if img is None:
        return False
    m = img.mean()
    return 110 < m < 170

def ensure_menu_open():
    """Ensure menu is open. Returns True if menu was just opened."""
    img = cap(T1)
    if is_menu(img):
        return False  # Already open
    # Not menu - try opening
    tap(1392, 79)
    time.sleep(3)
    img = cap(T1)
    if is_menu(img):
        return True
    # Might be in a panel - back out then open
    for _ in range(5):
        back()
        time.sleep(0.5)
    tap(1392, 79)
    time.sleep(3)
    return True

print("Golden Menu Test v2", flush=True)

# Take menu screenshot
if not ensure_menu_open():
    # Menu might already be open from previous
    pass

menu = cap(T1)
if menu is None:
    print("FATAL: no menu", flush=True)
    exit(1)
print(f"Menu: mean={menu.mean():.1f}", flush=True)
cv2.imwrite(os.path.join(CACHE, 'gv2_menu.png'), menu)

# Detect golden
golden = detect_golden(menu)
print(f"Found {len(golden)} golden elements", flush=True)
for i, g in enumerate(golden[:20]):
    region = "TOP" if g['cy'] < 200 else ("BTM" if g['cy'] > 800 else ("MID" if g['cy'] < 500 else "MID-BTM"))
    print(f"  [{i}] ({g['cx']:>4},{g['cy']:>4}) {g['w']:>4}x{g['h']:>4} area={g['area']:>8.0f} [{region}]", flush=True)

# Test each golden element
results = []
MENU_MEAN = menu.mean()

for i, g in enumerate(golden[:15]):
    x, y = g['cx'], g['cy']
    
    # Ensure on menu (not world or other screen)
    check = cap(T1)
    if check is None or not is_menu(check):
        print(f"  [{i}] Not on menu (mean={check.mean():.0f if check is not None else 'None'}), recovering...", flush=True)
        ensure_menu_open()
    
    before = cap(T1)
    if before is None:
        print(f"  [{i}] SKIP before", flush=True)
        continue
    
    tap(x, y)
    time.sleep(2.5)
    
    after = cap(T2)
    if after is None:
        print(f"  [{i}] SKIP after", flush=True)
        for _ in range(3):
            back()
            time.sleep(0.5)
        continue
    
    d = diff_files(T1, T2)
    tag = "BIG" if d > 800000 else ("MID" if d > 200000 else "low")
    
    print(f"  [{i}][{tag}] ({x:>4},{y:>4}) {g['w']}x{g['h']} area={g['area']:.0f} diff={d:>10,} bm={before.mean():.0f} am={after.mean():.0f}", flush=True)
    
    if d > 200000:
        cv2.imwrite(os.path.join(CACHE, f'gv2_golden_{i}_{x}_{y}.png'), after)
        results.append({"idx": i, "x": x, "y": y, "w": g['w'], "h": g['h'], "area": float(g['area']), "diff": int(d), "tag": tag})
    
    # Return to menu state
    for _ in range(3):
        back()
        time.sleep(0.5)
    time.sleep(0.5)
    ensure_menu_open()

# Save
out = os.path.join(CACHE, 'golden_test_v2.json')
with open(out, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\nSaved: {out}", flush=True)
print(f"\nBIG (>800k):", flush=True)
for r in results:
    if r['diff'] > 800000:
        print(f"  [{r['diff']//1000}k] ({r['x']},{r['y']}) area={r['area']:.0f}", flush=True)
print(f"MID (200k-800k):", flush=True)
for r in results:
    if 200000 < r['diff'] <= 800000:
        print(f"  [{r['diff']//1000}k] ({r['x']},{r['y']}) area={r['area']:.0f}", flush=True)
print(f"low (<200k):", flush=True)
for r in results:
    if r['diff'] <= 200000:
        print(f"  [{r['diff']//1000}k] ({r['x']},{r['y']}) area={r['area']:.0f}", flush=True)

print("Done", flush=True)
