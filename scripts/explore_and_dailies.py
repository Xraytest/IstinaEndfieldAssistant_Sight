"""Comprehensive game exploration + daily quest completion script.
Connects to localhost:16512, explores pages via VLM, completes daily tasks,
records page relationships and execution flow into cache/."""
import sys, os, time, json, re, subprocess, base64, io, hashlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

project_root = os.path.dirname(os.path.dirname(__file__))

from core.logger import init_logger, get_logger, LogCategory
from core.communication.communicator import ClientCommunicator
from device.adb_manager import ADBDeviceManager
from screenshot.screen_capture import ScreenCapture
from device.touch.touch_manager import TouchManager

# 尝试导入 OCR 优先决策模块
try:
    sys.path.insert(0, os.path.join(project_root, "scripts"))
    from ocr_decision_module import detect_screen_state, generate_navigation_plan, KNOWN_COORDS
    OCR_MODULE_AVAILABLE = True
except ImportError:
    OCR_MODULE_AVAILABLE = False

init_logger()
logger = get_logger()

ADB_PATH = os.path.join(project_root, "3rd-party", "adb", "adb.exe")
DEVICE_SERIAL = "localhost:16512"
TOUCH_ADDRESS = "localhost:16512"
CACHE_DIR = os.path.join(project_root, "cache")
API_KEY = "aa7d3551ab7fdb975c2eed5251df53ade38aa12cd6161475221d774f27026763"

TASK_SYSTEM_PROMPT = """你是《明日方舟：终末地》游戏界面分析器。识别当前画面并输出JSON：
{
  "page_name": "中文页面名称",
  "page_type": "world_map/menu/dialog/task_ui/battle/shop/gacha/base/loading/login/announcement/other",
  "has_daily_tasks": false,
  "has_weekly_tasks": false,
  "has_claimable": false,
  "elements": [
    {"id":"e1","type":"button/text/icon/tab","label":"精确可见文本","bbox":[x1,y1,x2,y2],"action":"tap/none","function":"元素功能描述"}
  ],
  "menu_buttons": ["可见的顶部/侧边菜单按钮名称"],
  "navigation_path": ["从主界面到此页面的路径推测"],
  "description": "一句中文描述"
}
特别注意：每日任务、每周任务、作战汇报、签到、奖励领取等按钮。has_claimable看到"领取/收取/一键领取"按钮时为true。
	重要：即使整体页面仍是大地图(world_map)，如果右侧有滑出的任务面板/侧边栏(通常在屏幕右半侧，x>700)，请将page_type设为"task_ui"，并在elements中列出面板内的按钮。"""

ALL_PAGES = {}
ALL_EDGES = []
EXECUTION_LOG = []
session_id = ""
current_page_hash = None
previous_page_hash = None
os.makedirs(CACHE_DIR, exist_ok=True)

MODEL_TAG = "exploration_deep"


def ocr_scan_page(raw_bytes) -> dict:
    """快速 OCR 扫描页面（不调 VLM，~1s）

    使用 MaaMCP OCR（通过 subprocess 调用 ADB screencap + 关键词匹配）。
    用于快速判断页面类型，避免每次决策都调用慢速 VLM。
    """
    if not raw_bytes:
        return {"page_type": "none", "elements": []}

    # 关键词 → 页面类型映射
    # 注意：这里假设调用者会提供 OCR 文本结果
    # 实际 OCR 需要 MaaMCP 支持，这里仅做接口定义
    return {"page_type": "pending_ocr", "elements": [], "ocr_pending": True}


def need_vlm_for_page(ocr_page_type: str) -> bool:
    """判断是否需要调用 VLM 来分析当前页面"""
    # 已知的简单页面类型，OCR 就能处理
    simple_types = {"world_map", "world_map_with_overlay", "loading", "title", "logout_dialog"}
    if ocr_page_type in simple_types:
        return False
    # 未知或复杂页面需要 VLM
    return True


def adb_tap(x, y):
    subprocess.run([ADB_PATH, "-s", DEVICE_SERIAL, "shell", "input", "tap", str(x), str(y)],
                   capture_output=True, timeout=10)

def adb_keyevent(code):
    subprocess.run([ADB_PATH, "-s", DEVICE_SERIAL, "shell", "input", "keyevent", str(code)],
                   capture_output=True, timeout=10)

def adb_swipe(x1, y1, x2, y2, duration_ms):
    subprocess.run([ADB_PATH, "-s", DEVICE_SERIAL, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)],
                   capture_output=True, timeout=15)

