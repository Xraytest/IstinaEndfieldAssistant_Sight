#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
IEA OCR 椹卞姩浠诲姟娴佺▼ 鈥?浣跨敤 MaaMCP OCR + 鍐崇瓥妯″潡瀹屾垚姣忔棩浠诲姟棰嗗彇銆?
鏍稿績鐞嗗康锛?  - OCR 浼樺厛妫€娴嬶紙~1s锛夛紝鏇夸唬 VLM锛垀20-30s锛?  - 鍙湁鍦?OCR 鏃犳硶纭畾鏃舵墠鍥為€€ VLM
  - 浣跨敤 MaaMCP 宸ュ叿杩涜鎴浘銆丱CR銆佺偣鍑汇€佹粦鍔?
鐢ㄦ硶锛?  python scripts/ocr_task_flow.py                    # 瀹屾暣娴佺▼
  python scripts/ocr_task_flow.py --once             # 鍗曟妫€娴?  python scripts/ocr_task_flow.py --claim-signin     # 鍙仛绛惧埌棰嗗彇

渚濊禆锛?  - MaaMCP 鏈嶅姟杩愯涓?  - 妯℃嫙鍣ㄥ凡杩炴帴 (localhost:16512)
  - IstinaPlatform 鏈嶅姟鍦?127.0.0.1:9999 (VLM 鍥為€€鐢?
"""

import sys, os, json, time, hashlib, base64
from typing import Optional, Dict, List, Tuple

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

from ocr_decision_module import (
    detect_screen_state, generate_navigation_plan,
    generate_overlay_pipeline, ScreenState, KNOWN_COORDS,
    TOP_BAR_BUTTONS
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(PROJECT_ROOT, "cache")
DEBUG_DIR = os.path.join(PROJECT_ROOT, "debug")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(DEBUG_DIR, exist_ok=True)


# 鈹€鈹€ 鎵ц鍣?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

class ExecutionReport:
    def __init__(self):
        self.claim_attempts = 0
        self.claims_success = 0
        self.steps_taken = []
        self.errors = []
        self.start_time = time.time()
        self.pages_seen = []

    def add_step(self, description: str, success: bool = True, detail: str = ""):
        self.steps_taken.append({
            "time": time.strftime("%H:%M:%S"),
            "description": description,
            "success": success,
            "detail": detail,
        })
        prefix = "鉁? if success else "鉂?
        print(f"[{self.steps_taken[-1]['time']}] {prefix} {description}")

    def summary(self) -> dict:
        elapsed = time.time() - self.start_time
        return {
            "elapsed_seconds": round(elapsed, 1),
            "claim_attempts": self.claim_attempts,
            "claims_success": self.claims_success,
            "steps": len(self.steps_taken),
            "errors": len(self.errors),
            "pages_seen": list(set(self.pages_seen)),
        }

    def save(self, path: str = None):
        if not path:
            path = os.path.join(CACHE_DIR, f"ocr_flow_{int(time.time())}.json")
        data = {
            "timestamp": time.time(),
            "summary": self.summary(),
            "steps": self.steps_taken,
            "errors": self.errors,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n鎶ュ憡宸蹭繚瀛? {path}")
        return path


class MaaMCPExecutor:
    """灏佽 MaaMCP 鎿嶄綔锛岄€傞厤 1280x720 鍧愭爣绌洪棿"""

    def __init__(self, controller_id: str):
        self.controller_id = controller_id
        self.last_ocr_results = []
        self.last_screenshot_path = ""

    def screencap(self) -> Optional[str]:
        """鎴浘骞惰繑鍥炶矾寰?""
        # 閫氳繃 MaaMCP screencap 宸ュ叿
        return self._call_maamcp("screencap", {})

    def ocr(self) -> list:
        """鎵ц OCR 骞惰繑鍥炵粨鏋?""
        result = self._call_maamcp("ocr", {})
        if isinstance(result, list):
            self.last_ocr_results = result
        return self.last_ocr_results

    def click(self, x: int, y: int, label: str = ""):
        """鐐瑰嚮"""
        self._call_maamcp("click", {"x": x, "y": y})
        print(f"  鈫?鐐瑰嚮 ({x}, {y}) {label}")

    def click_key(self, key: int):
        """鎸夐敭"""
        self._call_maamcp("click_key", {"key": key})

    def swipe(self, x1, y1, x2, y2, duration=300):
        """婊戝姩"""
        self._call_maamcp("swipe", {
            "start_x": x1, "start_y": y1,
            "end_x": x2, "end_y": y2, "duration": duration
        })

    def wait(self, seconds: float):
        """绛夊緟"""
        time.sleep(seconds)

    def detect_state(self) -> ScreenState:
        """浣跨敤 OCR 妫€娴嬪綋鍓嶅睆骞曠姸鎬?""
        ocr_results = self.ocr()
        state = detect_screen_state(ocr_results)
        return state

    def _call_maamcp(self, action: str, params: dict) -> any:
        """瀹為檯璋冪敤 MaaMCP 宸ュ叿锛堥€氳繃鍏ㄥ眬鍑芥暟锛?""
        # 杩欎簺鐢卞閮ㄨ剼鏈€氳繃 globals 娉ㄥ叆
        func_map = getattr(self, "_tool_funcs", {})
        func = func_map.get(action)
        if func:
            return func(self.controller_id, **params)
        print(f"  [WARN] MaaMCP 宸ュ叿 '{action}' 涓嶅彲鐢紙妯℃嫙妯″紡锛?)
        return None

    def inject_tools(self, tool_funcs: dict):
        """娉ㄥ叆 MaaMCP 宸ュ叿鍑芥暟锛堢敱澶栭儴鑴氭湰璋冪敤锛?""
        self._tool_funcs = tool_funcs


# 鈹€鈹€ 娴佺▼姝ラ 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def step_navigate_to_world(executor: MaaMCPExecutor, report: ExecutionReport, max_attempts: int = 30):
    """瀵艰埅鍒颁笘鐣屽湴鍥撅紙澶勭悊鏍囬/鐧诲綍/鍔犺浇绛夐〉闈級"""
    for attempt in range(max_attempts):
        state = executor.detect_state()
        report.pages_seen.append(state.page_type)
        print(f"  [{attempt+1}] {state.page_type}: {state.description}")

        if state.page_type == "world_map" or state.page_type == "world_map_with_overlay":
            report.add_step(f"宸插埌杈句笘鐣屽湴鍥?, True, state.description)
            return True

        elif state.page_type == "title":
            executor.click(640, 360, "鐐瑰嚮浠绘剰浣嶇疆缁х画")
            executor.wait(8)

        elif state.page_type == "loading":
            executor.wait(10)

        elif state.page_type == "logout_dialog":
            # 灏濊瘯 ADB 寮哄埗閲嶅惎
            import subprocess
            adb = os.path.join(PROJECT_ROOT, "3rd-part", "adb", "adb.exe")
            subprocess.run([adb, "-s", "localhost:16512", "shell", "am", "force-stop",
                          "com.hypergryph.endfield"], capture_output=True, timeout=10)
            time.sleep(3)
            subprocess.run([adb, "-s", "localhost:16512", "shell", "am", "start",
                          "-n", "com.hypergryph.endfield/com.u8.sdk.U8UnityContext"],
                         capture_output=True, timeout=10)
            executor.wait(20)

        elif state.page_type == "sub_page":
            # 鍦ㄥ瓙椤甸潰锛岃繑鍥?            executor.click_key(4)
            executor.wait(3)

        else:
            # 鏈煡椤甸潰锛屽皾璇曡繑鍥?            executor.click_key(4)
            executor.wait(3)

    report.add_step("瀵艰埅鍒颁笘鐣屽湴鍥惧け璐?, False)
    return False


def step_claim_signin(executor: MaaMCPExecutor, report: ExecutionReport):
    """鍦ㄦ椿鍔ㄧ鍒伴〉闈㈤鍙栧鍔?""
    state = executor.detect_state()
    if state.page_type not in ("sub_page", "world_map_with_overlay"):
        return False

    if not state.claim_buttons:
        # 鍙兘绛惧埌椤甸潰杩樻病鎵撳紑 鈫?灏濊瘯鎵撳紑绛惧埌
        executor.click(510, 22, "娲诲姩鎸夐挳")
        executor.wait(5)

        state = executor.detect_state()
        if state.page_type not in ("sub_page", "world_map_with_overlay"):
            return False

    # 灏濊瘯棰嗗彇
    if state.claim_buttons:
        for cx, cy, label in state.claim_buttons:
            executor.click(cx, cy, label)
            executor.wait(5)
            report.claim_attempts += 1

            # 妫€鏌ユ槸鍚︽湁濂栧姳寮圭獥
            state2 = executor.detect_state()
            if "鑾峰緱濂栧姳" in str(state2.overlay_texts) or "鑾峰緱濂栧姳" in str(state2.interactive_elements):
                # 濂栧姳寮圭獥 鈫?纭
                executor.click(KNOWN_COORDS["reward_confirm"][0],
                              KNOWN_COORDS["reward_confirm"][1], "纭濂栧姳")
                executor.wait(3)
                report.claims_success += 1
                report.add_step(f"绛惧埌棰嗗彇鎴愬姛: {label} at ({cx},{cy})")
    else:
        report.add_step("绛惧埌椤甸潰鏃犲彲棰嗗彇濂栧姳", False)

    return report.claim_attempts > 0


def step_open_task_panel(executor: MaaMCPExecutor, report: ExecutionReport):
    """鍦ㄤ笘鐣屽湴鍥句笂鎵撳紑浠诲姟闈㈡澘"""
    state = executor.detect_state()
    if state.page_type != "world_map":
        report.add_step("涓嶅湪涓栫晫鍦板浘锛屾棤娉曟墦寮€浠诲姟闈㈡澘", False, state.page_type)
        return False

    # 鐐瑰嚮浠诲姟鎸夐挳 (1280x720 鍧愭爣)
    executor.click(KNOWN_COORDS["tasks_button"][0],
                   KNOWN_COORDS["tasks_button"][1], "浠诲姟鎸夐挳")
    executor.wait(5)

    # 妫€娴嬮潰鏉挎槸鍚︽墦寮€
    state2 = executor.detect_state()
    if state2.overlay_detected or state2.page_type == "world_map_with_overlay":
        report.add_step("浠诲姟闈㈡澘宸叉墦寮€")
        return True
    else:
        report.add_step("浠诲姟闈㈡澘鍙兘鏈墦寮€", False, state2.page_type)
        return False


def step_claim_task_rewards(executor: MaaMCPExecutor, report: ExecutionReport):
    """鍦ㄤ换鍔￠潰鏉夸腑棰嗗彇濂栧姳"""
    state = executor.detect_state()

    # 鍏堝湪褰撳墠椤甸潰鏌ユ壘棰嗗彇鎸夐挳
    if state.claim_buttons:
        for cx, cy, label in state.claim_buttons:
            executor.click(cx, cy, label)
            executor.wait(5)
            report.claim_attempts += 1
            report.add_step(f"浠诲姟濂栧姳棰嗗彇: {label} at ({cx},{cy})")

    # 鍚戜笅婊戝姩闈㈡澘锛屾樉绀烘洿澶氬唴瀹?    executor.swipe(1100, 300, 1100, 600, 500)
    executor.wait(3)

    # 鍐嶆妫€娴?    state2 = executor.detect_state()
    if state2.claim_buttons:
        for cx, cy, label in state2.claim_buttons:
            executor.click(cx, cy, label)
            executor.wait(5)
            report.claim_attempts += 1
            report.add_step(f"婊戝姩鍚庨鍙? {label} at ({cx},{cy})")

    # 濡傛灉娌℃湁妫€娴嬪埌棰嗗彇鎸夐挳锛屽皾璇曟毚鍔涚偣鍑诲凡鐭ュ尯鍩?    if report.claim_attempts == 0:
        report.add_step("OCR 鏈娴嬪埌棰嗗彇鎸夐挳锛屽皾璇曞凡鐭ュ尯鍩?, False)
        for cy_fb in [220, 280, 340, 400, 460]:
            executor.click(890, cy_fb, f"鏆村姏鐐瑰嚮 ({890},{cy_fb})")
            executor.wait(2)

        # 鏈€缁堟娴?        state3 = executor.detect_state()
        if state3.claim_buttons:
            for cx, cy, label in state3.claim_buttons:
                executor.click(cx, cy, label)
                executor.wait(5)
                report.claim_attempts += 1

    return report.claim_attempts > 0


def step_close_overlay(executor: MaaMCPExecutor, report: ExecutionReport):
    """鍏抽棴浠诲姟闈㈡澘"""
    executor.click_key(4)  # Android 杩斿洖閿?    executor.wait(3)
    state = executor.detect_state()
    if state.page_type == "world_map":
        report.add_step("闈㈡澘宸插叧闂紝鍥炲埌涓栫晫鍦板浘")
        return True
    report.add_step("闈㈡澘鍏抽棴", True, f"褰撳墠: {state.page_type}")
    return True


# 鈹€鈹€ 瀹屾暣娴佺▼ 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def run_full_flow(executor: MaaMCPExecutor, report: ExecutionReport = None):
    """鎵ц瀹屾暣鐨勬瘡鏃ヤ换鍔℃祦绋?""
    VERSION = "1.0.0"
    if report is None:
        report = ExecutionReport()

    print(f"\n{'='*60}")
    print(f"IEA OCR 姣忔棩浠诲姟娴佺▼ v{VERSION}")
    print(f"{'='*60}")

    # 鈹€鈹€ Step 1: 瀵艰埅鍒颁笘鐣屽湴鍥?鈹€鈹€
    print(f"\n--- Step 1: 瀵艰埅鍒颁笘鐣屽湴鍥?---")
    if not step_navigate_to_world(executor, report):
        print("鏃犳硶鍒拌揪涓栫晫鍦板浘锛岀粓姝?)
        report.save()
        return report

    # 鈹€鈹€ Step 2: 棰嗗彇绛惧埌濂栧姳 鈹€鈹€
    # 鍏堟墦寮€娲诲姩涓績
    print(f"\n--- Step 2: 绛惧埌棰嗗彇 ---")
    executor.click(KNOWN_COORDS["event_button"][0],
                   KNOWN_COORDS["event_button"][1], "娲诲姩鎸夐挳")
    executor.wait(5)

    # 鏌ユ壘绛惧埌鍏ュ彛
    state = executor.detect_state()
    signin_texts = [e for e in state.interactive_elements
                    if any(k in str(e) for k in ["绛惧埌", "瀵诲鎺㈠菇"])]
    if signin_texts:
        # 鐐瑰嚮绛惧埌鍏ュ彛
        entry = signin_texts[0]
        executor.click(entry.get("cx", KNOWN_COORDS["signin_entry"][0]),
                       entry.get("cy", KNOWN_COORDS["signin_entry"][1]), "绛惧埌鍏ュ彛")
        executor.wait(5)
        step_claim_signin(executor, report)
    else:
        # 灏濊瘯宸茬煡绛惧埌鍏ュ彛鍧愭爣
        executor.click(KNOWN_COORDS["signin_entry"][0],
                       KNOWN_COORDS["signin_entry"][1], "绛惧埌鍏ュ彛(澶囩敤)")
        executor.wait(5)
        step_claim_signin(executor, report)

    # 鈹€鈹€ Step 3: 杩斿洖涓栫晫鍦板浘 鈹€鈹€
    print(f"\n--- Step 3: 杩斿洖涓栫晫鍦板浘 ---")
    for _ in range(3):
        executor.click_key(4)
        executor.wait(3)
        state = executor.detect_state()
        if state.page_type == "world_map":
            break

    # 鈹€鈹€ Step 4: 鎵撳紑浠诲姟闈㈡澘 鈹€鈹€
    print(f"\n--- Step 4: 浠诲姟闈㈡澘 ---")
    step_open_task_panel(executor, report)

    # 鈹€鈹€ Step 5: 棰嗗彇浠诲姟濂栧姳 鈹€鈹€
    print(f"\n--- Step 5: 棰嗗彇浠诲姟濂栧姳 ---")
    step_claim_task_rewards(executor, report)

    # 鈹€鈹€ Step 6: 鍏抽棴闈㈡澘 鈹€鈹€
    print(f"\n--- Step 6: 鍏抽棴闈㈡澘 ---")
    step_close_overlay(executor, report)

    # 鈹€鈹€ 淇濆瓨鎶ュ憡 鈹€鈹€
    print(f"\n{'='*60}")
    s = report.summary()
    print(f"娴佺▼瀹屾垚!")
    print(f"  鑰楁椂: {s['elapsed_seconds']}s")
    print(f"  棰嗗彇灏濊瘯: {s['claim_attempts']}")
    print(f"  棰嗗彇鎴愬姛: {s['claims_success']}")
    print(f"  椤甸潰璁块棶: {s['pages_seen']}")
    report.save()

    return report


# 鈹€鈹€ 涓诲叆鍙?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def main():
    """鐙珛杩愯鍏ュ彛"""
    import argparse
    parser = argparse.ArgumentParser(description="IEA OCR 浠诲姟娴佺▼")
    parser.add_argument("--once", action="store_true", help="浠呮娴嬪綋鍓嶅睆骞?)
    parser.add_argument("--claim-signin", action="store_true", help="浠呯鍒伴鍙?)
    parser.add_argument("--controller", default="", help="MaaMCP controller ID")
    args = parser.parse_args()

    print("IEA OCR 浠诲姟娴佺▼")
    print(f"鎺у埗鍣? {args.controller or '(闇€鎻愪緵)'}")

    if not args.controller:
        print("璇锋彁渚?--controller <ID> 鍙傛暟")
        print("鎴栭€氳繃 MaaMCP connect_adb_device 鑾峰彇")
        sys.exit(1)

    executor = MaaMCPExecutor(args.controller)

    if args.once:
        # 鍗曟妫€娴嬫ā寮?        state = executor.detect_state()
        print(f"\n褰撳墠灞忓箷鐘舵€?")
        print(f"  椤甸潰绫诲瀷: {state.page_type}")
        print(f"  椤堕儴鏍? {state.top_bar_visible}")
        print(f"  闈㈡澘鎵撳紑: {state.overlay_detected}")
        print(f"  棰嗗彇鎸夐挳: {state.claim_buttons}")
        print(f"  鎻忚堪: {state.description}")

        plan = generate_navigation_plan(state)
        print(f"\n寤鸿鎿嶄綔 ({len(plan)} 姝?:")
        for step in plan:
            print(f"  {step['description']}")

    elif args.claim_signin:
        # 浠呯鍒伴鍙?        report = ExecutionReport()
        step_navigate_to_world(executor, report)
        step_claim_signin(executor, report)
        report.save()

    else:
        # 瀹屾暣娴佺▼
        report = ExecutionReport()
        run_full_flow(executor, report)


if __name__ == "__main__":
    main()

