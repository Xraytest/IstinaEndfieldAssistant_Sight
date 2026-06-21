#!/usr/bin/env python3
"""
IEA OCR/VLM 选择机制 — 自适应当前游戏状态决策模块。

核心理念：
  1. OCR 优先：使用 MaaMCP OCR 快速检测屏幕状态（~1s），避免每次调用 VLM（~20-30s）
  2. 分级决策：OCR → 小模型 VLM → 大模型 VLM，按需升级
  3. 右侧面板检测：通过 OCR 检测任务面板覆盖层（而非依赖 VLM 的 page_type）
  4. 可集成到 MaaPipeline：生成 Pipeline JSON 供 run_pipeline 使用

用法：
  python scripts/ocr_decision_module.py                    # 独立测试
  python scripts/ocr_decision_module.py --once             # 单次检测

  作为模块导入:
    from scripts.ocr_decision_module import ScreenDecider
    decider = ScreenDecider()
    state = decider.detect_screen_state(ocr_results)
    if state == "world_map_with_overlay":
        # 面板已打开，进行领取操作
"""

import json, time, os, sys, re
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field


# ── 常量定义 ──────────────────────────────────────────────────────

# 屏幕分辨率（MaaMCP 截图坐标空间）
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720

# 顶部栏区域（基于实际 OCR 检测）
TOP_BAR_Y_RANGE = (10, 80)

# 右侧面板覆盖层 ROI（Overlay Panel Region）
# 当面板打开时，右侧会出现深色半透明区域，x > 950 左右
OVERLAY_ROI = {
    "x_start": 950,    # 面板左边缘
    "x_end": 1280,     # 右边缘
    "y_start": 60,     # 面板顶部
    "y_end": 700,      # 面板底部
}

# 顶部栏按钮预期位置（1280x720 坐标空间，基于实际 OCR 检测）
# Endfield 顶部栏图标从右到左排列，许多是纯图标无文字
TOP_BAR_BUTTONS = {
    "exploration":  {"label": "探索",       "x_range": (30, 120),   "y_range": (10, 45)},
    "back":         {"label": "返回",       "x_range": (420, 480),  "y_range": (10, 45)},
    "shop":         {"label": "商店",       "x_range": (450, 510),  "y_range": (10, 45)},
    "event":        {"label": "活动",       "x_range": (480, 540),  "y_range": (10, 45)},
    "signin":       {"label": "签到",       "x_range": (510, 570),  "y_range": (10, 45)},
    "tasks":        {"label": "任务",       "x_range": (540, 600),  "y_range": (10, 45)},
    "inventory":    {"label": "背包",       "x_range": (570, 630),  "y_range": (10, 45)},
    "settings":     {"label": "设置",       "x_range": (630, 690),  "y_range": (10, 45)},
}

# ═══════════════════════════════════════════════════════════════════
# 游戏导航知识库 — 由实际探索积累
# ═══════════════════════════════════════════════════════════════════

# 已知的功能坐标（1280x720 MaaMCP 空间）
KNOWN_COORDS = {
    # 顶部栏（仅当在主世界地图时可用）
    "tasks_button":     (570, 22),   # 任务按钮
    "event_button":     (510, 22),   # 活动按钮
    "back_button":      (450, 22),   # 返回按钮
    "close_overlay_x":  (1170, 22),  # 关闭面板 X 按钮

    # 签到页面
    "claim_all":        (1035, 323), # 一键领取（已验证成功）
    "reward_confirm":   (640, 500),  # 奖励确认弹窗点击位置

    # 活动中心
    "signin_entry":     (112, 296),  # 签到入口（活动中心左侧列表）

    # 退出游戏对话框
    "exit_confirm":     (793, 478),  # "确认" 退出
    "exit_cancel":      (556, 478),  # "取消" 退出
}

# 游戏模式切换
# Endfield 有两种主要游戏模式，通过左上角按钮切换：
MODE_SWITCH_BUTTON = (75, 21)  # 在 "探索" 和 "工业" 之间切换