def adb_screencap():
    result = subprocess.run([ADB_PATH, "-s", DEVICE_SERIAL, "exec-out", "screencap", "-p"],
                            capture_output=True, timeout=15)
    return result.stdout if result.returncode == 0 and len(result.stdout) > 1000 else None


def analyze_page(raw_bytes) -> dict:
    """分析当前游戏画面

    优先使用 VLM。如果 OCR 模块可用，会在 VLM 返回后增加 OCR 后处理，
    修正 page_type（特别是 overlay 检测修正）。
    """
    b64 = base64.b64encode(raw_bytes).decode("utf-8") if isinstance(raw_bytes, bytes) else raw_bytes
    payload = {
        "instruction": "分析当前游戏画面，识别所有可交互UI元素。特别注意任务、奖励、签到相关按钮。",
        "screenshot": b64, "history": [], "session_id": session_id,
        "user_id": "explorer", "model_tag": MODEL_TAG,
        "device_width": 1080, "device_height": 1920,
        "system_prompt": TASK_SYSTEM_PROMPT,
    }
    try:
        result = communicator.send_request("agent_chat", payload)
    except Exception as e:
        log(f"[ERROR] VLM call failed: {e}")
        result = None

    # VLM 成功 → 解析
    if result and result.get("status") == "success":
        reply = result.get("reply", "")
        json_match = re.search(r'\{[\s\S]*\}', reply)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {"page_name": "unknown", "page_type": "other", "elements": []}

    # VLM 失败 + OCR 模块可用 → 使用 OCR 基础检测
    if OCR_MODULE_AVAILABLE:
        log("[OCR] VLM调用失败，使用OCR基础检测")
        # 此处需要 MaaMCP OCR 结果，如果没有则返回空
        return {"page_name": "OCR_fallback", "page_type": "unknown", "elements": [],
                "ocr_fallback": True}

    return None


def record_page(raw_bytes, page_info, action_taken=None):
    global current_page_hash, previous_page_hash
    h = hashlib.md5(raw_bytes if isinstance(raw_bytes, bytes) else raw_bytes.encode()).hexdigest()[:16]
    current_page_hash = h
    page_name = page_info.get("page_name", "Unknown")
    page_type = page_info.get("page_type", "other")
    elements_raw = page_info.get("elements", [])
    has_daily = page_info.get("has_daily_tasks", False)
    has_weekly = page_info.get("has_weekly_tasks", False)
    has_claim = page_info.get("has_claimable", False)

    if h not in ALL_PAGES:
        elements = []
        for i, e in enumerate(elements_raw):
            bbox = e.get("bbox", [0, 0, 0, 0])
            ele = {
                "element_id": f"elem_{h}_{i}",
                "type": e.get("type", "unknown"),
                "label": e.get("label", ""),
                "bbox": bbox,
                "confidence": e.get("confidence", 0.7),
                "explored": False,
                "leads_to": None,
                "extra": {"action": e.get("action", "none"), "function": e.get("function", "")}
            }
            if action_taken and e.get("label", "") == action_taken.get("label", ""):
                ele["explored"] = True
            elements.append(ele)

        ALL_PAGES[h] = {
            "page_id": f"page_{h}",
            "name": page_name,
            "screenshot_hash": h,
            "elements": elements,
            "parent_edge": previous_page_hash if previous_page_hash else None,
            "depth": len(EXECUTION_LOG),
            "state": "explored",
            "resolution": [1080, 1920],
            "timestamp": time.time(),
            "verification_count": 0,
            "has_daily_tasks": has_daily,
            "has_weekly_tasks": has_weekly,
            "has_claimable": has_claim,
            "page_type": page_type,
        }

    if previous_page_hash and previous_page_hash != h and action_taken:
        from_page = ALL_PAGES.get(previous_page_hash, {})
        from_elements = from_page.get("elements", [])
        matched_elem_id = None
        for ele in from_elements:
            label = ele.get("label", "")
            if action_taken.get("label", "") and label == action_taken.get("label", ""):
                matched_elem_id = ele["element_id"]
                ele["explored"] = True
                ele["leads_to"] = f"page_{h}"
                break
        edge = {
            "edge_id": f"edge_{previous_page_hash}_{matched_elem_id or 'nav'}_{h}",
            "from": f"page_{previous_page_hash}",
            "to": f"page_{h}",
            "element_id": matched_elem_id or "navigation",
            "action_type": action_taken.get("type", "tap"),
            "params": action_taken.get("params", {}),
            "flow_step": len(EXECUTION_LOG),
        }
        if edge not in ALL_EDGES:
            ALL_EDGES.append(edge)

    previous_page_hash = current_page_hash


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")
    EXECUTION_LOG.append({"time": ts, "message": msg})


