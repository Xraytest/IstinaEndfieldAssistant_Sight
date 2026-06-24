"""
Scenario CLI 模块 — 场景采集、探索导航、快速任务流

用法（通过 istina.py）:
  istina.py scene capture [--count 20]           # 轻量场景采集
  istina.py scene nav <page>                      # 导航到页面
  istina.py scene analyze [--instruction ...]     # VLM 分析画面
  istina.py scene ocr                             # OCR 检测画面

独立运行:
  python -m src.cli.scenario_cli capture --count 5
"""

import sys, os, json, time, hashlib, random, re, argparse
from typing import Optional, Dict, Any
from core.foundation.paths import ensure_src_path, get_project_root
from core.foundation.logger import get_logger, LogCategory

_logger = get_logger()

ensure_src_path(__file__)
PROJECT_ROOT = get_project_root(__file__)


def _get_adb():
    from core.capability.adb_utils import ADB
    return ADB()


def _get_touch_manager():
    """获取 TouchManager 实例（用于 CLI 触控操作）"""
    try:
        from core.capability.device.touch.touch_manager import TouchManager
        from core.capability.device.touch.maafw_touch_adapter import MaaFwTouchConfig
        tm = TouchManager()
        config = MaaFwTouchConfig(
            adb_path=os.path.join(PROJECT_ROOT, "3rd-part", "adb", "adb.exe"),
            address="localhost:16512",
        )
        if tm.connect_android(
            adb_path=config.adb_path,
            address=config.address,
            screencap_methods=config.screencap_methods,
            input_methods=config.input_methods,
            config=config.config
        ):
            return tm
    except Exception as e:
        _logger.warning(LogCategory.ADB, f"TouchManager 初始化失败：{e}")
        return None


def _get_inference_manager():
    """获取 InferenceManager 实例（用于本地 VLM 推理）"""
    try:
        from core.foundation.logger import init_logger
        init_logger()
        from core.local_inference.inference_manager import InferenceManager

        # 加载配置
        cfg_path = os.path.join(PROJECT_ROOT, "config", "client_config.json")
        config = {}
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                config = json.load(f)

        im = InferenceManager(config_path=cfg_path)
        im.initialize()
        return im
    except Exception as e:
        _logger.warning(LogCategory.ADB, f"InferenceManager 初始化失败：{e}")
        return None


# ── 动作集 ──────────────────────────────────────────────────
ACTIONS = {
    "tap_random": lambda tm: (
        tm.safe_press(random.randint(100, 1100), random.randint(100, 600)),
        f"tap (随机)",
    ),
    "swipe_left": lambda tm: (
        tm.safe_swipe(900, 360, 300, 360, 600),
        "swipe_left",
    ),
    "swipe_right": lambda tm: (
        tm.safe_swipe(300, 360, 900, 360, 600),
        "swipe_right",
    ),
    "swipe_up": lambda tm: (
        tm.safe_swipe(640, 500, 640, 200, 600),
        "swipe_up",
    ),
    "swipe_down": lambda tm: (
        tm.safe_swipe(640, 200, 640, 500, 600),
        "swipe_down",
    ),
    "back": lambda tm: (
        tm.execute_tool_call("pipeline_task", {"entry": "Back"}),
        "BACK",
    ),
    "home": lambda tm: (
        tm.execute_tool_call("pipeline_task", {"entry": "Home"}),
        "HOME",
    ),
}


def cmd_capture(args) -> int:
    """轻量场景采集（随机探索 + 截图）"""
    adb = _get_adb()
    tm = _get_touch_manager()
    count = args.count or 10
    actions = args.actions or ["swipe_left", "swipe_right", "tap_random", "wait"]
    interval = args.interval or 2

    session_dir = os.path.join(
        PROJECT_ROOT, "cache",
        f"scene_{time.strftime('%Y%m%d_%H%M%S')}"
    )
    os.makedirs(session_dir, exist_ok=True)

    print(f"[scene] 采集目录：{session_dir}")
    print(f"[scene] 目标：{count} 张，动作：{actions}")

    last_hash = None
    captured = 0
    attempts = 0
    max_attempts = count * 3

    while captured < count and attempts < max_attempts:
        attempts += 1

        # 截图
        from core.capability.adb_utils import adb_screencap_unique
        img, h = adb_screencap_unique(last_hash=last_hash)
        if img is not None:
            last_hash = h
            path = os.path.join(session_dir, f"shot_{captured+1:03d}_{time.strftime('%H%M%S')}_{h[:8]}.png")
            with open(path, "wb") as f:
                f.write(img)
            captured += 1
            print(f"  [{captured}/{count}] {os.path.basename(path)} ({len(img)//1024}KB)")

        if captured >= count:
            break

        # 执行动作
        action_name = random.choice(actions)
        if action_name == "wait":
            t = random.uniform(1, interval)
            print(f"    -> wait {t:.1f}s")
            time.sleep(t)
        elif action_name in ACTIONS and tm:
            fn = ACTIONS[action_name]
            _, desc = fn(tm)
            print(f"    -> {desc}")
        elif action_name in ACTIONS:
            print(f"    -> 跳过 {action_name}（触控管理器不可用）")
        else:
            print(f"    -> unknown action: {action_name}")

        time.sleep(interval)

    print(f"[scene] 完成：{captured} 张截图 (尝试 {attempts} 次)")
    return 0 if captured > 0 else 1


