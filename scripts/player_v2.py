"""
终末地 真人v2 - 好奇心驱动 + 策略战斗
- 好奇心: 探索未知区域、尝试新交互、阅读信息
- 战斗策略: 技能连招、闪避、发现敌人弱点、低血量治疗
- 学习记忆: 记住有效行为，避免重复无效动作
"""
import json, base64, urllib.request, time, subprocess, sys, os, re, hashlib, random
from datetime import datetime

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

API = 'http://192.168.1.19:3000/v1/chat/completions'
AUTH = 'Bearer sk-IDYeDxp4uuC5doDT2mX6iPEkkTYwfAY1lwUzm5rQQw8Yzcv3'
HEADERS = {'Content-Type': 'application/json', 'Authorization': AUTH}
MEMORY_FILE = 'C:/Users/xray/AppData/Local/Temp/kilo/player_v2_memory.json'
ADB = ['3rd-party/adb/adb.exe', '-s', 'localhost:16512']

def rand_offset(n): return n + random.randint(-10, 10)
def tap(x,y): subprocess.run(ADB + ['shell','input','tap',str(rand_offset(x)),str(rand_offset(y))], capture_output=True, timeout=5)
def swipe(x1,y1,x2,y2,d=random.randint(200,600)): subprocess.run(ADB + ['shell','input','swipe',str(x1),str(y1),str(x2),str(y2),str(d)], capture_output=True, timeout=5)
def back(): subprocess.run(ADB + ['shell','input','keyevent','4'], capture_output=True, timeout=5)
def screencap():
    r = subprocess.run(ADB + ['exec-out','screencap','-p'], capture_output=True, timeout=10)
    return r.stdout if r.returncode == 0 and len(r.stdout) > 1000 else None

def game_alive():
    return 'com.hypergryph.endfield' in subprocess.run(ADB + ['shell','ps','-A'], capture_output=True, text=True).stdout

