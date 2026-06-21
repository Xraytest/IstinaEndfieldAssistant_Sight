"""扫描菜单面板上的实际按钮 - 网格扫描 + 金色检测"""
import subprocess, time, cv2, numpy as np, os, json, sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(PROJECT, 'cache')
os.makedirs(CACHE, exist_ok=True)

TMP1 = os.path.join(CACHE, '_m1.png')
TMP2 = os.path.join(CACHE, '_m2.png')

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True, timeout=10)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], capture_output=True, timeout=5)

def cap(path):
    with open(path, 'wb') as f:
        subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       stdout=f, stderr=subprocess.PIPE, timeout=15)
    return cv2.imread(path)

def diff_files(a_path, b_path):
    a = cv2.imread(a_path)
    b = cv2.imread(b_path)
    if a is None or b is None:
        return 0, 0, 0
    d = cv2.absdiff(a, b)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t), a.mean(), b.mean()

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

def ensure_menu(target_mean):
    """确保在菜单面板上"""
    for attempt in range(5):
        img = cap(TMP1)
        if img is None:
            continue
        m = img.mean()
        if m > 80 and m < 200:
            return img, m
        # 偏离了，back后重开
        for _ in range(3):
            back()
            time.sleep(0.5)
        tap(1392, 79)
        time.sleep(3)
    return None, 0

print("=" * 60, flush=True)
print("Menu Grid Scanner", flush=True)
print("=" * 60, flush=True)

# Step 1: 确保在菜单上
print("\n[1] Ensure on menu...", flush=True)
menu_img, menu_mean = ensure_menu(130)
if menu_img is None:
    print("FATAL: Cannot get menu", flush=True)
    sys.exit(1)
print(f"Menu: mean={menu_mean:.1f}", flush=True)
cv2.imwrite(os.path.join(CACHE, 'grid_menu.png'), menu_img)

# Step 2: 金色检测
print("\n[2] Golden detection...", flush=True)
golden = detect_golden(menu_img)
print(f"Found {len(golden)} golden elements", flush=True)
for g in golden[:25]:
    region = "TOP" if g['cy'] < 200 else ("BTM" if g['cy'] > 800 else ("MID-BTM" if g['cy'] > 500 else "MID"))
    print(f"  ({g['cx']:>4},{g['cy']:>4}) {g['w']:>4}x{g['h']:>4} area={g['area']:>8.0f} [{region}]", flush=True)

# Step 3: Grid scan on menu (40px step, focused on areas)
print("\n[3] Grid scan...", flush=True)
results = []

# Focus areas: left side (100-600), right side (1300-1800), middle (600-1300)
# Y ranges: top (20-200), mid (200-600), bottom (600-900)
scan_areas = [
    # (label, x_start, x_end, x_step, y_start, y_end, y_step)
    ("TOP", 300, 1800, 80, 20, 120, 30),
    ("TOP-MID", 200, 1800, 80, 120, 300, 40),
    ("MID-LEFT", 80, 700, 60, 300, 700, 50),
    ("MID-RIGHT", 1200, 1850, 60, 300, 700, 50),
    ("MID-CENTER", 700, 1250, 60, 300, 700, 50),
    ("BTM", 200, 1800, 80, 700, 1000, 50),
]

tested = set()
for label, xs, xe, xs_step, ys, ye, ys_step in scan_areas:
    print(f"\n  --- {label}: X={xs}-{xe} step={xs_step}, Y={ys}-{ye} step={ys_step} ---", flush=True)
    
    for x in range(xs, xe, xs_step):
        for y in range(ys, ye, ys_step):
            key = (x // 30, y // 30)
            if key in tested:
                continue
            tested.add(key)
            
            # 确保还在菜单上
            check = cap(TMP1)
            if check is None:
                continue
            if check.mean() < 50 or check.mean() > 200:
                print(f"    [RECOVER] mean={check.mean():.0f}", flush=True)
                menu_img, menu_mean = ensure_menu(130)
                if menu_img is None:
                    continue
            
            # 截图前
            before = cap(TMP1)
            if before is None or before.mean() < 0.5:
                continue
            
            # 点击
            tap(x, y)
            time.sleep(2.5)
            
            # 截图后
            after = cap(TMP2)
            if after is None or after.mean() < 0.5:
                # 返回菜单
                for _ in range(3):
                    back()
                    time.sleep(0.5)
                continue
            
            d, bm, am = diff_files(TMP1, TMP2)
            
            if d > 500000:
                tag = f"[BIG:{d//1000}k]"
                print(f"    {tag} ({x:>4},{y:>4}) diff={d:>10,}  {label}", flush=True)
                cv2.imwrite(os.path.join(CACHE, f'grid_{label}_{x}_{y}.png'), after)
                results.append({"label": label, "x": x, "y": y, "diff": int(d), "tag": "BIG"})
            elif d > 150000:
                tag = f"[MID:{d//1000}k]"
                print(f"    {tag} ({x:>4},{y:>4}) diff={d:>10,}  {label}", flush=True)
                if d > 300000:
                    results.append({"label": label, "x": x, "y": y, "diff": int(d), "tag": "MID"})
            
            # 返回菜单
            for _ in range(3):
                back()
                time.sleep(0.5)
            time.sleep(0.3)

# Step 4: Test golden elements precisely
print("\n[4] Test golden elements...", flush=True)
for g in golden[:15]:
    x, y = g['cx'], g['cy']
    key = (x // 20, y // 20)
    if key in tested:
        continue
    tested.add(key)
    
    ensure_menu(menu_mean)
    
    before = cap(TMP1)
    if before is None or before.mean() < 0.5:
        continue
    
    tap(x, y)
    time.sleep(2.5)
    
    after = cap(TMP2)
    if after is None or after.mean() < 0.5:
        for _ in range(3):
            back()
            time.sleep(0.5)
        continue
    
    d, bm, am = diff_files(TMP1, TMP2)
    
    tag = "BIG" if d > 800000 else ("MID" if d > 200000 else "low")
    print(f"  [{tag}] ({x:>4},{y:>4}) area={g['area']:.0f} diff={d:>10,}", flush=True)
    
    if d > 500000:
        cv2.imwrite(os.path.join(CACHE, f'grid_golden_{x}_{y}.png'), after)
        results.append({"label": "golden", "x": x, "y": y, "area": float(g['area']), "diff": int(d), "tag": tag})
    
    for _ in range(3):
        back()
        time.sleep(0.5)

# Save
out = os.path.join(CACHE, 'grid_scan_results.json')
with open(out, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n{'='*60}", flush=True)
print(f"Results: {out}", flush=True)
print(f"\nBIG hits (>{800000}):", flush=True)
big = [r for r in results if r.get('diff', 0) > 800000]
for r in sorted(big, key=lambda x: x['diff'], reverse=True):
    print(f"  [{r['diff']//1000}k] ({r['x']},{r['y']}) {r.get('label','')}", flush=True)

print(f"\nMID hits (300k-800k):", flush=True)
mid = [r for r in results if 300000 < r.get('diff', 0) <= 800000]
for r in sorted(mid, key=lambda x: x['diff'], reverse=True):
    print(f"  [{r['diff']//1000}k] ({r['x']},{r['y']}) {r.get('label','')}", flush=True)

print("\nDone", flush=True)
