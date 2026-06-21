"""导航按钮映射 v2 - 使用正确Y坐标 + ESC关闭面板"""
import subprocess, time, os, cv2, numpy as np, json, sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(PROJECT, 'cache')
os.makedirs(CACHE, exist_ok=True)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   timeout=10, capture_output=True)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5, capture_output=True)

def esc():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '111'], timeout=5, capture_output=True)

def cap():
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], timeout=15, capture_output=True)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def pixel_diff(img1, img2):
    d = cv2.absdiff(img1, img2)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)

def restart_game():
    """强制重启游戏"""
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'force-stop', 'com.hypergryph.endfield'],
                   capture_output=True, timeout=10)
    time.sleep(3)
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'start', '-n',
                    'com.hypergryph.endfield/com.u8.sdk.U8UnityContext'],
                   capture_output=True, timeout=10)
    time.sleep(25)
    # 点击进入游戏
    for _ in range(5):
        tap(960, 540)
        time.sleep(4)
    # 等待到达world
    for i in range(20):
        time.sleep(3)
        img = cap()
        if img is not None and img.mean() > 80 and img.std() > 50:
            # 验证world
            before = cap()
            tap(300, 80)
            time.sleep(2.5)
            after = cap()
            if before is not None and after is not None:
                diff = pixel_diff(before, after)
                if diff > 800000:
                    print("  [RESTART] 已到达world", flush=True)
                    # 关闭面板
                    for _ in range(3):
                        back()
                        time.sleep(1)
                    return True
        print(f"  [RESTART] 等待中... ({i*3}s)", flush=True)
    return False

# == 测试点位 ==
# 顶部栏 Y=40 (基于scan_nav_clean.py命中区域)
# 底部栏 Y=930 (基于scan_nav_clean.py命中区域)

test_batches = [
    # Batch 1: 顶部栏导航按钮 (Y=40, X从400到1860)
    {
        "label": "top_bar",
        "y": 40,
        "x_positions": list(range(400, 1900, 60)),  # 步长60px
    },
    # Batch 2: 顶部栏黄金元素下方 (Y=60)
    {
        "label": "top_bar_y60",
        "y": 60,
        "x_positions": list(range(400, 1900, 60)),
    },
    # Batch 3: 底部栏 (Y=930, 重点区域)
    {
        "label": "bottom_bar",
        "y": 930,
        "x_positions": list(range(300, 1900, 40)),  # 步长40px
    },
]

results = []
BASELINE_MEAN = None

print("=" * 60, flush=True)
print("导航按钮映射 v2", flush=True)
print("=" * 60, flush=True)

# 确认world状态
baseline = cap()
if baseline is None:
    print("ERROR: 无法截图", flush=True)
    sys.exit(1)

BASELINE_MEAN = baseline.mean()
print(f"基准画面: {baseline.shape[1]}x{baseline.shape[0]}, mean={BASELINE_MEAN:.1f}", flush=True)

# 验证world
before = cap()
tap(300, 80)
time.sleep(2.5)
after = cap()
if before is not None and after is not None:
    diff = pixel_diff(before, after)
    if diff > 800000:
        print(f"  [OK] World状态确认 (工业面板 diff={diff:,})", flush=True)
        for _ in range(3):
            back()
            time.sleep(1)
    else:
        print(f"  [WARN] 可能不在world (diff={diff:,})，尝试重启...", flush=True)
        if not restart_game():
            print("ERROR: 无法到达world", flush=True)
            sys.exit(1)
        baseline = cap()
        BASELINE_MEAN = baseline.mean()
else:
    print("ERROR: 截图失败", flush=True)
    sys.exit(1)

total = sum(len(b["x_positions"]) for b in test_batches)
done = 0

for batch in test_batches:
    label = batch["label"]
    y = batch["y"]
    print(f"\n--- {label} (Y={y}, {len(batch['x_positions'])} positions) ---", flush=True)
    
    for x in batch["x_positions"]:
        done += 1
        
        # 重新确保在world
        check = cap()
        if check is not None and abs(check.mean() - BASELINE_MEAN) > 20:
            print(f"  [RECOVER] mean={check.mean():.0f} 偏离基线, 尝试返回...", flush=True)
            for _ in range(8):
                esc()
                time.sleep(0.5)
                back()
                time.sleep(0.5)
            time.sleep(2)
            check2 = cap()
            if check2 is not None and abs(check2.mean() - BASELINE_MEAN) > 20:
                print(f"  [RESTART] 无法恢复, 重启游戏...", flush=True)
                if not restart_game():
                    print("ERROR: 重启失败", flush=True)
                    break
                baseline = cap()
                BASELINE_MEAN = baseline.mean()
        
        before = cap()
        if before is None:
            continue
        
        tap(x, y)
        time.sleep(2.5)
        
        after = cap()
        if after is None:
            continue
        
        diff = pixel_diff(before, after)
        
        if diff > 500000:
            level = f"[BIG:{diff//1000}k]"
            # 保存截图
            cv2.imwrite(os.path.join(CACHE, f'nav_{label}_x{x}_before.png'), before)
            cv2.imwrite(os.path.join(CACHE, f'nav_{label}_x{x}_after.png'), after)
        elif diff > 100000:
            level = f"[MID:{diff//1000}k]"
        else:
            level = f"[low:{diff//1000}k]"
        
        print(f"  [{done}/{total}] ({x:>4},{y:>3}) diff={diff:>10,} {level}", flush=True)
        
        results.append({
            "label": label, "x": x, "y": y,
            "diff": int(diff),
            "before_mean": float(before.mean()),
            "after_mean": float(after.mean()),
        })
        
        # 关闭面板
        esc()
        time.sleep(0.5)
        for _ in range(3):
            back()
            time.sleep(0.5)

# 保存结果
out = os.path.join(CACHE, 'nav_map_v2.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n\n结果已保存: {out}", flush=True)
print(f"\n高diff命中 (>{500000:,}):", flush=True)
hits = [r for r in results if r['diff'] > 500000]
for r in sorted(hits, key=lambda r: r['diff'], reverse=True):
    print(f"  {r['diff']:>10,}  ({r['x']:>4},{r['y']:>3})  {r['label']}", flush=True)

print("\nDone", flush=True)
