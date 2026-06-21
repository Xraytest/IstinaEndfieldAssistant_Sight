"""
终末地 真人v3 - 本地GPU分类(防幻觉) + Qwen策略
"""
import json, base64, urllib.request, time, subprocess, sys, os, re, hashlib, random

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

API_QWEN = 'http://192.168.1.19:3000/v1/chat/completions'
API_LOCAL = 'http://127.0.0.1:8080/v1/chat/completions'
QWEN_AUTH = 'Bearer sk-IDYeDxp4uuC5doDT2mX6iPEkkTYwfAY1lwUzm5rQQw8Yzcv3'
HD_QWEN = {'Content-Type':'application/json','Authorization':QWEN_AUTH}
HD_LOCAL = {'Content-Type':'application/json'}
MEMORY = 'C:/Users/xray/AppData/Local/Temp/kilo/player_v3_memory.json'
ADB = ['3rd-party/adb/adb.exe','-s','localhost:16512']

def tap(x,y):
    subprocess.run(ADB+['shell','input','tap',str(x+random.randint(-8,8)),str(y+random.randint(-8,8))], capture_output=True, timeout=5)
def swipe(x1,y1,x2,y2,d=400):
    subprocess.run(ADB+['shell','input','swipe',str(x1),str(y1),str(x2),str(y2),str(d)], capture_output=True, timeout=5)
def back():
    subprocess.run(ADB+['shell','input','keyevent','4'], capture_output=True, timeout=5)
def screencap():
    r = subprocess.run(ADB+['exec-out','screencap','-p'], capture_output=True, timeout=10)
    return r.stdout if r.returncode==0 and len(r.stdout)>1000 else None
def game_alive():
    return 'com.hypergryph.endfield' in subprocess.run(ADB+['shell','ps','-A'], capture_output=True, text=True).stdout

