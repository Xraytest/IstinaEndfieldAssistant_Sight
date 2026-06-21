"""
终末地 真人v4 - 单次Qwen3.6-Plus调用(分类+决策)，严格证据驱动
"""
import json, base64, urllib.request, time, subprocess, sys, os, re, hashlib, random

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

API = 'http://192.168.1.19:3000/v1/chat/completions'
AUTH = 'Bearer sk-IDYeDxp4uuC5doDT2mX6iPEkkTYwfAY1lwUzm5rQQw8Yzcv3'
HD = {'Content-Type':'application/json','Authorization':AUTH}
MEM = 'C:/Users/xray/AppData/Local/Temp/kilo/player_v4_memory.json'
ADB = ['3rd-party/adb/adb.exe','-s','localhost:16512']

def tap(x,y):
    subprocess.run(ADB+['shell','input','tap',str(x+random.randint(-6,6)),str(y+random.randint(-6,6))],capture_output=True,timeout=5)
def swipe(x1,y1,x2,y2,d=400):
    subprocess.run(ADB+['shell','input','swipe',str(x1),str(y1),str(x2),str(y2),str(d)],capture_output=True,timeout=5)
def back():
    subprocess.run(ADB+['shell','input','keyevent','4'],capture_output=True,timeout=5)
def scr():
    r=subprocess.run(ADB+['exec-out','screencap','-p'],capture_output=True,timeout=10)
    return r.stdout if r.returncode==0 and len(r.stdout)>1000 else None
def alive():
    return 'com.hypergryph.endfield' in subprocess.run(ADB+['shell','ps','-A'],capture_output=True,text=True).stdout

def think_and_act(img_b64, recent):
    """一次调用：严格基于证据判断场景 + 决定行动"""
    recent_why = [a.get('why','')[:40] for a in recent[-3:]]
    
    prompt = f"""You play Endfield. Recent: {recent_why}

STRICTLY based on screenshot evidence:
1. Is there a health bar UI? (yes/no)
2. Are enemies visible on screen? (yes/no)  
3. Are there attack/skill buttons? (yes/no)
4. What page is this actually? (title screen/login/loading/world_map/map_overlay/menu/dialog/character/base/quest/event/settings/combat/unknown)

Then decide ONE action a curious player would take.

JSON only:
{{"hp_ui":true/false,"enemies":true/false,"skill_btns":true/false,"page":"pagetype","action":"tap|swipe|back|wait|move","where":[x,y],"why":"reason"}}"""

    payload = {
        "model":"Qwen3.6-Max-Preview","max_tokens":1024,"temperature":0.1,
        "messages":[{"role":"system","content":"Endfield player. 1080x1920. Only output JSON. No markdown."},
            {"role":"user","content":[{"type":"image_url","image_url":{"url":"data:image/png;base64,"+img_b64}},{"type":"text","text":prompt}]}]
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(API, data=data, headers=HD)
    resp = urllib.request.urlopen(req, timeout=120)
    content = json.loads(resp.read().decode())['choices'][0]['message']['content']
    
    try:
        jm = re.search(r'\{.*\}', content, re.DOTALL)
        return json.loads(jm.group()) if jm else {"page":"unknown","action":"wait","seconds":3,"why":"parse fail"}
    except:
        return {"page":"unknown","action":"wait","seconds":3,"why":"parse fail"}

def act(d):
    a = d.get('action','wait')
    w = d.get('where',[540,960])
    if a=='tap': tap(w[0],w[1]); return f"tap {w}"
    elif a=='swipe': swipe(540,960,540+random.randint(-200,200),960+random.randint(-200,200)); return "swipe"
    elif a=='back': back(); return "back"
    elif a=='move': swipe(200,1700,200+random.randint(-100,100),1700-300,300); return "move"
    else: time.sleep(d.get('seconds',3)); return f"wait {d.get('seconds',3)}s"

def start_game():
    subprocess.run(ADB+['shell','am','force-stop','com.hypergryph.endfield'],capture_output=True,timeout=10)
    time.sleep(3)
    subprocess.run(ADB+['shell','am','start','-n','com.hypergryph.endfield/com.u8.sdk.U8UnityContext'],capture_output=True,timeout=10)
    time.sleep(40)
    for _ in range(4): tap(540,960); time.sleep(3)

# === MAIN ===
mem = {"recent_actions":[],"pages_seen":{},"actions":0}
if os.path.exists(MEM):
    with open(MEM,'r',encoding='utf-8') as f: mem = json.load(f)

print("=== Player v4 (Qwen3.6-Plus single call) ===")
if not alive(): start_game()

cnt = 0
while True:
    try:
        img = scr()
        if not img: time.sleep(3); continue
        b64 = base64.b64encode(img).decode()
        h = hashlib.md5(img).hexdigest()[:8]
        
        d = think_and_act(b64, mem.get("recent_actions",[]))
        
        page = d.get('page','?')
        enemies = d.get('enemies',False)
        hp_ui = d.get('hp_ui',False)
        skill_btns = d.get('skill_btns',False)
        why = d.get('why','')
        
        combat_evidence = "E:"+(str(enemies)[0])+" H:"+(str(hp_ui)[0])+" S:"+(str(skill_btns)[0])
        
        result = act(d)
        time.sleep(random.uniform(1.5,3))
        
        img2 = scr()
        changed = hashlib.md5(img2).hexdigest()!=h if img2 else True
        
        print(f"[{cnt}] {page:12s} {combat_evidence} | {why[:50]} | {result} | {'CHG' if changed else 'SAME'}")
        
        mem["recent_actions"].append({"page":page,"action":d.get('action',''),"why":why,"changed":changed})
        mem["recent_actions"] = mem["recent_actions"][-20:]
        mem["pages_seen"][page] = mem["pages_seen"].get(page,0)+1
        mem["actions"] = cnt
        cnt += 1
        
        if cnt%5==0:
            with open(MEM,'w',encoding='utf-8') as f: json.dump(mem,f,ensure_ascii=False,indent=2)
        
    except KeyboardInterrupt: break
    except Exception as e: print(f"  [ERR] {e}"); time.sleep(5)

with open(MEM,'w',encoding='utf-8') as f: json.dump(mem,f,ensure_ascii=False,indent=2)
print(f"Done: {cnt} actions, pages: {mem['pages_seen']}")
