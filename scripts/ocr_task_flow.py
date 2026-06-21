#!/usr/bin/env python3
"""
IEA OCR 驱动任务流程 — 使用 MaaMCP OCR + 决策模块完成每日任务领取。

核心理念：
  - OCR 优先检测（~1s），替代 VLM（~20-30s）
  - 只有在 OCR 无法确定时才回退 VLM
  - 使用 MaaMCP 工具进行截图、OCR、点击、滑动

用法：
  python scripts/ocr_task_flow.py                    # 完整流程
  python scripts/ocr_task_flow.py --once             # 单次检测
  python scripts/ocr_task_flow.py --claim-signin     # 只做签到领取

依赖：
  - MaaMCP 服务运行中
  - 模拟器已连接 (localhost:16512)
  - IstinaPlatform 服务在 127.0.0.1:9999 (VLM 回退用)
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


# ── 执行器 ────────────────────────────────────────────────────────

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
        prefix = "✅" if success else "❌"
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
        print(f"\n报告已保存: {path}")
        return path


class MaaMCPExecutor:
    """封装 MaaMCP 操作，适配 1280x720 坐标空间"""

    def __init__(self, controller_id: str):
        self.controller_id = controller_id
        self.last_ocr_results = []
        self.last_screenshot_path = ""

    def screencap(self) -> Optional[str]:
        """截图并返回路径"""
        # 通过 MaaMCP screencap 工具
        return self._call_maamcp("screencap", {})

    def ocr(self) -> list:
        """执行 OCR 并返回结果"""
        result = self._call_maamcp("ocr", {})
        if isinstance(result, list):
            self.last_ocr_results = result
        return self.last_ocr_results

    def click(self, x: int, y: int, label: str = ""):
        """点击"""
        self._call_maamcp("click", {"x": x, "y": y})
        print(f"  ↪ 点击 ({x}, {y}) {label}")

    def click_key(self, key: int):
        """按键"""
        self._call_maamcp("click_key", {"key": key})

    def swipe(self, x1, y1, x2, y2, duration=300):
        """滑动"""
        self._call_maamcp("swipe", {
            "start_x": x1, "start_y": y1,
            "end_x": x2, "end_y": y2, "duration": duration
        })

    def wait(self, seconds: float):
        """等待"""
        time.sleep(seconds)

    def detect_state(self) -> ScreenState:
        """使用 OCR 检测当前屏幕状态"""
        ocr_results = self.ocr()
        state = detect_screen_state(ocr_results)
        return state

    def _call_maamcp(self, action: str, params: dict) -> any:
        """实际调用 MaaMCP 工具（通过全局函数）"""
        # 这些由外部脚本通过 globals 注入
        func_map = getattr(self, "_tool_funcs", {})
        func = func_map.get(action)
        if func:
            return func(self.controller_id, **params)
        print(f"  [WARN] MaaMCP 工具 '{action}' 不可用（模拟模式）")
        return None

    def inject_tools(self, tool_funcs: dict):
        """注入 MaaMCP 工具函数（由外部脚本调用）"""
        self._tool_funcs = tool_funcs


# ── 流程步骤 ────────────────────────────────────────────────────

def step_navigate_to_world(executor: MaaMCPExecutor, report: ExecutionReport, max_attempts: int = 30):
    """导航到世界地图（处理标题/登录/加载等页面）"""
    for attempt in range(max_attempts):
        state = executor.detect_state()
        report.pages_seen.append(state.page_type)
        print(f"  [{attempt+1}] {state.page_type}: {state.description}")

        if state.page_type == "world_map" or state.page_type == "world_map_with_overlay":
            report.add_step(f"已到达世界地图", True, state.description)
            return True

        elif state.page_type == "title":
            executor.click(640, 360, "点击任意位置继续")
            executor.wait(8)

        elif state.page_type == "loading":
            executor.wait(10)

        elif state.page_type == "logout_dialog":
            # 尝试 ADB 强制重启
            import subprocess
            adb = os.path.join(PROJECT_ROOT, "3rd-party", "adb", "adb.exe")
            subprocess.run([adb, "-s", "localhost:16512", "shell", "am", "force-stop",
                          "com.hypergryph.endfield"], capture_output=True, timeout=10)
            time.sleep(3)
            subprocess.run([adb, "-s", "localhost:16512", "shell", "am", "start",
                          "-n", "com.hypergryph.endfield/com.u8.sdk.U8UnityContext"],
                         capture_output=True, timeout=10)
            executor.wait(20)

        elif state.page_type == "sub_page":
            # 在子页面，返回
            executor.click_key(4)
            executor.wait(3)

        else:
            # 未知页面，尝试返回
            executor.click_key(4)
            executor.wait(3)

    report.add_step("导航到世界地图失败", False)
    return False


def step_claim_signin(executor: MaaMCPExecutor, report: ExecutionReport):
    """在活动签到页面领取奖励"""
    state = executor.detect_state()
    if state.page_type not in ("sub_page", "world_map_with_overlay"):
        return False

    if not state.claim_buttons:
        # 可能签到页面还没打开 → 尝试打开签到
        executor.click(510, 22, "活动按钮")
        executor.wait(5)

        state = executor.detect_state()
        if state.page_type not in ("sub_page", "world_map_with_overlay"):
            return False

    # 尝试领取
    if state.claim_buttons:
        for cx, cy, label in state.claim_buttons:
            executor.click(cx, cy, label)
            executor.wait(5)
            report.claim_attempts += 1

            # 检查是否有奖励弹窗
            state2 = executor.detect_state()
            if "获得奖励" in str(state2.overlay_texts) or "获得奖励" in str(state2.interactive_elements):
                # 奖励弹窗 → 确认
                executor.click(KNOWN_COORDS["reward_confirm"][0],
                              KNOWN_COORDS["reward_confirm"][1], "确认奖励")
                executor.wait(3)
                report.claims_success += 1
                report.add_step(f"签到领取成功: {label} at ({cx},{cy})")
    else:
        report.add_step("签到页面无可领取奖励", False)

    return report.claim_attempts > 0


def step_open_task_panel(executor: MaaMCPExecutor, report: ExecutionReport):
    """在世界地图上打开任务面板"""
    state = executor.detect_state()
    if state.page_type != "world_map":
        report.add_step("不在世界地图，无法打开任务面板", False, state.page_type)
        return False

    # 点击任务按钮 (1280x720 坐标)
    executor.click(KNOWN_COORDS["tasks_button"][0],
                   KNOWN_COORDS["tasks_button"][1], "任务按钮")
    executor.wait(5)

    # 检测面板是否打开
    state2 = executor.detect_state()
    if state2.overlay_detected or state2.page_type == "world_map_with_overlay":
        report.add_step("任务面板已打开")
        return True
    else:
        report.add_step("任务面板可能未打开", False, state2.page_type)
        return False


def step_claim_task_rewards(executor: MaaMCPExecutor, report: ExecutionReport):
    """在任务面板中领取奖励"""
    state = executor.detect_state()

    # 先在当前页面查找领取按钮
    if state.claim_buttons:
        for cx, cy, label in state.claim_buttons:
            executor.click(cx, cy, label)
            executor.wait(5)
            report.claim_attempts += 1
            report.add_step(f"任务奖励领取: {label} at ({cx},{cy})")

    # 向下滑动面板，显示更多内容
    executor.swipe(1100, 300, 1100, 600, 500)
    executor.wait(3)

    # 再次检测
    state2 = executor.detect_state()
    if state2.claim_buttons:
        for cx, cy, label in state2.claim_buttons:
            executor.click(cx, cy, label)
            executor.wait(5)
            report.claim_attempts += 1
            report.add_step(f"滑动后领取: {label} at ({cx},{cy})")

    # 如果没有检测到领取按钮，尝试暴力点击已知区域
    if report.claim_attempts == 0:
        report.add_step("OCR 未检测到领取按钮，尝试已知区域", False)
        for cy_fb in [220, 280, 340, 400, 460]:
            executor.click(890, cy_fb, f"暴力点击 ({890},{cy_fb})")
            executor.wait(2)

        # 最终检测
        state3 = executor.detect_state()
        if state3.claim_buttons:
            for cx, cy, label in state3.claim_buttons:
                executor.click(cx, cy, label)
                executor.wait(5)
                report.claim_attempts += 1

    return report.claim_attempts > 0


def step_close_overlay(executor: MaaMCPExecutor, report: ExecutionReport):
    """关闭任务面板"""
    executor.click_key(4)  # Android 返回键
    executor.wait(3)
    state = executor.detect_state()
    if state.page_type == "world_map":
        report.add_step("面板已关闭，回到世界地图")
        return True
    report.add_step("面板关闭", True, f"当前: {state.page_type}")
    return True


# ── 完整流程 ────────────────────────────────────────────────────

def run_full_flow(executor: MaaMCPExecutor, report: ExecutionReport = None):
    """执行完整的每日任务流程"""
    VERSION = "1.0.0"
    if report is None:
        report = ExecutionReport()

    print(f"\n{'='*60}")
    print(f"IEA OCR 每日任务流程 v{VERSION}")
    print(f"{'='*60}")

    # ── Step 1: 导航到世界地图 ──
    print(f"\n--- Step 1: 导航到世界地图 ---")
    if not step_navigate_to_world(executor, report):
        print("无法到达世界地图，终止")
        report.save()
        return report

    # ── Step 2: 领取签到奖励 ──
    # 先打开活动中心
    print(f"\n--- Step 2: 签到领取 ---")
    executor.click(KNOWN_COORDS["event_button"][0],
                   KNOWN_COORDS["event_button"][1], "活动按钮")
    executor.wait(5)

    # 查找签到入口
    state = executor.detect_state()
    signin_texts = [e for e in state.interactive_elements
                    if any(k in str(e) for k in ["签到", "寻奇探幽"])]
    if signin_texts:
        # 点击签到入口
        entry = signin_texts[0]
        executor.click(entry.get("cx", KNOWN_COORDS["signin_entry"][0]),
                       entry.get("cy", KNOWN_COORDS["signin_entry"][1]), "签到入口")
        executor.wait(5)
        step_claim_signin(executor, report)
    else:
        # 尝试已知签到入口坐标
        executor.click(KNOWN_COORDS["signin_entry"][0],
                       KNOWN_COORDS["signin_entry"][1], "签到入口(备用)")
        executor.wait(5)
        step_claim_signin(executor, report)

    # ── Step 3: 返回世界地图 ──
    print(f"\n--- Step 3: 返回世界地图 ---")
    for _ in range(3):
        executor.click_key(4)
        executor.wait(3)
        state = executor.detect_state()
        if state.page_type == "world_map":
            break

    # ── Step 4: 打开任务面板 ──
    print(f"\n--- Step 4: 任务面板 ---")
    step_open_task_panel(executor, report)

    # ── Step 5: 领取任务奖励 ──
    print(f"\n--- Step 5: 领取任务奖励 ---")
    step_claim_task_rewards(executor, report)

    # ── Step 6: 关闭面板 ──
    print(f"\n--- Step 6: 关闭面板 ---")
    step_close_overlay(executor, report)

    # ── 保存报告 ──
    print(f"\n{'='*60}")
    s = report.summary()
    print(f"流程完成!")
    print(f"  耗时: {s['elapsed_seconds']}s")
    print(f"  领取尝试: {s['claim_attempts']}")
    print(f"  领取成功: {s['claims_success']}")
    print(f"  页面访问: {s['pages_seen']}")
    report.save()

    return report


# ── 主入口 ────────────────────────────────────────────────────────

def main():
    """独立运行入口"""
    import argparse
    parser = argparse.ArgumentParser(description="IEA OCR 任务流程")
    parser.add_argument("--once", action="store_true", help="仅检测当前屏幕")
    parser.add_argument("--claim-signin", action="store_true", help="仅签到领取")
    parser.add_argument("--controller", default="", help="MaaMCP controller ID")
    args = parser.parse_args()

    print("IEA OCR 任务流程")
    print(f"控制器: {args.controller or '(需提供)'}")

    if not args.controller:
        print("请提供 --controller <ID> 参数")
        print("或通过 MaaMCP connect_adb_device 获取")
        sys.exit(1)

    executor = MaaMCPExecutor(args.controller)

    if args.once:
        # 单次检测模式
        state = executor.detect_state()
        print(f"\n当前屏幕状态:")
        print(f"  页面类型: {state.page_type}")
        print(f"  顶部栏: {state.top_bar_visible}")
        print(f"  面板打开: {state.overlay_detected}")
        print(f"  领取按钮: {state.claim_buttons}")
        print(f"  描述: {state.description}")

        plan = generate_navigation_plan(state)
        print(f"\n建议操作 ({len(plan)} 步):")
        for step in plan:
            print(f"  {step['description']}")

    elif args.claim_signin:
        # 仅签到领取
        report = ExecutionReport()
        step_navigate_to_world(executor, report)
        step_claim_signin(executor, report)
        report.save()

    else:
        # 完整流程
        report = ExecutionReport()
        run_full_flow(executor, report)


if __name__ == "__main__":
    main()