# 页面类型 → 导航建议映射
NAVIGATION_MAP = {
    # (当前模式, 检测到的特征) → 操作
    "title": {
        "action": "click",
        "coords": (640, 360),
        "next": "loading",
        "desc": "标题画面 → 点击任意位置继续",
    },
    "loading": {
        "action": "wait",
        "duration": 15,
        "next": "sub_page_or_world",
        "desc": "加载中 → 等待",
    },
    "sub_page_signin": {
        "action": "claim",
        "claim_coords": [(1035, 323), (914, 586), (1043, 586)],
        "next": "back_to_world",
        "desc": "签到页面 → 领取奖励",
    },
    "mode_exploration": {
        "action": "switch_mode_or_back",
        "desc": "探索模式 → 按返回或切换模式到主世界",
    },
    "mode_industry": {
        "action": "switch_mode",
        "coords": MODE_SWITCH_BUTTON,
        "next": "mode_exploration",
        "desc": "工业模式 → 切换到探索模式",
    },
    "exit_dialog": {
        "action": "click",
        "coords": KNOWN_COORDS["exit_cancel"],
        "desc": "退出游戏对话框 → 取消",
    },
}

# 任务面板内可能出现的文本关键词
OVERLAY_KEYWORDS = [
    "每日", "每周", "任务", "日程", "签到", "作战汇报",
    "领取", "收取", "一键领取", "完成", "提交", "领奖",
    "进行中", "已完成", "可领取", "奖励",
    "活跃度", "经验", "信用", "合成玉",
]

# 领取按钮关键词
CLAIM_KEYWORDS = ["领取", "收取", "一键领取", "完成", "提交", "领奖", "CLAIM", "collect"]


# ── 状态定义 ──────────────────────────────────────────────────────

@dataclass
class ScreenState:
    """屏幕状态检测结果"""
    page_type: str = "unknown"           # world_map / world_map_with_overlay / dialog / loading / login / title / other
    confidence: float = 0.0
    top_bar_visible: bool = False
    top_bar_buttons: List[str] = field(default_factory=list)
    overlay_detected: bool = False
    overlay_texts: List[str] = field(default_factory=list)
    claim_buttons: List[Tuple[int, int, str]] = field(default_factory=list)
    interactive_elements: List[Dict] = field(default_factory=list)
    description: str = ""


# ── 检测函数 ──────────────────────────────────────────────────────

def _normalize_ocr(ocr_results: list) -> list:
    """归一化 OCR 结果，确保每个元素有标准字段"""
    normalized = []
    for item in ocr_results:
        box = item.get("box", [0, 0, 0, 0])
        text = item.get("text", "").strip()
        score = item.get("score", 0)
        if len(box) == 4 and text and score > 0.3:
            normalized.append({
                "text": text,
                "x": box[0],
                "y": box[1],
                "w": box[2],
                "h": box[3],
                "score": score,
                "cx": box[0] + box[2] // 2,
                "cy": box[1] + box[3] // 2,
            })
    return normalized


def _text_in_roi(elements: list, roi: dict) -> list:
    """筛选在 ROI 区域内的 OCR 文本"""
    x_start, x_end = roi.get("x_start", 0), roi.get("x_end", SCREEN_WIDTH)
    y_start, y_end = roi.get("y_start", 0), roi.get("y_end", SCREEN_HEIGHT)
    return [e for e in elements
            if x_start <= e["cx"] <= x_end and y_start <= e["cy"] <= y_end]


def _find_keyword_matches(elements: list, keywords: list) -> list:
    """在 OCR 文本中查找关键词"""
    matches = []
    for e in elements:
        for kw in keywords:
            if kw in e["text"]:
                matches.append(e)
                break
    return matches


def _find_button_at(elements: list, x_range: tuple, y_range: tuple) -> Optional[Dict]:
    """查找在指定坐标范围内的按钮文本"""
    for e in elements:
        if x_range[0] <= e["cx"] <= x_range[1] and y_range[0] <= e["cy"] <= y_range[1]:
            return e
    return None


def _get_text_at(elements: list, x: int, y: int, radius: int = 30) -> Optional[str]:
    """获取指定坐标附近 OCR 文本"""
    for e in elements:
        if abs(e["cx"] - x) <= radius and abs(e["cy"] - y) <= radius:
            return e["text"]
    return None


# ── 页面类型检测 ──────────────────────────────────────────────────

def _check_title_screen(elements: list) -> bool:
    """检测是否是标题/登录画面"""
    texts = [e["text"] for e in elements]
    keywords_found = sum(1 for t in texts if any(k in t for k in [
        "明日方舟", "终末地", "点击任意位置继续", "账户登出",
        "公告", "设置", "修复", "适龄提示"
    ]))
    return keywords_found >= 3


