"""纯像素差异法扫描建造模式底部取消按钮 - 无VLM依赖"""
import subprocess, time, os, sys, cv2, numpy as np

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJECT, 'cache')
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
os.makedirs(CACHE, exist_ok=True)

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   timeout=10, capture_output=True)

def cap():
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], timeout=15, capture_output=True)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def diff_count(img_a, img_b):
    """返回变化的像素数"""
    if img_a is None or img_b is None:
        return 0
    d = cv2.absdiff(img_a, img_b)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)

def is_building_mode(img, ref_building):
    """通过像素差异判断是否仍在建造模式 - 比较整个画面"""
    if img is None:
        return True
    d = diff_count(ref_building, img)
    # 建造模式画面稳定，大变化=退出建造
    return d < 500000

# ── 准备 ──
print("Step 0: 关闭可能存在的退出对话框...", flush=True)
tap(834, 717)  # 退出对话框取消
time.sleep(2)

# 获取建造模式参考截图
ref = cap()
if ref is None:
    print("ERROR: screenshot failed")
    sys.exit(1)
print(f"参考截图: {ref.shape[1]}x{ref.shape[0]}", flush=True)
cv2.imwrite(os.path.join(CACHE, 'eq_ref_building.png'), ref)

# ── 扫描底部区域 ──
# OCR "确认 旋转 取消" 三按钮预计在底部
# 扫描范围: Y=850-1050, X=600-1750, 步长60
print("\nPhase 1: 粗扫底部区域 (步长60)...", flush=True)
candidates = []

for y in range(850, 1060, 60):
    for x in range(600, 1760, 60):
        tap(x, y)
        time.sleep(1.5)
        img = cap()
        if img is None:
            continue
        
        d = diff_count(ref, img)
        
        if d > 500000:
            print(f"  ⭐ ({x},{y}): diff={d:,} - 可能退出建造!", flush=True)
            candidates.append((x, y, d))
            cv2.imwrite(os.path.join(CACHE, f'eq_hit_{x}_{y}.png'), img)
            # 重新进入建造模式(按back然后重新触发? 不，先记录)
            # 实际上如果退出了，通过back也回不去
            # 所以先记录，然后需要手动操作回到建造
            break
        elif d > 200000:
            print(f"  ? ({x},{y}): diff={d:,} - 中等变化", flush=True)
        
        # 回到建造参考状态（可能有UI面板弹出，用back关闭）
        back_needed = d > 100000
        if back_needed:
            for _ in range(2):
                subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5, capture_output=True)
                time.sleep(0.5)
            time.sleep(0.5)

if candidates:
    print(f"\n发现 {len(candidates)} 个候选位置:", flush=True)
    for x, y, d in candidates:
        print(f"  ({x},{y}): {d:,}", flush=True)
else:
    print("\nPhase 1 未找到，扩大扫描范围...", flush=True)
    # 扫描更宽的区域
    for y in range(800, 1080, 40):
        for x in range(200, 1900, 80):
            tap(x, y)
            time.sleep(1.5)
            img = cap()
            if img is None:
                continue
            d = diff_count(ref, img)
            if d > 500000:
                print(f"  ⭐ ({x},{y}): diff={d:,}", flush=True)
                candidates.append((x, y, d))
                cv2.imwrite(os.path.join(CACHE, f'eq_hit2_{x}_{y}.png'), img)
                break
            if d > 100000:
                # 有大变化（可能弹出面板），用back关闭
                subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5, capture_output=True)
                time.sleep(1.5)

print(f"\nDone. 候选: {len(candidates)}", flush=True)
for x, y, d in candidates:
    print(f"  ({x},{y}): {d:,}", flush=True)
