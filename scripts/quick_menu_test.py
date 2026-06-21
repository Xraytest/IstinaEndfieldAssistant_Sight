"""快速测试菜单和base_entry - 最小化"""
import subprocess, time, cv2, numpy as np, os, sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(PROJECT, 'cache')

TMP = os.path.join(CACHE, '_qt.png')

def run_adb(*args, timeout=15):
    """Run ADB with shell redirect for reliability"""
    return subprocess.run([ADB, '-s', SERIAL] + list(args),
                          capture_output=True, timeout=timeout)

def tap(x, y):
    run_adb('shell', 'input', 'tap', str(int(x)), str(int(y)), timeout=10)

def back():
    run_adb('shell', 'input', 'keyevent', '4', timeout=5)

def cap():
    """Screenshot via shell redirect"""
    with open(TMP, 'wb') as f:
        r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                           stdout=f, stderr=subprocess.PIPE, timeout=15)
    img = cv2.imread(TMP)
    return img

def diff(a, b):
    if a is None or b is None:
        return 0
    d = cv2.absdiff(a, b)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)

print("Quick menu test", flush=True)

# Check current
img = cap()
if img is None:
    print("FATAL: Initial screenshot failed", flush=True)
    sys.exit(1)
print(f"Current: mean={img.mean():.1f} std={img.std():.1f}", flush=True)

# Back to world
print("Backing to world...", flush=True)
for i in range(10):
    back()
    time.sleep(0.5)
time.sleep(2)

img2 = cap()
if img2 is None:
    print("FATAL: Screenshot after backs failed", flush=True)
    sys.exit(1)
print(f"After backs: mean={img2.mean():.1f} std={img2.std():.1f}", flush=True)

# Verify world
before = cap()
if before is None:
    sys.exit(1)
tap(300, 80)
time.sleep(2.5)
after = cap()
if after is None:
    sys.exit(1)
d = diff(before, after)
print(f"World check tap(300,80): diff={d:,}", flush=True)
for _ in range(5):
    back()
    time.sleep(0.5)
time.sleep(1)

# Open menu
print("Open menu (1392,79)...", flush=True)
tap(1392, 79)
time.sleep(3)
menu = cap()
if menu is None:
    print("FATAL: Menu cap failed", flush=True)
    sys.exit(1)
print(f"Menu: mean={menu.mean():.1f} std={menu.std():.1f}", flush=True)
cv2.imwrite(os.path.join(CACHE, '_qt_menu.png'), menu)

# Test base_entry
print("Test base_entry (997,85)...", flush=True)
before = cap()
if before is None:
    sys.exit(1)
tap(997, 85)
time.sleep(2.5)
after = cap()
if after is None:
    sys.exit(1)
d = diff(before, after)
print(f"base_entry(997,85): diff={d:,} bm={before.mean():.0f} am={after.mean():.0f}", flush=True)
if d > 200000:
    cv2.imwrite(os.path.join(CACHE, '_qt_after_base.png'), after)
    cv2.imwrite(os.path.join(CACHE, '_qt_before_base.png'), before)

print("Done", flush=True)
