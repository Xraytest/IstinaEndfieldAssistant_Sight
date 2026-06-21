"""导航按钮定位脚本 - 精细扫描 + 边缘滑动手势 + MaaFw 触控尝试"""
import subprocess, time, os, sys, cv2, numpy as np, json

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJECT, 'cache')
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
os.makedirs(CACHE, exist_ok=True)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   timeout=10, capture_output=True)

def swipe(x1, y1, x2, y2, dur=500):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'swipe',
                    str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(dur))],
                   timeout=10, capture_output=True)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5, capture_output=True)

def screencap(path):
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       timeout=15, capture_output=True)
    if len(r.stdout) < 1000:
        return None
    with open(path, 'wb') as f:
        f.write(r.stdout)
    return cv2.imread(path)

def pixel_diff(img_a, img_b, y1, y2, x1, x2):
    if img_a is None or img_b is None:
        return 0
    diff = cv2.absdiff(img_a[y1:y2, x1:x2], img_b[y1:y2, x1:x2])
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(thresh)

def full_diff(img_a, img_b):
    """全图像素差异"""
    if img_a is None or img_b is None:
        return 0
    diff = cv2.absdiff(img_a, img_b)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(thresh)

def is_dialog(img):
    if img is None:
        return True
    mid = img[300:700, 500:1400, :] if img.shape[0] > 700 else img[300:600, 200:800, :]
    return mid.mean() < 80

# ── 回到世界 ──
print("Phase 0: 回到世界...")
for _ in range(3):
    back()
    time.sleep(0.8)
time.sleep(1)

check_path = os.path.join(CACHE, 'nav_hunt_check.png')
for i in range(5):
    img = screencap(check_path)
    if not is_dialog(img):
        break
    tap(834, 717)
    time.sleep(1)
time.sleep(1)

baseline = screencap(os.path.join(CACHE, 'nav_hunt_baseline.png'))
if baseline is None:
    print("FATAL: 无法截图")
    sys.exit(1)
h, w = baseline.shape[:2]
print(f"设备分辨率: {w}x{h} (ADB native)")

# ── Phase 1: 精细扫描右侧导航区域 ──
# 对比左侧已知有效区域 (X=320-480, Y=25-55)
# 右侧扫描范围: X=550-1060, Y=15-70, step=25 (约70个点，~6分钟)
print("\nPhase 1: 精细扫描右侧导航栏 (X=550-1060, Y=15-70, step=25)")

results = []
# 左侧已知有效点 (positive control)
left_positions = [(360, 25), (400, 35), (400, 55)]
# 右侧扫描点 - 每点加随机抖动避免命中空白
right_positions = []
for y in [15, 25, 35, 45, 55, 65, 70]:
    for x in range(550, 1060, 25):
        right_positions.append((x, y))
# 合并，左侧先扫描
all_positions = left_positions + right_positions
total = len(all_positions)

for idx, (x, y) in enumerate(all_positions):
    # 处理对话框
    img = screencap(check_path)
    if is_dialog(img):
        tap(834, 717)
        time.sleep(1)
    
    before_path = os.path.join(CACHE, f'nh_before_{x}_{y}.png')
    img_before = screencap(before_path)
    if img_before is None:
        continue
    
    tap(x, y)
    time.sleep(2.5)
    
    after_path = os.path.join(CACHE, f'nh_after_{x}_{y}.png')
    img_after = screencap(after_path)
    if img_after is None:
        back()
        time.sleep(1)
        continue
    
    # 计算多个 ROI 的变化
    full_change = full_diff(img_before, img_after)
    center_change = pixel_diff(img_before, img_after, 80, min(650, h), 100, min(1180, w))
    top_change = pixel_diff(img_before, img_after, 0, 80, 0, w)
    
    results.append({
        'x': x, 'y': y,
        'full': int(full_change),
        'center': int(center_change),
        'top': int(top_change),
    })
    
    sig = ' ⭐' if center_change > 100000 else ''
    print(f'[{idx+1}/{total}] ({x},{y}): full={full_change:,} center={center_change:,} top={top_change:,}{sig}')
    
    # 返回
    back()
    time.sleep(1.5)

# 排序输出
results.sort(key=lambda r: r['center'], reverse=True)
print(f'\n{"="*60}')
print(f'TOP 30 结果 (按 center 变化排序):')
for r in results[:30]:
    flag = '⬅ 左侧' if r['x'] < 500 else '➡ 右侧'
    print(f"  ({r['x']:>4},{r['y']:>2}): full={r['full']:>10,} center={r['center']:>10,} top={r['top']:>10,} {flag}")

# ── Phase 2: 尝试边缘滑动 ──
print(f'\n{"="*60}')
print('Phase 2: 边缘滑动手势测试')

slide_tests = [
    # 从右边缘向左滑 (常见侧边栏手势)
    ("右边缘→左滑", (w - 5, 360), (w - 200, 360), 300),
    ("右边缘→左滑(快)", (w - 5, 360), (w - 300, 360), 150),
    # 从左边缘向右滑
    ("左边缘→右滑", (5, 360), (200, 360), 300),
    # 从顶部向下滑
    ("顶部→下滑", (540, 5), (540, 200), 300),
    ("顶部→下滑(宽)", (540, 5), (540, 300), 400),
    # 从右顶部向左下滑
    ("右顶→左下滑", (w - 5, 5), (500, 150), 300),
]

for label, (x1, y1), (x2, y2), dur in slide_tests:
    img = screencap(check_path)
    if is_dialog(img):
        tap(834, 717)
        time.sleep(1)
    
    before_p = os.path.join(CACHE, f'nh_slide_before_{label}.png')
    img_before = screencap(before_p)
    if img_before is None:
        continue
    
    swipe(x1, y1, x2, y2, dur)
    time.sleep(2)
    
    after_p = os.path.join(CACHE, f'nh_slide_after_{label}.png')
    img_after = screencap(after_p)
    if img_after is None:
        continue
    
    full_c = full_diff(img_before, img_after)
    center_c = pixel_diff(img_before, img_after, 80, min(650, h), 100, min(1180, w))
    top_c = pixel_diff(img_before, img_after, 0, 80, 0, w)
    
    sig = ' ⭐' if center_c > 100000 else ''
    print(f'  {label}: full={full_c:,} center={center_c:,} top={top_c:,}{sig}')
    
    back()
    time.sleep(1.5)

# 保存结果
out_path = os.path.join(CACHE, 'nav_hunt_results.json')
with open(out_path, 'w') as f:
    json.dump(results, f, indent=2)
print(f'\n结果保存到: {out_path}')
