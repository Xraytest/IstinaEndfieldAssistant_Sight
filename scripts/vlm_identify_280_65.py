"""识别 (280,65) 按钮打开的界面"""
import sys, os, cv2
from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()
from standard_flow_engine import ScreenAnalyzer

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
analyzer = ScreenAnalyzer()

img = cv2.imread(os.path.join(CACHE, 'v2b_after_280_65.png'))
r = analyzer.analyze(img)
print(f'=== (280,65) 界面 ===')
print(f'类型: {r["page_type"]}')
print(f'OCR: {r["ocr_text"][:300]}')
print(f'VLM: {r["vlm_judgment"][:200]}')
