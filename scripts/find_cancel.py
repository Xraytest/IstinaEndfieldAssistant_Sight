"""扫描找到取消按钮"""
import subprocess, time, hashlib, os

ADB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')

def screencap(path):
    with open(path, 'wb') as f:
        subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], stdout=f, timeout=15)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(x), str(y)], timeout=10)

# 截图基准
before_path = os.path.join(CACHE, 'scan_before.png')
screencap(before_path)
before_hash = hashlib.md5(open(before_path, 'rb').read()).hexdigest()
print(f'基准hash: {before_hash[:8]}')

# 扫描网格
positions = []
for y in range(800, 1600, 100):
    for x in range(200, 900, 100):
        positions.append((x, y))

for x, y in positions:
    tap(x, y)
    time.sleep(1.5)
    
    after_path = os.path.join(CACHE, f'scan_{x}_{y}.png')
    screencap(after_path)
    after_hash = hashlib.md5(open(after_path, 'rb').read()).hexdigest()
    
    if after_hash != before_hash:
        print(f'HIT! ({x}, {y}) -> {after_hash[:8]}')
        break
    else:
        # 恢复基准（画面没变）
        before_hash = after_hash
else:
    print('未找到')
print('done')
