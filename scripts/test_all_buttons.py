"""测试所有已知顶部栏按钮位置"""
import subprocess, time, os, sys, cv2

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
ADB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
from standard_flow_engine import ScreenAnalyzer

def screencap(path):
    with open(path, 'wb') as f:
        subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], stdout=f, timeout=15)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(x), str(y)], timeout=10)

def go_back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5)
    time.sleep(2)

def dismiss_dialog():
    """尝试关闭退出对话框"""
    # 点击取消按钮 (960, 717 for 1920x1080)
    tap(960, 717)
    time.sleep(1)

analyzer = ScreenAnalyzer()
output = []

# 1920x1080 下的按钮中心坐标(基于 game_coords.py TOP_BAR_BUTTONS)
buttons = [
    ("exploration", 75, 27),
    ("back", 675, 27),
    ("shop", 720, 27),
    ("event", 765, 27),
    ("signin", 810, 27),
    ("tasks", 855, 27),
    ("inventory", 900, 27),
    ("settings", 990, 27),
]

for name, x, y in buttons:
    # 截图前
    before_path = os.path.join(CACHE, f'btn_{name}_before.png')
    screencap(before_path)
    img_b = cv2.imread(before_path)
    r_b = analyzer.analyze(img_b)
    
    # 如果看到退出对话框，先关闭
    if 'exit' in r_b['page_type'] or '退出' in r_b['ocr_text']:
        dismiss_dialog()
        time.sleep(1.5)
        go_back()
        time.sleep(1.5)
        screencap(before_path)
        img_b = cv2.imread(before_path)
        r_b = analyzer.analyze(img_b)
    
    # 点击
    tap(x, y)
    time.sleep(2.5)
    
    # 截图后
    after_path = os.path.join(CACHE, f'btn_{name}_after.png')
    screencap(after_path)
    img_a = cv2.imread(after_path)
    r_a = analyzer.analyze(img_a)
    
    output.append(f'{name} ({x},{y}): {r_b["page_type"]} -> {r_a["page_type"]}')
    output.append(f'  OCR after: {r_a["ocr_text"][:80]}')
    
    # 返回
    go_back()
    time.sleep(1.5)
    # 如果有退出对话框
    dismiss_dialog()
    time.sleep(1)
    output.append('')

result = '\n'.join(output)
print(result)
open(os.path.join(CACHE, 'all_buttons_test.txt'), 'w', encoding='utf-8').write(result)