# === 本地GPU - 快速无幻觉场景分类 ===
def local_classify(img_b64):
    """本地GPU: 只做场景分类，不幻想"""
    payload = {
        "model":"local-model","max_tokens":128,"temperature":0.1,
        "messages":[
            {"role":"system","content":"Classify without guessing. Output only one word."},
            {"role":"user","content":[
                {"type":"image_url","image_url":{"url":"data:image/png;base64,"+img_b64}},
                {"type":"text","text":"Is this: combat, world_map, menu, dialog, loading, login, unknown? One word only."}
            ]}
        ]
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(API_LOCAL, data=data, headers=HD_LOCAL)
    resp = urllib.request.urlopen(req, timeout=60)
    r = json.loads(resp.read().decode())
    content = r['choices'][0]['message'].get('content','') or r['choices'][0]['message'].get('reasoning_content','')
    # 提取第一个词
    for word in ['combat','world_map','menu','dialog','loading','login','unknown']:
        if word in content.lower():
            return word
    return 'unknown'

# === Qwen - 策略决策 ===
def qwen_decide(img_b64, scene, memory):
    """Qwen: 基于真实场景做决策"""
    recent_actions = [a.get('why','') for a in memory.get('recent_actions',[])[-5:]]
    visited = memory.get('places_visited',{})
    
    prompt = f"""Current scene: {scene}
Recent actions: {recent_actions}
Places visited: {visited}

You are a curious Endfield player. Look at this screenshot and decide ONE action.
JSON: {{
  "action": "tap|swipe|back|wait|move",
  "where": [x,y]  (if tap, put coordinates),
  "from": [x1,y1]  (if swipe, start coords),
  "to": [x2,y2]  (if swipe, end coords),
  "seconds": N  (if wait),
  "direction": "forward|back|left|right"  (if move),
  "why": "brief reason"
}}"""

    payload = {
        "model":"Qwen3.6-Max-Preview","max_tokens":512,"temperature":0.3,
        "messages":[
            {"role":"system","content":"Endfield player. 1080x1920. JSON only."},
            {"role":"user","content":[
                {"type":"image_url","image_url":{"url":"data:image/png;base64,"+img_b64}},
                {"type":"text","text":prompt}
            ]}
        ]
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(API_QWEN, data=data, headers=HD_QWEN)
    resp = urllib.request.urlopen(req, timeout=60)
    r = json.loads(resp.read().decode())
    content = r['choices'][0]['message']['content']
    
    try:
        jm = re.search(r'\{.*\}', content, re.DOTALL)
        if jm: return json.loads(jm.group())
    except: pass
    return {"action":"wait","seconds":3,"why":"can't decide"}

def act(decision):
    action = decision.get('action','wait')
    why = decision.get('why','')
    
    if action == 'tap':
        w = decision.get('where',[540,960])
        tap(w[0],w[1])
        return f"tap {w}"
    elif action == 'swipe':
        f = decision.get('from',[540,960])
        t = decision.get('to',[540,500])
        swipe(f[0],f[1],t[0],t[1])
        return f"swipe {f}>{t}"
    elif action == 'back':
        back()
        return "back"
    elif action == 'move':
        d = decision.get('direction','forward')
        base = [200,1700]
        if d=='forward': swipe(base[0],base[1],base[0],base[1]-300,300)
        elif d=='back': swipe(base[0],base[1],base[0],base[1]+200,300)
        elif d=='left': swipe(base[0],base[1],base[0]-200,base[1],300)
        elif d=='right': swipe(base[0],base[1],base[0]+200,base[1],300)
        return f"move {d}"
    else:
        time.sleep(decision.get('seconds',3))
        return f"wait {decision.get('seconds',3)}s"

def start_game():
    subprocess.run(ADB+['shell','am','force-stop','com.hypergryph.endfield'], capture_output=True, timeout=10)
    time.sleep(3)
    subprocess.run(ADB+['shell','am','start','-n','com.hypergryph.endfield/com.u8.sdk.U8UnityContext'], capture_output=True, timeout=10)
    time.sleep(40)
    for _ in range(4):
        tap(540,960)
        time.sleep(3)

# === MAIN ===
mem = {"recent_actions":[],"places_visited":{},"actions":0}
if os.path.exists(MEMORY):
    with open(MEMORY,'r',encoding='utf-8') as f: mem = json.load(f)

print("=== Player v3 (Local GPU classify + Qwen decide) ===")

if not game_alive():
    start_game()

cnt = 0
while True:
    try:
        # 1. 截图
        img = screencap()
        if not img: time.sleep(3); continue
        b64 = base64.b64encode(img).decode()
        h = hashlib.md5(img).hexdigest()[:8]
        
        # 2. 本地GPU分类(防幻觉)
        scene = local_classify(b64)
        
        # 3. Qwen决策
        decision = qwen_decide(b64, scene, mem)
        
        # 4. 执行
        why = decision.get('why','')
        result = act(decision)
        time.sleep(random.uniform(1.5, 3.5))
        
        # 5. 验证
        img2 = screencap()
        changed = hashlib.md5(img2).hexdigest()!=h if img2 else True
        
        print(f"[{cnt}] {scene} | {why[:60]} | {result} | {'CHG' if changed else 'SAME'}")
        
        # 6. 记忆
        mem["recent_actions"].append({"scene":scene,"action":decision.get('action',''),"why":why,"changed":changed})
        mem["recent_actions"] = mem["recent_actions"][-20:]
        mem["places_visited"][scene] = mem["places_visited"].get(scene,0)+1
        mem["actions"] = cnt
        cnt += 1
        
        if cnt % 10 == 0:
            with open(MEMORY,'w',encoding='utf-8') as f: json.dump(mem,f,ensure_ascii=False,indent=2)
            print(f"  [SAVE] {cnt} actions, scenes: {mem['places_visited']}")
        
    except KeyboardInterrupt: break
    except Exception as e:
        print(f"  [ERR] {e}")
        time.sleep(3)

with open(MEMORY,'w',encoding='utf-8') as f: json.dump(mem,f,ensure_ascii=False,indent=2)
print(f"Done: {cnt} actions")