def _check_loading_screen(elements: list) -> bool:
    """检测是否是加载画面"""
    texts = [e["text"] for e in elements]
    has_loading = any("LOADING" in t.upper() or "加载" in t for t in texts)
    has_tips = any("TIPS" in t.upper() or "提示" in t for t in texts)
    has_uid = any("UID" in t.upper() for t in texts)
    has_version = any("REL_" in t for t in texts)
    return (has_loading and has_tips) or (has_loading and has_uid and not has_version)


def _check_logged_out_screen(elements: list) -> bool:
    """检测是否已登出（显示登出对话框）"""
    texts = " ".join([e["text"] for e in elements])
    return any(k in texts for k in ["登出", "超时", "重新登录", "会话过期"])


def _check_world_map_topbar(elements: list) -> bool:
    """检测是否显示世界地图顶部栏（探索/返回/商店/活动等按钮）"""
    # 检查顶部区域有没有"探索"文本
    top_area = [e for e in elements if TOP_BAR_Y_RANGE[0] <= e["cy"] <= TOP_BAR_Y_RANGE[1]]
    top_texts = [e["text"] for e in top_area]

    # 主世界地图特征：有"探索"在左上角
    has_exploration = any("探索" in t for t in top_texts)
    return has_exploration


def _detect_overlay(elements: list) -> Tuple[bool, list]:
    """检测右侧任务面板覆盖层是否打开"""
    # 面板区域内的文本
    overlay_area = _text_in_roi(elements, OVERLAY_ROI)
    if not overlay_area:
        return False, []

    # 查找任务关键词
    keyword_matches = _find_keyword_matches(overlay_area, OVERLAY_KEYWORDS)
    if keyword_matches:
        return True, keyword_matches

    # 如果面板区域有多个文本元素（>3），也可能表示面板打开
    if len(overlay_area) >= 3:
        return True, overlay_area

    return False, []


def _find_claim_buttons(elements: list) -> List[Tuple[int, int, str]]:
    """在 OCR 结果中查找所有领取按钮"""
    buttons = []
    for e in elements:
        for kw in CLAIM_KEYWORDS:
            if kw in e["text"]:
                buttons.append((e["cx"], e["cy"], e["text"]))
                break
    return buttons


# ── 主决策函数 ────────────────────────────────────────────────────

def detect_screen_state(ocr_results: list) -> ScreenState:
    """
    根据 OCR 结果检测当前屏幕状态。

    Args:
        ocr_results: MaaMCP OCR 返回的结果列表

    Returns:
        ScreenState: 屏幕状态检测结果
    """
    if not ocr_results:
        return ScreenState(description="OCR 无结果")

    elements = _normalize_ocr(ocr_results)
    if not elements:
        return ScreenState(description="OCR 无有效文本")

    state = ScreenState()
    state.top_bar_visible = _check_world_map_topbar(elements)

    # 检测顶部栏按钮
    if state.top_bar_visible:
        for name, cfg in TOP_BAR_BUTTONS.items():
            btn = _find_button_at(elements, cfg["x_range"], cfg["y_range"])
            if btn:
                state.top_bar_buttons.append(name)

    # 检测右侧面板覆盖层
    overlay_detected, overlay_elems = _detect_overlay(elements)
    state.overlay_detected = overlay_detected
    if overlay_detected:
        state.overlay_texts = [e["text"] for e in overlay_elems]

    # 检测领取按钮
    state.claim_buttons = _find_claim_buttons(elements)

    # 收集可交互元素（在顶部栏和面板区域的非噪声文本）
    for e in elements:
        if e["score"] > 0.5 and e["w"] > 20:  # 排除过小的噪声
            state.interactive_elements.append(e)

    # ── 确定页面类型 ──
    if _check_title_screen(elements):
        state.page_type = "title"
        state.description = "标题/登录画面"
    elif _check_loading_screen(elements):
        state.page_type = "loading"
        state.description = "游戏加载中"
    elif _check_logged_out_screen(elements):
        state.page_type = "logout_dialog"
        state.description = "登出/超时对话框"
    elif state.overlay_detected and state.top_bar_visible:
        state.page_type = "world_map_with_overlay"
        state.description = f"世界地图 + 右侧面板 (检测到 {len(state.overlay_texts)} 个面板文本)"
        if state.claim_buttons:
            state.description += f"，{len(state.claim_buttons)} 个领取按钮"
    elif state.top_bar_visible:
        state.page_type = "world_map"
        state.description = f"世界地图 (顶部栏: {', '.join(state.top_bar_buttons) or '无'})"
    elif len(elements) >= 5 and any(e["w"] > 100 for e in elements):
        # 大量文本但没有顶部栏 → 可能是任务/活动页面
        state.page_type = "sub_page"
        keywords_found = _find_keyword_matches(elements, OVERLAY_KEYWORDS)
        if keywords_found:
            state.description = f"子页面 (含 {len(keywords_found)} 个任务关键词)"
        else:
            state.description = f"子页面 ({len(elements)} 个文本元素)"
    else:
        state.page_type = "other"
        state.description = f"其他页面 ({len(elements)} 个文本)"

    state.confidence = min(1.0, len(elements) / 20)  # 文本越多置信度越高
    return state