def cmd_nav(args) -> int:
    """导航到页面"""
    from core.foundation.game_coords import NAVIGATION_MAP, PAGE_TYPE_KEYWORDS

    tm = _get_touch_manager()
    if not tm:
        print("[nav] 触控管理器初始化失败（需要 MaaFw 支持）")
        return 1

    target = args.target

    # 1. 直接匹配导航映射
    if target in NAVIGATION_MAP:
        nav = NAVIGATION_MAP[target]
        action = nav.get("action")
        desc = nav.get("desc", target)
        print(f"[nav] {desc}")

        if action == "click":
            coords = nav.get("coords")
            if coords:
                tm.safe_press(*coords)
                print(f"  -> 点击 {coords}")
        elif action == "wait":
            dur = nav.get("duration", 5)
            print(f"  -> 等待 {dur}s")
            time.sleep(dur)
        elif action == "claim":
            for cx, cy in nav.get("claim_coords", []):
                print(f"  -> 尝试点击 ({cx}, {cy})")
                tm.safe_press(cx, cy)
                time.sleep(1)
        else:
            print(f"  -> 未知动作：{action}")
            return 1
        return 0

    # 2. 关键词匹配页面类型
    for page_type, keywords in PAGE_TYPE_KEYWORDS.items():
        if any(kw in target for kw in keywords):
            print(f"[nav] 目标 '{target}' 匹配页面类型 '{page_type}'")
            return 0

    print(f"[nav] 未知目标：{target}")
    print(f"  可用：{list(NAVIGATION_MAP.keys())}")
    return 1


def cmd_analyze(args) -> int:
    """VLM 分析画面（使用本地推理）"""
    adb = _get_adb()
    im = _get_inference_manager()

    if not im:
        print('{"error":"InferenceManager 初始化失败"}')
        return 1

    img = adb.screencap(dedup=False)
    if img is None:
        print('{"error":"截图失败"}')
        return 1

    from core.capability.vlm import vlm_analyze, VLMOptions
    opts = VLMOptions(
        model_tag=args.model or "exploration_deep",
        timeout=args.timeout or 120,
        system_prompt=args.system_prompt or "你是终末地 UI 分析器。输出 JSON 格式。",
    )

    instruction = args.instruction or "识别当前游戏画面中的所有 UI 元素。JSON 输出。"
    resp = vlm_analyze(img, instruction=instruction, opts=opts, inference_manager=im)

    if resp:
        reply = resp.get("reply", resp.get("result", {}))
        print(json.dumps(reply, ensure_ascii=False, indent=2))
    else:
        print('{"error":"VLM 无响应"}')
        return 1
    return 0


def cmd_ocr(args) -> int:
    """快速 OCR 检测画面（通过本地引擎）"""
    try:
        from core.capability.adb_utils import ADB
        adb = ADB()
        img = adb.screencap(dedup=False)
        if img is None:
            print('{"error":"截图失败"}')
            return 1

        # 尝试使用本地 OCR
        print(f"截图大小：{len(img)//1024}KB")
        print(f"截图哈希：{hashlib.md5(img).hexdigest()[:8]}")

        # 关键词匹配（简单版）
        from core.foundation.game_coords import OVERLAY_KEYWORDS
        detected = []
        # 这里可以调用 MaaMCP OCR 或本地 OCR
        # 目前仅输出截图信息
        print(json.dumps({
            "screenshot_size_bytes": len(img),
            "screenshot_hash": hashlib.md5(img).hexdigest()[:8],
            "overlay_keywords": OVERLAY_KEYWORDS[:10],
            "note": "完整 OCR 需要 MaaMCP 支持",
        }, ensure_ascii=False, indent=2))
        return 0

    except Exception as e:
        print(f'{{"error":"OCR 失败：{e}"}}')
        return 1


# ── 独立入口 ─────────────────────────────────────────────────
def main(args_list: list = None):
    parser = argparse.ArgumentParser(description="Scenario CLI 模块")
    sub = parser.add_subparsers(dest="command")

    p_cap = sub.add_parser("capture", help="轻量场景采集")
    p_cap.add_argument("--count", type=int, default=10, help="目标截图数")
    p_cap.add_argument("--actions", nargs="+", help="动作列表")
    p_cap.add_argument("--interval", type=float, default=2, help="动作间隔")

    p_nav = sub.add_parser("nav", help="导航到页面")
    p_nav.add_argument("target", help="目标页面名")

    p_ana = sub.add_parser("analyze", help="VLM 分析画面")
    p_ana.add_argument("--model", help="模型标签")
    p_ana.add_argument("--instruction", "-i", default="", help="自定义指令")
    p_ana.add_argument("--system-prompt", help="系统提示词")
    p_ana.add_argument("--timeout", type=int, default=120)

    sub.add_parser("ocr", help="OCR 检测画面")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    cmds = {
        "capture": cmd_capture,
        "nav": cmd_nav,
        "analyze": cmd_analyze,
        "ocr": cmd_ocr,
    }
    return cmds[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
