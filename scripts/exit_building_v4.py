"""两步退出: 1)关退出对话框 2)关建造模式"""
import subprocess, time, os, sys, cv2, numpy as np

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJECT, 'cache')
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
os.makedirs(CACHE, exist_ok=True)
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

def analyze(img):
    r = analyzer.analyze(img)
    ocr = r['ocr_text']
    return {
        'building': '建造' in ocr,
        'exit_dialog': '是否退出游戏' in ocr,
        'ocr': ocr[:100]
    }

img = screencap(os.path.join(CACHE, 'eb4_start.png'))
state = analyze(img)
print(f"初始: building={state['building']} exit={state['exit_dialog']}")

# Step 1: 关退出对话框
if state['exit_dialog']:
    print("\nStep 1: 关闭退出对话框...")
    tap(834, 717)  # 退出对话框的取消按钮
    time.sleep(2)
    img = screencap(os.path.join(CACHE, 'eb4_step1.png'))
    state = analyze(img)
    print(f"  结果: building={state['building']} exit={state['exit_dialog']}")

# Step 2: 关建造模式
if state['building'] and not state['exit_dialog']:
    print("\nStep 2: 关闭建造模式...")
    
    # 策略: 尝试多个可能的关闭位置
    targets = [
        (1721, 49, "右上金色X"),
        (1887, 31, "最右上角"),
        (1751, 36, "右上暖金"),
        (1511, 551, "右侧按钮(可能是旋转/取消)"),
        (867, 555, "左侧按钮(确认)"),
        (1037, 551, "中间按钮(旋转)"),
        (181, 910, "左下暗金"),
    ]
    
    for x, y, desc in targets:
        tap(x, y)
        time.sleep(2)
        img = screencap(os.path.join(CACHE, f'eb4_{x}_{y}.png'))
        if img is None:
            continue
        state = analyze(img)
        print(f"  ({x},{y}) {desc}: building={state['building']} exit={state['exit_dialog']}")
        
        if not state['building']:
            print(f"\n✅ ({x},{y}) 成功退出建造模式!")
            cv2.imwrite(os.path.join(CACHE, 'eb4_success.png'), img)
            sys.exit(0)
        
        if state['exit_dialog']:
            # 又弹出了退出对话框，先关掉
            print(f"    又弹出退出对话框，关闭之...")
            tap(834, 717)
            time.sleep(2)

# Step 3: 如果还不行，试试连续back
print("\nStep 3: 连续back...")
for _ in range(3):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5, capture_output=True)
    time.sleep(0.8)
time.sleep(1)

img = screencap(os.path.join(CACHE, 'eb4_step3.png'))
state = analyze(img)
print(f"  结果: building={state['building']} exit={state['exit_dialog']}")
print(f"  OCR: {state['ocr']}")

# Step 4: 仔细扫描底部区域找到取消按钮
if state['building']:
    print("\nStep 4: 扫描底部区域(950-1050 全X)...")
    found_cancel = False
    for x in range(100, 1800, 50):
        tap(x, 1000)
        time.sleep(1.5)
        img = screencap(os.path.join(CACHE, 'eb4_scan.png'))
        if img is None:
            continue
        state = analyze(img)
        if not state['building']:
            print(f"\n✅ ({x}, 1000) 成功退出建造模式!")
            cv2.imwrite(os.path.join(CACHE, 'eb4_success.png'), img)
            found_cancel = True
            break
        # 关可能的退出对话框
        if state['exit_dialog']:
            tap(834, 717)
            time.sleep(1.5)
    
    if not found_cancel:
        print("  底部Y=1000扫描完毕，未找到取消")
        # 扫描Y=900
        print("  扫描Y=900...")
        for x in range(100, 1800, 50):
            tap(x, 900)
            time.sleep(1.5)
            # just check with OCR
            r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], timeout=15, capture_output=True)
            img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                continue
            state = analyze(img)
            if not state['building']:
                print(f"\n✅ ({x}, 900) 成功退出建造模式!")
                cv2.imwrite(os.path.join(CACHE, 'eb4_success.png'), img)
                found_cancel = True
                break
            if state['exit_dialog']:
                tap(834, 717)
                time.sleep(1.5)

print("\nDone")
