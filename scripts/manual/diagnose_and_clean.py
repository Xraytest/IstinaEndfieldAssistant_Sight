#!/usr/bin/env python3
"""Diagnose current game state and fix popup overlays for cloud version."""

import os, sys, json, time, subprocess
from pathlib import Path
import cv2

_bin = Path(__file__).resolve().parent.parent / "3rd-part" / "python" / "Lib" / "site-packages" / "maa" / "bin"
os.environ["MAAFW_BINARY_PATH"] = str(_bin)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

root = Path(__file__).resolve().parent.parent
adb = root / "3rd-part" / "adb" / "adb.exe"
serial = "127.0.0.1:16416"

from maa.resource import Resource
from maa.controller import AdbController
from maa.define import MaaAdbScreencapMethodEnum, MaaAdbInputMethodEnum
from maa.tasker import Tasker
from maa.pipeline import JOCR, JRecognitionType, JClick

# Connect
resource = Resource()
ctrl = AdbController(
    adb_path=adb, address=serial,
    screencap_methods=int(MaaAdbScreencapMethodEnum.Default),
    input_methods=int(MaaAdbInputMethodEnum.Default), config={})
ctrl.post_connection().wait()

resource.post_bundle(root/"3rd-part"/"maaend"/"resource").wait()
resource.post_ocr_model(root/"3rd-part"/"maaend"/"resource"/"model"/"ocr")
time.sleep(1)

tasker = Tasker()
tasker.bind(resource, ctrl)

debug_dir = root / "config" / "debug" / "screens"
debug_dir.mkdir(parents=True, exist_ok=True)

def ocr_screen(tasker_obj, ctrl_obj):
    sc = ctrl_obj.post_screencap()
    sc.wait()
    img = ctrl_obj.cached_image
    ocr_param = JOCR(expected=[], roi=[0, 0, img.shape[1], img.shape[0]], threshold=0.2)
    job = tasker_obj.post_recognition(JRecognitionType.OCR, ocr_param, img)
    detail = job.wait().get()
    texts = []
    if detail:
        for n in detail.nodes:
            if n.recognition:
                for r in n.recognition.all_results:
                    if hasattr(r, 'text'):
                        texts.append({"text": r.text, "score": float(r.score), "box": list(r.box)})
    return texts, img

def click_at(ctrl_obj, x, y, label=""):
    print(f"  Click ({x},{y}) {label}")
    click_job = ctrl_obj.post_click(x, y)
    click_job.wait()
    time.sleep(1.5)

def adb_shell(cmd):
    subprocess.run([str(adb), "-s", serial, "shell", cmd], timeout=10, capture_output=True)

# ============================================
# Step 1: Clear any popups with BACK spam + click dismiss
# ============================================
print("=== Step 1: Clear popup overlays ===")
for _ in range(5):
    adb_shell("input keyevent 4")
    time.sleep(0.3)

# Step 2: OCR + close known popups in a loop until clean
for attempt in range(5):
    texts, img = ocr_screen(tasker, ctrl)
    print(f"\nAttempt {attempt + 1}: {len(texts)} text blocks")

    found_popup = False
    for t in texts:
        # Cloud idle disconnect
        if "知道" in t["text"] and t["score"] > 0.8:
            cx = t["box"][0] + t["box"][2] // 2
            cy = t["box"][1] + t["box"][3] // 2
            click_at(ctrl, cx, cy, f"dismiss: {t['text']}")
            found_popup = True
            break

    if found_popup:
        continue

    # Check for other common dialogs
    keywords_to_dismiss = {
        "退出": "back",
        "确认": "back",
        "取消": "tap_center",
        "登录失败": "back",
    }
    for t in texts:
        for kw, action in keywords_to_dismiss.items():
            if kw in t["text"]:
                print(f"  Dialog detected: '{t['text']}' -> {action}")
                if action == "back":
                    adb_shell("input keyevent 4")
                else:
                    cx = t["box"][0] + t["box"][2] // 2
                    cy = t["box"][1] + t["box"][3] // 2
                    click_at(ctrl, cx, cy)
                found_popup = True
                break
        if found_popup:
            break

    if not found_popup:
        print("  No more popups detected")
        break

# Step 3: Final state capture
texts, img = ocr_screen(tasker, ctrl)
cv2.imwrite(str(debug_dir / "state_clean.png"), img)
with open(str(debug_dir / "ocr_clean.json"), "w", encoding="utf-8") as f:
    json.dump(texts, f, ensure_ascii=False, indent=2)

print(f"\n=== Final state: {len(texts)} text blocks ===")
for t in texts:
    print(f'  [{t["box"][0]:4d},{t["box"][1]:4d}] {t["score"]:.3f} "{t["text"]}"')

# Check: is this the main world or a menu?
world_keywords = ["地图", "好友", "背包", "任务", "菜单", "设置", "探索", "小组"]
menu_keywords = ["开始游戏", "进入游戏", "点击开始", "登录", "账号"]
in_world = any(any(kw in t["text"] for kw in world_keywords) for t in texts)
at_menu = any(any(kw in t["text"] for kw in menu_keywords) for t in texts)
print(f"\nIn world: {in_world}")
print(f"At menu: {at_menu}")

print(f"\nDone. Screenshots saved to {debug_dir}")
