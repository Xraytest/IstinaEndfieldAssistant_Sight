"""正确关闭退出对话框并扫描按钮"""
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

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

from standard_flow_engine import ScreenAnalyzer
analyzer = ScreenAnalyzer()

def is_exit_dialog(img):
    """检查是否是退出对话框"""
    r = analyzer.analyze(img)
    return 'exit' in r.get('page_type', '')

def ensure_world():
    """正确回到主世界(无对话框)"""
    # 先多次按返回确保触发对话框
    for _ in range(5):
        back()
        time.sleep(0.8)
    time.sleep(1)
    
    # 截图确认
    img = screencap(os.path.join(CACHE, 'ensure_check.png'))
    if is_exit_dialog(img):
        print('检测到退出对话框，正在关闭...')
        # 使用正确的取消按钮位置 (834,717) - game_coords exit_cancel scaled
        tap(834, 717)
        time.sleep(1.5)
    else:
        # 可能不需要关闭
        pass
    
    # 再按一次返回确保在世界
    back()
    time.sleep(1.5)
    
    img = screencap(os.path.join(CACHE, 'ensure_final.png'))
    r = analyzer.analyze(img)
    print(f'当前页面: {r["page_type"]}')
    return img

print("=== 确保回到主世界 ===")
img_base = ensure_world()

# 基准截图
base_path = os.path.join(CACHE, 'scan_world_baseline.png')
cv2.imwrite(base_path, img_base)

# 扫描任务按钮周围区域
# 任务按钮在 game_coords 是 (570,22) 720p → (855,33) 1080p
# 但之前测试都失败，所以我们扫描更大的范围
print("\n=== 扫描任务按钮周围区域 ===")
results = []

# 扫描 X=600-1100, Y=20-80
for y in range(20, 90, 15):
    for x in range(600, 1150, 75):
        # 确保在基准状态
        back()
        tap(834, 717)  # 防止对话框
        time.sleep(1)
        back()
        time.sleep(1.5)
        
        tap(x, y)
        time.sleep(2.5)
        
        after_path = os.path.join(CACHE, f'scan_tasks_{x}_{y}.png')
        screencap(after_path)
        img_after = cv2.imread(after_path)
        
        center_change = pixel_diff(img_base, img_after, (80, 650, 100, 1180))
        
        results.append({'x': x, 'y': y, 'center': int(center_change)})
        
        significant = center_change > 100000
        flag = '***' if significant else ''
        print(f'  ({x},{y}): center={center_change:,} {flag}')

# 排序并输出
results.sort(key=lambda r: r['center'], reverse=True)
print(f'\n=== TOP 10 ===")
for r in results[:10]:
    print(f"  ({r['x']},{r['y']}): center={r['center']:,}")

with open(os.path.join(CACHE, 'task_scan_results.json'), 'w') as f:
    json.dump(results, f, indent=2)
print('\n结果已保存')
