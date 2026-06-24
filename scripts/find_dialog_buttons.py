"""在退出对话框截图中找到取消/确认按钮"""
import cv2, numpy as np, os

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
# 使用已有的退出对话框截图
img = cv2.imread(os.path.join(CACHE, 'ocr_test_720.png'))
h, w = img.shape[:2]
print(f'Resolution: {w}x{h}')

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# 找底部区域（按钮通常在下半部分）
bottom = img[h//3:, :, :]
bgray = cv2.cvtColor(bottom, cv2.COLOR_BGR2GRAY)

# 找亮色区域(按钮文字/边框)
_, bright = cv2.threshold(bgray, 180, 255, cv2.THRESH_BINARY)

# 找连通区域
contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
button_candidates = []
for cnt in contours:
    x, y, bw, bh = cv2.boundingRect(cnt)
    if 50 < bw < 400 and 30 < bh < 200:
        cx = x + bw // 2
        cy = y + bh // 2 + h // 3
        button_candidates.append((cx, cy, bw, bh))

print(f'找到 {len(button_candidates)} 个候选按钮区域')
for i, (cx, cy, bw, bh) in enumerate(button_candidates):
    print(f'  按钮{i}: center=({cx},{cy}) size={bw}x{bh}')

# 找暗色背景上的亮色按钮（退出对话框特有的暗色面板）
# 先找大的暗色矩形区域
_, dark = cv2.threshold(bgray, 60, 255, cv2.THRESH_BINARY_INV)
# 膨胀后找大块区域
kernel = np.ones((20, 20), np.uint8)
dark_dilated = cv2.dilate(dark, kernel, iterations=2)
dark_contours, _ = cv2.findContours(dark_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
for cnt in dark_contours:
    x, y, bw, bh = cv2.boundingRect(cnt)
    if bw > 200 and bh > 100:
        print(f'  暗色面板: ({x},{y+h//3}) {bw}x{bh}')

# 分析底部2/3区域的列亮度
print('\n底部Y=360-720亮度分析(每50px):')
for y_ in range(360, 720, 50):
    roi = img[y_:min(y_+50, h), :, :]
    bgr = roi.mean(axis=(0, 1))
    bright_count = (cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) > 150).sum()
    tag = '亮' if bgr.mean() > 80 else '暗'
    print(f'  Y={y_}: {tag} B={bgr[0]:.0f} G={bgr[1]:.0f} R={bgr[2]:.0f} bright_px={bright_count}')
