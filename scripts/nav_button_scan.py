"""VLM 识别 + 精细像素扫描联合定位导航按钮"""
import subprocess, time, os, cv2, numpy as np, json, base64, urllib.request, sys

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
ADB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
LLAMA = 'http://127.0.0.1:8080'

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(x), str(y)],
                   timeout=10, capture_output=True)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'],
                   timeout=5, capture_output=True)

def screencap(path):
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       timeout=15, capture_output=True)
    if len(r.stdout) < 1000:
        return None
    open(path, 'wb').write(r.stdout)
    return cv2.imread(path)

def pixel_diff(img_a, img_b, roi):
    y1, y2, x1, x2 = roi
    if img_a is None or img_b is None:
        return 0
    diff = cv2.absdiff(img_a[y1:y2, x1:x2], img_b[y1:y2, x1:x2])
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(thresh)

def ask_vlm(img_path, prompt):
    img = cv2.imread(img_path)
    _, buf = cv2.imencode('.png', img)
    b64 = base64.b64encode(buf).decode()
    req = urllib.request.Request(f'{LLAMA}/v1/chat/completions',
        data=json.dumps({'messages': [{'role': 'user', 'content': [
            {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{b64}'}},
            {'type': 'text', 'text': prompt}
        ]}], 'max_tokens': 500, 'temperature': 0,
        'chat_template_kwargs': {'enable_thinking': False}}).encode(),
        headers={'Content-Type': 'application/json'})
    resp = urllib.request.urlopen(req, timeout=120)
    return json.loads(resp.read())['choices'][0]['message']['content']

# Step 1: 确保在世界页面
print("Step 1: 回到世界...")
for _ in range(4):
    back()
    time.sleep(0.8)
time.sleep(1)
# 关闭退出对话框
for _ in range(5):
    img = screencap(os.path.join(CACHE, 'check.png'))
    if img is not None and img[300:700, 500:1400, :].mean() > 80:
        break
    tap(834, 717)
    time.sleep(1)

# Step 2: 截图世界并让 VLM 识别顶部栏
world_path = os.path.join(CACHE, 'nav_world.png')
img_world = screencap(world_path)
h, w = img_world.shape[:2]
print(f"世界截图: {w}x{h}")

prompt = f"""你是游戏《明日方舟：终末地》UI分析专家。图片分辨率{w}x{h}。

请精确识别画面顶部栏（Y坐标约0-60区域）中所有可点击的图标/按钮，按从左到右排列。

每个按钮返回: label(中文标签), bbox[x1,y1,x2,y2](精确到像素), type(button/icon/text)

顶部栏通常包含: 游戏Logo(打开工业面板), 模式切换图标, 商店, 活动, 签到, 任务, 背包, 设置等。

返回纯JSON:
{{"buttons":[{{"label":"工业面板","bbox":[300,20,520,55],"type":"button"}},{{"label":"商店","bbox":[700,25,740,50],"type":"icon"}}]}}"""

print("请求VLM识别...")
result = ask_vlm(world_path, prompt)
print(f"VLM: {result}")

# 解析VLM结果
import re
json_match = re.search(r'\{[\s\S]*\}', result)
if json_match:
    try:
        data = json.loads(json_match.group(0))
        vlm_buttons = data.get('buttons', [])
        print(f"\nVLM识别到 {len(vlm_buttons)} 个按钮:")
        for btn in vlm_buttons:
            bbox = btn.get('bbox', [0,0,0,0])
            cx = (bbox[0] + bbox[2]) // 2
            cy = (bbox[1] + bbox[3]) // 2
            print(f"  {btn['label']}: bbox={bbox} center=({cx},{cy}) type={btn.get('type','?')}")
    except:
        print("JSON解析失败")
        vlm_buttons = []
else:
    print("未找到JSON")
    vlm_buttons = []

# Step 3: 精细像素扫描验证（Y=28-38, X=550-1050, 间距8px）
print("\nStep 3: 精细像素扫描 Y=28-38...")
results = []
scan_positions = []
for y in [28, 30, 32, 34, 36, 38]:
    for x in range(100, 500, 20):  # 左侧精细
        scan_positions.append((x, y))
    for x in range(550, 1060, 10):  # 右侧极细
        scan_positions.append((x, y))

# 去重
scan_positions = list(dict.fromkeys(scan_positions))
total = len(scan_positions)

for idx, (x, y) in enumerate(scan_positions):
    before_path = os.path.join(CACHE, f'nav_before_{x}_{y}.png')
    img_before = screencap(before_path)
    if img_before is None:
        continue
    
    tap(x, y)
    time.sleep(2)
    
    after_path = os.path.join(CACHE, f'nav_after_{x}_{y}.png')
    img_after = screencap(after_path)
    if img_after is None:
        back()
        time.sleep(1)
        continue
    
    center_change = pixel_diff(img_before, img_after, (80, 650, 100, 1180))
    
    results.append({'x': x, 'y': y, 'center': int(center_change)})
    
    sig = ' ***' if center_change > 50000 else ''
    if center_change > 10000 or idx % 20 == 0:
        print(f'[{idx+1}/{total}] ({x},{y}): center={center_change:,}{sig}')
    
    back()
    time.sleep(1.2)

# 排序
results.sort(key=lambda r: r['center'], reverse=True)
print(f'\n=== TOP 30 ===')
for r in results[:30]:
    print(f"  ({r['x']},{r['y']}): center={r['center']:,}")

# 保存
with open(os.path.join(CACHE, 'nav_scan_results.json'), 'w') as f:
    json.dump({'vlm_buttons': vlm_buttons, 'pixel_results': results}, f, indent=2)
print(f'\n结果保存到 nav_scan_results.json')