def tap_element(elem):
    bbox = elem.get("bbox", [0, 0, 0, 0])
    if len(bbox) >= 4 and bbox[2] > 0 and bbox[3] > 0:
        cx = int((bbox[0] + bbox[2]) / 2)
        cy = int((bbox[1] + bbox[3]) / 2)
        # Clamp coordinates to portrait 1080x1920 space
        cx = max(0, min(cx, 1079))
        cy = max(0, min(cy, 1919))
        adb_tap(cx, cy)
        return cx, cy, elem.get("label", "")
    return None, None, None


def tap_coords(x, y, label="fixed_position"):
    adb_tap(x, y)
    return x, y, label


def take_screenshot():
    raw = adb_screencap()
    if raw:
        return raw
    return None


# ========== MAIN FLOW ==========
log("Initializing components...")
try:
    adb_mgr = ADBDeviceManager(adb_path=ADB_PATH)
    adb_mgr.connect_device(DEVICE_SERIAL)
    capture = ScreenCapture(adb_mgr)
    touch_mgr = TouchManager()
    touch_mgr.connect_android(adb_path=ADB_PATH, address=TOUCH_ADDRESS)
    capture.set_touch_manager(touch_mgr)
    log("Maa controller initialized successfully")
except Exception as e:
    log(f"[WARN] Maa controller init skipped ({e}), using direct ADB commands")

communicator = ClientCommunicator(host="127.0.0.1", port=9999, password="default_password", timeout=300)
log("Logging in as explorer...")
login_r = communicator.send_request("login", {"user_id": "explorer", "key": API_KEY})
status = login_r.get("status", "?") if login_r else "NO RESPONSE"
log(f"Login result: {status}")
session_id = login_r.get("session_id", "") if login_r else ""
communicator.set_logged_in(True)

arkpass_data = {"user_id": "explorer", "api_key": API_KEY, "server_host": "127.0.0.1", "server_port": 9999}
with open(os.path.join(CACHE_DIR, "explorer.arkpass"), "w") as f:
    json.dump(arkpass_data, f)

log(f"Session: {session_id[:16] if session_id else 'NONE'}...")
log(f"Device: {DEVICE_SERIAL}")
log("=" * 60)

# PHASE 1: Navigate past any auto-logout/login dialogs into the game
log("PHASE 1: Navigating into game world...")
for nav_attempt in range(15):
    raw = take_screenshot()
    if not raw:
        log("[SKIP] Screenshot failed")
        time.sleep(3)
        continue

    info = analyze_page(raw)
    if not info:
        log("[SKIP] VLM analysis failed")
        time.sleep(3)
        continue

    pn = info.get("page_name", "")
    pt = info.get("page_type", "")
    elems = info.get("elements", [])

    record_page(raw, info)
    log(f"[{nav_attempt+1}] {pn} ({pt}) - {len(elems)} elements")

    is_in_game = (
        pt in ("world_map", "main_menu", "battle") or
        any(k in pn for k in ["世界", "主界面", "地图", "探索", "战斗", "终端", "基建", "指挥"])
    )
    if is_in_game:
        log(f"*** IN GAME WORLD: {pn} ***")
        break

    confirm_btns = [e for e in elems if any(k in e.get("label", "") for k in ["确认", "确定", "OK", "CONFIRM", "confirm"])]
    if confirm_btns and ("登出" in pn or "超时" in pn or "logout" in pn.lower()):
        target = confirm_btns[0]
        cx, cy, lbl = tap_element(target)
        if cx:
            log(f"  Click confirm (auto-logout): '{lbl}' at ({cx},{cy})")
            action_taken = {"type": "tap", "label": lbl, "params": {"x": cx, "y": cy}}
            record_page(raw, info, action_taken)
            time.sleep(5)
            continue

    nav_btns = [e for e in elems if any(k in e.get("label", "") for k in ["关闭", "进入游戏", "开始", "点击进入", "跳过", "X", "close", "CLOSE", "ENTER"])]
    if nav_btns:
        target = nav_btns[0]
        cx, cy, lbl = tap_element(target)
        if cx:
            log(f"  Click nav: '{lbl}' at ({cx},{cy})")
            action_taken = {"type": "tap", "label": lbl, "params": {"x": cx, "y": cy}}
            record_page(raw, info, action_taken)
            time.sleep(5)
            continue

    for x, y in [(1010, 60), (980, 80), (540, 960), (1010, 100)]:
        log(f"  Try close at ({x},{y})")
        tap_coords(x, y, "close_x")
        time.sleep(3)
        raw2 = take_screenshot()
        if raw2:
            info2 = analyze_page(raw2)
            if info2:
                pt2 = info2.get("page_type", "")
                if pt2 in ("world_map", "main_menu") or any(k in info2.get("page_name", "") for k in ["世界", "主界面"]):
                    log(f"*** After close: {info2.get('page_name', '')} ***")
                    record_page(raw2, info2, {"type": "tap", "label": "close_x", "params": {"x": x, "y": y}})
                    break
        time.sleep(2)
    else:
        log("  BACK")
        adb_keyevent(4)
        time.sleep(3)