# ── Pipeline JSON 生成 ────────────────────────────────────────────

def generate_overlay_pipeline(claim_coords: List[Tuple[int, int, str]] = None) -> dict:
    """
    生成检测和点击任务面板覆盖层的 Pipeline JSON。

    这个 Pipeline:
    1. 点击"任务"按钮打开面板
    2. OCR 检测右侧面板区域是否有任务文本
    3. 如果有面板 → 查找领取按钮并点击
    4. 关闭面板返回

    Returns:
        dict: Pipeline JSON
    """
    pipeline = {}

    # ── 入口：打开任务面板 ──
    pipeline["OpenTaskPanel"] = {
        "recognition": "DirectHit",
        "action": "Click",
        "target": [810, 25],  # 任务按钮坐标 (1280x720 空间)
        "post_delay": 3000,   # 等待面板动画
        "next": ["DetectOverlay"]
    }

    # ── 检测面板是否打开 ──
    pipeline["DetectOverlay"] = {
        "recognition": "OCR",
        "expected": "每日|每周|任务|日程|签到|领取",
        "roi": [950, 60, 330, 640],  # 右侧面板区域
        "action": "DoNothing",
        "next": ["SwipePanelDown", "CloseOverlay"]
    }

    # ── 向下滑动面板 ──
    pipeline["SwipePanelDown"] = {
        "recognition": "DirectHit",
        "action": "Swipe",
        "begin": [1100, 400],
        "end": [1100, 600],
        "duration": 500,
        "post_delay": 2000,
        "next": ["ClaimRewards", "BruteForceClaim"]
    }

    # ── 领取奖励 ──
    pipeline["ClaimRewards"] = {
        "recognition": "OCR",
        "expected": "领取|收取|一键领取|完成|提交|领奖",
        "roi": [950, 60, 330, 640],
        "action": "Click",
        "target": True,
        "post_delay": 5000,
        "next": ["ClaimRewards", "SwipePanelUp"]  # 可能还有更多奖励
    }

    # ── 暴力点击领取区域 ──
    pipeline["BruteForceClaim"] = {
        "recognition": "DirectHit",
        "action": "DoNothing",
        "next": []  # 如果要用暴力点击，在外部脚本中处理
    }

    # ── 上滑回到面板顶部 ──
    pipeline["SwipePanelUp"] = {
        "recognition": "DirectHit",
        "action": "Swipe",
        "begin": [1100, 600],
        "end": [1100, 300],
        "duration": 500,
        "post_delay": 1000,
        "next": ["CloseOverlay"]
    }

    # ── 关闭面板 ──
    pipeline["CloseOverlay"] = {
        "recognition": "DirectHit",
        "action": "ClickKey",
        "key": 4,  # Android 返回键
        "post_delay": 2000,
        "next": []
    }

    return pipeline


# ── 主流程 ────────────────────────────────────────────────────────

