"""快速测试建造模式取消按钮 - 轻量版"""
import subprocess, time, os, sys, cv2, numpy as np

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJECT, 'cache')
ADB = os.path.join(PROJECT, '3rd-part', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
os.makedirs(CACHE, exist_ok=True)
from standard_flow_engine import ScreenAnalyzer

print("Loading Analyzer...", flush=True)
analyzer = ScreenAnalyzer()
print("Analyzer ready.", flush=True)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   timeout=10, capture_output=True)

def cap():
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], timeout=15, capture_output=True)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def check(img):
    r = analyzer.analyze(img)
    ocr = r['ocr_text']
    return '建造' in ocr, '退出游戏' in ocr, ocr[:80]

# Step 1: 当前状态
print("\nChecking current state...", flush=True)
img = cap()
if img is None:
    print("ERROR: screenshot failed")
    sys.exit(1)
b, e, ocr = check(img)
print(f"build={b} exit_dialog={e} OCR={ocr}", flush=True)

# 关退出对话框
if e:
    print("Closing exit dialog...", flush=True)
    tap(834, 717)
    time.sleep(2)
    img = cap()
    b, e, ocr = check(img)
    print(f"After close: build={b} exit_dialog={e}", flush=True)

if not b:
    print("Already out of building mode!")
    sys.exit(0)

# Step 2: 尝试底部三按钮区域
# OCR: "确认 旋转 取消" - 从高到底扫描
print("\nScanning for cancel button...", flush=True)
found = False
for y in [1020, 1000, 980, 960, 940, 920, 900, 880]:
    if found:
        break
    for x in range(1700, 700, -100):
        tap(x, y)
        time.sleep(2)
        img = cap()
        if img is None:
            continue
        b_new, e_new, ocr_new = check(img)
        changed = b_new != b
        
        if changed:
            print(f"  ({x},{y}): build changed! b={b_new}", flush=True)
        if not b_new:
            print(f"\n✅ SUCCESS! ({x},{y}) exited building mode!", flush=True)
            cv2.imwrite(os.path.join(CACHE, 'exit_success.png'), img)
            found = True
            break
        if e_new and not e:
            print(f"  ({x},{y}): exit dialog appeared, closing...", flush=True)
            tap(834, 717)
            time.sleep(2)
            img = cap()
            b, e, ocr = check(img)

if not found:
    print("\n❌ All positions failed. Trying ESC + back approach...", flush=True)
    # 极端方案：反复按ESC和back
    for _ in range(3):
        subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5, capture_output=True)
        time.sleep(1)
    img = cap()
    b, e, ocr = check(img)
    print(f"After 3x back: build={b} exit={e} OCR={ocr}", flush=True)

print("\nDone.", flush=True)
