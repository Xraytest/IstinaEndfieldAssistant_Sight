"""用VLM识别顶部栏所有按钮的bbox坐标"""
import subprocess, time, os, cv2, base64, json, urllib.request

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
ADB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
LLAMA_URL = "http://127.0.0.1:8080"

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(x), str(y)],
                   timeout=10, capture_output=True)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'],
                   timeout=5, capture_output=True)

def screencap(path):
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       timeout=15, capture_output=True)
    open(path, 'wb').write(r.stdout)
    return cv2.imread(path)

def ask_vlm(img_b64: str, prompt: str) -> str:
    """发送图片到本地VLM并返回文本"""
    req = urllib.request.Request(
        f"{LLAMA_URL}/v1/chat/completions",
        data=json.dumps({
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
            ]}],
            "max_tokens": 800,
            "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False}
        }).encode(),
        headers={"Content-Type": "application/json"}
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=120).read())
    return resp["choices"][0]["message"]["content"].strip()

# 1. 确保回到主世界
print("回到主世界...")
for _ in range(5):
    back()
    time.sleep(0.8)
time.sleep(1)

# 关闭可能存在的退出对话框
tap(834, 717)  # 取消按钮
time.sleep(1.5)
back()
time.sleep(2)

# 截图
path = os.path.join(CACHE, 'vlm_find_buttons.png')
img = screencap(path)
h, w = img.shape[:2]
print(f"截图: {w}x{h}")

# 编码
_, buf = cv2.imencode('.png', img)
img_b64 = base64.b64encode(buf).decode()

# 2. VLM 识别顶部栏按钮
prompt = f"""你是游戏UI分析专家。图片分辨率是{w}x{h}。

请识别画面顶部栏（Y坐标范围大约0-80）中所有可点击的按钮/图标，返回JSON格式。

要求：
- bbox格式为[x1,y1,x2,y2]，精确到像素
- 按从左到右顺序排列
- 识别类型包括: exploration(探索模式切换), back(返回), shop(商店), event(活动), signin(签到), tasks(任务), inventory(背包), settings(设置)

返回格式示例：
```json
{{
  "buttons": [
    {{"label": "exploration", "bbox": [50, 10, 100, 50], "confidence": 0.9}},
    {{"label": "tasks", "bbox": [550, 8, 590, 50], "confidence": 0.85}}
  ],
  "page_type": "world"
}}
```"""

print("发送VLM请求...")
response = ask_vlm(img_b64, prompt)
print(f"VLM响应:\n{response}")

# 3. 解析JSON
import re
json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
if json_match:
    data = json.loads(json_match.group(1))
elif response.strip().startswith('{'):
    data = json.loads(response.strip())
else:
    print("无法解析JSON响应")
    data = None

output = []
if data and 'buttons' in data:
    print(f"\n找到 {len(data['buttons'])} 个按钮:")
    for btn in data['buttons']:
        bbox = btn['bbox']
        cx = (bbox[0] + bbox[2]) // 2
        cy = (bbox[1] + bbox[3]) // 2
        label = btn['label']
        conf = btn.get('confidence', 0)
        print(f"  {label}: bbox={bbox} center=({cx},{cy}) conf={conf}")
        output.append(f"{label}: center=({cx},{cy}) bbox={bbox} conf={conf}")

with open(os.path.join(CACHE, 'vlm_buttons_result.txt'), 'w', encoding='utf-8') as f:
    f.write(f"VLM响应:\n{response}\n\n")
    f.write('\n'.join(output))

print(f"\n结果保存到 vlm_buttons_result.txt")
