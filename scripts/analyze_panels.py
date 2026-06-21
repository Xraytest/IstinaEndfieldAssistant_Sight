"""分析武陵工业计划面板的内容和导航选项"""
import sys, os, cv2, json

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()
from standard_flow_engine import ScreenAnalyzer

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
analyzer = ScreenAnalyzer()

# 分析武陵工业计划面板
img = cv2.imread(os.path.join(CACHE, 'test_活动(左)_before.png'))
if img is None:
    img = cv2.imread(os.path.join(CACHE, 'v2_after_360_25.png'))

r = analyzer.analyze(img)
print(f'=== 武陵工业计划面板 ===')
print(f'类型: {r["page_type"]}')
print(f'完整OCR:')
print(r['ocr_text'])
print(f'\nVLM判断: {r["vlm_judgment"]}')
print(f'\n金色元素: {len(r["golden_elements"])}个')
print(f'YOLO: {r["yolo_objects"]}')

# 也分析世界截图中的顶部栏
img_world = cv2.imread(os.path.join(CACHE, 'nav_world.png'))
if img_world is not None:
    # 只裁剪顶部区域
    top = img_world[0:80, :, :]
    r_top = analyzer.analyze(top)
    print(f'\n=== 世界顶部栏 ===')
    print(f'OCR: {r_top["ocr_text"][:200]}')
