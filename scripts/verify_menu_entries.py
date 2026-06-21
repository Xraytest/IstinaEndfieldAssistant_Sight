"""验证菜单内精确坐标 — 用于标准流导航的 base/character 入口定位

用法: 确保游戏已运行, 在world状态后执行此脚本
      python scripts/verify_menu_entries.py

产出: cache/verify_menu_entries.json — 菜单内各入口的精确坐标
"""
import subprocess, time, cv2, numpy as np, os, json, sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(PROJECT, 'cache')
os.makedirs(CACHE, exist_ok=True)

T1 = os.path.join(CACHE, '_vme1.png')
T2 = os.path.join(CACHE, '_vme2.png')

MENU_X, MENU_Y = 1392, 79  # 已验证的系统菜单按钮

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True, timeout=10)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], capture_output=True, timeout=5)

def cap(path):
    with open(path, 'wb') as f:
        subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       stdout=f, stderr=subprocess.PIPE, timeout=15)
    img = cv2.imread(path)
    return img if (img is not None and img.mean() > 0.5) else None

def cap_mem():
    """截图到内存, 避免磁盘IO"""
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       capture_output=True, timeout=15)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def diff_files(a_path, b_path):
    a = cv2.imread(a_path)
    b = cv2.imread(b_path)
    if a is None or b is None:
        return 0, 0, 0
    d = cv2.absdiff(a, b)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t), a.mean(), b.mean()

