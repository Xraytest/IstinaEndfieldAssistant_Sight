"""干净扫描: ESC确保world → 像素差异扫描底部和右侧导航按钮
使用参考对比法 (与world参考比较)"""
import subprocess, time, os, cv2, numpy as np, json

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

def keyevent(code):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', str(code)], timeout=5, capture_output=True)

def cap():
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], timeout=15, capture_output=True)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def diff_px(img_a, img_b):
    if img_a is None or img_b is None:
        return 0
    d = cv2.absdiff(img_a, img_b)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)

# ── Step 1: 确保在可交互状态 ──
print("Step 1: 稳定游戏状态...", flush=True)
# ESC关闭所有弹窗
keyevent(111)
time.sleep(1)
keyevent(111)
time.sleep(1)
# 关退出对话框
tap(834, 717)
time.sleep(1.5)
# 连续back到顶层
for _ in range(4):
    back()
    time.sleep(0.4)
time.sleep(1)

# 获取基准截图
ref = cap()
if ref is None:
    print("ERROR: 截图失败")
    import sys; sys.exit(1)
print(f"基准画面: mean={ref.mean():.1f} std={ref.std():.1f}", flush=True)
cv2.imwrite(os.path.join(CACHE, 'scan2_ref.png'), ref)

# ── Step 2: 底部栏扫描 (Y=880-1070, 步长50) ──
print("\nStep 2: 底部栏扫描...", flush=True)
bottom_hits = []

for y in range(880, 1080, 50):
    for x in range(80, 1850, 100):
        # 每行开始时重新校准参考
        if x == 80:
            ref_current = cap()
            if ref_current is None:
                continue
        
        tap(x, y)
        time.sleep(1.8)
        
        after = cap()
        if after is None:
            continue
        
        d = diff_px(ref_current, after)
        
        if d > 400000:
            tag = f"bottom_{x}_{y}"
            bottom_hits.append({"tag": tag, "x": x, "y": y, "diff": d})
            print(f"  ⭐ ({x},{y}): diff={d:>10,}", flush=True)
            cv2.imwrite(os.path.join(CACHE, f'scan2_hit_{x}_{y}.png'), after)
        elif d > 200000:
            print(f"  ✓  ({x},{y}): diff={d:>10,}", flush=True)
        
        # 如果变化大，返回基准状态
        if d > 100000:
            for _ in range(3):
                back()
                time.sleep(0.3)
            time.sleep(0.5)
            keyevent(111)  # ESC关弹窗
            time.sleep(0.5)

# ── Step 3: 右上区域扫描 (X=1300-1900, Y=0-150) ──
print("\nStep 3: 右上区域扫描...", flush=True)
top_right_hits = []

for y in range(10, 160, 30):
    for x in range(1300, 1910, 80):
        if x == 1300:
            ref_current = cap()
            if ref_current is None:
                continue
        
        tap(x, y)
        time.sleep(1.8)
        
        after = cap()
        if after is None:
            continue
        
        d = diff_px(ref_current, after)
        
        if d > 400000:
            tag = f"topright_{x}_{y}"
            top_right_hits.append({"tag": tag, "x": x, "y": y, "diff": d})
            print(f"  ⭐ ({x},{y}): diff={d:>10,}", flush=True)
            cv2.imwrite(os.path.join(CACHE, f'scan2_hit_{x}_{y}.png'), after)
        
        if d > 100000:
            for _ in range(3):
                back()
                time.sleep(0.3)
            time.sleep(0.5)
            keyevent(111)
            time.sleep(0.5)

# ── 汇总 ──
print(f"\n{'='*60}")
print(f"底部栏命中: {len(bottom_hits)}")
for h in sorted(bottom_hits, key=lambda h: h['diff'], reverse=True)[:15]:
    print(f"  ({h['x']},{h['y']}): {h['diff']:,}")

print(f"\n右上命中: {len(top_right_hits)}")
for h in sorted(top_right_hits, key=lambda h: h['diff'], reverse=True)[:15]:
    print(f"  ({h['x']},{h['y']}): {h['diff']:,}")

all_hits = bottom_hits + top_right_hits
with open(os.path.join(CACHE, 'scan2_hits.json'), 'w') as f:
    json.dump(all_hits, f, indent=2)
print(f"\n全部结果: cache/scan2_hits.json")