def qwen(prompt, img_b64, model='Qwen3.6-Max-Preview', max_tok=1024):
    payload = {
        "model": model, "max_tokens": max_tok, "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "You play Endfield. You are curious and skilled. 1080x1920. JSON only."},
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

def observe(memory):
    """好奇地观察世界"""
    img = screencap()
    if not img: return None
    b64 = base64.b64encode(img).decode()
    h = hashlib.md5(img).hexdigest()[:8]
    
    # 注入好奇心上下文
    visited = memory.get("places_visited", {})
    explored = memory.get("map_explored", [])
    recent = [a.get("action","") for a in memory.get("recent_actions", [])[-5:]]
    
    r = qwen(f"""You are playing Endfield. Be curious about the game world.
Recent actions: {recent[-3:] if recent else 'none'}
Places seen: {list(visited.keys())[-5:] if visited else 'none'}

Analyze this screenshot with CURIOSITY:
JSON: {{
  "scene": "combat|world_map|menu|dialog|loading|login|unknown",
  "what_i_see": "detailed description of this scene",
  "hp_percent": your HP percentage estimate (0-100),
  "enemies_visible": number of visible enemies (0 if none),
  "skill_cooldowns": ["skill names that appear ready vs on cooldown"],
  "curiosities": ["things that look interesting to explore"],
  "danger_level": 0-10,
  "dodge_needed": true/false (enemy about to attack?),
  "mood": "what a curious player would feel"
}}""", b64, max_tok=2048)
    
    try:
        jm = re.search(r'\{.*\}', r, re.DOTALL)
        obs = json.loads(jm.group()) if jm else {"scene":"unknown"}
        obs["hash"] = h
        return obs
    except:
        return {"scene": "unknown", "hash": h, "what_i_see": "parse failed", "hp_percent": 50}

def decide(obs, memory):
    """策略决策：好奇+战斗智慧"""
    scene = obs.get("scene", "unknown")
    hp = obs.get("hp_percent", 50)
    danger = obs.get("danger_level", 0)
    enemies = obs.get("enemies_visible", 0)
    cooldowns = obs.get("skill_cooldowns", [])
    curiosities = obs.get("curiosities", [])
    
    # 获取记忆
    recent_actions = memory.get("recent_actions", [])[-10:]
    combat_history = [a for a in recent_actions if a.get("scene") == "combat"]
    skills_used = [a.get("why","") for a in combat_history if "fight" in a.get("why","")]
    
    # === 战斗策略 ===
    if scene == "combat" or danger > 3:
        # 需要闪避
        if obs.get("dodge_needed"):
            dodge_dirs = [(200, 1500), (200, 1400), (300, 1600), (100, 1600)]
            dx, dy = random.choice(dodge_dirs)
            swipe(200, 1700, dx, dy, random.randint(200, 400))
            return {"action": "move", "why": "dodge enemy attack", "priority": 10}
        
        # 低血量 - 撤退/治疗
        if hp < 30 and combat_history:
            # 寻找治疗/撤退
            if len(recent_actions) > 2 and recent_actions[-1].get("action") == "move":
                back()  # 尝试打开菜单治疗
                tap(700, 200)  # 角色管理
                time.sleep(2)
            return {"action": "move", "dir": "backward", "why": "retreat - low HP ({})".format(hp), "priority": 9}
        
        # 中等血量 - 谨慎攻击
        if hp < 50:
            # 使用远程技能或等待
            return {"action": "move", "dir": random.choice(["left","right"]), "why": "reposition - caution", "priority": 7}
        
        # 健康 - 主动进攻
        if enemies > 0:
            # 技能连招策略
            skill_zones = [
                {"name": "Skill 1", "xy": [300, 1400]},
                {"name": "Skill 2", "xy": [500, 1400]},
                {"name": "Ultimate", "xy": [700, 1400]},
                {"name": "Basic Attack", "xy": [900, 1700]},
            ]
            
            # 尝试未使用的技能
            unused = [s for s in skill_zones if s["name"] not in skills_used[-3:]]
            if unused:
                s = random.choice(unused)
                return {"action": "tap", "where": s["xy"], "why": "fight: {} (try new combo)".format(s["name"]), "priority": 8}
            
            # 混合攻击
            action = random.choice([
                {"action": "tap", "where": [900, 1700], "why": "fight: attack", "priority": 5},
                {"action": "tap", "where": [300, 1400], "why": "fight: skill 1", "priority": 6},
                {"action": "tap", "where": [500, 1400], "why": "fight: skill 2", "priority": 6},
                {"action": "move", "dir": "forward", "why": "close distance", "priority": 4},
            ])
            return action
        
        # 没有敌人？清理战场
        if len(combat_history) > 5:
            return {"action": "wait", "seconds": 3, "why": "check if battle ended", "priority": 3}
    
    # === 好奇心探索 ===
    if scene == "world_map":
        # 有新的好奇点
        if curiosities:
            c = curiosities[0]
            # 尝试找一个坐标（从curiosity描述推断）
            map_xy = memory.get("map_explored", [])
            # 优先未探索区域
            if len(map_xy) < 5:
                new_x = random.choice([200, 400, 600, 800])
                new_y = random.choice([400, 600, 800, 1000])
                while [new_x, new_y] in map_xy:
                    new_x = random.choice([200, 400, 600, 800])
                    new_y = random.choice([400, 600, 800, 1000])
                memory.setdefault("map_explored", []).append([new_x, new_y])
                return {"action": "tap", "where": [new_x, new_y], "why": "explore: new area", "priority": 5}
            
            return {"action": "tap", "where": [540, 960], "why": "explore: {}".format(c[:40]), "priority": 4}
        
        # 随机探索新区域
        if random.random() < 0.3:
            return {"action": "tap", "where": [random.randint(150, 900), random.randint(200, 1600)], "why": "curious: random explore", "priority": 3}
    
    # === 菜单好奇心 ===
    if scene == "menu":
        menu_items = [
            {"action": "tap", "where": [700, 200], "why": "curious: check characters"},
            {"action": "tap", "where": [80, 480], "why": "curious: check quests"},
            {"action": "tap", "where": [200, 80], "why": "curious: check base"},
        ]
        return random.choice(menu_items)
    
    # === 默认：观察+不重复 ===
    if recent_actions and recent_actions[-1].get("action") == "wait":
        return {"action": "tap", "where": [540, 960], "why": "try something", "priority": 2}
    
    return {"action": "wait", "seconds": random.randint(2, 5), "why": "curious observation", "priority": 1}

def act(decision):
    action = decision.get("action", "wait")
    why = decision.get("why", "")
    action_executed = why
    
    if action == "tap":
        w = decision.get("where", [540, 960])
        tap(w[0], w[1])
    elif action == "move":
        d = decision.get("dir", "forward")
        base = [200, 1700]
        if d == "forward": swipe(base[0], base[1], base[0], base[1]-300, 300)
        elif d == "backward": swipe(base[0], base[1], base[0], base[1]+200, 300)
        elif d == "left": swipe(base[0], base[1], base[0]-200, base[1], 300)
        elif d == "right": swipe(base[0], base[1], base[0]+200, base[1], 300)
        action_executed = "move " + d
    elif action == "back":
        back()
        action_executed = "back"
    else:
        time.sleep(decision.get("seconds", 3))
    
    return action_executed

def start_game():
    subprocess.run(ADB + ['shell','am','force-stop','com.hypergryph.endfield'], capture_output=True, timeout=10)
    time.sleep(3)
    subprocess.run(ADB + ['shell','am','start','-n','com.hypergryph.endfield/com.u8.sdk.U8UnityContext'], capture_output=True, timeout=10)
    time.sleep(40)
    for _ in range(3):
        tap(540, 960)
        time.sleep(3)

# ==================== MAIN ====================
memory = {"recent_actions": [], "places_visited": {}, "map_explored": [], "total_actions": 0,
          "combat_wins": 0, "battles_fought": 0, "curiosities_satisfied": 0}
if os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
        memory = json.load(f)

print("=== Curious Player v2 ===")

if not game_alive():
    start_game()

action_count = 0
while True:
    try:
        obs = observe(memory)
        if not obs:
            time.sleep(3)
            continue
        
        scene = obs.get("scene", "?")
        hp = obs.get("hp_percent", "?")
        danger = obs.get("danger_level", "?")
        enemies = obs.get("enemies_visible", "?")
        curiosity = obs.get("curiosities", [])
        dodge = obs.get("dodge_needed", False)
        
        # 紧凑的状态输出
        flags = []
        if dodge: flags.append("DODGE!")
        if int(hp) < 30 if isinstance(hp, (int,float)) and hp != "?" else False: flags.append("LOW_HP")
        if enemies and int(enemies) > 0 if isinstance(enemies, (int,float)) and enemies != "?" else False: flags.append("ENEMIES:"+str(enemies))
        if curiosity: flags.append("CURIOUS")
        
        status = " ".join(flags) if flags else "normal"
        print(f"[{action_count}] {scene} | HP:{hp}% | Danger:{danger} | [{status}]")
        
        decision = decide(obs, memory)
        before_hash = obs.get("hash", "")
        
        result = act(decision)
        time.sleep(random.uniform(1.0, 3.0))
        
        after_img = screencap()
        changed = hashlib.md5(after_img).hexdigest() != before_hash if after_img else True
        
        # 记录战斗统计
        if scene == "combat" and "fight" in decision.get("why", ""):
            memory["battles_fought"] = memory.get("battles_fought", 0) + 0.5
        if scene != "combat" and memory["recent_actions"] and memory["recent_actions"][-1].get("scene") == "combat":
            memory["combat_wins"] = memory.get("combat_wins", 0) + 1
        
        # 满足好奇心
        if curiosity and changed:
            memory["curiosities_satisfied"] = memory.get("curiosities_satisfied", 0) + 1
        
        # 记忆
        memory["recent_actions"].append({
            "scene": scene, "hp": hp, "action": decision.get("action",""),
            "why": decision.get("why",""), "changed": changed,
            "time": datetime.now().isoformat(),
        })
        memory["recent_actions"] = memory["recent_actions"][-30:]
        memory["places_visited"][scene] = memory["places_visited"].get(scene, 0) + 1
        memory["total_actions"] = action_count
        action_count += 1
        
        # 每10轮保存+显示统计
        if action_count % 10 == 0:
            with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(memory, f, ensure_ascii=False, indent=2)
            stats = memory
            print(f"[STATS] actions:{action_count} battles:{stats.get('battles_fought',0)} wins:{stats.get('combat_wins',0)} curious:{stats.get('curiosities_satisfied',0)}")
        
        # 卡住检测
        recent_same = sum(1 for a in memory["recent_actions"][-8:] if a.get("scene") == scene and not a.get("changed"))
        if recent_same >= 4:
            print("[Player] Seems stuck! Trying back + random tap...")
            back()
            time.sleep(1)
            tap(random.randint(100, 950), random.randint(100, 1800))
            memory["recent_actions"] = []
        
        # 登出检测
        if scene in ["login", "dialog"] and "logout" in str(obs.get("what_i_see","")).lower():
            print("[Player] Logged out! Restarting...")
            start_game()
            memory["recent_actions"] = []
        
    except KeyboardInterrupt:
        break
    except Exception as e:
        print(f"[Error] {e}")
        time.sleep(3)

with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
    json.dump(memory, f, ensure_ascii=False, indent=2)
print(f"\n[Player] Ended. {action_count} actions, battles:{memory.get('battles_fought',0)}, wins:{memory.get('combat_wins',0)}")
