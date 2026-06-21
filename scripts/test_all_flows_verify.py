#!/usr/bin/env python3
"""
全标准流验证 — 逐个执行，每流之间恢复到world

验证标准：每流至少1个关键步骤触发画面变化(>100K像素)即为通过
"""

import subprocess, time, cv2, numpy as np, json, sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path; ensure_path()

from core.page_analyzer import HighPrecisionPageAnalyzer

ADB = PROJECT / '3rd-party' / 'adb' / 'adb.exe'
SER = 'localhost:16512'


def screencap():
    r = subprocess.run([str(ADB), '-s', SER, 'exec-out', 'screencap', '-p'],
                      capture_output=True, timeout=10)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)


def tap(x, y):
    subprocess.run([str(ADB), '-s', SER, 'shell', 'input', 'tap',
                   str(int(x)), str(int(y))], capture_output=True, timeout=5)


def back():
    subprocess.run([str(ADB), '-s', SER, 'shell', 'input', 'keyevent', '4'],
                  capture_output=True, timeout=5)


def keyevent(k):
    subprocess.run([str(ADB), '-s', SER, 'shell', 'input', 'keyevent', str(k)],
                  capture_output=True, timeout=5)


def screen_change(before, after, threshold=50000):
    if before is None or after is None:
        return 0
    diff = cv2.absdiff(before, after)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(thresh)


def recover_to_world(analyzer):
    """恢复到world页面"""
    for attempt in range(30):
        img = screencap()
        if img is None:
            continue
        r = analyzer.analyze(img)
        pt = r['page_type']

        if pt == 'world':
            return True

        if pt == 'exit_dialog':
            for cx, cy in [(600, 750), (540, 720), (660, 780)]:
                tap(cx, cy); time.sleep(0.6)
            keyevent(23); time.sleep(0.3)
        elif pt == 'quest_panel':
            back(); time.sleep(1)
        elif pt == 'menu':
            back(); time.sleep(1)
        elif pt == 'enter_game_prompt':
            for cx, cy in [(960, 540), (955, 400)]:
                tap(cx, cy); time.sleep(1.5)
            keyevent(66)
        else:
            back(); time.sleep(0.5)
    return False


def load_flow(name):
    path = PROJECT / "config" / "standard_flows" / "flows_config.json"
    with open(path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    return cfg["flows"].get(name), cfg["variables"]["nav_coords"]


def resolve_coords(raw, nav):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and "{{" in raw:
        key = raw.strip("{}").strip().split(".")[-1]
        return nav.get(key)
    return None


def run_one_flow(flow_name: str) -> bool:
    """执行单个流，至少1个关键步骤有画面变化即成功"""
    flow, nav = load_flow(flow_name)
    if not flow:
        return False

    steps = flow["steps"]
    max_change = 0

    for i, step in enumerate(steps):
        action = step.get("action", "none")
        wait_s = step.get("wait", 2)

        before = screencap()

        if action == "tap":
            coords = resolve_coords(step.get("coords"), nav)
            if coords:
                tap(coords[0], coords[1])
                time.sleep(wait_s)
                after = screencap()
                change = screen_change(before, after)
                if change > max_change:
                    max_change = change

        elif action == "back":
            back()
            time.sleep(wait_s)
            after = screencap()
            change = screen_change(before, after)
            if change > max_change:
                max_change = change

        elif action == "claim":
            coords = nav.get("claim_all", [810, 900])
            tap(coords[0], coords[1])
            time.sleep(2)
            after = screencap()
            change = screen_change(before, after)
            if change > max_change:
                max_change = change

        elif action == "swipe":
            start = step.get("start", [200, 1700])
            end = step.get("end", [200, 1400])
            dur = step.get("duration", 1000)
            subprocess.run([str(ADB), '-s', SER, 'shell', 'input', 'swipe',
                          str(start[0]), str(start[1]), str(end[0]), str(end[1]),
                          str(dur)], capture_output=True, timeout=5)
            time.sleep(1)
            after = screencap()
            change = screen_change(before, after)
            if change > max_change:
                max_change = change

        elif action == "navigate":
            for _ in range(6):
                back()
                time.sleep(0.3)
            time.sleep(2)
            after = screencap()
            change = screen_change(before, after)
            if change > max_change:
                max_change = change

        elif action == "wait":
            time.sleep(wait_s)

    return max_change > 100000  # 至少100K像素变化


def main():
    analyzer = HighPrecisionPageAnalyzer()
    print("=" * 60)
    print("全标准流验证（10流独立测试，流间world恢复）")
    print("=" * 60)

    results = {}
    flows = ["daily_quest", "weekly_quest", "event_rewards",
             "resource_collection", "base_management",
             "character_ascension", "weapon_crafting",
             "delivery_mission", "dungeon_grinding", "auto_move"]

    for flow_name in flows:
        print(f"\n{'-'*40}")
        print(f"recover world -> {flow_name}...")

        # 恢复world
        if not recover_to_world(analyzer):
            print(f"  [FAIL] cannot recover to world")
            results[flow_name] = False
            continue

        # 执行流
        passed = run_one_flow(flow_name)
        status = "PASS" if passed else "FAIL"
        results[flow_name] = passed
        print(f"  [{status}] {flow_name}")

        # 等待稳定
        time.sleep(1)

    # 总结
    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)
    passed_count = sum(1 for v in results.values() if v)
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
    print(f"  Passed: {passed_count}/{len(results)}")

    return 0 if passed_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