def detect_golden(img):
    """多范围金色检测 (与 ScreenAnalyzer 参数一致)"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    ranges = [
        ("亮金", np.array([15, 80, 150]), np.array([35, 255, 255])),
        ("暗金", np.array([15, 50, 80]), np.array([35, 255, 200])),
        ("暖金", np.array([10, 60, 100]), np.array([40, 255, 255])),
    ]
    all_elems = []
    for name, lower, upper in ranges:
        mask = cv2.inRange(hsv, lower, upper)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 30:
                x, y, bw, bh = cv2.boundingRect(cnt)
                all_elems.append({
                    "cx": x + bw // 2, "cy": y + bh // 2,
                    "w": bw, "h": bh, "area": area, "range": name
                })
    # 去重
    unique = []
    for elem in sorted(all_elems, key=lambda e: e["area"], reverse=True):
        if not any(abs(elem["cx"] - u["cx"]) < 20 and abs(elem["cy"] - u["cy"]) < 20 for u in unique):
            unique.append(elem)
    return unique

def in_world():
    """检查是否在world (mean 50-150 且 tap测试有大幅变化)"""
    img = cap(T1)
    if img is None:
        return False
    m = img.mean()
    if m < 50 or m > 150:
        return False
    before = cap(T1)
    if before is None:
        return False
    tap(300, 80)
    time.sleep(2.5)
    after = cap(T2)
    if after is None:
        return False
    d, _, _ = diff_files(T1, T2)
    for _ in range(5):
        back()
        time.sleep(0.3)
    time.sleep(1)
    return d > 500000

def ensure_world():
    """确保在world"""
    for attempt in range(8):
        if in_world():
            return True
        for _ in range(5):
            back()
            time.sleep(0.5)
        time.sleep(1)
    # Force restart
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'force-stop', 'com.hypergryph.endfield'],
                   capture_output=True, timeout=10)
    time.sleep(3)
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'am', 'start', '-n',
                    'com.hypergryph.endfield/com.u8.sdk.U8UnityContext'],
                   capture_output=True, timeout=10)
    for i in range(20):
        time.sleep(3)
        img = cap_mem()
        if img is not None and img.mean() > 50 and img.std() > 30:
            break
    for _ in range(5):
        tap(960, 540)
        time.sleep(4)
    for i in range(30):
        time.sleep(3)
        if in_world():
            return True
    return False

def ensure_menu():
    """确保在菜单上 (mean 100-200)"""
    for attempt in range(5):
        img = cap_mem()
        if img is None:
            continue
        m = img.mean()
        if 100 < m < 200:
            return True
        for _ in range(3):
            back()
            time.sleep(0.5)
        tap(MENU_X, MENU_Y)
        time.sleep(3)
    return False

def classify_region(cx, cy):
    """根据坐标判断UI区域"""
    if cy < 200:
        return "TOP"
    elif cy > 800:
        return "BTM"
    elif cx < 400:
        return "LEFT-MID"
    elif cx > 1400:
        return "RIGHT-MID"
    elif cy < 500:
        return "CENTER-TOP"
    else:
        return "CENTER-BTM"

print("=" * 60, flush=True)
print("Verify Menu Entries — 菜单内坐标精确验证", flush=True)
print("=" * 60, flush=True)

# Phase 1: 确保在world并发现在菜单上的金色元素
print("\n[P1] 确保在world...", flush=True)
if not ensure_world():
    print("FATAL: Cannot reach world", flush=True)
    sys.exit(1)

world = cap_mem()
print(f"World: mean={world.mean():.1f}", flush=True)

# Phase 2: 打开菜单, 检测金色元素
print(f"\n[P2] 打开系统菜单 ({MENU_X}, {MENU_Y})...", flush=True)
tap(MENU_X, MENU_Y)
time.sleep(3)

menu = cap_mem()
if menu is None:
    print("FATAL: Cannot capture menu", flush=True)
    sys.exit(1)
print(f"Menu: mean={menu.mean():.1f}", flush=True)
cv2.imwrite(os.path.join(CACHE, 'vme_menu_full.png'), menu)

golden = detect_golden(menu)
print(f"金色元素: {len(golden)} 个", flush=True)
print(f"\n{'序号':<5} {'坐标':<15} {'尺寸':<12} {'面积':<10} {'范围':<6} {'区域':<12}")
print("-" * 65)
for i, g in enumerate(golden[:30]):
    region = classify_region(g['cx'], g['cy'])
    print(f"{i:<5} ({g['cx']:>4},{g['cy']:>4})  {g['w']:>4}x{g['h']:<4}  {g['area']:>8.0f}   {g['range']:<6} {region:<12}", flush=True)

# Phase 3: 逐个测试金色元素 (筛选按钮尺寸的)
print(f"\n[P3] 测试金色元素 (区域 20-400x20-200, area>200)...", flush=True)

# 筛选: 按钮大小的元素 + 顶部元素 (可能是导航入口)
candidates = []
for g in golden:
    if g['area'] > 200 and 20 < g['w'] < 400 and 20 < g['h'] < 200:
        candidates.append(g)
    elif g['cy'] < 200 and g['area'] > 100:
        candidates.append(g)

# 去重 + 限制数量
seen = set()
filtered = []
for g in candidates:
    key = (g['cx'] // 30, g['cy'] // 30)
    if key not in seen:
        seen.add(key)
        filtered.append(g)

print(f"测试候选: {len(filtered)} 个", flush=True)

results = []

for i, g in enumerate(filtered[:20]):
    x, y = g['cx'], g['cy']
    region = classify_region(x, y)

    # 确保在菜单上
    if not ensure_menu():
        print(f"  [{i}] 菜单恢复失败, 跳过", flush=True)
        continue

    before = cap(T1)
    if before is None:
        print(f"  [{i}] 截图失败", flush=True)
        continue

    tap(x, y)
    time.sleep(2.5)

    after = cap(T2)
    if after is None:
        for _ in range(3):
            back()
            time.sleep(0.3)
        print(f"  [{i}] 截图失败", flush=True)
        continue

    d, bm, am = diff_files(T1, T2)
    tag = "BIG" if d > 800000 else ("MID" if d > 200000 else "low")

    print(f"  [{i}][{tag}] ({x:>4},{y:>4}) {g['w']}x{g['h']} area={g['area']:.0f} diff={d:>10,} bm={bm:.0f}→{am:.0f} [{region}]", flush=True)

    if d > 500000:
        cv2.imwrite(os.path.join(CACHE, f'vme_hit_{i}_{x}_{y}.png'), after)
        results.append({
            "idx": i, "x": x, "y": y,
            "w": g['w'], "h": g['h'], "area": float(g['area']),
            "diff": int(d), "tag": tag, "region": region,
            "before_mean": float(bm), "after_mean": float(am)
        })

    # 返回菜单
    for _ in range(3):
        back()
        time.sleep(0.3)
    time.sleep(0.5)

# Phase 4: 对顶部区域额外细扫 (Y=50-120, X=800-1400)
print(f"\n[P4] 顶部区域细扫: X=800-1400 step=40, Y=50-120 step=10...", flush=True)

for x in range(800, 1420, 40):
    for y in range(50, 121, 15):
        if not ensure_menu():
            continue

        before = cap(T1)
        if before is None:
            continue

        tap(x, y)
        time.sleep(2.5)

        after = cap(T2)
        if after is None:
            for _ in range(3):
                back()
                time.sleep(0.3)
            continue

        d, bm, am = diff_files(T1, T2)

        if d > 300000:
            tag = "BIG" if d > 800000 else "MID"
            print(f"  [{tag}] ({x:>4},{y:>3}) top-scan diff={d:>10,}", flush=True)
            if d > 500000:
                cv2.imwrite(os.path.join(CACHE, f'vme_top_{x}_{y}.png'), after)
                results.append({
                    "idx": -1, "x": x, "y": y,
                    "w": 0, "h": 0, "area": 0,
                    "diff": int(d), "tag": tag, "region": "TOP-SCAN",
                    "before_mean": float(bm), "after_mean": float(am)
                })

        for _ in range(4):
            back()
            time.sleep(0.3)
        time.sleep(0.3)

# 保存结果
out = os.path.join(CACHE, 'verify_menu_entries.json')
with open(out, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n{'='*60}", flush=True)
print(f"结果已保存: {out}", flush=True)
print(f"\nBIG hits (>800k):", flush=True)
big = [r for r in results if r['diff'] > 800000]
if big:
    for r in sorted(big, key=lambda x: x['diff'], reverse=True):
        print(f"  [{r['diff']//1000}k] ({r['x']},{r['y']}) {r.get('region','?')} area={r.get('area',0):.0f}", flush=True)
else:
    print("  (无)", flush=True)

print(f"\nMID hits (300-800k):", flush=True)
mid = [r for r in results if 300000 < r['diff'] <= 800000]
if mid:
    for r in sorted(mid, key=lambda x: x['diff'], reverse=True):
        print(f"  [{r['diff']//1000}k] ({r['x']},{r['y']}) {r.get('region','?')}", flush=True)
else:
    print("  (无)", flush=True)

print(f"\n下一步:", flush=True)
print(f"  1. 查看 BIG hits 截图确定按钮功能", flush=True)
print(f"  2. 更新 flows_config.json 中 base_entry_menu / char_entry_menu 坐标", flush=True)
print(f"  3. 运行标准流引擎测试: python scripts/standard_flow_engine.py --flow daily_quest", flush=True)

print("\nDone", flush=True)
