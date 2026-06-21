"""确认当前游戏画面状态"""
import subprocess, time, os, sys, cv2

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJECT, 'cache')
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
os.makedirs(CACHE, exist_ok=True)

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()
from standard_flow_engine import ScreenAnalyzer
analyzer = ScreenAnalyzer()

def screencap(path):
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], timeout=15, capture_output=True)
    if len(r.stdout) < 1000:
        return None
    with open(path, 'wb') as f:
        f.write(r.stdout)
    return cv2.imread(path)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   timeout=10, capture_output=True)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5, capture_output=True)

# 先截图当前状态
img = screencap(os.path.join(CACHE, 'cs_current.png'))
print(f"当前画面: {img.shape[1]}x{img.shape[0]}")
r = analyzer.analyze(img)
print(f"类型: {r['page_type']}")
print(f"OCR: {r['ocr_text'][:500]}")
print(f"VLM: {r['vlm_judgment'][:300]}")

# 如果是world，尝试回到正常world（可能卡在退出对话框）
if '退出' in r['ocr_text'] or '确认' in r['ocr_text']:
    print("\n检测到退出对话框，按取消...")
    tap(834, 717)
    time.sleep(2)
    
    img2 = screencap(os.path.join(CACHE, 'cs_after_cancel.png'))
    r2 = analyzer.analyze(img2)
    print(f"关闭后: type={r2['page_type']}")
    print(f"OCR: {r2['ocr_text'][:300]}")

# 尝试回世界
print("\n尝试回到世界...")
for i in range(5):
    back()
    time.sleep(0.8)

time.sleep(1)
img3 = screencap(os.path.join(CACHE, 'cs_after_backs.png'))
r3 = analyzer.analyze(img3)
print(f"\n5次back后: type={r3['page_type']}")
print(f"OCR: {r3['ocr_text'][:300]}")

# 再用VLM确认是否在探索/world
print(f"\n最终确认: VLM={r3['vlm_judgment'][:200]}")
