"""
IEA 优化版探索引擎 — 基于 OCR 优先的智能探索 + 任务覆盖

相对于原版 exploration_engine.py 的改进:
  1. OCR 优先检测游戏模式（探索/工业/签到/任务面板）
  2. 模式感知导航（自动切换探索/工业模式）
  3. 任务面板覆盖层检测（不依赖 VLM page_type）
  4. 每日/每周任务完整覆盖路径
  5. 领取按钮优先级检测
  6. 页面树增加 overlay 状态记录

用法:
  from exploration_engine_optimized import OptimizedExplorationEngine
  engine = OptimizedExplorationEngine(communicator, screen_capture, touch_executor)
  engine.start_daily_flow()  # 执行每日任务流程
"""

import json, os, re, time, hashlib, base64, subprocess
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum

# ── 坐标常量（统一引用 game_coords） ────────────────────────────
from core.foundation.game_data import (
    MODE_SWITCH_BUTTON as MODE_SWITCH,
    TOP_BAR, EXIT_DIALOG, SIGNIN_PAGE, EVENT_CENTER,
    OVERLAY_ROI_TUPLE as OVERLAY_ROI,
    OVERLAY_KEYWORDS, CLAIM_KEYWORDS,
)


# ── 扩展页面状态 ────────────────────────────────────────────────

class GameMode(Enum):
    UNKNOWN = "unknown"
    EXPLORATION = "exploration"      # 探索模式（野外）
    INDUSTRY = "industry"            # 工业/基建模式

class OverlayState(Enum):
    NONE = "none"                    # 无覆盖层
    TASK_PANEL = "task_panel"        # 任务面板打开
    SIGNIN = "signin"               # 签到页面
    EVENT = "event"                 # 活动中心
    DIALOG = "dialog"               # 弹窗
    LOADING = "loading"             # 加载中

@dataclass
class GameContext:
    """游戏上下文 — 跟踪当前状态"""
    game_mode: GameMode = GameMode.UNKNOWN
    overlay: OverlayState = OverlayState.NONE
    on_world_map: bool = False
    current_page: str = ""
    page_hash: str = ""
    claim_available: bool = False
    claim_locations: List[Tuple[int, int, str]] = field(default_factory=list)

    def reset(self):
        self.game_mode = GameMode.UNKNOWN
        self.overlay = OverlayState.NONE
        self.on_world_map = False
        self.claim_available = False
        self.claim_locations = []


# ── OCR 扫描器（不依赖 VLM） ───────────────────────────────────

class OCRAnalyzer:
    """基于 OCR 结果的快速屏幕分析"""

    @staticmethod
    def analyze(ocr_results: list) -> GameContext:
        ctx = GameContext()

        if not ocr_results:
            return ctx

        texts = [(e["text"], e["box"]) for e in ocr_results
                 if e.get("text") and e.get("score", 0) > 0.3]

        # 检测游戏模式
        for text, box in texts:
            if text == "探索" and OCRAnalyzer._in_region(box, (60, 100), (10, 45)):
                ctx.game_mode = GameMode.EXPLORATION
            elif text == "工业" and OCRAnalyzer._in_region(box, (60, 100), (10, 45)):
                ctx.game_mode = GameMode.INDUSTRY

        # 检测世界地图（有探索/工业按钮在左上角 = 在游戏中）
        ctx.on_world_map = ctx.game_mode in (GameMode.EXPLORATION, GameMode.INDUSTRY)

        # 检测标题画面和登出
        content_text = " ".join([t for t, b in texts])
        if "点击任意位置继续" in content_text or ("终末地" in content_text and "明日方舟" in content_text):
            ctx.overlay = OverlayState.LOADING  # title screen
            return ctx
        if "自动登出" in content_text or "长时间没有操作" in content_text:
            ctx.overlay = OverlayState.DIALOG
            return ctx

        # 检测覆盖层
        overlay_texts = [t for t, b in texts
                         if OCRAnalyzer._in_region(b, OVERLAY_ROI[:2],
                                                   (OVERLAY_ROI[0]+OVERLAY_ROI[2], OVERLAY_ROI[1]+OVERLAY_ROI[3]))]
        if overlay_texts:
            all_text = " ".join(overlay_texts)
            if any(kw in all_text for kw in ["签到", "寻奇探幽"]):
                ctx.overlay = OverlayState.SIGNIN
            elif any(kw in all_text for kw in ["每日", "每周", "任务"]):
                ctx.overlay = OverlayState.TASK_PANEL
            elif any(kw in all_text for kw in ["活动中心", "活动"]):
                ctx.overlay = OverlayState.EVENT
            elif any(kw in all_text for kw in ["退出游戏"]):
                ctx.overlay = OverlayState.DIALOG

        # 检测领取按钮
        for item in ocr_results:
            t = item.get("text", "") if isinstance(item, dict) else (item if isinstance(item, str) else "")
            box_data = item.get("box", [0, 0, 10, 10]) if isinstance(item, dict) else [0, 0, 10, 10]
            if not t:
                continue
            for kw in CLAIM_KEYWORDS:
                if kw in t:
                    cx = box_data[0] + box_data[2] // 2
                    cy = box_data[1] + box_data[3] // 2
                    ctx.claim_locations.append((cx, cy, t))
                    ctx.claim_available = True
                    break

        return ctx

    @staticmethod
    def _in_region(box: list, x_range: tuple, y_range: tuple) -> bool:
        if len(box) < 2:
            return False
        cx = box[0] + box[2] // 2 if len(box) >= 4 else box[0]
        cy = box[1] + box[3] // 2 if len(box) >= 4 else box[1]
        return x_range[0] <= cx <= x_range[1] and y_range[0] <= cy <= y_range[1]


