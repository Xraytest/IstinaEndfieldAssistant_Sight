"""诊断并恢复游戏响应"""
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

def diff(img_a, img_b):
    if img_a is None or img_b is None:
        return -1
    d = cv2.absdiff(img_a, img_b)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)

print("=== 设备诊断 ===")

# 1. 检查ADB连接
r = subprocess.run([ADB, '-s', SERIAL, 'shell', 'echo', 'OK'], timeout=10, capture_output=True)
print(f"ADB: {'OK' if b'OK' in r.stdout else 'FAIL'} ({r.stdout.decode().strip()})")

# 2. 唤醒设备
print("\n唤醒设备...")
keyevent(26)  # POWER
time.sleep(0.5)
keyevent(82)  # UNLOCK
time.sleep(0.5)

# 3. 截图对比
img1 = cap()
if img1 is None:
    print("ERROR: 截图失败!")
    import sys; sys.exit(1)

print(f"\n截图1: shape={img1.shape}, mean={img1.mean():.1f}, std={img1.std():.1f}")
cv2.imwrite(os.path.join(CACHE, 'diag_1.png'), img1)

# 4. 点击屏幕中央
tap(960, 540)
time.sleep(2)

img2 = cap()
if img2 is not None:
    d = diff(img1, img2)
    print(f"点击(960,540)后: mean={img2.mean():.1f}, std={img2.std():.1f}, diff={d}")
    cv2.imwrite(os.path.join(CACHE, 'diag_2.png'), img2)
else:
    print("点击后截图失败!")

# 5. 尝试返回
back()
time.sleep(1.5)
img3 = cap()
if img3 is not None:
    d2 = diff(img2, img3) if img2 is not None else -1
    print(f"Back后: mean={img3.mean():.1f}, std={img3.std():.1f}, diff={d2}")
    cv2.imwrite(os.path.join(CACHE, 'diag_3.png'), img3)

# 6. 检查图像标准差 - 是否接近纯色
if img1.std() < 10:
    print("\n⚠️ 图像标准差极低 - 可能冻结/黑屏/加载画面")
elif img1.std() < 40:
    print("\n⚠️ 图像标准差较低 - 可能静置画面")
else:
    print(f"\n图像正常 (std={img1.std():.1f})")

print("\nDone")
