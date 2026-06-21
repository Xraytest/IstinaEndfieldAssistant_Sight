"""
终末地 真人玩家模拟引擎 v1.0
- 观察→思考→决策→行动→验证 循环
- 自然行为: 走动/转视角/跳跃/战斗/采集/交互
- 场景感知: 根据画面内容决定行为
- 记忆系统: 记录经历，避免重复无效动作
"""
import json, base64, urllib.request, time, subprocess, sys, os, re, hashlib, random
from datetime import datetime

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

API = 'http://192.168.1.19:3000/v1/chat/completions'
AUTH = 'Bearer sk-IDYeDxp4uuC5doDT2mX6iPEkkTYwfAY1lwUzm5rQQw8Yzcv3'
HEADERS = {'Content-Type': 'application/json', 'Authorization': AUTH}
MEMORY_FILE = 'C:/Users/xray/AppData/Local/Temp/kilo/player_memory.json'
ADB = ['3rd-party/adb/adb.exe', '-s', 'localhost:16512']

def adb(args, timeout=10):
    subprocess.run(ADB + args, capture_output=True, timeout=timeout)

def tap(x, y):
    ox = x + random.randint(-8, 8)
    oy = y + random.randint(-8, 8)
    adb(['shell', 'input', 'tap', str(ox), str(oy)])

def swipe(x1, y1, x2, y2, dur=random.randint(300, 800)):
    adb(['shell', 'input', 'swipe', str(x1), str(y1), str(x2), str(y2), str(dur)])

def hold(x, y, ms=random.randint(500, 1500)):
    swipe(x, y, x+1, y+1, ms)

def back():
    adb(['shell', 'input', 'keyevent', '4'])

def screencap():
    r = subprocess.run(ADB + ['exec-out', 'screencap', '-p'], capture_output=True, timeout=10)
    if r.returncode == 0 and len(r.stdout) > 1000:
        return r.stdout
    return None

def game_alive():
    return 'com.hypergryph.endfield' in subprocess.run(ADB + ['shell', 'ps', '-A'], capture_output=True, text=True).stdout