# ── 任务覆盖路径定义 ────────────────────────────────────────────

@dataclass
class TaskRoute:
    """定义一条任务覆盖路径"""
    name: str
    steps: List[Dict]              # 操作步骤列表
    claim_keywords: List[str]      # 要查找的领取关键词
    priority: int = 5              # 优先级（1=最高）

# 标准日周任务覆盖路线
DAILY_ROUTES = [
    TaskRoute(
        name="签到领取",
        priority=1,
        claim_keywords=["领取", "一键领取", "签到"],
        steps=[
            {"action": "tap", "target": TOP_BAR["event"], "wait": 5,
             "desc": "打开活动中心"},
            {"action": "tap", "target": EVENT_CENTER["signin_entry"], "wait": 5,
             "desc": "进入签到页面"},
            {"action": "claim_any", "wait": 5,
             "desc": "领取签到奖励"},
            {"action": "tap", "target": SIGNIN_PAGE["reward_close"], "wait": 3,
             "desc": "关闭奖励弹窗"},
        ]
    ),
    TaskRoute(
        name="任务面板奖励",
        priority=2,
        claim_keywords=["领取", "收取", "一键领取"],
        steps=[
            {"action": "tap", "target": TOP_BAR["tasks"], "wait": 5,
             "desc": "打开任务面板"},
            {"action": "swipe", "params": {"x1": 1100, "y1": 300, "x2": 1100, "y2": 600, "duration": 500}, "wait": 3,
             "desc": "向下滑动查看任务"},
            {"action": "claim_any", "wait": 5,
             "desc": "领取任务奖励"},
            {"action": "back", "wait": 3,
             "desc": "关闭面板"},
        ]
    ),
    TaskRoute(
        name="作战汇报奖励",
        priority=3,
        claim_keywords=["领取", "收取"],
        steps=[
            {"action": "tap", "target": TOP_BAR["tasks"], "wait": 5,
             "desc": "打开任务面板"},
            {"action": "tap", "target": (1100, 120), "wait": 3,
             "desc": "切换到作战汇报标签"},
            {"action": "claim_any", "wait": 5,
             "desc": "领取作战汇报奖励"},
            {"action": "back", "wait": 3,
             "desc": "关闭面板"},
        ]
    ),
]

WEEKLY_ROUTES = [
    TaskRoute(
        name="每周事务",
        priority=4,
        claim_keywords=["领取", "完成"],
        steps=[
            {"action": "tap", "target": TOP_BAR["tasks"], "wait": 5,
             "desc": "打开任务面板"},
            {"action": "tap", "target": (1100, 160), "wait": 3,
             "desc": "切换到每周事务标签"},
            {"action": "swipe", "params": {"x1": 1100, "y1": 300, "x2": 1100, "y2": 600, "duration": 500}, "wait": 3,
             "desc": "向下滑动查看周常"},
            {"action": "claim_any", "wait": 5,
             "desc": "领取周常奖励"},
            {"action": "back", "wait": 3,
             "desc": "关闭面板"},
        ]
    ),
]

