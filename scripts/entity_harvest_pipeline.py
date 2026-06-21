#!/usr/bin/env python3
"""
IEA 实体图像采集管线 — 全自动 v3

特点：
- 多模态输入（截图给 Qwen3.6-Max 看）
- 行为多样性检测（自动中断重复模式）
- 探索策略自动切换（世界探索→UI导航→副本）
- OCR辅助检测页面类型
"""

import json, time, base64, os, sys, re, hashlib, subprocess, struct
from typing import Dict, List, Optional
from datetime import datetime
import requests

# ── 修复控制台编码 ──
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ── 配置 ──
API_URL = "http://192.168.1.19:3000/v1"
API_KEY = "sk-IDYeDxp4uuC5doDT2mX6iPEkkTYwfAY1lwUzm5rQQw8Yzcv3"
MODEL = "Qwen3.6-Max-Preview-thinking"
ADB = r"C:\Users\xray\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant\3rd-party\adb\adb.exe"
DEVICE = "localhost:16512"
BASE_DIR = r"C:\Users\xray\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant\training_data"

os.makedirs(f"{BASE_DIR}/raw/entities", exist_ok=True)
os.makedirs(f"{BASE_DIR}/raw/creatures", exist_ok=True)
os.makedirs(f"{BASE_DIR}/raw/buildings", exist_ok=True)
os.makedirs(f"{BASE_DIR}/raw/npcs", exist_ok=True)
os.makedirs(f"{BASE_DIR}/raw/items", exist_ok=True)
os.makedirs(f"{BASE_DIR}/raw/ui_elements", exist_ok=True)
os.makedirs(f"{BASE_DIR}/pipeline_logs", exist_ok=True)
os.makedirs(f"{BASE_DIR}/screenshots", exist_ok=True)

# ── 定时清洁配置 ──
CLEANUP_INTERVAL = 50  # 每 50 张截图清洁一次暂存
MAX_SESSION_SCREENSHOTS = 100  # 每个 session 保留的最大截图数

# ── ADB 层 ──
def adb_tap(x, y):
    subprocess.run([ADB, "-s", DEVICE, "shell", "input", "tap", str(x), str(y)], capture_output=True, timeout=10)

def adb_swipe(x1, y1, x2, y2, d=500):
    subprocess.run([ADB, "-s", DEVICE, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(d)], capture_output=True, timeout=10)

def adb_keyevent(k):
    subprocess.run([ADB, "-s", DEVICE, "shell", "input", "keyevent", str(k)], capture_output=True, timeout=10)

def adb_screencap():
    r = subprocess.run([ADB, "-s", DEVICE, "exec-out", "screencap", "-p"], capture_output=True, timeout=15)
    return r.stdout if r.returncode == 0 and len(r.stdout) > 10000 else None

# ── 图片哈希比较（检测重复画面）──
def image_hash(img_bytes: bytes) -> str:
    return hashlib.md5(img_bytes).hexdigest()[:16]

def images_similar(h1: str, h2: str, threshold: int = 8) -> bool:
    """MD5前缀相似度检测"""
    match = sum(1 for a, b in zip(h1, h2) if a == b)
    return match >= threshold

# ── Qwen 通信 ──
def qwen_ask(messages: List[Dict], max_tokens=4096) -> str:
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.05,
    }
    for attempt in range(5):
        try:
            r = requests.post(f"{API_URL}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json=payload, timeout=300)
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"]["content"] or ""
                if "  response" in content:
                    parts = content.split("  response", 1)
                    if len(parts) > 1:
                        content = parts[1].strip()
                return content
            print(f"  API error {r.status_code}, retry {attempt+1}")
            time.sleep(5)
        except Exception as e:
            print(f"  API exception: {e}, retry {attempt+1}")
            time.sleep(10)
    return ""

def make_image_message(img_bytes: bytes, text: str = "这是当前游戏画面。请分析并输出下一步动作。") -> Dict:
    b64 = base64.b64encode(img_bytes).decode()
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
        ]
    }

def make_text_message(text: str) -> Dict:
    return {"role": "user", "content": text}

