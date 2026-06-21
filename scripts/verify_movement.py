"""
三轮验证：ADB是否能胜任终末地游戏操作
Round 1: 长按移动
Round 2: 长按任务触发自动寻路
Round 3: 菜单关卡选择
"""
import subprocess, time, sys, os, base64, hashlib, json, urllib.request, re

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

from core.adb_utils import adb_screencap

ADB = ['3rd-party/adb/adb.exe', '-s', 'localhost:16512']

def tap(x, y):
    subprocess.run(ADB + ['shell', 'input', 'tap', str(x), str(y)], capture_output=True, timeout=5)

def long_press(x, y, ms=2000):
    subprocess.run(ADB + ['shell', 'input', 'swipe', str(x), str(y), str(x), str(y), str(ms)], capture_output=True, timeout=10)

def screencap_bytes():
    img = adb_screencap()
    if img:
        return img, hashlib.md5(img).hexdigest()[:8]
    return None, None

def get_distance(img_b64):
    """读取距离数字(只看m单位)"""
    payload = {
        "model": "local-model", "max_tokens": 64, "temperature": 0.1,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + img_b64}},
            {"type": "text", "text": "The quest distance in meters (number followed by 'm' like '735 m'). Return ONLY the number."}
        ]}]
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request('http://127.0.0.1:8080/v1/chat/completions', data=data, headers={'Content-Type': 'application/json'})
    resp = urllib.request.urlopen(req, timeout=30)
    r = json.loads(resp.read().decode())
    content = r['choices'][0]['message'].get('content', '') or r['choices'][0]['message'].get('reasoning_content', '')
    nums = re.findall(r'\d+', content)
    return nums[0] if nums else '?'

# 跳过标题页
time.sleep(3)
for _ in range(4):
    tap(540, 960)
    time.sleep(3)
tap(1000, 100); time.sleep(1)
tap(540, 960); time.sleep(3)
tap(1040, 30); time.sleep(1)  # 关闭可能的弹窗
tap(540, 960); time.sleep(5)

# ============ Round 1: 长按移动 ============
print("=" * 50)
print("Round 1: 长按摇杆移动")
print("=" * 50)

img1, h1 = screencap_bytes()
b64_1 = base64.b64encode(img1).decode() if img1 else None
d1 = get_distance(b64_1) if b64_1 else '?'
print(f"Before: hash={h1}, distance={d1}")

# 持续按住摇杆3秒
long_press(200, 1700, 3000)
time.sleep(2)

img2, h2 = screencap_bytes()
b64_2 = base64.b64encode(img2).decode() if img2 else None
d2 = get_distance(b64_2) if b64_2 else '?'
changed = h1 != h2
print(f"After: hash={h2}, distance={d2}, changed={changed}")
print(f"Result: {'SUCCESS' if d1 != d2 and d2 != '?' and int(d2) < int(d1) else 'FAIL'}")

# ============ Round 2: 长按任务触发自动寻路 ============
print("\n" + "=" * 50)
print("Round 2: 长按任务文字触发自动寻路")
print("=" * 50)

long_press(80, 300, 2500)
time.sleep(4)

img3, h3 = screencap_bytes()
b64_3 = base64.b64encode(img3).decode() if img3 else None
d3 = get_distance(b64_3) if b64_3 else '?'
changed2 = h2 != h3
print(f"After long press quest: hash={h3}, distance={d3}, changed={changed2}")
print(f"Result: {'SUCCESS' if d3 != '?' and d3 != d2 and int(d3) < int(d2) else 'FAIL'}")

# ============ Round 3: 菜单→关卡选择 ============
print("\n" + "=" * 50)
print("Round 3: 探索→菜单→寻找关卡选择功能")
print("=" * 50)

# 打开世界地图
tap(150, 150); time.sleep(3)
img4, h4 = screencap_bytes()
b64_4 = base64.b64encode(img4).decode() if img4 else None

# 用Qwen分析地图上有什么
payload = {
    "model": "Qwen3.6-Max-Preview", "max_tokens": 512, "temperature": 0.2,
    "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + (b64_4 or "")}},
        {"type": "text", "text": "Is this a map view? Are there selectable nodes/missions? Where? Output JSON: {\"is_map\":true/false,\"has_nodes\":true/false,\"node_locations\":[[x,y]],\"can_enter_dungeon\":true/false,\"advice\":\"what to do\"}"}
    ]}]
}
data = json.dumps(payload).encode()
req = urllib.request.Request(
    'http://192.168.1.19:3000/v1/chat/completions',
    data=data,
    headers={'Content-Type': 'application/json', 'Authorization': 'Bearer sk-IDYeDxp4uuC5doDT2mX6iPEkkTYwfAY1lwUzm5rQQw8Yzcv3'}
)
try:
    resp = urllib.request.urlopen(req, timeout=60)
    r = json.loads(resp.read().decode())
    content = r['choices'][0]['message']['content']
    print(content[:500])
except Exception as e:
    print(f"Error: {e}")

print("\nDone.")
