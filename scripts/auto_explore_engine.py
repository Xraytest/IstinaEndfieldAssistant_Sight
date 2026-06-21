"""
终末地无人值守探索引擎 v1.0
- 自恢复: 检测登出→重启→登录
- 保活: 心跳tap防止15分钟超时
- 持久化: 探索队列保存，崩溃恢复
- 弹窗: 自动检测+关闭
"""
import json, base64, urllib.request, time, subprocess, sys, os, re, hashlib
from datetime import datetime

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

API = 'http://192.168.1.19:3000/v1/chat/completions'
AUTH = 'Bearer sk-IDYeDxp4uuC5doDT2mX6iPEkkTYwfAY1lwUzm5rQQw8Yzcv3'
HEADERS = {'Content-Type': 'application/json', 'Authorization': AUTH}
STATE_FILE = 'C:/Users/xray/AppData/Local/Temp/kilo/auto_explore_state.json'
ADB = ['3rd-party/adb/adb.exe', '-s', 'localhost:16512']

def adb_cmd(args, timeout=10):
    try:
        r = subprocess.run(ADB + args, capture_output=True, timeout=timeout)
        return r.stdout.decode()
    except:
        return ""

def tap(x, y):
    subprocess.run(ADB + ['shell', 'input', 'tap', str(x), str(y)], capture_output=True, timeout=5)

def screencap():
    r = subprocess.run(ADB + ['exec-out', 'screencap', '-p'], capture_output=True, timeout=10)
    if r.returncode == 0 and len(r.stdout) > 1000:
        return r.stdout
    return None

def game_running():
    return 'com.hypergryph.endfield' in adb_cmd(['shell', 'ps', '-A'])

def qwen(prompt, img_b64, model='Qwen3.6-Max-Preview', max_tok=512):
    payload = {
        "model": model, "max_tokens": max_tok, "temperature": 0.3,
        "messages": [
            {"role": "system", "content": "终末地专家。1080x1920。JSON only。"},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + img_b64}},
                {"type": "text", "text": prompt}
            ]}
        ]
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(API, data=data, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=60)
    return json.loads(resp.read().decode())['choices'][0]['message']['content']

def check_logout(img_b64):
    """快速检测是否登出弹窗"""
    r = qwen("Is this the auto-logout popup? JSON: {\"is_logout\":true/false}", img_b64, max_tok=64)
    return '"is_logout": true' in r.lower() or '"is_logout":true' in r.lower()

def check_announcement(img_b64):
    """检测是否公告弹窗"""
    r = qwen("Is this a game announcement popup? JSON: {\"is_announcement\":true/false}", img_b64, max_tok=64)
    return '"is_announcement": true' in r.lower() or '"is_announcement":true' in r.lower()

def start_game():
    """启动游戏并等待加载"""
    print("[AUTO] Starting game...")
    subprocess.run(ADB + ['shell', 'am', 'force-stop', 'com.hypergryph.endfield'], capture_output=True, timeout=10)
    time.sleep(3)
    subprocess.run(ADB + ['shell', 'am', 'start', '-n', 'com.hypergryph.endfield/com.u8.sdk.U8UnityContext'], capture_output=True, timeout=10)
    time.sleep(40)  # 等待加载
    
    # 点击标题页继续
    for _ in range(3):
        tap(540, 960)
        time.sleep(5)
    
    # 关闭公告弹窗
    img = screencap()
    if img:
        b64 = base64.b64encode(img).decode()
        if check_announcement(b64):
            print("[AUTO] Closing announcement...")
            tap(1000, 100)  # X关闭按钮
            time.sleep(2)
            tap(540, 960)   # 点任意位置
            time.sleep(3)

def load_queue():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "queue": [
            {"id": "world_map", "entry": [100, 150], "done": False},
            {"id": "quest_ui", "entry": [80, 480], "done": False},
            {"id": "base_industry", "entry": [200, 80], "done": False},
            {"id": "character", "entry": [700, 200], "done": False},
            {"id": "warehouse", "entry": [800, 120], "done": False},
            {"id": "workshop", "entry": [540, 400], "done": False},
            {"id": "event", "entry": [900, 200], "done": False},
            {"id": "mail", "entry": [1000, 80], "done": False},
            {"id": "shop", "entry": [950, 120], "done": False},
            {"id": "team", "entry": [400, 200], "done": False},
            {"id": "settings", "entry": [1040, 60], "done": False},
        ],
        "discovered": {},
        "heartbeat_interval": 60,
        "last_heartbeat": 0,
        "total_rounds": 0,
    }

def save_queue(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ==================== MAIN LOOP ====================
state = load_queue()
print(f"[AUTO] Resumed: {sum(1 for q in state['queue'] if q['done'])}/{len(state['queue'])} done")

while True:
    try:
        # 1. 确保游戏运行
        if not game_running():
            start_game()
        
        # 2. 心跳保活
        now = time.time()
        if now - state["last_heartbeat"] > state["heartbeat_interval"]:
            tap(540, 960)  # 轻触屏幕保持活跃
            state["last_heartbeat"] = now
            print(f"[AUTO] Heartbeat #{state['total_rounds']}")
        
        # 3. 检查是否登出
        img = screencap()
        if img:
            b64 = base64.b64encode(img).decode()
            if check_logout(b64):
                print("[AUTO] Logout detected! Restarting...")
                state["last_heartbeat"] = 0
                start_game()
                continue
            if check_announcement(b64):
                print("[AUTO] Announcement! Dismissing...")
                tap(1000, 100); time.sleep(2)
                tap(540, 960); time.sleep(3)
                continue
        
        # 4. 探索下一个目标
        undone = [q for q in state["queue"] if not q["done"]]
        if not undone:
            print("[AUTO] All targets explored! Waiting for new targets...")
            save_queue(state)
            time.sleep(60)
            continue
        
        target = undone[0]
        print(f"\n[AUTO] Round {state['total_rounds']}: {target['id']} at {target['entry']}")
        
        # 导航
        tap(target["entry"][0], target["entry"][1])
        time.sleep(3)
        
        # 记录
        img = screencap()
        if img:
            b64 = base64.b64encode(img).decode()
            h = hashlib.md5(img).hexdigest()[:8]
            try:
                r = qwen(f"Analyze this Endfield page. JSON: {{\"page\":\"{target['id']}\",\"title\":\"title\",\"buttons_count\":0}}", b64)
                jm = re.search(r'\{.*\}', r, re.DOTALL)
                if jm:
                    d = json.loads(jm.group())
                    state["discovered"][target["id"]] = {
                        "title": d.get("title", ""),
                        "buttons": d.get("buttons_count", 0),
                        "hash": h,
                        "round": state["total_rounds"],
                        "time": datetime.now().isoformat(),
                    }
                    target["done"] = True
                    print(f"  [DONE] {d.get('title','?')} (btns:{d.get('buttons_count',0)})")
            except Exception as e:
                print(f"  [SKIP] {e}")
                target["done"] = True  # skip on error, retry later if needed
        
        state["total_rounds"] += 1
        save_queue(state)
        
        # 返回探索界面
        tap(100, 150)
        time.sleep(2)
        
    except KeyboardInterrupt:
        print("\n[AUTO] Stopped by user")
        save_queue(state)
        break
    except Exception as e:
        print(f"[AUTO] Error: {e}")
        time.sleep(5)
