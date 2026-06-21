"""从world精细扫描顶部栏 - 寻找导航图标"""
import subprocess, time, cv2, numpy as np, os, json

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(PROJECT, 'cache')
os.makedirs(CACHE, exist_ok=True)

T1 = os.path.join(CACHE, '_top1.png')
T2 = os.path.join(CACHE, '_top2.png')

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

def in_world():
    """Check if currently in world"""
    img = cap(T1)
    if img is None:
        return False
    m = img.mean()
    if m < 50 or m > 150:
        return False
    # Verify with tap test
    before = cap(T1)
    if before is None:
        return False
    tap(300, 80)
    time.sleep(2.5)
    after = cap(T2)
    if after is None:
        return False
    d = diff_files(T1, T2)
    # Close panel
    for _ in range(5):
        back()
        time.sleep(0.3)
    time.sleep(1)
    return d > 500000

def ensure_world():
    """Ensure we're in world. If not, try back then restart."""
    for attempt in range(8):
        if in_world():
            return True
        for _ in range(5):
            back()
            time.sleep(0.5)
        time.sleep(1)
    # Force restart
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
    for i in range(30):
        time.sleep(3)
        if in_world():
            return True
    return False

print("Top Bar Fine Scan", flush=True)

if not ensure_world():
    print("FATAL: Cannot reach world", flush=True)
    exit(1)

world = cap(T1)
print(f"World: mean={world.mean():.1f}", flush=True)

# Scan top area: X=100-1800, Y=15-100
# Finer step where we expect icons
results = []
tested = set()

print("\nFine scan: X=200-1800 step=20, Y=20-80 step=10", flush=True)
for x in range(200, 1820, 20):
    for y in range(20, 81, 10):
        key = (x, y)
        if key in tested:
            continue
        tested.add(key)
        
        if not in_world():
            print(f"  [RECOVER] Not in world, restarting...", flush=True)
            if not ensure_world():
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
                time.sleep(0.3)
            continue
        
        d = diff_files(T1, T2)
        
        if d > 300000:
            tag = "BIG" if d > 800000 else "MID"
            print(f"  [{tag}] ({x:>4},{y:>3}) diff={d:>10,} bm={before.mean():.0f} am={after.mean():.0f}", flush=True)
            if d > 500000:
                cv2.imwrite(os.path.join(CACHE, f'top_{x}_{y}.png'), after)
            results.append({"x": x, "y": y, "diff": int(d), "tag": tag})
        elif d > 100000:
            # Show first few MID-low results for context
            pass
        
        # Back to world
        for _ in range(4):
            back()
            time.sleep(0.3)
        time.sleep(0.5)

# Also scan Y=80-100 (might have icons lower)
print("\nExtended: X=400-1500 step=30, Y=80-100 step=10", flush=True)
for x in range(400, 1520, 30):
    for y in range(80, 101, 10):
        if (x, y) in tested:
            continue
        tested.add((x, y))
        
        if not in_world():
            if not ensure_world():
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
                time.sleep(0.3)
            continue
        
        d = diff_files(T1, T2)
        
        if d > 300000:
            tag = "BIG" if d > 800000 else "MID"
            print(f"  [{tag}] ({x:>4},{y:>3}) diff={d:>10,}", flush=True)
            if d > 500000:
                cv2.imwrite(os.path.join(CACHE, f'top_{x}_{y}.png'), after)
            results.append({"x": x, "y": y, "diff": int(d), "tag": tag})
        
        for _ in range(4):
            back()
            time.sleep(0.3)
        time.sleep(0.5)

# Save
out = os.path.join(CACHE, 'topbar_scan.json')
with open(out, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\nSaved: {out}", flush=True)
print(f"\nResults (sorted by diff):", flush=True)
for r in sorted(results, key=lambda x: x['diff'], reverse=True):
    print(f"  [{r['diff']//1000}k] ({r['x']},{r['y']}) {r['tag']}", flush=True)

print("Done", flush=True)
