"""像素差异法扫描顶部栏按钮（针对静态背景优化）"""
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
    open(path, 'wb').write(r.stdout)
    return cv2.imread(path)

def pixel_diff(img_a, img_b, roi):
    y1, y2, x1, x2 = roi
    diff = cv2.absdiff(img_a[y1:y2, x1:x2], img_b[y1:y2, x1:x2])
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(thresh)

def dismiss_dialog():
    tap(834, 717)
    time.sleep(1)

# 确保回到主世界
print("回到主世界...")
for _ in range(4):
    back()
    time.sleep(0.8)
time.sleep(1)
dismiss_dialog()
time.sleep(0.5)
back()
time.sleep(2)

# 基准截图
base_path = os.path.join(CACHE, 'pixel_scan_base.png')
img_base = screencap(base_path)
h, w = img_base.shape[:2]
print(f"基准: {w}x{h}")

# 扫描策略: 扫描顶部栏 Y=20-70, X=50-1200
# 每个位置拍前/后对比来避免3D场景漂移
results = []

scan_x = list(range(50, 1250, 60))
scan_y = [25, 35, 45, 55, 65]

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
from standard_flow_engine import ScreenAnalyzer
analyzer = ScreenAnalyzer()

# 先分析当前页面
r = analyzer.analyze(img_base)
print(f"当前页面: {r['page_type']}")
print(f"OCR: {r['ocr_text'][:150]}")

total = len(scan_y) * len(scan_x)
print(f"\n开始扫描 {total} 个位置...")

for yi, y in enumerate(scan_y):
    for xi, x in enumerate(scan_x):
        idx = yi * len(scan_x) + xi
        
        # 每次前: 确保无对话框
        dismiss_dialog()
        time.sleep(0.3)
        
        # 截图前
        before_path = os.path.join(CACHE, f'pscan_before_{x}_{y}.png')
        img_before = screencap(before_path)
        
        # 点击
        tap(x, y)
        time.sleep(2.5)
        
        # 截图后
        after_path = os.path.join(CACHE, f'pscan_after_{x}_{y}.png')
        img_after = screencap(after_path)
        
        # 像素差异 - 用"前"截图比较而非基准
        center_change = pixel_diff(img_before, img_after, (80, 650, 100, 1180))
        global_change = pixel_diff(img_before, img_after, (0, h, 0, w))
        topbar_change = pixel_diff(img_before, img_after, (10, 80, 0, w))
        
        results.append({
            'x': x, 'y': y,
            'center': int(center_change),
            'global': int(global_change),
            'topbar': int(topbar_change),
        })
        
        significant = center_change > 100000
        flag = '***' if significant else ''
        print(f'[{idx+1}/{total}] ({x},{y}): center={center_change:,} global={global_change:,} topbar={topbar_change:,} {flag}')
        
        # 返回
        back()
        time.sleep(1.5)

# 排序
results.sort(key=lambda r: r['center'], reverse=True)
print(f'\n=== TOP 15 ===')
for r in results[:15]:
    print(f"  ({r['x']},{r['y']}): center={r['center']:,} global={r['global']:,} topbar={r['topbar']:,}")

with open(os.path.join(CACHE, 'pixel_scan_results.json'), 'w') as f:
    json.dump(results, f, indent=2)
print(f'\n结果保存到 pixel_scan_results.json')
