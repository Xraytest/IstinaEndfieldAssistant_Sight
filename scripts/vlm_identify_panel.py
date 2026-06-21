"""用 ScreenAnalyzer 识别扫描打开的界面"""
import sys, os
from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()
from standard_flow_engine import ScreenAnalyzer
import cv2

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')

analyzer = ScreenAnalyzer()

# 分析点击(360,25)后打开的界面
img1 = cv2.imread(os.path.join(CACHE, 'v2_after_360_25.png'))
r1 = analyzer.analyze(img1)
print(f"=== (360,25) 界面 ===")
print(f"类型: {r1['page_type']}")
print(f"OCR: {r1['ocr_text'][:200]}")
print(f"VLM: {r1['vlm_judgment'][:200]}")

# 分析点击(360,35)后打开的界面
img2 = cv2.imread(os.path.join(CACHE, 'v2_after_360_35.png'))
r2 = analyzer.analyze(img2)
print(f"\n=== (360,35) 界面 ===")
print(f"类型: {r2['page_type']}")
print(f"OCR: {r2['ocr_text'][:200]}")
print(f"VLM: {r2['vlm_judgment'][:200]}")
