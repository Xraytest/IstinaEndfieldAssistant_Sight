"""系统扫描顶部栏找到任务按钮"""
import cv2, numpy as np, subprocess, os, sys, time, hashlib

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
ADB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'

def screencap(path):
    with open(path, 'wb') as f:
        subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], stdout=f, timeout=15)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(x), str(y)], timeout=10)

output = []

# 1. 截图当前状态
screenshot_path = os.path.join(CACHE, 'find_quest_screen.png')
screencap(screenshot_path)
img = cv2.imread(screenshot_path)
h, w = img.shape[:2]
output.append(f'Screen: {w}x{h}')

# 2. 分析顶部栏按钮区域 (0-100px)
top = img[0:100, :, :]
gray = cv2.cvtColor(top, cv2.COLOR_BGR2GRAY)

# 找亮色（按钮）像素
bright = (gray > 140).sum(axis=0)
output.append(f'Top bar bright pixel distribution (columns with >140 gray):')
for x in range(0, w, 50):
    count = bright[x:min(x+50, w)].sum()
    if count > 50:
        output.append(f'  X={x}-{min(x+50, w)}: {count} bright pixels')

# 3. 扫描可能的Y位置
output.append(f'\nTesting top bar taps...')
test_taps = []

# 先试固定Y=40, 扫描X
for x in range(200, 1700, 150):
    test_taps.append((x, 40))

# 也试Y=50
for x in range(200, 1700, 150):
    test_taps.append((x, 50))

for x, y in test_taps[:20]:  # 只测试前20个
    # 每次截图前先返回世界
    tap(x, y)
    time.sleep(2)
    
    check_path = os.path.join(CACHE, f'check_{x}_{y}.png')
    screencap(check_path)
    check_img = cv2.imread(check_path)
    if check_img is not None:
        # 简易页面检测: 检查图片左上角区域
        roi = check_img[0:200, 0:400, :]
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        non_black = (roi_gray > 30).sum()
        output.append(f'  ({x},{y}): non_black={non_black}')
    
    # 按返回键
    tap(540, 960)  # 可能关闭任何弹窗
    time.sleep(0.5)
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5)
    time.sleep(1)

result = '\n'.join(output)
print(result)
with open(os.path.join(CACHE, 'find_quest_output.txt'), 'w', encoding='utf-8') as f:
    f.write(result)
print('DONE')
