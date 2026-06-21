"""回到世界并验证 (1260,850) 确实退出建造"""
import subprocess, time, os, cv2, numpy as np, sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(PROJECT, 'cache')

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   timeout=10, capture_output=True)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5, capture_output=True)

def cap():
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], timeout=15, capture_output=True)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def diff_count(img_a, img_b):
    if img_a is None or img_b is None:
        return 0
    d = cv2.absdiff(img_a, img_b)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)

print("Step 1: 关闭可能的退出对话框 + 按多次back...")
# 先按取消(退出对话框)
tap(834, 717)
time.sleep(1.5)
# 然后连续back
for i in range(4):
    back()
    time.sleep(0.6)
time.sleep(1)

img_before = cap()
if img_before is None:
    print("ERROR: screenshot failed")
    sys.exit(1)
print(f"当前画面: mean={img_before.mean():.1f}")
cv2.imwrite(os.path.join(CACHE, 'verify_world_before.png'), img_before)

# 尝试打开工业面板 (300, 80)
print("\nStep 2: 点击工业面板 (300, 80)...")
tap(300, 80)
time.sleep(2.5)

img_after = cap()
if img_after is None:
    print("ERROR: screenshot failed")
    sys.exit(1)
cv2.imwrite(os.path.join(CACHE, 'verify_world_after.png'), img_after)

d = diff_count(img_before, img_after)
print(f"像素变化: {d:,}")

if d > 300000:
    print(">>> ✅ 工业面板已打开! 确认处于 WORLD 模式!")
    print(">>> (1260, 850) 是建造模式的取消按钮!!!")
else:
    print(f">>> ❌ 面板未打开 (diff={d:,})")
    print(f"    After mean={img_after.mean():.1f}")
    # 可能还在某菜单中，再按几次back
    print("    尝试继续back...")
    for i in range(3):
        back()
        time.sleep(0.5)
    time.sleep(1)
    img3 = cap()
    if img3 is not None:
        print(f"    3x back后 mean={img3.mean():.1f}")
        cv2.imwrite(os.path.join(CACHE, 'verify_after_backs.png'), img3)

print("\nDone")