# 需要从世界地图导航到目标页面的路径
NAV_PATHS = {
    "activity_center": [
        {"action": "tap", "target": TOP_BAR["event"], "wait": 5},
    ],
    "task_panel": [
        {"action": "tap", "target": TOP_BAR["tasks"], "wait": 5},
    ],
    "signin": [
        {"action": "tap", "target": TOP_BAR["event"], "wait": 5},
        {"action": "tap", "target": EVENT_CENTER["signin_entry"], "wait": 5},
    ],
}


# ── 优化版探索引擎 ─────────────────────────────────────────────

class OptimizedExplorationEngine:
    """OCR 优先的优化探索引擎"""

    def __init__(self, adb_shell_func=None, maa_ocr_func=None, maa_click_func=None,
                 maa_swipe_func=None, maa_back_func=None, maa_screencap_func=None, vlm_func=None):
        self._adb_shell = adb_shell_func or self._default_adb
        self._ocr = maa_ocr_func
        self._click = maa_click_func
        self._swipe = maa_swipe_func
        self._back = maa_back_func
        self._screencap = maa_screencap_func
        self._vlm = vlm_func
        self._context = GameContext()
        self._stats = {
            "ocr_calls": 0, "vlm_calls": 0, "taps": 0,
            "claims_attempted": 0, "claims_success": 0,
            "pages_discovered": 0, "routes_completed": 0,
        }
        self._execution_log = []

    def _default_adb(self, cmd: str, *args) -> bytes:
        """默认 ADB 调用（仅保留截图功能，触控已完全迁移至 MaaFw）"""
        adb = r"C:\Users\xray\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant\3rd-party\adb\adb.exe"
        # 触控操作已移除，仅保留截图
        if cmd == "screencap":
            return subprocess.run(
                [adb, "-s", "localhost:16512", "exec-out", "screencap", "-p"],
                capture_output=True, timeout=15).stdout
        # 触控命令不再支持（已迁移至 MaaFw TouchManager）
        import logging
        logging.getLogger(__name__).warning(f"ADB 触控命令已弃用：{cmd}，请使用 MaaFw TouchManager")
        return b""

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        self._execution_log.append(line)

    # ── 核心操作 ──────────────────────────────────────────────

    def tap(self, x: int, y: int, label: str = ""):
        """点击操作（必须通过回调函数，不再支持 ADB 回退）"""
        if self._click:
            self._click(x, y)
        else:
            import logging
            logging.getLogger(__name__).error("触控点击未配置回调函数，无法执行。请通过 MaaFw TouchManager 注入 click 回调")
            raise RuntimeError("No click callback configured. Must use MaaFw TouchManager.")
        self._stats["taps"] += 1
        self.log(f"  tap ({x},{y}) {label}")

    def swipe(self, x1, y1, x2, y2, duration=500):
        """滑动操作（必须通过回调函数，不再支持 ADB 回退）"""
        if self._swipe:
            self._swipe(x1, y1, x2, y2, duration)
        else:
            import logging
            logging.getLogger(__name__).error("触控滑动未配置回调函数，无法执行。请通过 MaaFw TouchManager 注入 swipe 回调")
            raise RuntimeError("No swipe callback configured. Must use MaaFw TouchManager.")
        self.log(f"  swipe ({x1},{y1})→({x2},{y2})")

    def back(self):
        """返回键操作（必须通过回调函数，不再支持 ADB 回退）"""
        if self._back:
            self._back()
        else:
            import logging
            logging.getLogger(__name__).error("返回键未配置回调函数，无法执行。请通过 MaaFw TouchManager 注入 back 回调")
            raise RuntimeError("No back callback configured. Must use MaaFw TouchManager.")
        self.log("  back")

    def wait(self, s: float):
        time.sleep(s)

    def get_ocr(self) -> list:
        """获取 OCR 结果"""
        self._stats["ocr_calls"] += 1
        if self._ocr:
            return self._ocr()
        # 无 MaaMCP 时的回退
        return []

    def get_screenshot(self) -> Optional[str]:
        """获取截图（base64）"""
        if self._screencap:
            path = self._screencap()
            if path:
                with open(path, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
        raw = self._adb_shell("screencap")
        if raw:
            return base64.b64encode(raw).decode("utf-8")
        return None

    def call_vlm(self, instruction: str, screenshot_b64: str = None,
                 system_prompt: str = "") -> Optional[Dict]:
        """调用 VLM（回退）"""
        self._stats["vlm_calls"] += 1
        if self._vlm:
            return self._vlm(instruction, screenshot_b64 or "", system_prompt)
        return None

    # ── 上下文管理 ──────────────────────────────────────────────

    def refresh_context(self) -> GameContext:
        """通过 OCR 刷新游戏上下文"""
        ocr_results = self.get_ocr()
        self._context = OCRAnalyzer.analyze(ocr_results)
        if self._context.page_hash:
            self._stats["pages_discovered"] += 1
        return self._context

    def wait_for_stable(self, timeout: int = 20) -> bool:
        """等待画面稳定（连续 3 次 OCR 相同）"""
        last_hash = ""
        stable_count = 0
        for _ in range(timeout):
            ocr = self.get_ocr()
            h = hashlib.md5(str(ocr).encode()).hexdigest()[:12]
            if h == last_hash:
                stable_count += 1
                if stable_count >= 2:
                    return True
            else:
                stable_count = 0
                last_hash = h
            self.wait(1)
        return stable_count >= 2

    # ── 导航 ──────────────────────────────────────────────────

    def ensure_world_map(self, max_attempts: int = 40) -> bool:
        """确保在主世界地图（处理标题/加载/弹窗/登出等）"""
        for attempt in range(max_attempts):
            ctx = self.refresh_context()

            if ctx.on_world_map:
                return True

            # 对话框（退出确认/奖励弹窗等）
            if ctx.overlay == OverlayState.DIALOG:
                # 检测是否"退出游戏"
                ocr = self.get_ocr()
                has_exit = any("退出游戏" in str(e) for e in ocr)
                has_logout = any("自动登出" in str(e) or "自动登出" in str(e) for e in ocr)
                if has_exit:
                    self.tap(*EXIT_DIALOG["cancel"], "取消退出")
                    self.wait(3)
                    continue
                elif has_logout:
                    # 自动登出 → 点确认
                    ocr_texts = [e.get("text", "") if isinstance(e, dict) else str(e) for e in ocr]
                    # 找确认按钮
                    for e in ocr:
                        if isinstance(e, dict) and e.get("text") == "确认":
                            bx = e.get("box", [0, 0, 20, 20])
                            self.tap(bx[0] + bx[2]//2, bx[1] + bx[3]//2, "确认登出")
                            self.wait(5)
                            break
                    self.wait(5)
                    continue

            # 标题画面
            ocr = self.get_ocr()
            ocr_texts = [str(e.get("text", "") if isinstance(e, dict) else e) for e in ocr]
            full_text = " ".join(ocr_texts)
            if "点击任意位置继续" in full_text:
                self.log(f"  标题画面，点击进入 ({attempt+1})")
                self.tap(640, 360, "点击进入游戏")
                self.wait(10)
                continue
            if "终末地" in full_text and "明日方舟" in full_text:
                self.tap(640, 360, "点击进入游戏")
                self.wait(10)
                continue

            if "NOWLOADING" in full_text or "NOW LOADING" in full_text or "LOADING" in full_text:
                self.log(f"  加载中，等待 ({attempt+1})")
                self.wait(10)
                continue

            # 未知页面 → 尝试返回，但限制次数
            if attempt < 10:
                self.back()
                self.wait(3)
            else:
                self.log(f"  尝试点击屏幕中央 ({attempt+1})")
                self.tap(640, 360, "点击中央")
                self.wait(3)

        self.log("WARN: 无法返回世界地图")
        return False

    def navigate_to(self, target: str) -> bool:
        """导航到指定目标页面"""
        if target not in NAV_PATHS:
            self.log(f"WARN: 未知目标 '{target}'")
            return False

        if not self.ensure_world_map():
            return False

        for step in NAV_PATHS[target]:
            if step["action"] == "tap":
                self.tap(*step["target"], step.get("desc", ""))
                self.wait(step.get("wait", 3))
            elif step["action"] == "wait":
                self.wait(step.get("wait", 3))

        self.wait_for_stable()
        ctx = self.refresh_context()
        return ctx.on_world_map or ctx.overlay != OverlayState.NONE

    # ── 执行路线 ──────────────────────────────────────────────

    def execute_route(self, route: TaskRoute) -> bool:
        """执行一条任务覆盖路线"""
        self.log(f"\n{'='*50}")
        self.log(f"执行: {route.name} (优先级 {route.priority})")

        if not self.ensure_world_map():
            self.log(f"  FAIL: 不在世界地图")
            return False

        for i, step in enumerate(route.steps):
            action = step["action"]
            wait_time = step.get("wait", 3)

            if action == "tap":
                self.tap(*step["target"], step.get("desc", ""))
                self.wait(wait_time)

            elif action == "swipe":
                p = step["params"]
                self.swipe(p["x1"], p["y1"], p["x2"], p["y2"], p.get("duration", 500))
                self.wait(wait_time)

            elif action == "back":
                self.back()
                self.wait(wait_time)

            elif action == "wait":
                self.wait(step.get("duration", wait_time))

            elif action == "claim_any":
                # 查找并领取
                ctx = self.refresh_context()
                if ctx.claim_locations:
                    for cx, cy, label in ctx.claim_locations:
                        self.tap(cx, cy, f"领取: {label}")
                        self.wait(wait_time)
                        self._stats["claims_attempted"] += 1

                        # 检查是否有奖励弹窗
                        ctx2 = self.refresh_context()
                        if ctx2.overlay == OverlayState.DIALOG or \
                           any("获得" in str(e) for e in self.get_ocr()):
                            self.tap(*SIGNIN_PAGE["reward_close"], "关闭奖励")
                            self.wait(3)
                            self._stats["claims_success"] += 1
                else:
                    self.log(f"  [OCR] 未检测到领取按钮")

        self._stats["routes_completed"] += 1
        return True

    # ── 完整每日流程 ──────────────────────────────────────────

    def start_daily_flow(self):
        """执行完整的每日任务流程"""
        self.log("=" * 60)
        self.log("IEA 优化版 — 每日任务流程")
        self.log("=" * 60)

        start_time = time.time()

        # Phase 1: 确保在世界地图
        self.log("\n[Phase 1] 导航到世界地图")
        if not self.ensure_world_map():
            self.log("ERROR: 无法进入游戏")
            self._print_summary(start_time)
            return

        # Phase 2: 执行每日路线
        self.log(f"\n[Phase 2] 执行 {len(DAILY_ROUTES)} 条每日路线")
        for route in DAILY_ROUTES:
            self.execute_route(route)

        # Phase 3: 执行每周路线
        self.log(f"\n[Phase 3] 执行 {len(WEEKLY_ROUTES)} 条每周路线")
        for route in WEEKLY_ROUTES:
            self.execute_route(route)

        # Phase 4: 回收
        self.log("\n[Phase 4] 返回世界地图")
        self.ensure_world_map()

        self._print_summary(start_time)

    def start_weekly_flow(self):
        """仅执行每周任务流程"""
        self.log("=" * 60)
        self.log("IEA 优化版 — 每周任务流程")
        self.log("=" * 60)

        start_time = time.time()

        if not self.ensure_world_map():
            self.log("ERROR: 无法进入游戏")
            return

        for route in WEEKLY_ROUTES:
            self.execute_route(route)

        self.ensure_world_map()
        self._print_summary(start_time)

    def _print_summary(self, start_time: float):
        elapsed = time.time() - start_time
        self.log(f"\n{'='*60}")
        self.log(f"流程完成! 耗时: {elapsed:.1f}s")
        self.log(f"  OCR 调用:   {self._stats['ocr_calls']}")
        self.log(f"  VLM 调用:   {self._stats['vlm_calls']}")
        self.log(f"  点击操作:   {self._stats['taps']}")
        self.log(f"  领取尝试:   {self._stats['claims_attempted']}")
        self.log(f"  领取成功:   {self._stats['claims_success']}")
        self.log(f"  路线完成:   {self._stats['routes_completed']}")
        self.log(f"{'='*60}")

    # ── 页面树增强 ──────────────────────────────────────────────

    def page_tree_to_dict(self) -> Dict:
        """输出可记录的页面树信息"""
        return {
            "context": {
                "game_mode": self._context.game_mode.value,
                "overlay": self._context.overlay.value,
                "on_world_map": self._context.on_world_map,
                "claim_available": self._context.claim_available,
            },
            "claim_locations": [
                {"x": x, "y": y, "label": lbl}
                for x, y, lbl in self._context.claim_locations
            ],
            "stats": dict(self._stats),
            "execution_log": self._execution_log[-100:],  # 最近 100 条
        }
