"""导航按钮功能精确映射 - 逐一测试顶部栏和底部栏位置，记录打开的面板"""
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

def esc():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '111'], timeout=5, capture_output=True)

# 测试点位：基于金色元素检测 + 像素扫描结果
# 顶部栏 Y≈29-60 区域 (golden @ 29, scan hits @ 40)
# 底部栏 Y=930 区域 (scan整行命中)
# 也测试底部栏Y=980和1030

# 顶部栏点：从 flows_config.json 推算 1080p 坐标
# quest_icon: [855,33] 未缩放在1080p下= [1282,49]
# event_icon: [928,53] 1080p = [1392,79] 
# menu_icon: [1392,79] (已是1080p)
# base_entry: [997,85] 1080p (已是1080p)

test_points = [
    # === 顶部栏左侧 ===
    {"name": "top_left_1", "x": 429, "y": 29, "desc": "顶部左1 golden"},
    {"name": "top_left_2", "x": 511, "y": 29, "desc": "顶部左2 golden"},
    {"name": "top_left_mid", "x": 700, "y": 40, "desc": "顶部左中"}, 
    
    # === 顶部栏右侧 - 逐个测试 ===
    {"name": "top_right_g1", "x": 1283, "y": 29, "desc": "顶部右1 golden (可能event/quest)"},
    {"name": "top_right_g2", "x": 1365, "y": 29, "desc": "顶部右2 golden"},
    {"name": "top_right_g3", "x": 1447, "y": 29, "desc": "顶部右3 golden"},
    {"name": "top_right_g4", "x": 1529, "y": 29, "desc": "顶部右4 golden"},
    {"name": "top_right_g5", "x": 1597, "y": 59, "desc": "顶部右5 golden (较大)"},
    
    # === 顶部栏右端 ===
    {"name": "top_right_edge", "x": 1860, "y": 40, "desc": "顶部右端 (scan最高diff)"},
    
    # === 中心金色按钮 ===
    {"name": "center_golden", "x": 1154, "y": 718, "desc": "中心大金色按钮"},
    
    # === 底部栏 Y=930 ===
    {"name": "btm_580", "x": 580, "y": 930, "desc": "底部左"},
    {"name": "btm_880", "x": 880, "y": 930, "desc": "底部中左"},
    {"name": "btm_1180", "x": 1180, "y": 930, "desc": "底部中"},
    {"name": "btm_1480", "x": 1480, "y": 930, "desc": "底部中右"},
    {"name": "btm_1780", "x": 1780, "y": 930, "desc": "底部右"},
    
    # === 底部栏 Y=980 ===
    {"name": "btm2_580", "x": 580, "y": 980, "desc": "底部2左"},
    {"name": "btm2_1480", "x": 1480, "y": 980, "desc": "底部2右"},
    
    # === 底部栏 Y=1030 ===
    {"name": "btm3_880", "x": 880, "y": 1030, "desc": "底部3"},
]

print("=" * 60)
print("导航按钮功能映射")
print("=" * 60)

# 先确认在 world
baseline = cap()
if baseline is None:
    print("ERROR: 无法截图")
    exit(1)

print(f"基准画面: {baseline.shape[1]}x{baseline.shape[0]}, mean={baseline.mean():.1f}, std={baseline.std():.1f}")

results = []
for i, pt in enumerate(test_points):
    print(f"\n[{i+1}/{len(test_points)}] {pt['name']}: ({pt['x']},{pt['y']}) {pt['desc']}")
    
    # 截图前
    before = cap()
    if before is None:
        print("  ✗ 截图失败")
        continue
    
    before_mean = before.mean()
    before_std = before.std()
    
    # 点击
    tap(pt['x'], pt['y'])
    time.sleep(2.5)
    
    # 截图后
    after = cap()
    if after is None:
        print("  ✗ 截图失败")
        # 尝试回到 world
        for _ in range(3):
            back()
            time.sleep(1)
        continue
    
    after_mean = after.mean()
    after_std = after.std()
    
    diff = pixel_diff(before, after)
    
    # 判断变化程度
    if diff > 1500000:
        level = "[HUGE] 面板打开"
    elif diff > 800000:
        level = "[BIG] 面板打开?"
    elif diff > 300000:
        level = "[MID] 中等变化"
    elif diff > 100000:
        level = "[LOW] 轻微变化"
    else:
        level = "[NONE] 几乎无变化"
    
    print(f"  diff={diff:>10,}  |  before: mean={before_mean:.0f} std={before_std:.0f}  →  after: mean={after_mean:.0f} std={after_std:.0f}")
    print(f"  {level}")
    
    # 保存截图
    label = pt['name']
    cv2.imwrite(os.path.join(CACHE, f'map_{label}_before.png'), before)
    cv2.imwrite(os.path.join(CACHE, f'map_{label}_after.png'), after)
    
    result = {
        "name": pt['name'],
        "x": pt['x'],
        "y": pt['y'],
        "desc": pt['desc'],
        "diff": int(diff),
        "before_mean": float(before_mean),
        "after_mean": float(after_mean),
        "before_std": float(before_std),
        "after_std": float(after_std),
    }
    results.append(result)
    
    # 尝试回到 world (多按几次back)
    for b in range(6):
        back()
        time.sleep(1)
        # 检查是否已回到world (mean与baseline接近)
        check = cap()
        if check is not None:
            cm = check.mean()
            if abs(cm - before_mean) < 15:
                break
    
    time.sleep(1)

# 保存结果
out = os.path.join(CACHE, 'nav_button_map.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n\n{'='*60}")
print(f"结果已保存: {out}")
print(f"\n按diff降序排列:")
for r in sorted(results, key=lambda r: r['diff'], reverse=True):
    print(f"  {r['diff']:>10,}  ({r['x']:>4},{r['y']:>3}) {r['name']:20s}  {r['desc']}")

print("\nDone")
