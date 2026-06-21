"""像素差异法扫描补充 - Y=55 + 更细粒度右侧扫描"""
import subprocess, time, os, cv2, json

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
ADB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(x), str(y)],
                   timeout=10, capture_output=True)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'],
                   timeout=5, capture_output=True)

def screencap(path):
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       timeout=15, capture_output=True)
    if len(r.stdout) < 1000:
        return None
    open(path, 'wb').write(r.stdout)
    return cv2.imread(path)

def pixel_diff(img_a, img_b, roi):
    y1, y2, x1, x2 = roi
    if img_a is None or img_b is None:
        return 0
    diff = cv2.absdiff(img_a[y1:y2, x1:x2], img_b[y1:y2, x1:x2])
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(thresh)

def is_dialog_simple(img):
    if img is None:
        return True
    mid = img[300:700, 500:1400, :]
    return mid.mean() < 80

check_path = os.path.join(CACHE, 'v2_check.png')

# 先关闭对话框
for _ in range(3):
    back()
    time.sleep(0.8)
time.sleep(1)
for _ in range(5):
    img_check = screencap(check_path)
    if not is_dialog_simple(img_check):
        break
    tap(834, 717)
    time.sleep(1)

img_base = screencap(os.path.join(CACHE, 'v2b_baseline.png'))
if img_base is None:
    print("ERROR")
    exit(1)
w = img_base.shape[1]
print(f"基准: {img_base.shape[1]}x{img_base.shape[0]}")

results = []

# 补充扫描: Y=55 (全部) + Y=65 + 右侧精细扫描
scan_positions = []
# Y=55: 全范围
for x in range(80, 500, 40):
    scan_positions.append((x, 55))
for x in range(560, 1060, 40):
    scan_positions.append((x, 55))
# Y=65: 重点左侧
for x in range(80, 560, 40):
    scan_positions.append((x, 65))
# 右侧精细 (2x密度): game_coords在Y=55附近可能有按钮
for y in [45, 55, 65]:
    for x in range(550, 1060, 20):
        scan_positions.append((x, y))

# 去重
scan_positions = list(dict.fromkeys(scan_positions))
total = len(scan_positions)

for idx, (x, y) in enumerate(scan_positions):
    img_check = screencap(check_path)
    if is_dialog_simple(img_check):
        tap(834, 717)
        time.sleep(1)
    
    before_path = os.path.join(CACHE, f'v2b_before_{x}_{y}.png')
    img_before = screencap(before_path)
    if img_before is None:
        print(f'[{idx+1}/{total}] ({x},{y}): SKIP')
        continue
    
    tap(x, y)
    time.sleep(2.5)
    
    after_path = os.path.join(CACHE, f'v2b_after_{x}_{y}.png')
    img_after = screencap(after_path)
    if img_after is None:
        print(f'[{idx+1}/{total}] ({x},{y}): SKIP')
        back()
        time.sleep(1)
        continue
    
    center_change = pixel_diff(img_before, img_after, (80, 650, 100, 1180))
    top_change = pixel_diff(img_before, img_after, (0, 80, 0, w))
    
    results.append({
        'x': x, 'y': y,
        'center': int(center_change),
        'top': int(top_change),
    })
    
    sig = ' ***' if center_change > 100000 else ''
    print(f'[{idx+1}/{total}] ({x},{y}): center={center_change:,} top={top_change:,}{sig}')
    
    back()
    time.sleep(1.5)

results.sort(key=lambda r: r['center'], reverse=True)
print(f'\n=== TOP 30 ===')
for r in results[:30]:
    print(f"  ({r['x']},{r['y']}): center={r['center']:,} top={r['top']:,}")

# 合并结果
try:
    with open(os.path.join(CACHE, 'v2_scan_results.json')) as f:
        old = json.load(f)
    old.extend(results)
    with open(os.path.join(CACHE, 'v2_scan_results.json'), 'w') as f:
        json.dump(old, f, indent=2)
    print(f"\n总计 {len(old)} 条结果")
except:
    with open(os.path.join(CACHE, 'v2b_scan_results.json'), 'w') as f:
        json.dump(results, f, indent=2)
