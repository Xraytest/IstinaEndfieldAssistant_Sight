"""VLM analysis helper - takes screenshot, sends to VLM, outputs analysis JSON to stdout"""
import sys, os, json, base64, hashlib, re, subprocess

project_root = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
from core.logger import init_logger
init_logger()
from core.communication.communicator import ClientCommunicator

ADB = os.path.join(project_root, "3rd-part", "adb", "adb.exe")
SERIAL = "localhost:16512"
LAYOUTS = os.path.join(project_root, "page_layouts")

result = subprocess.run([ADB, "-s", SERIAL, "exec-out", "screencap", "-p"], capture_output=True, timeout=15)
if result.returncode != 0 or len(result.stdout) <= 1000:
    print(json.dumps({"error": "screenshot failed", "returncode": result.returncode, "stdout_len": len(result.stdout)}))
    sys.exit(1)

raw = result.stdout
h = hashlib.sha256(raw).hexdigest()[:16]

with open(os.path.join(LAYOUTS, "screenshots", f"page_{h}.png"), "wb") as f:
    f.write(raw)

b64 = base64.b64encode(raw).decode("utf-8")
comm = ClientCommunicator(host="127.0.0.1", port=9999, password="default_password", timeout=300)
r = comm.send_request("login", {"user_id": "explorer", "key": "aa7d3551ab7fdb975c2eed5251df53ade38aa12cd6161475221d774f27026763"})
session_id = r.get("session_id", "") if r else ""
comm.set_logged_in(True)

SYSTEM_PROMPT = """你是《明日方舟：终末地》游戏界面分析器。识别当前画面并输出JSON：
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
特别注意：每日任务、每周任务、作战汇报、签到、奖励领取等按钮。"""

payload = {
    "instruction": "分析当前游戏画面，识别所有可交互UI元素。特别注意任务、奖励、签到相关按钮。",
    "screenshot": b64, "history": [], "session_id": session_id,
    "user_id": "explorer", "model_tag": "vision",
    "system_prompt": SYSTEM_PROMPT,
}
resp = comm.send_request("agent_chat", payload)

output = {"page_hash": h, "screenshot_path": f"screenshots/page_{h}.png"}
if resp and resp.get("status") == "success":
    reply = resp.get("reply", "")
    output["reply_length"] = len(reply)
    m = re.search(r'\{[\s\S]*\}', reply)
    if m:
        try:
            parsed = json.loads(m.group())
            output["analysis"] = parsed
            # Save page JSON
            page_data = {
                "page_id": f"page_{h}",
                "name": parsed.get("page_name","Unknown"),
                "screenshot_hash": h,
                "page_type": parsed.get("page_type","other"),
                "has_daily_tasks": parsed.get("has_daily_tasks", False),
                "has_weekly_tasks": parsed.get("has_weekly_tasks", False),
                "has_claimable": parsed.get("has_claimable", False),
                "elements": parsed.get("elements", []),
                "menu_buttons": parsed.get("menu_buttons", []),
                "navigation_path": parsed.get("navigation_path", []),
                "description": parsed.get("description", ""),
            }
            with open(os.path.join(LAYOUTS, "pages", f"page_{h}.json"), "w", encoding="utf-8") as f:
                json.dump(page_data, f, ensure_ascii=False, indent=2)
            output["page_saved"] = f"pages/page_{h}.json"
        except json.JSONDecodeError as e:
            output["json_error"] = str(e)
            output["raw_reply"] = reply[:500]
    else:
        output["raw_reply"] = reply[:500]
else:
    output["vlm_error"] = str(resp)

print(json.dumps(output, ensure_ascii=False))