# ── 动作解析 ──
def parse_actions(text: str) -> List[Dict]:
    actions = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith(">>>"):
            line = line[3:].strip()
        try:
            action = json.loads(line)
            if isinstance(action, dict) and "action" in action:
                actions.append(action)
        except:
            continue
    return actions

TOOL_IMPLS = {
    "tap": lambda x, y: adb_tap(int(x), int(y)),
    "swipe": lambda x1, y1, x2, y2, d=500: adb_swipe(int(x1), int(y1), int(x2), int(y2), int(d)),
    "wait": lambda s: time.sleep(float(s)),
    "back": lambda: adb_keyevent(4),
    "screenshot": lambda: None,
}

def execute_actions(actions: List[Dict]) -> str:
    feedback = []
    for i, action in enumerate(actions):
        a = action["action"]
        p = {k: v for k, v in action.items() if k != "action"}
        impl = TOOL_IMPLS.get(a)
        if impl:
            try:
                impl(**p)
                feedback.append(f"[{i+1}] {json.dumps(action)} > OK")
            except Exception as e:
                feedback.append(f"[{i+1}] {json.dumps(action)} > FAIL: {e}")
        else:
            feedback.append(f"[{i+1}] {json.dumps(action)} > UNKNOWN")
    return "\n".join(feedback)

# ── 屏幕分析 ──
def quick_screen_analysis(ocr_results, img_hash) -> dict:
    """快速判断当前画面类型"""
    # 先用简单的像素特征判断
    # 实际项目中可集成OCR
    return {"page_type": "unknown"}

# ── 实体检测与裁剪 ──
def analyze_screenshot_entities(img_bytes: bytes) -> dict:
    """Qwen VL 分析截图，检测实体目标并返回边界框"""
    b64 = base64.b64encode(img_bytes).decode()
    msgs = [
        {"role": "system", "content": "你是游戏实体检测器。只输出 JSON，不要任何其他内容。"},
        {"role": "user", "content": [
            {"type": "text", "text": """分析这张《明日方舟：终末地》游戏截图。检测所有可见实体。

输出格式（纯 JSON，不要其他文字）：
{
  "entities": [
    {"label": "实体名称", "type": "creature|building|npc|item|ui_element", "bbox": [x1,y1,x2,y2], "confidence": 0.0-1.0}
  ]
}

规则：
- bbox = [左上角X, 左上角Y, 右下角X, 右下角Y]，1280x720 坐标空间
- type: creature=敌人/怪物, building=建筑/设施, npc=角色, item=物品, ui_element=界面元素
- 只包含置信度 > 0.5 的实体
- 如果没有实体: {"entities": []}"""},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
        ]}
    ]
    for attempt in range(3):
        try:
            r = requests.post(f"{API_URL}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={"model": MODEL, "messages": msgs, "max_tokens": 2048, "temperature": 0.01},
                timeout=120)
            if r.status_code == 200:
                raw = r.json()["choices"][0]["message"]["content"] or ""
                # 清理 thinking 模型的额外输出
                content = raw
                # 去掉 think 标签包裹的内容
                content = re.sub(r'<think>[\s\S]*?</think>', '', content)
                # 去掉  response 标记及其之前的内容
                if "  response" in content:
                    content = content.split("  response", 1)[-1].strip()
                # 去掉 markdown 代码块标记
                content = re.sub(r'```(?:json)?\s*', '', content)
                content = content.strip()
                # 用平衡花括号法提取最外层的 JSON 对象
                json_strs = []
                depth = 0
                start = -1
                for i, c in enumerate(content):
                    if c == '{':
                        if depth == 0:
                            start = i
                        depth += 1
                    elif c == '}':
                        depth -= 1
                        if depth == 0 and start >= 0:
                            json_strs.append(content[start:i+1])
                            start = -1
                # 从后往前找包含 entities 的 JSON
                for js in reversed(json_strs):
                    try:
                        parsed = json.loads(js)
                        if "entities" in parsed:
                            return parsed
                    except json.JSONDecodeError:
                        continue
                # 回退：尝试解析最后一个 JSON 对象
                if json_strs:
                    try:
                        return json.loads(json_strs[-1])
                    except json.JSONDecodeError:
                        pass
                return {"entities": []}
            time.sleep(3)
        except Exception as e:
            print(f"  实体分析错误: {e}")
            time.sleep(5)
    return {"entities": []}

