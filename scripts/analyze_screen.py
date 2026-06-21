"""分析当前屏幕，找顶部栏按钮位置"""
import cv2, numpy as np, subprocess, os, sys

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
ADB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'

# 截图
screenshot_path = os.path.join(CACHE, 'current_world.png')
with open(screenshot_path, 'wb') as f:
    subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], stdout=f, timeout=15)

img = cv2.imread(screenshot_path)
if img is None:
    print("ERROR: 截图读取失败")
    sys.exit(1)

h, w = img.shape[:2]
res = [f'尺寸: {w}x{h}']

# 分析顶部100px区域
top = img[0:100, :, :]
gray = cv2.cvtColor(top, cv2.COLOR_BGR2GRAY)

# 找非黑区域
row_nonblack = (gray > 20).sum(axis=1)
top_content_start = np.where(row_nonblack > 50)[0]
if len(top_content_start) > 0:
    res.append(f'顶部内容起始行: {top_content_start[0]}')
else:
    res.append('顶部100px全黑')

# 分析非黑像素分布 - 找按钮列
col_nonblack = (gray > 30).sum(axis=0)
# 找活跃区域（有内容的列）
active_cols = np.where(col_nonblack > 5)[0]
if len(active_cols) > 0:
    # 找连续活跃区域
    gaps = np.diff(active_cols)
    breaks = np.where(gaps > 20)[0]
    regions = []
    start = active_cols[0]
    for b in breaks:
        end = active_cols[b]
        if end - start > 15:
            regions.append((int(start), int(end)))
        start = active_cols[b + 1]
    end = active_cols[-1]
    if end - start > 15:
        regions.append((int(start), int(end)))
    
    res.append(f'顶部按钮区域 (x范围): {regions[:10]}')

# 缩放保存1280版本
img_small = cv2.resize(img, (1280, 720))
small_path = os.path.join(CACHE, 'current_world_1280.png')
cv2.imwrite(small_path, img_small)
res.append(f'已保存: {small_path}')

# 输出
output = '\n'.join(res)
print(output)
result_path = os.path.join(CACHE, 'screen_analysis.txt')
with open(result_path, 'w', encoding='utf-8') as f:
    f.write(output)