def generate_navigation_plan(state: ScreenState) -> List[Dict]:
    """
    根据当前屏幕状态生成导航计划。

    Args:
        state: 屏幕状态检测结果

    Returns:
        list: 操作步骤列表，每步包含 type/params/description
    """
    plan = []

    if state.page_type == "title":
        plan.append({
            "type": "tap",
            "params": {"x": 640, "y": 360},  # 点击任意位置继续
            "description": "点击标题画面进入游戏"
        })
        plan.append({
            "type": "wait",
            "params": {"duration": 10},
            "description": "等待加载"
        })

    elif state.page_type == "loading":
        plan.append({
            "type": "wait",
            "params": {"duration": 10},
            "description": "等待加载完成"
        })

    elif state.page_type == "logout_dialog":
        plan.append({
            "type": "tap",
            "params": {"label": "confirm"},
            "description": "确认重新登录"
        })

    elif state.page_type == "world_map":
        # 在世界地图 → 打开任务面板（使用 MaaMCP 1280x720 坐标）
        # 顶部栏按钮很多是纯图标，用已知坐标点击
        plan.append({
            "type": "tap",
            "params": {"x": KNOWN_COORDS["tasks_button"][0],
                       "y": KNOWN_COORDS["tasks_button"][1],
                       "label": "任务按钮"},
            "description": "点击顶部任务按钮打开面板"
        })
        plan.append({
            "type": "wait",
            "params": {"duration": 5},
            "description": "等待面板打开"
        })

    elif state.page_type == "world_map_with_overlay":
        # 面板已打开 → 尝试领取
        if state.claim_buttons:
            for cx, cy, label in state.claim_buttons:
                plan.append({
                    "type": "tap",
                    "params": {"x": cx, "y": cy, "label": label},
                    "description": f"点击领取按钮: {label}"
                })
                plan.append({
                    "type": "wait",
                    "params": {"duration": 5},
                    "description": "等待领取完成"
                })
        else:
            # 面板已打开但没有领取按钮 → 滑动找更多内容
            plan.append({
                "type": "swipe",
                "params": {"x1": 1100, "y1": 300, "x2": 1100, "y2": 600, "duration": 500},
                "description": "向下滑动面板"
            })
            plan.append({
                "type": "wait",
                "params": {"duration": 3},
                "description": "等待滑动完成"
            })
            # 滑动后再检测
            plan.append({
                "type": "detect",
                "description": "重新检测面板内容"
            })

        # 导航计划不自动关闭面板（留给后续步骤处理）

    elif state.page_type == "sub_page":
        # 在子页面 → 先返回
        plan.append({
            "type": "back",
            "description": "返回上一级"
        })
        plan.append({
            "type": "wait",
            "params": {"duration": 3},
            "description": "等待返回完成"
        })

    return plan


# ── 独立运行 ──────────────────────────────────────────────────────

def main():
    """独立测试：连接到 MaaMCP 并检测当前屏幕"""
    print("=" * 60)
    print("IEA OCR 决策模块 — 屏幕状态检测")
    print("=" * 60)

    # 尝试通过 MaaMCP OCR 获取结果
    # 注：在独立运行时，直接通过 ADB 截图并用本地 OCR
    try:
        import subprocess
        import base64
        adb = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                          "3rd-party", "adb", "adb.exe")
        dev = "localhost:16512"

        r = subprocess.run([adb, "-s", dev, "exec-out", "screencap", "-p"],
                          capture_output=True, timeout=15)
        if r.returncode != 0:
            print("ADB 截图失败")
            return

        print(f"截图: {len(r.stdout)} bytes")

        # 模拟 OCR 结果（在实际使用中由 MaaMCP OCR 提供）
        # 这里我们尝试用 ADB + 简单文本检测
        # 安装 pytesseract 的话可以本地 OCR
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(r.stdout))
            print(f"图像尺寸: {img.size}")

            # 检查右侧区域亮度变化（作为面板是否打开的指标）
            right_strip = img.crop((950, 60, 1280, 700))
            avg_brightness = sum(
                sum(right_strip.getpixel((x, y))[:3]) / 3
                for x in range(0, right_strip.width, 10)
                for y in range(0, right_strip.height, 10)
            ) / max(1, (right_strip.width // 10) * (right_strip.height // 10))

            print(f"右侧面板区域平均亮度: {avg_brightness:.1f}")
            print(f"(亮度 < 100 = 深色面板可能打开)")
        except ImportError:
            print("PIL 不可用，跳过图像分析")

        print()
        print("使用方法:")
        print("  将此模块集成到脚本中:")
        print("    from scripts.ocr_decision_module import detect_screen_state")
        print("    state = detect_screen_state(ocr_results)")
        print("    plan = generate_navigation_plan(state)")
        print()
        print("  Pipeline JSON 保存:")
        print("    pipeline = generate_overlay_pipeline()")
        print("    with open('overlay_pipeline.json', 'w') as f:")
        print("        json.dump(pipeline, f, indent=2)")

    except Exception as e:
        print(f"检测异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 测试模式
    if "--once" in sys.argv:
        # 单一检测模式
        import subprocess, base64
        adb = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                          "3rd-party", "adb", "adb.exe")
        dev = "localhost:16512"
        r = subprocess.run([adb, "-s", dev, "exec-out", "screencap", "-p"],
                          capture_output=True, timeout=15)
        if r.returncode == 0:
            print(f"截图: {len(r.stdout)} bytes")
            print("需通过 MaaMCP OCR 获取文本结果后再调用 detect_screen_state()")
    else:
        main()