def qwen(prompt, img_b64, model='Qwen3.6-Max-Preview', max_tok=512):
    payload = {
        "model": model, "max_tokens": max_tok, "temperature": 0.3,
        "messages": [
            {"role": "system", "content": "你是终末地游戏玩家。坐标1080x1920。JSON only。"},
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

def observe():
    """观察世界"""
    img = screencap()
    if not img: return None
    b64 = base64.b64encode(img).decode()
    h = hashlib.md5(img).hexdigest()[:8]
    
    r = qwen("""You are playing Endfield. Analyze this screenshot like a real player would:
JSON: {
  "scene": "world_map|combat|menu|dialog|loading|login|unknown",
  "what_i_see": "what a player would notice first",
  "interactive": [{"what":"description","where":[x,y],"action":"tap|swipe|hold"}],
  "danger": true/false,
  "should_explore": true/false,
  "mood": "what would a player feel looking at this?"
}""", b64, max_tok=1024)
    
    try:
        jm = re.search(r'\{.*\}', r, re.DOTALL)
        obs = json.loads(jm.group()) if jm else {}
        obs["hash"] = h
        return obs
    except:
        return {"scene": "unknown", "hash": h}

def decide(observation, memory):
    """基于观察和历史决策"""
    scene = observation.get("scene", "unknown")
    interactives = observation.get("interactive", [])
    
    # 弹窗优先处理
    if scene == "dialog":
        close_btns = [i for i in interactives if any(k in str(i.get("what","")).lower() for k in ["close","confirm","ok","关闭","确认"])]
        if close_btns:
            b = close_btns[0]
            return {"action": "tap", "where": b.get("where", [520, 690]), "why": "close dialog"}
        return {"action": "tap", "where": [520, 690], "why": "try close dialog"}
    
    if scene == "loading":
        return {"action": "wait", "seconds": random.randint(3, 8), "why": "loading"}
    
    if scene == "login":
        return {"action": "tap", "where": [540, 1600], "why": "tap login"}
    
    # 加载记忆/最近经历
    recent = memory.get("recent_actions", [])[-5:]
    recent_scenes = [a.get("scene", "") for a in recent]
    
    # 战斗模式
    if scene == "combat" or observation.get("danger"):
        if interactives:
            fight = [i for i in interactives if i.get("action") == "tap"]
            if fight:
                b = random.choice(fight)
                return {"action": "tap", "where": b.get("where", [900, 1700]), "why": "fight: " + b.get("what", "")}
        return {"action": "tap", "where": [900, 1700], "why": "attack"}
    
    # 世界探索模式 - 真人行为
    if scene == "world_map":
        # 混合不同行为
        behaviors = []
        
        # 如果有交互物，优先交互
        if interactives:
            for i in interactives[:3]:
                behaviors.append({
                    "action": i.get("action", "tap"),
                    "where": i.get("where", [540, 960]),
                    "why": "interact: " + i.get("what", "")
                })
        
        # 自然行为候选
        natural = [
            {"action": "move", "dir": "forward", "why": "walk forward"},
            {"action": "move", "dir": random.choice(["left", "right"]), "why": "turn"},
            {"action": "swipe_camera", "why": "look around"},
            {"action": "jump", "why": "jump over obstacle"},
            {"action": "tap", "where": [200, 1700], "why": "check movement"},
        ]
        
        # 避免重复同一行为
        if recent_scenes and recent_scenes[-1] == scene:
            natural = [n for n in natural if n["action"] != recent[-1].get("action", "")]
        
        behaviors.extend(natural)
        
        # 偶尔打开菜单
        if random.random() < 0.15:
            behaviors.append({"action": "tap", "where": [700, 200], "why": "check characters"})
        if random.random() < 0.10:
            behaviors.append({"action": "tap", "where": [80, 480], "why": "check quests"})
        
        chosen = behaviors[0] if behaviors else {"action": "wait", "seconds": 3, "why": "idle"}
        return chosen
    
    # 菜单模式 - 看几秒就返回
    if scene == "menu":
        if len(recent_scenes) >= 3 and recent_scenes[-1] == "menu":
            return {"action": "back", "why": "enough menu browsing"}
        if interactives:
            b = random.choice(interactives)
            return {"action": "tap", "where": b.get("where", [540, 960]), "why": "browse: " + b.get("what", "")}
        return {"action": "back", "why": "nothing interesting"}
    
    # 默认: 点一下屏幕看看
    return {"action": "wait", "seconds": random.randint(2, 5), "why": "observe"}

def act(decision):
    """执行动作"""
    action = decision.get("action", "wait")
    why = decision.get("why", "")
    
    if action == "tap":
        w = decision.get("where", [540, 960])
        tap(w[0], w[1])
        return f"tap {w} ({why})"
    
    elif action == "swipe_camera":
        direction = random.choice([(-200, 0), (200, 0), (0, -200), (0, 200)])
        cx, cy = 540, 960
        swipe(cx, cy, cx + direction[0], cy + direction[1])
        return f"look around ({why})"
    
    elif action == "move":
        d = decision.get("dir", "forward")
        if d == "forward":
            swipe(200, 1700, 200, 1500, 400)  # 向前推摇杆
        elif d == "left":
            swipe(200, 1700, 100, 1700, 400)
        elif d == "right":
            swipe(200, 1700, 300, 1700, 400)
        swipe(200, 1700, 200, 1700, 100)  # 回中
        return f"move {d} ({why})"
    
    elif action == "jump":
        tap(540, 1500)  # 跳跃按钮区域
        return f"jump ({why})"
    
    elif action == "back":
        back()
        return f"back ({why})"
    
    elif action == "swipe":
        w = decision.get("where", [540, 960])
        to = decision.get("to", [540, 500])
        swipe(w[0], w[1], to[0], to[1])
        return f"swipe {w}→{to} ({why})"
    
    elif action == "hold":
        w = decision.get("where", [540, 960])
        hold(w[0], w[1])
        return f"hold {w} ({why})"
    
    else:
        time.sleep(decision.get("seconds", 3))
        return f"wait {decision.get('seconds',3)}s ({why})"

def verify(before_hash, after_img):
    """验证动作效果"""
    if not after_img: return False
    after_hash = hashlib.md5(after_img).hexdigest()
    return before_hash != after_hash

def start_game():
    subprocess.run(ADB + ['shell', 'am', 'force-stop', 'com.hypergryph.endfield'], capture_output=True, timeout=10)
    time.sleep(3)
    subprocess.run(ADB + ['shell', 'am', 'start', '-n', 'com.hypergryph.endfield/com.u8.sdk.U8UnityContext'], capture_output=True, timeout=10)
    time.sleep(40)
    for _ in range(4):
        tap(540, 960)
        time.sleep(4)

# ==================== 主循环 ====================
memory = {"recent_actions": [], "places_visited": {}, "total_actions": 0}
if os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
        memory = json.load(f)

print("=== 真人玩家模拟引擎 启动 ===")

if not game_alive():
    print("[Player] Starting game...")
    start_game()

action_count = 0
while True:
    try:
        # 1. 观察世界
        print(f"\n[{action_count}] Observing...")
        obs = observe()
        if not obs:
            time.sleep(3)
            continue
        
        scene = obs.get("scene", "unknown")
        what = obs.get("what_i_see", "")[:80]
        mood = obs.get("mood", "")
        print(f"[{action_count}] Scene: {scene} | See: {what} | Mood: {mood}")
        
        # 2. 思考决策
        decision = decide(obs, memory)
        
        # 3. 执行动作
        before_hash = obs.get("hash", "")
        result = act(decision)
        time.sleep(random.uniform(1.5, 4.0))  # 真人般的停顿
        
        # 4. 验证效果
        after_img = screencap()
        changed = verify(before_hash, after_img)
        status = "CHANGED" if changed else "SAME"
        print(f"  → {result} [{status}]")
        
        # 5. 记忆
        memory["recent_actions"].append({
            "scene": scene,
            "action": decision.get("action", ""),
            "why": decision.get("why", ""),
            "changed": changed,
            "time": datetime.now().isoformat(),
        })
        memory["recent_actions"] = memory["recent_actions"][-20:]  # 保留最近20次
        memory["total_actions"] = action_count
        
        # 记录访问过的场景
        if scene not in memory["places_visited"]:
            memory["places_visited"][scene] = 0
        memory["places_visited"][scene] += 1
        
        action_count += 1
        
        # 每10次保存记忆
        if action_count % 10 == 0:
            with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(memory, f, ensure_ascii=False, indent=2)
            print(f"[Memory] Saved: {len(memory['places_visited'])} places, {action_count} actions")
        
        # 检查是否登出
        if scene == "dialog" and "logout" in obs.get("what_i_see", "").lower():
            print("[Player] Detected logout! Restarting...")
            start_game()
            memory["recent_actions"] = []
        
        # 长时间同场景，尝试新行为
        recent_same = sum(1 for a in memory["recent_actions"][-8:] if a.get("scene") == scene)
        if recent_same >= 6 and changed == False:
            print("[Player] Stuck! Trying random action...")
            tap(random.randint(100, 980), random.randint(100, 1800))
            back()
        
    except KeyboardInterrupt:
        print("\n[Player] Stopped.")
        break
    except Exception as e:
        print(f"[Player] Error: {e}")
        time.sleep(5)

with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
    json.dump(memory, f, ensure_ascii=False, indent=2)
print(f"[Player] Done. {action_count} actions, {len(memory['places_visited'])} places visited.")