def crop_entities(img_bytes: bytes, analysis: dict, tag: str) -> int:
    """根据分析结果裁剪实体图像并分类保存"""
    if not analysis.get("entities"):
        return 0
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(img_bytes))
    w, h = img.size
    count = 0
    for ent in analysis["entities"]:
        bbox = ent.get("bbox", [])
        label = ent.get("label", "unknown")
        etype = ent.get("type", "unknown")
        conf = ent.get("confidence", 1.0)
        if len(bbox) == 4:
            x1, y1, x2, y2 = bbox
            if x2 > x1 and y2 > y1 and x1 >= 0 and y1 >= 0 and x2 <= w and y2 <= h:
                safe_label = re.sub(r'[^\w\u4e00-\u9fff\u3400-\u4dbf]', '_', label)
                type_dir = f"{BASE_DIR}/raw/{etype}s"
                os.makedirs(type_dir, exist_ok=True)
                crop = img.crop((x1, y1, x2, y2))
                crop_path = f"{type_dir}/{safe_label}_{tag}_{count}.png"
                crop.save(crop_path)
                count += 1
                print(f"    裁剪: {safe_label} ({etype}) [{x1},{y1},{x2},{y2}] conf={conf}")
    return count

def cleanup_session_staging(screen_dir: str, session_id: str, total_images: int) -> dict:
    """
    定时清洁暂存数据：
    - 统计已裁剪的实体数量
    - 清理超过 MAX_SESSION_SCREENSHOTS 的旧截图
    - 返回清洁报告
    """
    report = {"screenshots_pruned": 0, "entities_count": {}, "freed_mb": 0}

    # 统计各类型实体目录的文件数
    for etype in ["creatures", "buildings", "npcs", "items", "ui_elements", "entities"]:
        type_dir = f"{BASE_DIR}/raw/{etype}"
        if os.path.exists(type_dir):
            count = len([f for f in os.listdir(type_dir) if f.endswith(".png")])
            report["entities_count"][etype] = count

    # 如果当前 session 截图超过阈值，删除最早的截图
    if os.path.exists(screen_dir) and total_images > MAX_SESSION_SCREENSHOTS:
        screenshots = sorted([f for f in os.listdir(screen_dir) if f.endswith(".png")])
        to_delete = screenshots[:len(screenshots) - MAX_SESSION_SCREENSHOTS]
        for fname in to_delete:
            fpath = os.path.join(screen_dir, fname)
            try:
                size = os.path.getsize(fpath)
                os.remove(fpath)
                report["screenshots_pruned"] += 1
                report["freed_mb"] += size / (1024 * 1024)
            except Exception as e:
                print(f"  删除失败 {fname}: {e}")

    return report

# ── 探索策略 ──
NAV_ACTIONS = {
    "move_forward":    [{"action": "tap", "x": 65, "y": 235}],
    "move_forward2":   [{"action": "tap", "x": 66, "y": 262}],
    "move_left":       [{"action": "swipe", "x1": 640, "y1": 360, "x2": 300, "y2": 360, "d": 800}],
    "move_right":      [{"action": "swipe", "x1": 640, "y1": 360, "x2": 980, "y2": 360, "d": 800}],
    "turn_left":       [{"action": "swipe", "x1": 640, "y1": 360, "x2": 200, "y2": 360, "d": 1200}],
    "turn_right":      [{"action": "swipe", "x1": 640, "y1": 360, "x2": 1080, "y2": 360, "d": 1200}],
    "look_up":         [{"action": "swipe", "x1": 640, "y1": 400, "x2": 640, "y2": 200, "d": 600}],
    "look_down":       [{"action": "swipe", "x1": 640, "y1": 200, "x2": 640, "y2": 400, "d": 600}],
    "open_menu":       [{"action": "tap", "x": 930, "y": 19}],
    "toggle_mode":     [{"action": "tap", "x": 81, "y": 21}],
    "back":            [{"action": "back"}],
    "wait":            [{"action": "wait", "s": 3.0}],
    "screenshot":      [{"action": "screenshot"}],
}

