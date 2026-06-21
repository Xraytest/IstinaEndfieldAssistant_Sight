"""扫描顶部栏找按钮位置"""
import cv2, numpy as np, os

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
img = cv2.imread(os.path.join(CACHE, 'after_back2.png'))
h, w = img.shape[:2]

output = [f'尺寸: {w}x{h}']

# 分析顶部80px
top = img[0:80, :, :]
gray = cv2.cvtColor(top, cv2.COLOR_BGR2GRAY)
edges = cv2.Canny(gray, 30, 100)

edge_cols = edges.sum(axis=0)
active = np.where(edge_cols > 20)[0]

if len(active) > 0:
    groups = []
    start = active[0]
    prev = active[0]
    for x in active[1:]:
        if x - prev > 15:
            groups.append((int(start), int(prev), int(edge_cols[start:prev+1].max())))
            start = x
        prev = x
    groups.append((int(start), int(prev), int(edge_cols[start:prev+1].max())))

    buttons = [(s,e,m) for s,e,m in groups if e-s > 20]
    output.append(f'可能的按钮X区域(>20px宽):')
    for s, e, m in buttons:
        cx = (s+e)//2
        output.append(f'  X={s}-{e} 中心={cx} 边缘强度={m}')

# 显示非黑行的分布（了解游戏内容区域）
row_nonblack = (gray > 20).sum(axis=1)
for r in range(80):
    if row_nonblack[r] > 50:
        output.append(f'  行{r}: {row_nonblack[r]} 非黑像素')
        break

result = '\n'.join(output)
print(result)
with open(os.path.join(CACHE, 'topbar_scan.txt'), 'w', encoding='utf-8') as f:
    f.write(result)
