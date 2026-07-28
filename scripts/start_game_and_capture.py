#!/usr/bin/env python3
"""Start game, reach in-world, capture screens of all needed UI states."""

import os, sys, json, time, subprocess
from pathlib import Path
import cv2

_bin = Path(__file__).resolve().parent.parent / "3rd-part" / "python" / "Lib" / "site-packages" / "maa" / "bin"
os.environ["MAAFW_BINARY_PATH"] = str(_bin)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

root = Path(__file__).resolve().parent.parent
adb = root / "3rd-part" / "adb" / "adb.exe"
serial = "127.0.0.1:16416"
debug_dir = root / "config" / "debug" / "screens"
debug_dir.mkdir(parents=True, exist_ok=True)

from maa.resource import Resource
from maa.controller import AdbController
from maa.define import MaaAdbScreencapMethodEnum, MaaAdbInputMethodEnum
from maa.tasker import Tasker
from maa.pipeline import JOCR, JRecognitionType

def adb_shell(cmd):
    r = subprocess.run([str(adb), "-s", serial, "shell", cmd], timeout=15, capture_output=True, text=True)
    return r.stdout.strip()

def screenshot(tasker_obj, ctrl_obj, label):
    sc = ctrl_obj.post_screencap()
    sc.wait()
    img = ctrl_obj.cached_image
    cv2.imwrite(str(debug_dir / f"{label}.png"), img)
    # OCR
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
    with open(str(debug_dir / f"{label}.json"), "w", encoding="utf-8") as f:
        json.dump(texts, f, ensure_ascii=False, indent=2)
    return texts, img

def click(x, y, ctrl_obj, label=""):
    print(f"  Click ({x},{y}) {label}")
    ctrl_obj.post_click(x, y).wait()
    time.sleep(2)

# Step 1: Connect and dismiss popups
print("=== Initial connect ===")
resource = Resource()
ctrl = AdbController(adb_path=adb, address=serial,
    screencap_methods=int(MaaAdbScreencapMethodEnum.Default),
    input_methods=int(MaaAdbInputMethodEnum.Default), config={})
ctrl.post_connection().wait()

resource.post_bundle(root/"3rd-part"/"maaend"/"resource").wait()
resource.post_ocr_model(root/"3rd-part"/"maaend"/"resource"/"model"/"ocr")
time.sleep(1)

tasker = Tasker()
tasker.bind(resource, ctrl)

# Clear popups
print("\n=== Clear popups ===")
for _ in range(5):
    adb_shell("input keyevent 4")
    time.sleep(0.2)

for attempt in range(5):
    texts, img = screenshot(tasker, ctrl, f"cleanup_{attempt}")
    found = False
    for t in texts:
        if "知道" in t["text"]:
            cx = t["box"][0] + t["box"][2] // 2
            cy = t["box"][1] + t["box"][3] // 2
            click(cx, cy, ctrl, f"dismiss: {t['text']}")
            found = True
            break
    if not found:
        print("  No popups")
        break

# Step 2: Current state
texts, img = screenshot(tasker, ctrl, "state_launch")
print(f"\n=== Launch screen: {len(texts)} blocks ===")
for t in texts:
    print(f'  [{t["box"][0]:4d},{t["box"][1]:4d},{t["box"][2]:4d}x{t["box"][3]:4d}] {t["score"]:.3f} "{t["text"]}"')

# Step 3: Click "开始游戏" to enter game
start_game_btn = None
for t in texts:
    if "开始" in t["text"] and t["score"] > 0.8:
        cx = t["box"][0] + t["box"][2] // 2
        cy = t["box"][1] + t["box"][3] // 2
        start_game_btn = (cx, cy, t)
        break

if start_game_btn:
    cx, cy, t = start_game_btn
    print(f"\n=== Clicking '开始游戏' at ({cx},{cy}) ===")
    click(cx, cy, ctrl, "start game")
    time.sleep(5)

# Step 4: Wait for game to load (watch for "enter world")
print("\n=== Wait for game to load (40s) ===")
for i in range(20):
    time.sleep(2)
    texts, img = screenshot(tasker, ctrl, f"loading_{i}")
    # Check for in-world indicators
    world_kw = ["地图", "好友", "设置", "任务", "UID"]
    menu_kw = ["开始游戏", "进入游戏"]
    for t in texts:
        for kw in world_kw:
            if kw in t["text"]:
                print(f"  In-world detected at ~{i*2+5}s: '{t['text']}'")
                screenshot(tasker, ctrl, "in_world")
                print(f"\n=== IN-WORLD SCREEN ===")
                for tt in texts:
                    print(f'  [{tt["box"][0]:4d},{tt["box"][1]:4d}] {tt["score"]:.3f} "{tt["text"]}"')
                sys.exit(0)
    if i == 0:
        # After first wait, check what we see
        for t in texts:
            print(f'  Loading: [{t["box"][0]:4d},{t["box"][1]:4d}] {t["score"]:.3f} "{t["text"]}"')

# Step 5: Final state after timeout
texts, img = screenshot(tasker, ctrl, "after_load")
print(f"\n=== After load timeout: {len(texts)} blocks ===")
for t in texts:
    print(f'  [{t["box"][0]:4d},{t["box"][1]:4d}] {t["score"]:.3f} "{t["text"]}"')

print(f"\nAll screenshots saved to {debug_dir}")
