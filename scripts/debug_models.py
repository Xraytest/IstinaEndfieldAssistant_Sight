#!/usr/bin/env python3
"""检查可用模型并测试不同标签"""
import sys, os, json, base64, subprocess
from pathlib import Path

os.environ["LOG_QUIET"] = "1"
import logging
logging.disable(logging.CRITICAL)

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

from core.service.cloud.communication.communicator import ClientCommunicator

comm = ClientCommunicator(host="127.0.0.1", port=9999, password="default_password", timeout=30)
r = comm.send_request("login", {"user_id": "explorer", "key": "aa7d3551ab7fdb975c2eed5251df53ade38aa12cd6161475221d774f27026763"})
sid = r.get("session_id", "") if r else ""
comm.set_logged_in(True)

# 1. 获取可用模型
print("=== 获取可用模型 ===")
resp = comm.send_request("get_available_models", {})
print(json.dumps(resp, ensure_ascii=False, indent=2)[:2000] if resp else "None")

# 2. 测试不同模型标签
ADB = [str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"), "-s", "localhost:16512"]
raw = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True, timeout=15).stdout
b64 = base64.b64encode(raw).decode("utf-8")

for tag in ["exploration_deep", "vision", "standard"]:
    print(f"\n=== 测试模型标签: {tag} ===")
    resp = comm.send_request("agent_chat", {
        "instruction": "用一句话描述这个画面",
        "screenshot": b64,
        "history": [],
        "session_id": sid,
        "user_id": "explorer",
        "model_tag": tag,
        "system_prompt": ""
    })
    if resp:
        reply = resp.get("reply", "")
        print(f"  状态: {resp.get('status')}")
        print(f"  回复长度: {len(reply)}")
        print(f"  回复: {reply[:300]}")
    else:
        print(f"  无响应")