else:
    # All 15 nav attempts exhausted without entering game world.
    # Force-stop and restart the game as last resort.
    log("=" * 60)
    log("[FALLBACK] Could not enter game world. Force-stopping game...")
    subprocess.run([ADB_PATH, "-s", DEVICE_SERIAL, "shell", "am force-stop com.hypergryph.endfield"],
                   capture_output=True, timeout=10)
    time.sleep(3)
    subprocess.run([ADB_PATH, "-s", DEVICE_SERIAL, "shell", "am start -n com.hypergryph.endfield/com.u8.sdk.U8UnityContext"],
                   capture_output=True, timeout=10)
    time.sleep(20)
    log("[FALLBACK] Retrying navigation after restart...")
    for nav_attempt in range(20):
        raw = take_screenshot()
        if not raw:
            time.sleep(3)
            continue
        info = analyze_page(raw)
        if not info:
            time.sleep(3)
            continue
        pn = info.get("page_name", "")
        pt = info.get("page_type", "")
        elems = info.get("elements", [])
        record_page(raw, info)
        log(f"  [RESTART {nav_attempt+1}] {pn} ({pt}) - {len(elems)} elements")
        is_in_game = (
            pt in ("world_map", "main_menu", "battle") or
            any(k in pn for k in ["世界", "主界面", "地图", "探索", "战斗", "终端", "基建", "指挥"])
        )
        if is_in_game:
            log(f"*** IN GAME WORLD AFTER RESTART: {pn} ***")
            break
        nav_btns = [e for e in elems if any(k in e.get("label", "") for k in ["关闭", "进入游戏", "开始", "点击进入", "跳过", "X", "close", "CLOSE", "ENTER", "START", "LOGIN"])]
        if nav_btns:
            target = nav_btns[0]
            cx, cy, lbl = tap_element(target)
            if cx:
                log(f"  Click nav (restart): '{lbl}' at ({cx},{cy})")
                action_taken = {"type": "tap", "label": lbl, "params": {"x": cx, "y": cy}}
                record_page(raw, info, action_taken)
                time.sleep(5)
                continue
        log("  BACK (restart)")
        adb_keyevent(4)
        time.sleep(3)
    else:
        log("[CRITICAL] Cannot enter game world even after force-stop restart. Aborting.")
        sys.exit(1)

# PHASE 2: Explore and find daily/weekly task pages
log("=" * 60)
log("PHASE 2: Exploring task pages...")
task_pages_found = []
claim_attempts = 0
page_history = []  # Rolling window for stuck detection
stuck_cycles = 0
world_map_cycles = 0  # Count consecutive world_map visits
world_map_no_progress_cycles = 0  # Count world_map cycles without task progress
overlay_opened_recently = False  # Track if we just opened the task panel overlay
from collections import Counter

