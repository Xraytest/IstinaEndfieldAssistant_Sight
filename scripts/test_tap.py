"""简单测试：点击坐标 + 截图对比"""
import subprocess, time, hashlib, sys, os

ADB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')

def screencap(path):
    with open(path, 'wb') as f:
        subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], stdout=f, timeout=15)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(x), str(y)], timeout=10)

# 截图前
before_path = os.path.join(CACHE, 'test_before.png')
screencap(before_path)
b1 = open(before_path, 'rb').read()
h1 = hashlib.md5(b1).hexdigest()[:8]
print(f'before: {h1}', flush=True)

# 点击 (855, 33) - nav_coords quest_icon
tap(855, 33)
time.sleep(3)

# 截图后
after_path = os.path.join(CACHE, 'test_after.png')
screencap(after_path)
a1 = open(after_path, 'rb').read()
h2 = hashlib.md5(a1).hexdigest()[:8]
print(f'after: {h2}, changed={h1!=h2}', flush=True)
print('done', flush=True)
