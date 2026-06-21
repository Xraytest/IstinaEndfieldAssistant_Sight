"""像素差异法扫描v2 - 移除VLM依赖，纯像素判断"""
import subprocess, time, os, cv2, numpy as np, json

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
    """纯像素判断：对话框区域暗且对比度高"""
    if img is None:
        return True
    mid = img[300:700, 500:1400, :]
    brightness = mid.mean()
    return brightness < 80  # 退出对话框通常很暗

# Step 1: 回到世界
print("Step 1: 回到世界...")
for _ in range(4):
    back()
    time.sleep(0.8)
time.sleep(1)

# Step 2: 关闭可能的退出对话框
check_path = os.path.join(CACHE, 'v2_check.png')
for attempt in range(10):
    img_check = screencap(check_path)
    if img_check is None:
        print("截图失败，重试...")
        time.sleep(1)
        continue
    if not is_dialog_simple(img_check):
        print(f"未检测到对话框 (brightness={img_check[300:700,500:1400,:].mean():.0f})")
        break
    print(f"检测到对话框，尝试关闭... (attempt {attempt+1})")
    cancel_candidates = [
        (834, 717), (600, 700), (500, 650), (840, 650),
    ]
    for cx, cy in cancel_candidates:
        tap(cx, cy)
        time.sleep(1)
    back()
    time.sleep(1)

# Step 3: 确认在世界
time.sleep(1.5)
img_base = screencap(os.path.join(CACHE, 'v2_baseline.png'))
if img_base is None:
    print("ERROR: 无法获取基准截图")
    exit(1)
h, w = img_base.shape[:2]
print(f"基准: {w}x{h}, brightness={img_base[300:700,500:1400,:].mean():.0f}")

# Step 4: 扫描
print("\nStep 4: 扫描按钮...")
results = []

# 聚焦关键区域:
# Y=25-55, X=80-500 (左侧) + X=560-1040 (右侧)
scan_positions = []
for y in [25, 35, 45, 55]:
    for x in range(80, 500, 40):
        scan_positions.append((x, y))
    for x in range(560, 1060, 40):
        scan_positions.append((x, y))

total = len(scan_positions)

for idx, (x, y) in enumerate(scan_positions):
    # 确保无对话框
    img_check = screencap(check_path)
    if is_dialog_simple(img_check):
        tap(834, 717)
        time.sleep(1)
    
    # 截图前
    before_path = os.path.join(CACHE, f'v2_before_{x}_{y}.png')
    img_before = screencap(before_path)
    if img_before is None:
        print(f'[{idx+1}/{total}] ({x},{y}): SKIP (screenshot failed)')
        continue
    
    # 点击
    tap(x, y)
    time.sleep(2.5)
    
    # 截图后
    after_path = os.path.join(CACHE, f'v2_after_{x}_{y}.png')
    img_after = screencap(after_path)
    if img_after is None:
        print(f'[{idx+1}/{total}] ({x},{y}): SKIP (after failed)')
        continue
    
    center_change = pixel_diff(img_before, img_after, (80, 650, 100, 1180))
    top_change = pixel_diff(img_before, img_after, (0, 80, 0, w))
    
    results.append({
        'x': x, 'y': y,
        'center': int(center_change),
        'top': int(top_change),
    })
    
    significant = center_change > 100000
    flag = '***' if significant else ''
    print(f'[{idx+1}/{total}] ({x},{y}): center={center_change:,} top={top_change:,} {flag}')
    
    # 返回
    back()
    time.sleep(1.5)

# 排序
results.sort(key=lambda r: r['center'], reverse=True)
print(f'\n=== TOP 20 ===')
for r in results[:20]:
    print(f"  ({r['x']},{r['y']}): center={r['center']:,} top={r['top']:,}")

with open(os.path.join(CACHE, 'v2_scan_results.json'), 'w') as f:
    json.dump(results, f, indent=2)
print(f'\n结果保存到 v2_scan_results.json')
