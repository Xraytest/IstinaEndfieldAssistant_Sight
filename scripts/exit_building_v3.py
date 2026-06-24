"""点击取消按钮并验证"""
import subprocess, time, os, sys, cv2, numpy as np

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJECT, 'cache')
ADB = os.path.join(PROJECT, '3rd-part', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
from standard_flow_engine import ScreenAnalyzer
analyzer = ScreenAnalyzer()

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   timeout=10, capture_output=True)

def screencap(path):
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], timeout=15, capture_output=True)
    if len(r.stdout) < 1000:
        return None
    with open(path, 'wb') as f:
        f.write(r.stdout)
    return cv2.imread(path)

# 1. 截图确认当前状态
img = screencap(os.path.join(CACHE, 'eb3_before.png'))
if img is None:
    print("FAIL: 截图失败")
    sys.exit(1)

r = analyzer.analyze(img)
print(f"点击前: type={r['page_type']} build={'建造' in r['ocr_text']}")
print(f"OCR前60字: {r['ocr_text'][:60]}")

# 2. 点击取消按钮 - 使用金色元素 (1511, 551)
# 但这可能是错误的。OCR "确认 旋转 取消" 三按钮的实际位置需要通过 VLM 判断
# 先试试点击右下区域
print("\n尝试1: 点击 (1511, 551)...")
tap(1511, 551)
time.sleep(2)

img2 = screencap(os.path.join(CACHE, 'eb3_after1.png'))
if img2 is not None:
    r2 = analyzer.analyze(img2)
    build2 = '建造' in r2['ocr_text']
    print(f"结果: build={build2} OCR={r2['ocr_text'][:60]}")
    if not build2:
        print("✅ 退出建造模式!")
        sys.exit(0)

# 3. 尝试点击更大的取消区域 (OCR三按钮可能在底部)
print("\n尝试2: 点击 (1500, 800)...")
tap(1500, 800)
time.sleep(2)

img3 = screencap(os.path.join(CACHE, 'eb3_after2.png'))
if img3 is not None:
    r3 = analyzer.analyze(img3)
    build3 = '建造' in r3['ocr_text']
    print(f"结果: build={build3} OCR={r3['ocr_text'][:60]}")
    if not build3:
        print("✅ 退出建造模式!")
        sys.exit(0)

# 4. 尝试按 ESC (keyevent 111)
print("\n尝试3: 按 ESC...")
subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '111'], timeout=5, capture_output=True)
time.sleep(2)

img4 = screencap(os.path.join(CACHE, 'eb3_after3.png'))
if img4 is not None:
    r4 = analyzer.analyze(img4)
    build4 = '建造' in r4['ocr_text']
    print(f"结果: build={build4} OCR={r4['ocr_text'][:60]}")
    if not build4:
        print("✅ ESC退出建造模式!")
        sys.exit(0)
    print(f"完整OCR: {r4['ocr_text'][:200]}")

# 5. 尝试点击底部中间区域 (可能的三按钮位置)
print("\n尝试4: 点击底部按钮区域...")
# 假设三按钮在底部 Y=950-1050, X 从左到右排列
# 取消 = 最右, 约 X=1500-1700
tap(1600, 980)
time.sleep(2)

img5 = screencap(os.path.join(CACHE, 'eb3_after4.png'))
if img5 is not None:
    r5 = analyzer.analyze(img5)
    build5 = '建造' in r5['ocr_text']
    print(f"结果: build={build5} OCR={r5['ocr_text'][:60]}")

print("\n所有尝试已完成")
