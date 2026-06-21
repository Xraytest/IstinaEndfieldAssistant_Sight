"""全面扫描 world 状态下所有可交互 UI 元素
使用像素差异法，分区域扫描: 顶部栏、底部栏、右侧、左侧
每个区域用不同密度扫描"""
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

def diff_count(img_a, img_b):
    if img_a is None or img_b is None:
        return 0
    d = cv2.absdiff(img_a, img_b)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)

def return_to_world():
    """简单粗暴回到world：连续back + 关退出对话框"""
    for _ in range(3):
        back()
        time.sleep(0.4)
    time.sleep(0.5)
    tap(834, 717)  # 预防退出对话框
    time.sleep(1)

# ── 定义扫描区域 ──
# 区域1: 顶部栏 (Y=0-150, X全扫描, 步长40)
# 区域2: 底部栏 (Y=850-1080, X全扫描, 步长60)  
# 区域3: 右侧 (X=1400-1920, Y=100-850, 步长80)
# 区域4: 左侧已验证区域 (X=0-400, Y=0-200) - 细扫
# 区域5: 中部偏右 (X=800-1400, Y=0-300) - 导航图标可能位置

regions = [
    # 底部栏 (最可能有导航按钮) - 粗扫
    ("bottom_bar", [(y, x) for y in range(880, 1070, 50) for x in range(100, 1850, 120)]),
    # 顶部栏右侧 (之前未找到，再扫一次，更密)
    ("top_right", [(y, x) for y in range(15, 120, 30) for x in range(1200, 1900, 80)]),
    # 顶部栏左侧 (已知有效点附近，确认)
    ("top_left", [(y, x) for y in range(15, 120, 30) for x in range(30, 500, 80)]),
    # 右侧边缘（可能有侧边栏触发）
    ("right_edge", [(y, x) for y in range(200, 900, 100) for x in range(1800, 1920, 60)]),
    # 左侧边缘
    ("left_edge", [(y, x) for y in range(200, 900, 100) for x in range(5, 120, 60)]),
]

print("Phase 0: 确保在 world 状态...")
# 确保在world
for _ in range(3):
    back()
    time.sleep(0.5)
time.sleep(1)
# 关可能的退出对话框
tap(834, 717)
time.sleep(1.5)
print("World 状态就绪")
print(f"扫描 {len(regions)} 个区域")

all_hits = []  # (tag, x, y, diff, region)

for region_name, points in regions:
    print(f"\n{'='*50}")
    print(f"扫描区域: {region_name} ({len(points)} 点)")
    print(f"{'='*50}")
    
    region_hits = []
    total = len(points)
    
    for idx, (y, x) in enumerate(points):
        # 每15个点回到world
        if idx % 15 == 0 and idx > 0:
            return_to_world()
        
        before = cap()
        if before is None:
            continue
        
        tap(x, y)
        time.sleep(1.5)
        
        after = cap()
        if after is None:
            continue
        
        d = diff_count(before, after)
        
        if d > 200000:
            tag = f"{region_name}_{x}_{y}"
            all_hits.append((tag, x, y, d, region_name))
            region_hits.append((tag, x, y, d))
            
            if d > 500000:
                print(f"  ⭐ [{idx+1}/{total}] ({x},{y}): diff={d:>10,}", flush=True)
                # 保存大变化的截图
                cv2.imwrite(os.path.join(CACHE, f'scan_hit_{x}_{y}.png'), after)
            elif d > 300000:
                print(f"  ✓  [{idx+1}/{total}] ({x},{y}): diff={d:>10,}", flush=True)
        
        # 如果变化>100k，可能弹出面板，用back关掉
        if d > 100000:
            for _ in range(2):
                back()
                time.sleep(0.4)
            time.sleep(0.5)
    
    print(f"  {region_name} 命中: {len(region_hits)}")

# ── 汇总 ──
print(f"\n{'='*60}")
print(f"=== 汇总结果 ({len(all_hits)} 个命中) ===")

# 按diff排序
all_hits.sort(key=lambda h: h[3], reverse=True)

with open(os.path.join(CACHE, 'scan_all_hits.json'), 'w') as f:
    json.dump([{"tag": h[0], "x": h[1], "y": h[2], "diff": h[3], "region": h[4]} for h in all_hits], f, indent=2)

print("\nTOP 30 命中:")
for tag, x, y, d, region in all_hits[:30]:
    print(f"  ({x:>4},{y:>4}) diff={d:>10,} [{region}] {tag}")

print(f"\n全部结果已保存到 cache/scan_all_hits.json")
