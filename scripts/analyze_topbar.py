"""分析当前截图顶部栏找到所有按钮"""
import cv2, numpy as np, subprocess, os

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
ADB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'

# 截图
path = os.path.join(CACHE, 'topbar_analysis.png')
with open(path, 'wb') as f:
    subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], stdout=f, timeout=15)

img = cv2.imread(path)
h, w = img.shape[:2]
output = [f'Screen: {w}x{h}']

# 分析顶部80px - 找按钮间隔
top = img[0:80, :, :]
gray = cv2.cvtColor(top, cv2.COLOR_BGR2GRAY)

# 分别看R、G、B通道来找按钮颜色
for ch_name, ch in [('B', top[:,:,0]), ('G', top[:,:,1]), ('R', top[:,:,2])]:
    ch_mean = ch.mean(axis=0)
    # 找方差大的列（可能是按钮边界）
    ch_diff = np.abs(np.diff(ch_mean, prepend=ch_mean[0]))
    peaks = np.where(ch_diff > 10)[0]
    if len(peaks) > 0:
        output.append(f'{ch_name} channel peaks (>10 diff): {list(peaks[:30])}')

# 检查每一行的颜色均值来看按钮区域
output.append(f'\nColumn brightness (every 20px):')
for x in range(0, w, 20):
    roi = top[10:60, x:min(x+40, w), :]
    mean_bgr = roi.mean(axis=(0,1))
    is_bright = mean_bgr.max() > 120
    tag = 'BRIGHT' if is_bright else 'dark'
    output.append(f'  X={x}: B={mean_bgr[0]:.0f} G={mean_bgr[1]:.0f} R={mean_bgr[2]:.0f} [{tag}]')

result = '\n'.join(output)
print(result)
with open(os.path.join(CACHE, 'topbar_analysis.txt'), 'w', encoding='utf-8') as f:
    f.write(result)
