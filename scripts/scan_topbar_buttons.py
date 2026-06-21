"""系统扫描顶部栏按钮位置（像素差异法）"""
import subprocess
import time
import os
import cv2
import numpy as np

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
ADB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'


def screencap(path):
    with open(path, 'wb') as f:
        subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], stdout=f, timeout=15)
    return cv2.imread(path)


def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(x), str(y)], timeout=10)


def go_back():
    """按返回键并等待"""
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5)
    time.sleep(1.5)


def dismiss_exit_dialog():
    """关闭退出对话框"""
    # 点取消按钮
    tap(960, 717)
    time.sleep(1.0)


def pixel_diff(img_a, img_b, roi):
    """计算两个图片在指定ROI内的像素变化量"""
    y1, y2, x1, x2 = roi
    diff = cv2.absdiff(img_a[y1:y2, x1:x2], img_b[y1:y2, x1:x2])
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(thresh)


def ensure_world():
    """确保在主世界界面"""
    # 多次按返回直到退出对话框出现
    for _ in range(10):
        go_back()
    time.sleep(1)
    # 关闭可能出现的退出对话框
    dismiss_exit_dialog()
    time.sleep(1)
    # 再按一次返回确认
    go_back()
    time.sleep(1)


print("=== 确保在主世界界面 ===")
ensure_world()

# 基准截图
base_path = os.path.join(CACHE, 'scan_baseline.png')
img_base = screencap(base_path)
h, w = img_base.shape[:2]
print(f"基准截图: {w}x{h}")

# 进度条
PROGRESS = os.path.join(CACHE, 'scan_progress.txt')

# 扫描区域：顶部栏 y=20-80, X=100-1850, step=50
results = []
scan_x = list(range(100, 1900, 50))
scan_y = [25, 30, 35, 40, 45, 50, 55, 60]
total = len(scan_y) * len(scan_x)
done = 0

# 加载之前的进度
if os.path.exists(PROGRESS):
    done = int(open(PROGRESS).read().strip() or '0')
    print(f"从进度 {done}/{total} 恢复")

for yi, y in enumerate(scan_y):
    for xi, x in enumerate(scan_x):
        idx = yi * len(scan_x) + xi
        if idx < done:
            continue

        # 确保在基准状态：回到主世界
        tap(x, y)
        time.sleep(2.5)

        after_path = os.path.join(CACHE, f'scan_{x}_{y}.png')
        img_after = screencap(after_path)

        # 中央面板区域变化 (该区域打开面板时应有大量变化)
        center_change = pixel_diff(img_base, img_after, (80, 650, 100, 1180))
        # 顶部栏区域变化
        topbar_change = pixel_diff(img_base, img_after, (10, 80, 0, w))

        results.append({
            'x': x, 'y': y,
            'center': int(center_change),
            'topbar': int(topbar_change),
        })

        significant = center_change > 100000
        flag = '*** SIGNIFICANT ***' if significant else ''
        print(f"[{idx+1}/{total}] ({x},{y}): center={center_change} topbar={topbar_change} {flag}")

        # 回到主世界
        go_back()
        dismiss_exit_dialog()
        time.sleep(0.5)

        # 保存进度
        done = idx + 1
        with open(PROGRESS, 'w') as f:
            f.write(str(done))

# 保存结果
import json
result_path = os.path.join(CACHE, 'topbar_scan_results.json')
with open(result_path, 'w') as f:
    json.dump(results, f, indent=2)

# 清理进度
if os.path.exists(PROGRESS):
    os.remove(PROGRESS)

# 输出排名前20结果
sorted_results = sorted(results, key=lambda r: r['center'], reverse=True)
print(f"\n=== TOP 20 扫描结果 ===")
for r in sorted_results[:20]:
    print(f"  ({r['x']},{r['y']}): center={r['center']:,} topbar={r['topbar']:,}")

print(f"\n结果已保存到 {result_path}")
