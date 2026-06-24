"""检测当前画面的金色元素和YOLO对象 - 无VLM依赖"""
import subprocess, time, os, cv2, numpy as np, sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJECT, '3rd-part', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(PROJECT, 'cache')

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()
from standard_flow_engine import ScreenAnalyzer
analyzer = ScreenAnalyzer()

# 截图
r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], timeout=15, capture_output=True)
img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
print(f"画面: {img.shape[1]}x{img.shape[0]}, mean={img.mean():.1f}, std={img.std():.1f}")
cv2.imwrite(os.path.join(CACHE, 'golden_analysis.png'), img)

# YOLO检测
yolo_objects = analyzer._detect_yolo(img)
print(f"\nYOLO对象 ({len(yolo_objects)}):")
for obj in yolo_objects[:15]:
    print(f"  {obj['class']}: ({obj['cx']},{obj['cy']}) {obj['w']}x{obj['h']} conf={obj['confidence']}")

# 金色元素
golden = analyzer._detect_golden(img)
print(f"\n金色元素 ({len(golden)}):")
for g in golden:
    y_label = ""
    if g['cy'] < 150:
        y_label = " [顶部]"
    elif g['cy'] > 850:
        y_label = " [底部]"
    elif g['cy'] > 700:
        y_label = " [中下]"
    print(f"  ({g['cx']:>4},{g['cy']:>4}) {g['w']:>3}x{g['h']:>3} area={g['area']:>8.1f} {g['range']}{y_label}")

# 底部区域分析
print(f"\n底部区域 (Y>800) 金色元素:")
bottom_golden = [g for g in golden if g['cy'] > 800]
if bottom_golden:
    for g in sorted(bottom_golden, key=lambda g: g['area'], reverse=True):
        print(f"  ({g['cx']},{g['cy']}) w={g['w']} h={g['h']} area={g['area']:.0f} {g['range']}")
else:
    print("  (无底部金色元素)")

# 顶部区域分析
print(f"\n顶部区域 (Y<150) 金色元素:")
top_golden = [g for g in golden if g['cy'] < 150]
for g in sorted(top_golden, key=lambda g: g['area'], reverse=True):
    print(f"  ({g['cx']},{g['cy']}) w={g['w']} h={g['h']} area={g['area']:.0f} {g['range']}")

# 右侧区域 (X>1200) 金色元素
print(f"\n右侧区域 (X>1200) 金色元素:")
right_golden = [g for g in golden if g['cx'] > 1200]
for g in sorted(right_golden, key=lambda g: g['area'], reverse=True):
    print(f"  ({g['cx']},{g['cy']}) w={g['w']} h={g['h']} area={g['area']:.0f} {g['range']}")

print("\nDone")
