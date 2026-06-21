"""强力回到 world 状态并验证"""
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

def diff_count(img_a, img_b):
    if img_a is None or img_b is None:
        return 0
    d = cv2.absdiff(img_a, img_b)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)

print("强力回到 world...")

# 策略: 多次back + 关退出对话框，直到工业面板能打开
for round_num in range(10):
    # 关退出对话框
    tap(834, 717)
    time.sleep(1)
    
    for _ in range(4):
        back()
        time.sleep(0.4)
    time.sleep(1)
    
    img = cap()
    if img is None:
        continue
    
    m = img.mean()
    print(f"  Round {round_num+1}: mean={m:.1f}", flush=True)
    cv2.imwrite(os.path.join(CACHE, f'recover_{round_num}.png'), img)
    
    # 测试: 点工业面板
    tap(300, 80)
    time.sleep(2.5)
    
    img2 = cap()
    if img2 is None:
        continue
    
    d = diff_count(img, img2)
    print(f"    工业面板 diff={d:,}", flush=True)
    
    if d > 800000:
        print(f"\n✅ Round {round_num+1}: 成功回到 world! 面板已打开!")
        cv2.imwrite(os.path.join(CACHE, 'world_confirmed.png'), img2)
        break
    
    # 如果面板没打开，多按几次back
    for _ in range(2):
        back()
        time.sleep(0.4)

print("\nDone")
