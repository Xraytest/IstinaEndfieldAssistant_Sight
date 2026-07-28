#!/usr/bin/env python3
"""全屏诊断：抓图、OCR 全量识别、Scene 节点测试、空闲断连弹窗检测。"""
import os, sys, json, time
from pathlib import Path

_bin = Path(__file__).resolve().parent.parent / "3rd-part" / "python" / "Lib" / "site-packages" / "maa" / "bin"
os.environ["MAAFW_BINARY_PATH"] = str(_bin)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from maa.resource import Resource
from maa.controller import AdbController
from maa.tasker import Tasker
from maa.define import MaaAdbScreencapMethodEnum, MaaAdbInputMethodEnum
from maa.pipeline import JOCR, JRecognitionType

root = Path(__file__).resolve().parent.parent
out_dir = root / "config" / "debug" / "diagnose"
out_dir.mkdir(parents=True, exist_ok=True)

# Connect
resource = Resource()
ctrl = AdbController(adb_path=root/"3rd-part"/"adb"/"adb.exe", address="127.0.0.1:16416",
    screencap_methods=int(MaaAdbScreencapMethodEnum.Default),
    input_methods=int(MaaAdbInputMethodEnum.Default), config={})
ctrl.post_connection().wait()
print(f"Connected: {ctrl.connected}")

resource.post_bundle(root/"3rd-part"/"maaend"/"resource").wait()
ocr_job = resource.post_ocr_model(root/"3rd-part"/"maaend"/"resource"/"model"/"ocr")
time.sleep(2)

tasker = Tasker()
tasker.bind(resource, ctrl)

# Take screenshot
sc = ctrl.post_screencap()
sc.wait()
img = ctrl.cached_image
print(f"Screenshot: {img.shape}")

import cv2
cv2.imwrite(str(out_dir / "full_screen.png"), img)
print(f"Saved: {out_dir / 'full_screen.png'}")

# 1. Full-screen OCR (detect ALL text)
print("\n=== 1. Full-screen OCR ===")
ocr_param = JOCR(expected=[], roi=[0, 0, img.shape[1], img.shape[0]], threshold=0.1)
job = tasker.post_recognition(JRecognitionType.OCR, ocr_param, img)
detail = job.wait().get()
all_texts = []
if detail:
    for n in detail.nodes:
        if n.recognition:
            for r in n.recognition.all_results:
                all_texts.append({"text": r.text, "score": float(r.score), "box": list(r.box)})
all_texts.sort(key=lambda x: (x["box"][1], x["box"][0]))
print(f"Found {len(all_texts)} text blocks:")
with open(out_dir / "ocr_results.json", "w", encoding="utf-8") as f:
    json.dump(all_texts, f, ensure_ascii=False, indent=2)
for t in all_texts:
    print(f'  [{t["box"][0]:4d},{t["box"][1]:4d},{t["box"][2]:4d}x{t["box"][3]:4d}] score={t["score"]:.3f} "{t["text"]}"')

# 2. Check for common cloud game disconnect dialogs
print("\n=== 2. Idle disconnect detection ===")
disconnect_keywords = ["长时间未操作", "自动结束", "已断开", "重新连接", "返回", "退出游戏",
                       "重新开始", "连接已断开", "网络异常", "重试", "重连", "连接失败",
                       "timeout", "disconnected", "reconnect", "IDLE", "KICK"]
for t in all_texts:
    for kw in disconnect_keywords:
        if kw.lower() in t["text"].lower():
            print(f'  DISCONNECT DETECTED: keyword="{kw}" text="{t["text"]}" box={t["box"]}')

# 3. Test key scene nodes
print("\n=== 3. Scene node detection ===")
scene_nodes = [
    "InWorld", "InWorldFactory", "InWorldOcrText",
    "SceneAnyEnterWorld", "SceneAnyEnterWorldSuccess",
    "SceneMenu", "SceneLogin", "EnterGame",
    "__ScenePrivateAnyEnterWorldSuccess",
]
for node_name in scene_nodes:
    node_data = resource.get_node_data(node_name)
    if node_data:
        # Run the node
        override = {node_name: node_data}
        try:
            j = tasker.post_task(node_name, override if override else {})
            j.wait()
            d = j.get()
            hit = False
            if d and d.nodes:
                for n in d.nodes:
                    if n.recognition and n.recognition.hit:
                        hit = True
            print(f'  {node_name:40s}: hit={hit}')
        except Exception as e:
            print(f'  {node_name:40s}: ERROR {e}')
    else:
        print(f'  {node_name:40s}: NOT FOUND')

# 4. Test LoginFailed (OCR dialog detector)
print("\n=== 4. LoginFailed detection ===")
try:
    j = tasker.post_task("LoginFailed", {})
    import threading
    box = {"done": False, "detail": None}
    def w():
        j.wait()
        box["detail"] = j.get()
        box["done"] = True
    t = threading.Thread(target=w, daemon=True)
    t.start()
    t.join(timeout=15)
    if box["done"]:
        d = box["detail"]
        print(f"  succeeded: {j.succeeded}")
        if d and d.nodes:
            for n in d.nodes:
                if n.recognition:
                    print(f'  hit={n.recognition.hit} results={len(n.recognition.all_results)}')
                    for r in n.recognition.all_results:
                        print(f'    "{r.text}" score={r.score:.3f}')
            if j.succeeded:
                print(f"  ** LoginFailed triggered - game probably NOT in main world **")
except Exception as e:
    print(f"  Error: {e}")

# 5. Try OpenGame nodes
print("\n=== 5. OpenGame flow nodes ===")
for node_name in ["ClickContinue", "CheckIn", "MonthlyCard", "CloseButton"]:
    nd = resource.get_node_data(node_name)
    if nd:
        try:
            j = tasker.post_task(node_name, {node_name: nd})
            j.wait()
            d = j.get()
            if d and d.nodes:
                hit = any(n.recognition and n.recognition.hit for n in d.nodes if n.recognition)
                print(f'  {node_name:30s}: hit={hit}')
            else:
                print(f'  {node_name:30s}: no nodes')
        except Exception as e:
            print(f'  {node_name:30s}: ERROR {e}')

print(f"\n=== Done. All results saved to {out_dir} ===")
