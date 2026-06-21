"""验证flows_config坐标 - 最小化版本"""
import subprocess, time, os, cv2, numpy as np, json, sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(PROJECT, 'cache')
os.makedirs(CACHE, exist_ok=True)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True, timeout=10)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], capture_output=True, timeout=5)

def cap():
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], capture_output=True, timeout=15)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def diff(a, b):
    d = cv2.absdiff(a, b)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)

# 从flows_config.json提取的待验证坐标
test_coords = [
    ("quest_icon", 855, 33, "任务图标"),
    ("event_icon", 928, 53, "活动图标"),
    ("menu_icon", 1392, 79, "菜单图标"),
    ("base_entry", 997, 85, "基建入口"),
    ("base_alt", 665, 57, "基建备用"),
    ("char_alt", 800, 220, "角色备用"),
    ("char_portrait", 1200, 330, "角色头像"),
    ("minimap", 120, 180, "小地图"),
    ("explore", 150, 150, "探索"),
    ("back_btn", 90, 120, "返回"),
    ("claim_all", 810, 900, "一键领取"),
    ("daily_claim", 975, 288, "每日领取"),
]

print("=" * 60, flush=True)
print("Verify flows_config coords", flush=True)
print("=" * 60, flush=True)

# 确保在world
for attempt in range(3):
    img = cap()
    if img is None:
        print("ERROR: cant screenshot", flush=True)
        sys.exit(1)
    
    m = img.mean()
    print(f"Current mean={m:.1f}", flush=True)
    
    # Test if world by clicking (300,80)
    before = cap()
    tap(300, 80)
    time.sleep(2.5)
    after = cap()
    d = diff(before, after)
    
    if d > 500000:
        print(f"  World confirmed: diff={d:,}", flush=True)
        # Close panel
        for _ in range(5):
            back()
            time.sleep(0.5)
        break
    else:
        print(f"  Not world (diff={d:,}), trying back...", flush=True)
        for _ in range(8):
            back()
            time.sleep(0.3)
else:
    print("Cant reach world, trying force restart...", flush=True)
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'force-stop', 'com.hypergryph.endfield'],
                   capture_output=True, timeout=10)
    time.sleep(3)
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'start', '-n',
                    'com.hypergryph.endfield/com.u8.sdk.U8UnityContext'],
                   capture_output=True, timeout=10)
    time.sleep(30)
    for _ in range(5):
        tap(960, 540)
        time.sleep(4)
    time.sleep(30)

# 验证每个坐标
results = []
for name, x, y, desc in test_coords:
    before = cap()
    if before is None:
        continue
    
    tap(x, y)
    time.sleep(2.5)
    
    after = cap()
    if after is None:
        continue
    
    d = diff(before, after)
    bm = before.mean()
    am = after.mean()
    
    tag = "BIG" if d > 800000 else ("MID" if d > 200000 else "low")
    
    print(f"[{tag}] ({x:>4},{y:>3}) {name:20s} diff={d:>10,}  mean: {bm:.0f}->{am:.0f}  {desc}", flush=True)
    
    # Save if big change
    if d > 500000:
        cv2.imwrite(os.path.join(CACHE, f'verify_{name}_before.png'), before)
        cv2.imwrite(os.path.join(CACHE, f'verify_{name}_after.png'), after)
    
    results.append({"name": name, "x": x, "y": y, "diff": int(d), "before_mean": float(bm), "after_mean": float(am)})
    
    # Go back
    for _ in range(6):
        back()
        time.sleep(0.5)
    time.sleep(1)

# Save
with open(os.path.join(CACHE, 'verify_coords.json'), 'w') as f:
    json.dump(results, f, indent=2)

print("\nDone", flush=True)
