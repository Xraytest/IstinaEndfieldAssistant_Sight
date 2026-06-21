"""快速扫描顶部栏"""
import subprocess, time, os, cv2, numpy as np

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
ADB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'],
                   timeout=10, capture_output=True)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(x), str(y)],
                   timeout=10, capture_output=True)

def screencap(path):
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       timeout=15, capture_output=True)
    with open(path, 'wb') as f:
        f.write(r.stdout)
    return cv2.imread(path)

# 回到主世界
print("返回主世界...")
for _ in range(4):
    back()
    time.sleep(1.5)
tap(960, 717)  # 取消退出对话框
time.sleep(1.5)
back()
time.sleep(2)

# 截图
img = screencap(os.path.join(CACHE, 'clean_world.png'))
h, w = img.shape[:2]
print(f"屏幕: {w}x{h}")

# 分析顶部120px
top = img[0:120, :, :]

# 按50px间隔分析
output = []
output.append(f"{'X范围':<12} {'亮度':<8} {'B':<5} {'G':<5} {'R':<5}")
output.append("-" * 35)
for x in range(0, w, 50):
    roi = top[10:60, x:min(x+50, w)]
    bgr = roi.mean(axis=(0, 1))
    tag = '亮' if bgr.mean() > 120 else '暗'
    output.append(f"{x:3d}-{min(x+49, w-1):<4d}  {tag:<8} {bgr[0]:3.0f} {bgr[1]:3.0f} {bgr[2]:3.0f}")

result = '\n'.join(output)
print(result)

# 保存
with open(os.path.join(CACHE, 'quick_scan.txt'), 'w', encoding='utf-8') as f:
    f.write(result)
print("DONE")
