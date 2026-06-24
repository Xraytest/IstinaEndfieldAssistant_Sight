#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鍔ㄤ綔-楠岃瘉娴佹墽琛屽櫒 鈥?涓嶄緷璧栧畬缇庨〉闈㈠垎绫?
姣忔鎵ц閫昏緫锛?1. 鎴浘 (before)
2. 鎵ц鍔ㄤ綔 (tap/back/swipe)
3. 鎴浘 (after)
4. 璁＄畻鐢婚潰鍙樺寲閲?5. 鏈夊彉鍖?鈫?鎴愬姛锛涙棤鍙樺寲 鈫?閲嶈瘯鎴栬烦杩?
TAN () 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
"""

import subprocess, time, cv2, numpy as np, json, sys
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

PROJECT = PROJECT_ROOT

from core.capability.adb_utils import ADB

ADB_EXE = PROJECT / '3rd-part' / 'adb' / 'adb.exe'
SER = 'localhost:16512'


def screencap():
    r = subprocess.run([str(ADB_EXE), '-s', SER, 'exec-out', 'screencap', '-p'],
                      capture_output=True, timeout=10)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)


def screen_change(before, after, threshold=50000):
    """璁＄畻鐢婚潰鍙樺寲鍍忕礌鏁?""
    if before is None or after is None:
        return 0
    diff = cv2.absdiff(before, after)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(thresh)


def tap(x, y):
    subprocess.run([str(ADB_EXE), '-s', SER, 'shell', 'input', 'tap',
                   str(int(x)), str(int(y))], capture_output=True, timeout=5)


def back():
    subprocess.run([str(ADB_EXE), '-s', SER, 'shell', 'input', 'keyevent', '4'],
                  capture_output=True, timeout=5)


def load_flow(name):
    path = PROJECT / "config" / "standard_flows" / "flows_config.json"
    with open(path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    return cfg["flows"].get(name), cfg["variables"]["nav_coords"]


def resolve_coords(raw, nav):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and "{{" in raw:
        key = raw.strip("{}").strip()
        parts = key.split(".")
        if parts[0] == "nav_coords":
            return nav.get(parts[-1])
    return None


def run_flow(flow_name):
    flow, nav = load_flow(flow_name)
    if not flow:
        print(f"鏈壘鍒? {flow_name}")
        return

    steps = flow["steps"]
    print(f"\n{'='*50}")
    print(f"鎵ц: {flow_name} ({len(steps)}姝?")
    print(f"{'='*50}")

    for i, step in enumerate(steps):
        sid = step.get("id", f"step_{i}")
        action = step.get("action", "none")
        desc = step.get("desc", "")
        wait_s = step.get("wait", 2)

        print(f"\n[姝ラ {i+1}/{len(steps)}] {desc}")

        before = screencap()

        if action == "tap":
            coords = resolve_coords(step.get("coords"), nav)
            if coords:
                tap(coords[0], coords[1])
                time.sleep(wait_s)
                after = screencap()
                change = screen_change(before, after)
                print(f"  [tap ({coords[0]},{coords[1]})] 鍙樺寲={change:,}")

        elif action == "back":
            back()
            time.sleep(wait_s)
            after = screencap()
            change = screen_change(before, after)
            print(f"  [back] 鍙樺寲={change:,}")

        elif action == "claim":
            coords = nav.get("claim_all", [810, 900])
            tap(coords[0], coords[1])
            time.sleep(2)
            after = screencap()
            change = screen_change(before, after)
            print(f"  [claim ({coords[0]},{coords[1]})] 鍙樺寲={change:,}")

        elif action == "swipe":
            start = step.get("start", [200, 1700])
            end = step.get("end", [200, 1400])
            dur = step.get("duration", 1000)
            subprocess.run([str(ADB_EXE), '-s', SER, 'shell', 'input', 'swipe',
                          str(start[0]), str(start[1]), str(end[0]), str(end[1]),
                          str(dur)], capture_output=True, timeout=5)
            time.sleep(1)
            after = screencap()
            change = screen_change(before, after)
            print(f"  [swipe] 鍙樺寲={change:,}")

        elif action == "check":
            after = screencap()
            if after is not None:
                print(f"  [check] 鐢婚潰宸叉崟鑾?)
            else:
                print(f"  [check] 鎴浘澶辫触")

        elif action == "navigate":
            for _ in range(6):
                back()
                time.sleep(0.5)
            time.sleep(2)
            after = screencap()
            change = screen_change(before, after)
            print(f"  [navigate] 鍙樺寲={change:,}")

        elif action == "wait":
            time.sleep(wait_s)
            print(f"  [wait] {wait_s}s")


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "daily_quest"
    run_flow(name)

