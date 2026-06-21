"""检查游戏状态 - 纯像素分析"""
import subprocess, os, cv2, numpy as np

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(PROJECT, 'cache')

r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], timeout=15, capture_output=True)
img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
if img is None:
    print("ERROR: screenshot failed")
    import sys; sys.exit(1)

h, w = img.shape[:2]
center = img[h//4:3*h//4, w//4:3*w//4]
top = img[0:h//6, :]
bottom = img[5*h//6:h, :]

print(f"Size: {w}x{h}")
print(f"Full mean: {img.mean():.1f}")
print(f"Center mean: {center.mean():.1f}")
print(f"Top mean: {top.mean():.1f}")
print(f"Bottom mean: {bottom.mean():.1f}")

# 底部亮像素(UI文字/按钮)
bottom_gray = cv2.cvtColor(bottom, cv2.COLOR_BGR2GRAY)
bright_pixels = (bottom_gray > 150).sum()
print(f"Bottom bright ratio: {bright_pixels/bottom_gray.size:.3f}")

# 中心亮像素(3D场景)
center_gray = cv2.cvtColor(center, cv2.COLOR_BGR2GRAY)
center_bright = (center_gray > 100).sum()
print(f"Center bright ratio: {center_bright/center_gray.size:.3f}")

# 判断
# 建造模式: center暗, bottom有按钮白色文字
# World模式: center亮, bottom相对暗
cv2.imwrite(os.path.join(CACHE, 'pixel_check.png'), img)
print(f"\nSaved to {os.path.join(CACHE, 'pixel_check.png')}")

# 与已知的建造模式参考图对比
ref_path = os.path.join(CACHE, 'eq_ref_building.png')
if os.path.exists(ref_path):
    ref = cv2.imread(ref_path)
    if ref is not None:
        d = cv2.absdiff(ref, img)
        g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
        _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
        diff_px = cv2.countNonZero(t)
        print(f"Diff vs building ref: {diff_px:,} pixels")
        if diff_px > 500000:
            print(">>> 判断: 不在建造模式 (diff大)")
        else:
            print(">>> 判断: 仍在建造模式 (diff小)")
