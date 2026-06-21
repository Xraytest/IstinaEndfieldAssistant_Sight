"""尝试从当前菜单回到 world"""
import subprocess, time, os, cv2, numpy as np

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(PROJECT, 'cache')

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   timeout=10, capture_output=True)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5, capture_output=True)

def keyevent(code):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', str(code)], timeout=5, capture_output=True)

def cap():
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], timeout=15, capture_output=True)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

# 策略: 尝试多个退出路径
strategies = [
    ("top_left_golden", lambda: tap(161, 33)),
    ("back_x5", lambda: [back() or time.sleep(0.3) for _ in range(5)]),
    ("center_golden", lambda: tap(1154, 718)),
    ("bottom_golden", lambda: tap(1476, 871)),
    ("ESC", lambda: keyevent(111)),
    ("top_right_X", lambda: tap(1864, 31)),
    ("back_x10", lambda: [back() or time.sleep(0.3) for _ in range(10)]),
]

for name, action in strategies:
    img = cap()
    if img is None:
        continue
    m = img.mean()
    print(f"\n{name}: before mean={m:.1f}", flush=True)
    
    action()
    time.sleep(2)
    
    img2 = cap()
    if img2 is not None:
        m2 = img2.mean()
        d = cv2.absdiff(img, img2)
        g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
        _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
        diff = cv2.countNonZero(t)
        print(f"  after mean={m2:.1f} diff={diff:,}", flush=True)
        cv2.imwrite(os.path.join(CACHE, f'escape_{name}.png'), img2)

# 最终检查: 尝试打开工业面板
print("\n\n最终测试: 打开工业面板...", flush=True)
img_before = cap()
if img_before is not None:
    tap(300, 80)
    time.sleep(2.5)
    img_after = cap()
    if img_after is not None:
        d = cv2.absdiff(img_before, img_after)
        g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
        _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
        diff = cv2.countNonZero(t)
        print(f"  工业面板 diff={diff:,}", flush=True)
        if diff > 800000:
            print("  ✅ 回到 WORLD! 面板已打开!", flush=True)
        else:
            print("  ❌ 未回到 world", flush=True)

print("\nDone", flush=True)
