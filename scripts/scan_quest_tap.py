"""系统扫描X坐标找到任务按钮"""
import subprocess, time, hashlib, os, json

ADB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')

def screencap(path):
    with open(path, 'wb') as f:
        subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], stdout=f, timeout=15)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(x), str(y)], timeout=10)

def go_back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5)
    time.sleep(2)

results = {}

# 扫描X: 300-1100 at y=33, step 50
for x in range(300, 1150, 50):
    # 截图前
    before_path = os.path.join(CACHE, f'scan_before_{x}.png')
    screencap(before_path)
    before_hash = hashlib.md5(open(before_path, 'rb').read()).hexdigest()
    
    # 点击
    tap(x, 33)
    time.sleep(2)
    
    # 截图后
    after_path = os.path.join(CACHE, f'scan_{x}_33.png')
    screencap(after_path)
    after_hash = hashlib.md5(open(after_path, 'rb').read()).hexdigest()
    
    changed = before_hash != after_hash
    results[x] = {'changed': changed, 'before': before_hash[:8], 'after': after_hash[:8]}
    
    if changed:
        print(f'X={x}: CHANGED ({before_hash[:8]} -> {after_hash[:8]})')
    else:
        print(f'X={x}: same')
    
    # 返回世界
    go_back()

result_path = os.path.join(CACHE, 'scan_results.json')
with open(result_path, 'w') as f:
    json.dump(results, f, indent=2)
print(f'\nResults saved to {result_path}')