# 策略轮换表（防止Qwen陷入重复模式时手动接管）
STRATEGY_ROTATION = [
    "explore_world",     # 自由探索世界
    "visit_menu",        # 打开活动中心
    "toggle_industry",   # 切换到工业模式
    "enter_combat",      # 尝试进入副本
    "back_to_world",     # 返回世界
    "explore_world",
    "visit_menu",
    "explore_world",
    "toggle_industry",
    "explore_world",
]

def get_strategy_actions(strategy: str) -> List[Dict]:
    if strategy == "explore_world":
        return [{"action": "screenshot"}]
    elif strategy == "visit_menu":
        # 打开活动中心
        return [{"action": "wait", "s": 2}, {"action": "tap", "x": 930, "y": 19}, {"action": "wait", "s": 3}, {"action": "screenshot"}]
    elif strategy == "toggle_industry":
        # 切换探索/工业模式
        return [{"action": "wait", "s": 2}, {"action": "tap", "x": 81, "y": 21}, {"action": "wait", "s": 3}, {"action": "screenshot"}]
    elif strategy == "enter_combat":
        # 打开活动中心→点击左侧密境行者→前往→进入协议空间
        return [
            {"action": "tap", "x": 930, "y": 19}, {"action": "wait", "s": 3},
            # 点击左侧密境行者
            {"action": "tap", "x": 60, "y": 240}, {"action": "wait", "s": 2},
            {"action": "screenshot"},
        ]
    elif strategy == "enter_combat2":
        # 进入协议空间（接上一步）
        return [
            {"action": "tap", "x": 640, "y": 480}, {"action": "wait", "s": 3},
            {"action": "tap", "x": 640, "y": 360}, {"action": "wait", "s": 5},
            {"action": "screenshot"},
        ]
    elif strategy == "back_to_world":
        # 多次返回回到世界地图
        return [{"action": "back"}, {"action": "wait", "s": 2}, {"action": "back"}, {"action": "wait", "s": 2}, {"action": "back"}, {"action": "wait", "s": 2}, {"action": "screenshot"}]
    elif strategy == "move_around":
        # 多方向移动，打破卡死
        return [
            {"action": "swipe", "x1": 640, "y1": 360, "x2": 200, "y2": 360, "d": 1500},
            {"action": "wait", "s": 2},
            {"action": "tap", "x": 65, "y": 235}, {"action": "wait", "s": 1},
            {"action": "swipe", "x1": 640, "y1": 360, "x2": 1080, "y2": 360, "d": 1500},
            {"action": "wait", "s": 2},
            {"action": "tap", "x": 66, "y": 262}, {"action": "wait", "s": 1},
            {"action": "screenshot"},
        ]
    return [{"action": "screenshot"}]

# ── 实体类型轮换表 ──
ENTITY_QUESTS = [
    {"focus": "敌人/怪物", "locations": "野外区域、副本内部", "hint": "在野外四处走动寻找敌人，或者通过活动中心→密境行者进入副本"},
    {"focus": "建筑/设施", "locations": "基地、野外据点", "hint": "观察地图上的建筑，切换到工业模式查看基地设施"},
    {"focus": "地形/场景", "locations": "各种野外区域", "hint": "探索不同地形：草地、沙漠、废墟、水域"},
    {"focus": "NPC/队友", "locations": "基地、活动中心", "hint": "在基地中寻找NPC，或者编队界面查看队友"},
    {"focus": "UI/界面元素", "locations": "菜单界面", "hint": "打开活动中心、编队、仓库等界面拍摄UI"},
    {"focus": "战斗场景", "locations": "密境行者副本", "hint": "进入副本后拍摄战斗画面"},
]