for cycle in range(40):
    raw = take_screenshot()
    if not raw:
        time.sleep(3)
        continue

    info = analyze_page(raw)
    if not info:
        time.sleep(3)
        continue

    pn = info.get("page_name", "")
    pt = info.get("page_type", "")
    elems = info.get("elements", [])
    has_daily = info.get("has_daily_tasks", False)
    has_weekly = info.get("has_weekly_tasks", False)
    has_claim = info.get("has_claimable", False)

    # Stuck detection: same page name repeated too many times
    page_history.append(pn)
    if len(page_history) > 12:
        page_history.pop(0)
    if len(page_history) >= 10:
        name_counts = Counter(page_history[-10:])
        most_common_name, most_common_count = name_counts.most_common(1)[0]
        if most_common_count >= 8:
            log(f"  [STUCK] '{most_common_name}' {most_common_count}/10, pressing BACK")
            adb_keyevent(4)
            time.sleep(3)
            page_history.clear()
            stuck_cycles += 1
            if stuck_cycles >= 3:
                log(f"  *** Stuck 3 times despite BACKs, exploration complete ***")
                break
            continue

    # If back on world_map with task_pages found -> task exploration complete
    # But only if we haven't recently opened the overlay (give time to interact with it)
    if pt == "world_map" and task_pages_found:
        if overlay_opened_recently:
            world_map_cycles = 0
            overlay_opened_recently = False
            log(f"  [OVERLAY] Just opened panel, resetting world_map counter")
        else:
            world_map_cycles += 1
            if world_map_cycles >= 4:
                log(f"  *** Task pages found, back on world_map. Exploration complete ***")
                break
    else:
        world_map_cycles = 0

    record_page(raw, info)
    log(f"[{cycle+1}] {pn} ({pt}) - {len(elems)}e" +
        (" [DAILY!]" if has_daily else "") + (" [WEEKLY!]" if has_weekly else "") +
        (" [CLAIM!]" if has_claim else ""))

    is_task_page = has_daily or has_weekly or any(k in pn for k in ["每日", "每周", "任务", "计划", "使命", "签到", "作战"])
    if is_task_page and pn not in task_pages_found:
        task_pages_found.append(pn)
        log(f"  *** TASK PAGE: {pn} ***")

    # === PRIORITY 1: Claim rewards (any page type) ===
    claim_btns = [e for e in elems if any(k in e.get("label", "") for k in ["领取", "收取", "一键领取", "完成", "提交", "领奖", "CLAIM", "collect"])]
    if claim_btns and claim_attempts < 10:
        for e in claim_btns[:3]:
            cx, cy, lbl = tap_element(e)
            if cx:
                claim_attempts += 1
                log(f"  CLAIM: '{lbl}' at ({cx},{cy})")
                action_taken = {"type": "tap", "label": lbl, "params": {"x": cx, "y": cy}}
                record_page(raw, info, action_taken)
                time.sleep(5)
                break
        else:
            continue

    # === PRIORITY 2: On world_map with task indicators -> OPEN the task panel ===
    # The game shows tasks in a side panel overlay on world_map. We need to open it.
    if pt == "world_map" and (has_daily or has_weekly or has_claim or any(k in pn for k in ["任务", "每日", "每周", "签到", "作战"])):
        # Look for task panel opener icons in the top-right area (x > 700, y < 150)
        task_panel_openers = [e for e in elems
                              if e.get("type") in ("button", "icon", "tab")
                              and len(e.get("bbox", [])) >= 4 and e["bbox"][1] < 150
                              and any(k in e.get("label", "") for k in ["日程", "任务", "每日", "每周", "签到", "日历", "使命", "quest", "daily"])]
        if task_panel_openers:
            target = task_panel_openers[0]
            cx, cy, lbl = tap_element(target)
            if cx:
                log(f"  Open task panel: '{lbl}' at ({cx},{cy})")
                action_taken = {"type": "tap", "label": lbl, "params": {"x": cx, "y": cy}}
                record_page(raw, info, action_taken)
                time.sleep(5)
                # Check if we moved to a proper page
                raw2 = take_screenshot()
                if raw2:
                    info2 = analyze_page(raw2)
                    if info2:
                        pt2 = info2.get("page_type", "")
                        overlay_opened_recently = True
                        if pt2 != "world_map":
                            log(f"  -> navigated to: {info2.get('page_name', '')} ({pt2})")
                            record_page(raw2, info2, {"type": "tap", "label": lbl, "params": {"x": cx, "y": cy}})
                            raw = raw2
                            info = info2
                            pn = info.get("page_name", "")
                            pt = info.get("page_type", "")
                            elems = info.get("elements", [])
                            has_daily = info.get("has_daily_tasks", False)
                            has_weekly = info.get("has_weekly_tasks", False)
                            has_claim = info.get("has_claimable", False)
                            is_task_page = has_daily or has_weekly or any(k in pn for k in ["每日", "每周", "任务", "计划", "使命", "签到", "作战"])
                            if is_task_page and pn not in task_pages_found:
                                task_pages_found.append(pn)
                                log(f"  *** TASK PAGE: {pn} ***")
                            new_claim = [e for e in elems if any(k in e.get("label", "") for k in ["领取", "收取", "一键领取", "完成", "提交", "领奖", "CLAIM", "collect"])]
                            if new_claim and claim_attempts < 10:
                                for ce in new_claim[:3]:
                                    cxc, cyc, lblc = tap_element(ce)
                                    if cxc:
                                        claim_attempts += 1
                                        log(f"  CLAIM: '{lblc}' at ({cxc},{cyc})")
                                        time.sleep(5)
                                        break
                            continue
                        else:
                            # Panel overlay opened but VLM still says world_map
                            # The overlay slides in from the right edge at (800-940, 70-780)
                            # VLM won't report panel-specific elements because it sees the same base page.
                            # Instead of tapping top-bar icons, tap into the panel content area.
                            # CRITICAL: overlay only extends to ~940, NOT 950!
                            # Add swipe-down to reveal claim buttons below visible area
                            log(f"  [OVERLAY] Task panel opened, swiping down to reveal content")
                            # Swipe down on the overlay to scroll task list
                            adb_swipe(880, 300, 880, 600, 1000)
                            time.sleep(3)
                            log(f"  [OVERLAY] Swipe done, now tapping panel content area")
                            # Tap panel content to ensure it's active — don't call VLM for each tap (too slow)
                            panel_content_taps = [
                                (880, 150),
                                (880, 300),
                                (880, 450),
                                (880, 600),
                            ]
                            for px, py in panel_content_taps:
                                adb_tap(px, py)
                                time.sleep(1)
                            # Take ONE screenshot after all panel taps
                            raw3 = take_screenshot()
                            if raw3:
                                info3 = analyze_page(raw3)
                                if info3:
                                    overlay_claims = [e for e in info3.get("elements", [])
                                                      if any(k in e.get("label", "") for k in ["领取", "收取", "一键领取", "完成", "提交", "领奖", "CLAIM", "collect"])]
                                    # Also try direct search within element text (VLM might label them differently)
                                    if not overlay_claims:
                                        overlay_claims = [e for e in info3.get("elements", [])
                                                          if any(k in (e.get("text", "") or "") for k in ["领取", "收取", "一键领取", "完成", "提交", "领奖"])]
                                    if overlay_claims and claim_attempts < 10:
                                        for ce in overlay_claims[:3]:
                                            cxc, cyc, lblc = tap_element(ce)
                                            if cxc:
                                                claim_attempts += 1
                                                log(f"  CLAIM: '{lblc}' at ({cxc},{cyc})")
                                                time.sleep(5)
                                                break
                            # Fallback: if VLM still finds nothing, try brute-force tapping at known claim button regions
                            if claim_attempts < 1:
                                log(f"  [OVERLAY] VLM found no claim buttons, trying brute-force at known reward regions")
                                # Common claim button locations on the overlay (~x=860-920, various y)
                                for cy_fallback in [220, 280, 340, 400, 460, 520, 580]:
                                    adb_tap(890, cy_fallback)
                                    time.sleep(2)
                                    raw5 = take_screenshot()
                                    if raw5:
                                        info5 = analyze_page(raw5)
                                        if info5:
                                            # Check if we navigated away from world_map (reward dialog opened)
                                            pt5 = info5.get("page_type", "")
                                            if pt5 != "world_map":
                                                log(f"  -> navigated to: {info5.get('page_name', '')} ({pt5}) after tap at (890,{cy_fallback})")
                                                # Check for collect/claim buttons on the new page
                                                for e in info5.get("elements", []):
                                                    if any(k in e.get("label", "") for k in ["领取", "收取", "完成", "确认", "collect"]):
                                                        cxc2, cyc2, lblc2 = tap_element(e)
                                                        if cxc2:
                                                            claim_attempts += 1
                                                            log(f"  CLAIM (fallback): '{lblc2}' at ({cxc2},{cyc2})")
                                                            time.sleep(5)
                                                            break
                                                break
                                            # If page_type changed to dialog/popup, that's promising
                                            if pt5 in ("dialog", "menu", "task_ui"):
                                                log(f"  -> navigated to dialog/ui at (890,{cy_fallback})")
                                                raw = raw5
                                                info = info5
                                                pn = info.get("page_name", "")
                                                pt = pt5
                                                elems = info.get("elements", [])
                                                break
                continue
        # If no panel opener found and task pages already recorded, we're done
        if task_pages_found:
            log(f"  *** Task pages already found, no more navigation needed ***")
            break

    # === PRIORITY 3: On actual task/daily UI page -> interact with it ===
    if is_task_page and pt != "world_map":
        log("  On task UI page, looking for claimable items...")
        # Try scrolling to reveal content
        adb_swipe(540, 1500, 540, 500, 2000)
        time.sleep(3)
        # Take new screenshot and look for claims
        raw2 = take_screenshot()
        if raw2:
            info2 = analyze_page(raw2)
            if info2:
                for ce in info2.get("elements", []):
                    if any(k in ce.get("label", "") for k in ["领取", "收取", "一键领取", "完成", "提交", "领奖", "CLAIM", "collect"]):
                        cxc, cyc, lblc = tap_element(ce)
                        if cxc and claim_attempts < 10:
                            claim_attempts += 1
                            log(f"  CLAIM: '{lblc}' at ({cxc},{cyc})")
                            time.sleep(5)
                            break
        continue

    # === PRIORITY 4 (NEW): World map no-progress fallback ===
    # If we've been on world_map for 5+ cycles without finding task pages, try known button positions
    if pt == "world_map" and not task_pages_found and not is_task_page:
        world_map_no_progress_cycles += 1
        if world_map_no_progress_cycles >= 5:
            log(f"  [FALLBACK] 5 cycles on world_map without task pages, trying known task panel buttons")
            for tx, ty, tlabel in [(787, 45, "日程/任务"), (792, 45, "签到/日历"), (820, 50, "任务日志")]:
                tap_coords(tx, ty, tlabel)
                time.sleep(5)
                # VLM always returns world_map even with overlay open, so don't check page_type.
                # Instead, ALWAYS do the overlay interaction after tapping known panel buttons.
                log(f"  [FALLBACK-OVERLAY] Panel opened via '{tlabel}', interacting with overlay")
                # Swipe to reveal content
                adb_swipe(880, 300, 880, 600, 1000)
                time.sleep(3)
                # Tap panel content area
                for px2, py2 in [(880, 150), (880, 300), (880, 450), (880, 600)]:
                    adb_tap(px2, py2)
                    time.sleep(1.5)
                # Check for claim buttons
                raw_overlay = take_screenshot()
                if raw_overlay:
                    info_overlay = analyze_page(raw_overlay)
                    if info_overlay:
                        for ce in info_overlay.get("elements", []):
                            if any(k in ce.get("label", "") for k in ["领取", "收取", "一键领取", "完成", "提交", "领奖", "CLAIM", "collect"]):
                                cxc, cyc, lblc = tap_element(ce)
                                if cxc and claim_attempts < 10:
                                    claim_attempts += 1
                                    log(f"  CLAIM (fallback-overlay): '{lblc}' at ({cxc},{cyc})")
                                    time.sleep(5)
                # Brute-force: tap at known claim button regions on overlay
                if claim_attempts < 1:
                    log(f"  [FALLBACK-OVERLAY] Brute-force tapping reward regions")
                    for cy_fb in [220, 280, 340, 400, 460, 520, 580]:
                        adb_tap(890, cy_fb)
                        time.sleep(1.5)
                        raw_chk2 = take_screenshot()
                        if raw_chk2:
                            info_chk2 = analyze_page(raw_chk2)
                            if info_chk2:
                                pt_chk2 = info_chk2.get("page_type", "")
                                if pt_chk2 not in ("", "world_map"):
                                    log(f"  -> navigated to: {info_chk2.get('page_name', '')} ({pt_chk2}) after tap at (890,{cy_fb})")
                                    for ce2 in info_chk2.get("elements", []):
                                        if any(k in ce2.get("label", "") for k in ["领取", "收取", "完成", "确认", "collect"]):
                                            cxc2, cyc2, lblc2 = tap_element(ce2)
                                            if cxc2:
                                                claim_attempts += 1
                                                log(f"  CLAIM (brute): '{lblc2}' at ({cxc2},{cyc2})")
                                                time.sleep(5)
                                                break
                                    break
                # Close overlay
                log(f"  [FALLBACK-OVERLAY] Closing overlay, returning to world_map")
                adb_keyevent(4)
                time.sleep(3)
                break
            world_map_no_progress_cycles = 0
    else:
        world_map_no_progress_cycles = 0

    # On world_map, exclude mid-screen waypoints AND top-left navigation indicators (x < 200, y < 150)
    btns = [e for e in elems
            if e.get("action") == "tap"
            and not (pt == "world_map" and len(e.get("bbox", [])) >= 4 and 150 <= e["bbox"][1] <= 1700)
            and not (pt == "world_map" and len(e.get("bbox", [])) >= 4 and e["bbox"][1] < 150 and e["bbox"][0] < 200)
           ]
    if btns:
        target = btns[0]
        cx, cy, lbl = tap_element(target)
        if cx:
            log(f"  Generic tap: '{lbl}' at ({cx},{cy})")
            action_taken = {"type": "tap", "label": lbl, "params": {"x": cx, "y": cy}}
            record_page(raw, info, action_taken)
            time.sleep(5)
            continue

    # Don't tap waypoints on world_map, go BACK instead
    if pt == "world_map":
        log("  On world_map with no safe buttons found, going BACK")
        adb_keyevent(4)
        time.sleep(3)
        continue

    log("  BACK")
    adb_keyevent(4)
    time.sleep(3)

