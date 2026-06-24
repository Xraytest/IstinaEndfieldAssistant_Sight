"""分析退出对话框中心区域"""
import cv2, numpy as np, os

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
img = cv2.imread(os.path.join(CACHE, 'ocr_test_720.png'))
h, w = img.shape[:2]

# 分析中心区域 (对话框通常居中)
center = img[200:800, 400:1500, :]
cgray = cv2.cvtColor(center, cv2.COLOR_BGR2GRAY)

# 找暗色区域(对话框背景)
_, dark = cv2.threshold(cgray, 50, 255, cv2.THRESH_BINARY_INV)
contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print('中心暗色区域:')
for cnt in contours:
    x, y, bw, bh = cv2.boundingRect(cnt)
    if bw > 50 and bh > 50:
        ax, ay = x + 400, y + 200
        print(f'  ({ax},{ay}) {bw}x{bh}')

# 分析中心区域每个像素行
print('\n中心Y=200-800亮度(每20px):')
for y_ in range(200, 800, 20):
    roi = img[y_:y_+20, 400:1500, :]
    bgr_mean = roi.mean(axis=(0, 1))
    gray_mean = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).mean()
    bright_count = (cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) > 150).sum()
    tag = '暗' if gray_mean < 80 else '亮'
    print(f'  Y={y_}: {tag} gray={gray_mean:.0f} B={bgr_mean[0]:.0f} bright={bright_count}')

# 尝试找白色文字区域
_, white = cv2.threshold(cgray, 200, 255, cv2.THRESH_BINARY)
# 膨胀
kernel = np.ones((3, 15), np.uint8)
white_dilated = cv2.dilate(white, kernel, iterations=1)
wcontours, _ = cv2.findContours(white_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print(f'\n白色文字候选区域:')
for cnt in wcontours:
    x, y, bw, bh = cv2.boundingRect(cnt)
    if 20 < bw < 300 and 10 < bh < 100:
        ax, ay = x + 400, y + 200
        print(f'  ({ax},{ay}) {bw}x{bh}')

# 保存中心区域便于查看
cv2.imwrite(os.path.join(CACHE, 'dialog_center.png'), center)
print('\n中心区域保存到 dialog_center.png')
