"""VLM 定位建造模式中的取消按钮"""
import subprocess, time, os, sys, cv2, numpy as np

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJECT, 'cache')
ADB = os.path.join(PROJECT, '3rd-part', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
os.makedirs(CACHE, exist_ok=True)
from standard_flow_engine import ScreenAnalyzer
analyzer = ScreenAnalyzer()

def screencap(path):
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], timeout=15, capture_output=True)
    if len(r.stdout) < 1000:
        print(f"  screencap failed: {len(r.stdout)} bytes")
        return None
    with open(path, 'wb') as f:
        f.write(r.stdout)
    return cv2.imread(path)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   timeout=10, capture_output=True)

# 1. 截图
img = screencap(os.path.join(CACHE, 'ev2_current.png'))
if img is None:
    print("ERROR: screenshot failed")
    sys.exit(1)

print(f"截图: {img.shape[1]}x{img.shape[0]}")

# 2. 完整 VLM 分析
r = analyzer.analyze(img)
print(f"\ntype: {r['page_type']}")
print(f"OCR全文:\n{r['ocr_text']}")
print(f"\nVLM: {r['vlm_judgment'][:500]}")
print(f"\n金色元素 ({len(r.get('golden_elements', []))}):")
for g in r.get('golden_elements', []):
    print(f"  {g}")

# 3. 搜索OCR中的"取消"位置
ocr = r['ocr_text']
if '取消' in ocr:
    print("\n✅ OCR中找到'取消'")
    # 搜索带位置信息的OCR结果
    if 'ocr_boxes' in r:
        for box in r['ocr_boxes']:
            if '取消' in box.get('text', ''):
                print(f"  取消按钮位置: {box}")
    else:
        print("  (无位置信息)")

# 4. 如果有金色元素，分析哪些可能是取消按钮
golden = r.get('golden_elements', [])
for g in golden:
    x, y, w, h = g.get('bbox', [0,0,0,0])
    cx, cy = x + w//2, y + h//2
    print(f"  金色元素: bbox={g.get('bbox')} center=({cx},{cy}) area={w*h}")

print("\nDone - 请根据上述信息定位取消按钮")