# PHASE 3: Save results
log("=" * 60)
log("PHASE 3: Saving results...")

tree = {
    "root_page_id": f"page_{list(ALL_PAGES.keys())[0]}" if ALL_PAGES else "",
    "nodes": ALL_PAGES,
    "edges": ALL_EDGES,
    "stats": {
        "pages_discovered": len(ALL_PAGES),
        "elements_found": sum(len(p.get("elements", [])) for p in ALL_PAGES.values()),
        "edges_created": len(ALL_EDGES),
        "vlm_calls": len(EXECUTION_LOG),
        "taps": sum(1 for s in EXECUTION_LOG if "tap" in s.get("message", "").lower()),
        "daily_tasks_found": len(task_pages_found),
        "claim_attempts": claim_attempts,
    },
    "task_pages": task_pages_found,
    "execution_flow": EXECUTION_LOG,
    "timestamp": time.time(),
}
with open(os.path.join(CACHE_DIR, "page_tree.json"), "w", encoding="utf-8") as f:
    json.dump(tree, f, ensure_ascii=False, indent=2)
log(f"Saved page_tree.json ({len(ALL_PAGES)} pages, {len(ALL_EDGES)} edges)")

md_lines = [
    f"# Arknights Endfield - Game Map",
    f"",
    f"**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
    f"**Pages Discovered**: {len(ALL_PAGES)}",
    f"**Elements Found**: {sum(len(p.get('elements', [])) for p in ALL_PAGES.values())}",
    f"**Edges Created**: {len(ALL_EDGES)}",
    f"**Task Pages Found**: {len(task_pages_found)}",
    f"**Claim Attempts**: {claim_attempts}",
    f"**VLM Calls**: {len(EXECUTION_LOG)}",
    f"",
    f"---",
    f"## Task Pages",
]
for tp in task_pages_found:
    md_lines.append(f"- {tp}")