# ── 强约束系统提示词 ──
SYSTEM_PROMPT = """你是一个《明日方舟：终末地》实体图像采集 AI。

## 核心规则
你只能输出动作行，每行一个动作，以 >>> 开头。不要输出任何其他内容。

## 可用动作
>>> {"action":"screenshot"}
>>> {"action":"tap","x":int,"y":int}
>>> {"action":"wait","s":float}
>>> {"action":"back"}
>>> {"action":"swipe","x1":int,"y1":int,"x2":int,"y2":int,"d":int}

## 导航坐标参考（1280x720）
- ★按钮 (930,19)：打开活动中心
- 探索/工业切换 (81,21)
- 前移 (65,235) 和 (66,262)
- 活动中心左侧列表：密境行者/理智补给/每周事务
- 密境行者入口：在活动中心中点击左侧的"密境行者"
- 进入协议空间：密境行者界面点击"前往"→"进入协议空间"

## 通用提示
- 每次动作后我会给你新截图
- 每次只输出 3-6 个动作，不要太多
- 动作要多样化，不要连续重复相同操作
- 如果你在一个地方停留太久，尝试移动到新区域
- 看到敌人时，尝试从不同角度拍摄

## 当前采集任务
当前需要重点采集：{quest_focus}
建议位置：{locations}
提示：{hint}

## 输出格式示例
>>> {"action":"screenshot"}
>>> {"action":"wait","s":2.0}
>>> {"action":"tap","x":640,"y":360}

只输出动作行，不要任何解释。"""

