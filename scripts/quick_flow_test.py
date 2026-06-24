#!/usr/bin/env python3
"""
快速流测试 — 从当前游戏状态直接执行流步骤（跳过 preamble）

用法: python scripts/quick_flow_test.py daily_quest
"""

import sys, time, json
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT / "scripts"))

from core.capability.adb_utils import ADB, adb_screencap
from core.service.page_analyzer import HighPrecisionPageAnalyzer
from core.service.gui_client import GUIClient
import cv2, numpy as np


def load_flow(flow_name):
    path = PROJECT / "config" / "standard_flows" / "flows_config.json"
    with open(path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    flow = config.get("flows", {}).get(flow_name)
    nav = config.get("variables", {}).get("nav_coords", {})
    if not flow:
        print(f"未找到流程: {flow_name}")
        sys.exit(1)
    return flow, nav


def resolve_coords(raw, nav_coords):
    """解析坐标（支持 {{nav_coords.xxx}} 引用）"""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and "{{" in raw:
        key = raw.strip("{}").strip()
        parts = key.split(".")
        if parts[0] == "nav_coords" and len(parts) == 2:
            return nav_coords.get(parts[1])
    return None


def run_flow(flow_name: str):
    flow, nav = load_flow(flow_name)
    steps = flow.get("steps", [])
    adb = ADB()
    analyzer = HighPrecisionPageAnalyzer()
    vlm = GUIClient({"vlm_mode": "local"})

    print(f"\n{'='*60}")
    print(f"执行: {flow_name} ({flow.get('description','')})")
    print(f"步骤: {len(steps)}")
    print(f"{'='*60}")

    for i, step in enumerate(steps):
        sid = step.get("id", f"step_{i}")
        action = step.get("action", "none")
        desc = step.get("desc", sid)
        wait_s = step.get("wait", 2)

        print(f"\n[步骤 {i+1}/{len(steps)}] {desc}")

        # 截图分析当前页面
        img_bytes = adb_screencap()
        if not img_bytes:
            print("  截图失败")
            continue
        cv_img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        page_result = analyzer.analyze(cv_img)
        pt = page_result["page_type"]
        conf = page_result["confidence"]

        print(f"  当前页面: {pt} (置信度 {conf:.2f})")

        # 自动处理退出对话框
        if pt == "exit_dialog":
            print(f"  [AUTO] 检测到退出对话框，自动关闭...")
            closed = False
            for cx, cy in [(600, 750), (540, 720), (660, 780), (580, 730), (620, 770)]:
                adb.tap(cx, cy)
                time.sleep(1.5)
                img_bytes2 = adb_screencap()
                cv_img2 = cv2.imdecode(np.frombuffer(img_bytes2, np.uint8), cv2.IMREAD_COLOR)
                r2 = analyzer.analyze(cv_img2)
                if r2["page_type"] != "exit_dialog":
                    print(f"  [OK] 对话框已关闭，当前={r2['page_type']}")
                    r = r2
                    pt = r["page_type"]
                    conf = r["confidence"]
                    closed = True
                    break
            if not closed:
                print(f"  [WARN] 无法关闭退出对话框，按返回")
                adb.back()
                time.sleep(1)
                continue

        # Check for special screen and handle
        if pt in ("enter_game_prompt", "title"):
            print(f"  [INFO] {pt} 画面，点击中央进入游戏")
            adb.tap(960, 540)
            time.sleep(3)
            continue

        if pt == "menu":
            print(f"  [INFO] 菜单页面，left_bar={r['features'].get('left_bar_brightness',0):.0f}")

        # 处理 actions
        if action == "tap":
            coords = resolve_coords(step.get("coords"), nav)
            if coords and len(coords) == 2:
                print(f"  [TAP] ({coords[0]}, {coords[1]})")
                adb.tap(coords[0], coords[1])
                time.sleep(wait_s)
            else:
                print(f"  [WARN] 无有效坐标")

        elif action == "back":
            print(f"  [BACK]")
            adb.back()
            time.sleep(wait_s)

        elif action == "check":
            expect = step.get("expect", "")
            if expect:
                if pt == expect:
                    print(f"  [OK] 页面匹配预期: {expect}")
                elif expect == "world" and pt in ("world", "world_transition"):
                    print(f"  [OK] 页面匹配预期 (world)")
                else:
                    print(f"  [WARN] 预期={expect} 实际={pt}")

        elif action == "claim":
            coords = nav.get("claim_all", [810, 900])
            print(f"  [CLAIM] ({coords[0]}, {coords[1]})")
            adb.tap(coords[0], coords[1])
            time.sleep(wait_s)

        elif action == "swipe":
            start = step.get("start", [200, 1700])
            end = step.get("end", [200, 1400])
            dur = step.get("duration", 1000)
            print(f"  [SWIPE] {start} -> {end} ({dur}ms)")
            adb.swipe(start[0], start[1], end[0], end[1], dur)
            time.sleep(wait_s)

        elif action == "navigate":
            target = step.get("target", "world")
            print(f"  [NAV] 导航到 {target}")
            for _ in range(6):
                adb.back()
                time.sleep(0.5)
            time.sleep(wait_s)

        elif action == "wait":
            print(f"  [WAIT] {wait_s}s")
            time.sleep(wait_s)

    # 最终状态
    img_bytes = adb_screencap()
    cv_img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    final = analyzer.analyze(cv_img)
    print(f"\n最终页面: {final['page_type']} (置信度 {final['confidence']:.2f})")


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "daily_quest"
    run_flow(name)