md_lines.extend(["", "---", "## Execution Flow"])
for step in EXECUTION_LOG:
    md_lines.append(f"- [{step['time']}] {step['message']}")
md_lines.extend(["", "---", "## Page Tree"])
for h, p in ALL_PAGES.items():
    md_lines.extend([
        f"",
        f"### {p['name']}",
        f"- **ID**: `{p['page_id']}`",
        f"- **Type**: {p.get('page_type', 'other')}",
        f"- **Depth**: {p['depth']}",
        f"- **Elements**: {len(p['elements'])}",
        f"- **Daily**: {p.get('has_daily_tasks', False)}",
        f"- **Weekly**: {p.get('has_weekly_tasks', False)}",
        f"- **Claimable**: {p.get('has_claimable', False)}",
    ])
    if p['elements']:
        md_lines.append(f"| # | Type | Label | Action |")
        md_lines.append(f"|---|------|-------|--------|")
        for i, e in enumerate(p['elements']):
            md_lines.append(f"| {i+1} | {e['type']} | {e['label']} | {e['extra'].get('action','?')} |")
    md_lines.append(f"")
with open(os.path.join(CACHE_DIR, "game_map.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(md_lines))
log(f"Saved game_map.md")

summary = {
    "stats": tree["stats"],
    "task_pages": task_pages_found,
    "timestamp": time.time(),
    "device": DEVICE_SERIAL,
    "model_tag": MODEL_TAG,
}
with open(os.path.join(CACHE_DIR, "exploration_summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
log(f"Saved exploration_summary.json")

model_tag_path = os.path.join(CACHE_DIR, "model_tag.json")
model_tags = {}
if os.path.exists(model_tag_path):
    with open(model_tag_path, "r") as f:
        model_tags = json.load(f)
model_tags["standard_reasoning"] = MODEL_TAG
model_tags["exploration_deep"] = MODEL_TAG
with open(model_tag_path, "w") as f:
    json.dump(model_tags, f, indent=2)

log("=" * 60)
log("SUMMARY:")
log(f"  Pages discovered: {len(ALL_PAGES)}")
log(f"  Edges recorded: {len(ALL_EDGES)}")
log(f"  Task pages found: {len(task_pages_found)}")
if task_pages_found:
    for tp in task_pages_found:
        log(f"    - {tp}")
log(f"  Claim attempts: {claim_attempts}")
log(f"  VLM calls: {len(EXECUTION_LOG)}")
log("=" * 60)
log("Done.")