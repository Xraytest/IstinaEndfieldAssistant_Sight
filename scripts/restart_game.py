"""强制重启游戏并导航到 world"""
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

def cap():
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], timeout=15, capture_output=True)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

print("Step 1: 强制停止游戏...", flush=True)
subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'force-stop', 'com.hypergryph.endfield'],
               capture_output=True, timeout=10)
time.sleep(3)

print("Step 2: 启动游戏...", flush=True)
subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'start', '-n',
                'com.hypergryph.endfield/com.u8.sdk.U8UnityContext'],
               capture_output=True, timeout=10)

print("Step 3: 等待加载...", flush=True)
# 等待游戏启动+标题画面
for i in range(40):
    time.sleep(3)
    img = cap()
    if img is not None:
        m = img.mean()
        std = img.std()
        if m > 20 and std > 20:
            print(f"  [{i*3}s] 画面就绪: mean={m:.1f} std={std:.1f}", flush=True)
            cv2.imwrite(os.path.join(CACHE, f'boot_{i*3}s.png'), img)
            if m > 50 and std > 40:
                print(f"  看起来已到达标题/主画面", flush=True)
                break
        else:
            print(f"  [{i*3}s] 黑屏/加载中: mean={m:.1f}", flush=True)

print("\nStep 4: 点击进入游戏...", flush=True)
# 标题画面需要点击进入
for _ in range(5):
    tap(960, 540)  # 点击任意位置
    time.sleep(4)

print("Step 5: 等待世界加载...", flush=True)
for i in range(30):
    time.sleep(3)
    img = cap()
    if img is not None:
        m = img.mean()
        std = img.std()
        cv2.imwrite(os.path.join(CACHE, f'world_wait_{i*3}s.png'), img)
        if m > 80 and std > 50:
            print(f"  [{i*3}s] mean={m:.1f} std={std:.1f} - 可能已进入世界", flush=True)
            break
        elif m < 20:
            print(f"  [{i*3}s] 加载中 (黑屏)", flush=True)
        else:
            print(f"  [{i*3}s] mean={m:.1f} std={std:.1f}", flush=True)

print("\nStep 6: 验证世界状态...", flush=True)
for attempt in range(5):
    img_before = cap()
    if img_before is None:
        continue
    tap(300, 80)
    time.sleep(2.5)
    img_after = cap()
    if img_after is None:
        continue
    
    d = cv2.absdiff(img_before, img_after)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    diff = cv2.countNonZero(t)
    
    m = img_after.mean()
    print(f"  Attempt {attempt+1}: diff={diff:,} mean={m:.1f}", flush=True)
    
    if diff > 800000:
        print(f"\n✅ 游戏已重启并进入 WORLD!", flush=True)
        cv2.imwrite(os.path.join(CACHE, 'world_restarted.png'), img_after)
        break
    else:
        # 可能还需要更多back
        for _ in range(3):
            back()
            time.sleep(0.5)

print("\nDone", flush=True)
