#!/usr/bin/env python3
"""
全标准流测试 — 强制重启 + 前置到world + 逐个流 + 结果汇总

每次流执行后通过 back*6 回到 world
"""
import subprocess, time, cv2, numpy as np, json, sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path; ensure_path()
from core.page_analyzer import HighPrecisionPageAnalyzer

ADB = PROJECT / '3rd-party' / 'adb' / 'adb.exe'
SER = 'localhost:16512'


def sc():
    r = subprocess.run([str(ADB), '-s', SER, 'exec-out', 'screencap', '-p'],
                      capture_output=True, timeout=10)
    if len(r.stdout) < 1000: return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def tap(x, y):
    subprocess.run([str(ADB), '-s', SER, 'shell', 'input', 'tap',
                   str(int(x)), str(int(y))], capture_output=True, timeout=5)

def bk():
    subprocess.run([str(ADB), '-s', SER, 'shell', 'input', 'keyevent', '4'],
                  capture_output=True, timeout=5)

def diff(a, b):
    if a is None or b is None: return 0
    d = cv2.absdiff(a, b); g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)


def force_restart_and_enter_world():
    """强制重启游戏并导航到world"""
    print("Force restart game...")
    subprocess.run([str(ADB), '-s', SER, 'shell', 'am', 'force-stop',
                   'com.hypergryph.endfield'], capture_output=True, timeout=10)
    time.sleep(3)
    subprocess.run([str(ADB), '-s', SER, 'shell', 'monkey', '-p',
                   'com.hypergryph.endfield', '-c',
                   'android.intent.category.LAUNCHER', '1'],
                  capture_output=True, timeout=15)
    print("Wait 30s for loading...")
    time.sleep(30)

    # Click through title/loading screens
    for i in range(10):
        tap(960, 540)
        time.sleep(2)

    # Check state and navigate to world
    analyzer = HighPrecisionPageAnalyzer()
    for attempt in range(30):
        img = sc()
        if img is None: continue
        r = analyzer.analyze(img)
        pt = r['page_type']

        if pt == 'world':
            print(f"  -> world (attempt {attempt+1})")
            return True

        if pt == 'enter_game_prompt':
            for cx, cy in [(960, 540), (955, 400), (960, 1000)]:
                tap(cx, cy); time.sleep(1)
        elif pt == 'exit_dialog':
            tap(600, 750); time.sleep(1)
            subprocess.run([str(ADB), '-s', SER, 'shell', 'input', 'keyevent', '23'],
                          capture_output=True, timeout=5)
        elif pt == 'menu':
            bk(); time.sleep(1)
        elif pt == 'quest_panel':
            bk(); time.sleep(1)
        elif pt == 'unknown':
            tap(960, 540); time.sleep(2)
            bk(); time.sleep(1)
        else:
            bk(); time.sleep(0.5)

    return False


def load_cfg():
    path = PROJECT / "config" / "standard_flows" / "flows_config.json"
    with open(path, 'r', encoding='utf-8') as f: return json.load(f)


def resolve(raw, nav):
    if isinstance(raw, list): return raw
    if isinstance(raw, str) and "{{" in raw:
        return nav.get(raw.strip("{}").split(".")[-1])
    return None


def back_to_world():
    """简单返回world"""
    for _ in range(8):
        bk(); time.sleep(0.3)
    time.sleep(1)


def run_flow(flow, nav):
    """执行流，返回屏幕变化的最大值"""
    max_chg = 0
    for step in flow.get("steps", []):
        act = step.get("action", "none")
        before = sc()

        if act == "tap":
            xy = resolve(step.get("coords"), nav)
            if xy:
                tap(xy[0], xy[1]); time.sleep(step.get("wait", 2))
                chg = diff(before, sc())
                if chg > max_chg: max_chg = chg

        elif act == "back":
            bk(); time.sleep(step.get("wait", 2))
            chg = diff(before, sc())
            if chg > max_chg: max_chg = chg

        elif act == "claim":
            xy = nav.get("claim_all", [810, 900])
            tap(xy[0], xy[1]); time.sleep(2)
            chg = diff(before, sc())
            if chg > max_chg: max_chg = chg

        elif act == "swipe":
            s = step.get("start", [200, 1700]); e = step.get("end", [200, 1400])
            subprocess.run([str(ADB), '-s', SER, 'shell', 'input', 'swipe',
                          str(s[0]), str(s[1]), str(e[0]), str(e[1]),
                          str(step.get("duration", 1000))], capture_output=True, timeout=5)
            time.sleep(1)
            chg = diff(before, sc())
            if chg > max_chg: max_chg = chg

        elif act == "navigate":
            back_to_world()
            chg = diff(before, sc())
            if chg > max_chg: max_chg = chg

        elif act == "wait":
            time.sleep(step.get("wait", 2))

    return max_chg


def main():
    if not force_restart_and_enter_world():
        print("FAIL: cannot reach world after restart")
        return 1

    cfg = load_cfg()
    nav = cfg["variables"]["nav_coords"]
    results = {}

    flows_order = ["daily_quest", "weekly_quest", "event_rewards",
                   "resource_collection", "base_management",
                   "character_ascension", "weapon_crafting",
                   "delivery_mission", "dungeon_grinding", "auto_move"]

    for fname in flows_order:
        flow = cfg["flows"].get(fname)
        if not flow: continue

        print(f"\n--- {fname} ---")
        max_chg = run_flow(flow, nav)
        passed = max_chg > 100000
        results[fname] = passed
        print(f"  max_change={max_chg:,} -> {'PASS' if passed else 'FAIL'}")

        # 返回world
        back_to_world()

    print("\n" + "=" * 50)
    print("Results:")
    passed = sum(1 for v in results.values() if v)
    for n, r in results.items():
        print(f"  {'[PASS]' if r else '[FAIL]'} {n}")
    print(f"  Total: {passed}/{len(results)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