# ── 主循环 ──
def run_entity_collection():
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = f"{BASE_DIR}/pipeline_logs/session_{session_id}.jsonl"
    screen_dir = f"{BASE_DIR}/screenshots/{session_id}"
    os.makedirs(screen_dir, exist_ok=True)

    messages = [{"role": "system", "content": SYSTEM_PROMPT.replace(
        "{quest_focus}", ENTITY_QUESTS[0]["focus"],
    ).replace(
        "{locations}", ENTITY_QUESTS[0]["locations"],
    ).replace(
        "{hint}", ENTITY_QUESTS[0]["hint"],
    )}]
    total_images = 0
    round_num = 0
    last_few_actions = []
    same_action_count = 0
    strategy_idx = 0
    qwen_stuck_count = 0
    last_hash = ""
    stuck_same_scene = 0
    quest_idx = 0  # 当前采集的实体类型索引
    quest_screenshots = 0  # 当前实体类型已采集张数

    print(f"实体采集管线 v3 启动 | session={session_id}")
    print(f"日志: {log_path}")
    print(f"截图目录: {screen_dir}")

    # 首次截图
    img_data = adb_screencap()
    if not img_data:
        print("错误: ADB不可用")
        return

    ts = datetime.now().strftime("%H%M%S")
    h = hashlib.md5(img_data).hexdigest()[:8]
    init_fname = f"init_{ts}_{h}.png"
    with open(f"{screen_dir}/{init_fname}", "wb") as f:
        f.write(img_data)
    last_hash = h

    messages.append(make_image_message(img_data))
    messages.append(make_text_message(
        "开始采集！先截图看看当前画面，然后导航探索不同场景，拍摄各种实体（敌人、建筑、NPC、地形等）的多角度图像。"
        "每次动作后我会给你新截图。动作要多样化，不要重复相同操作。"
    ))

    with open(log_path, "w", encoding="utf-8") as log:
        while total_images < 200:
            round_num += 1
            print(f"\n=== Round {round_num} (total_images={total_images}) ===")
            sys.stdout.flush()

            # 检测卡死：Qwen 如果连续多次不输出有效动作，手动接管
            if qwen_stuck_count >= 3:
                strategy = STRATEGY_ROTATION[strategy_idx % len(STRATEGY_ROTATION)]
                strategy_idx += 1
                print(f"  Qwen 卡死 #{qwen_stuck_count}，手动执行策略: {strategy}")
                override_actions = get_strategy_actions(strategy)
                feedback = execute_actions(override_actions)
                qwen_stuck_count = 0

                # 执行后截图
                time.sleep(2)
                img_data = adb_screencap()
                if img_data:
                    ts = datetime.now().strftime("%H%M%S")
                    h = hashlib.md5(img_data).hexdigest()[:8]
                    fname = f"r{round_num:03d}_override_{ts}_{h}.png"
                    with open(f"{screen_dir}/{fname}", "wb") as f:
                        f.write(img_data)
                    total_images += 1
                    print(f"  手动策略截图 #{total_images}: {fname}")

                    messages.append(make_text_message(f"手动执行策略 {strategy}。这是新画面，请分析并继续探索。"))
                    messages.append(make_image_message(img_data))
                    messages.append(make_text_message("继续输出动作。"))
                continue

            # Qwen 决策
            response = qwen_ask(messages)
            if not response:
                print(f"  Qwen 无响应")
                qwen_stuck_count += 1
                time.sleep(5)
                continue

            log.write(json.dumps({"round": round_num, "response_len": len(response)}, ensure_ascii=False) + "\n")
            log.flush()

            # 解析动作
            actions = parse_actions(response)
            print(f"  解析到 {len(actions)} 个动作")
            if actions:
                for a in actions:
                    print(f"    {json.dumps(a, ensure_ascii=False)}")

            if not actions:
                print(f"  未解析到动作")
                qwen_stuck_count += 1
                messages.append({"role": "assistant", "content": response})
                messages.append(make_text_message("请只输出 >>> 开头的动作行。"))
                time.sleep(2)
                continue

            qwen_stuck_count = 0

            # ── 单次响应去重：移除连续重复的动作序列 ──
            deduped = []
            seen_patterns = set()
            for a in actions:
                key = json.dumps(a, sort_keys=True)
                if key not in seen_patterns:
                    seen_patterns.add(key)
                    deduped.append(a)
            if len(deduped) < len(actions):
                print(f"  去重: {len(actions)} -> {len(deduped)} 个动作")
                actions = deduped

            # 如果去重后还有很多，只取前6个
            if len(actions) > 6:
                print(f"  截断: {len(actions)} -> 前6个动作")
                actions = actions[:6]

            # 检测重复动作（基于动作签名，而非完整JSON）
            # 防止Qwen在同一轮输出完全相同的动作序列
            action_signature = json.dumps([{k: a.get(k) for k in ("action", "x", "y") if k in a} for a in actions], sort_keys=True)
            last_few_actions.append(action_signature)
            if len(last_few_actions) > 5:
                last_few_actions.pop(0)

            # 如果最后3个动作序列完全相同，干涉
            if len(last_few_actions) >= 3 and len(set(last_few_actions[-3:])) == 1:
                print(f"  检测到重复动作模式! 切换策略")
                strategy = STRATEGY_ROTATION[strategy_idx % len(STRATEGY_ROTATION)]
                strategy_idx += 1
                override = get_strategy_actions(strategy)
                actions = override
                print(f"  覆盖为策略: {strategy}")
                for a in actions:
                    print(f"    {json.dumps(a, ensure_ascii=False)}")

            # 执行动作
            feedback = execute_actions(actions)
            print(f"  执行完成")
            log.write(json.dumps({"round": round_num, "actions": [json.dumps(a) for a in actions], "feedback": feedback}, ensure_ascii=False) + "\n")
            log.flush()

            # 执行后截图
            time.sleep(1.5)
            img_data = adb_screencap()
            if img_data:
                ts = datetime.now().strftime("%H%M%S")
                h = hashlib.md5(img_data).hexdigest()[:8]
                fname = f"r{round_num:03d}_{ts}_{h}.png"
                with open(f"{screen_dir}/{fname}", "wb") as f:
                    f.write(img_data)

                # ── 实体检测与裁剪 ──
                print(f"  正在分析实体...")
                sys.stdout.flush()
                analysis = analyze_screenshot_entities(img_data)
                cropped = crop_entities(img_data, analysis, h[:8])
                entities_found = len(analysis.get("entities", []))
                print(f"  截图 #{total_images + 1}: {fname} | 实体：{entities_found} 个，裁剪：{cropped} 张")

                total_images += 1

                # ── 定时清洁暂存 ──
                if total_images % CLEANUP_INTERVAL == 0:
                    print(f"  [清洁] 第 {total_images} 张，执行定时清洁...")
                    sys.stdout.flush()
                    report = cleanup_session_staging(screen_dir, session_id, total_images)
                    print(f"  [清洁] 实体统计：{report['entities_count']}")
                    if report['screenshots_pruned'] > 0:
                        print(f"  [清洁] 删除 {report['screenshots_pruned']} 张旧截图，释放 {report['freed_mb']:.1f}MB")

                # 检测是否跟上一张太像
                if images_similar(h, last_hash, 12):
                    stuck_same_scene += 1
                else:
                    stuck_same_scene = 0
                last_hash = h

                # 每采集一定张数后切换实体类型
                quest_screenshots += 1
                if quest_screenshots >= 30:
                    quest_idx = (quest_idx + 1) % len(ENTITY_QUESTS)
                    quest_screenshots = 0
                    q = ENTITY_QUESTS[quest_idx]
                    print(f"  切换采集目标: {q['focus']}")
                    # 替换 system prompt 中的采集任务
                    messages[0] = {"role": "system", "content": SYSTEM_PROMPT.replace(
                        "{quest_focus}", q["focus"],
                    ).replace(
                        "{locations}", q["locations"],
                    ).replace(
                        "{hint}", q["hint"],
                    )}

                # 如果连续3张非常相似，强制切换策略
                if stuck_same_scene >= 3:
                    print(f"  画面卡死! 强制切换")
                    strategy = STRATEGY_ROTATION[strategy_idx % len(STRATEGY_ROTATION)]
                    strategy_idx += 1
                    execute_actions(get_strategy_actions(strategy))
                    time.sleep(2)
                    img_data2 = adb_screencap()
                    if img_data2:
                        ts2 = datetime.now().strftime("%H%M%S")
                        h2 = hashlib.md5(img_data2).hexdigest()[:8]
                        fname2 = f"r{round_num:03d}_escape_{ts2}_{h2}.png"
                        with open(f"{screen_dir}/{fname2}", "wb") as f:
                            f.write(img_data2)
                        total_images += 1
                        print(f"  逃离截图 #{total_images}: {fname2}")
                    stuck_same_scene = 0

                # 构建反馈上下文
                scene_warning = ""
                if stuck_same_scene > 0:
                    scene_warning = f" 注意：连续 {stuck_same_scene} 次画面变化很小，请尝试大幅移动或进入新区域。"

                messages.append({"role": "assistant", "content": response})
                msg = f"动作执行结果:\n{feedback}\n\n新截图已保存，当前总截图数: {total_images}。{scene_warning}\n请继续采集不同实体，尝试新路线。"
                messages.append(make_text_message(msg))
                messages.append(make_image_message(img_data, f"这是执行后的新画面{scene_warning}。请分析并输出下一步动作。"))
                messages.append(make_text_message("继续。输出 >>> 动作行。"))
            else:
                print(f"  截图失败")
                messages.append({"role": "assistant", "content": response})
                messages.append(make_text_message(f"动作执行结果:\n{feedback}\n\n截图失败，重试。"))

            # 控制上下文长度
            if len(messages) > 24:
                keep = [messages[0]] + messages[-20:]
                messages = keep
                print(f"  上下文裁剪: {len(messages)} 条消息")

            time.sleep(1)

    print(f"\n{'='*50}")
    print(f"采集完成! 总截图: {total_images}")
    print(f"截图目录: {screen_dir}")
    print(f"会话日志: {log_path}")

    # ── 最终清洁总结 ──
    print(f"\n{'='*50}")
    print("实体采集统计:")
    final_report = cleanup_session_staging(screen_dir, session_id, total_images)
    for etype, count in final_report["entities_count"].items():
        print(f"  {etype}: {count} 个")
    print(f"\n暂存清理完成!")

if __name__ == "__main__":
    run_entity_collection()
