#!/usr/bin/env python3
"""
屏幕决策模块 - 基于 OCR 结果进行页面状态决策

从 IstinaEndfieldAssistant_Sight 迁移，用于替代 VLM 图像输入。
使用 MaaMCP OCR 快速检测屏幕状态（~1s），避免每次调用 VLM（~20-30s）
"""

import sys
import os
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field

from core.game_coords import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    TOP_BAR_Y_RANGE, OVERLAY_ROI,
    TOP_BAR_BUTTONS, KNOWN_COORDS,
    MODE_SWITCH_BUTTON,
    OVERLAY_KEYWORDS, CLAIM_KEYWORDS,
)


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

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于构建 LLM 提示词）"""
        return {
            "page_type": self.page_type,
            "confidence": self.confidence,
            "top_bar_visible": self.top_bar_visible,
            "top_bar_buttons": self.top_bar_buttons,
            "overlay_detected": self.overlay_detected,
            "overlay_texts": self.overlay_texts,
            "claim_buttons": [{"x": x, "y": y, "text": t} for x, y, t in self.claim_buttons],
            "interactive_elements": self.interactive_elements,
            "description": self.description,
        }

    def to_llm_prompt(self) -> str:
        """转换为 LLM 提示词格式"""
        lines = [
            f"页面类型：{self.page_type}",
            f"置信度：{self.confidence:.2f}",
            f"顶部栏可见：{'是' if self.top_bar_visible else '否'}",
        ]
        
        if self.top_bar_buttons:
            lines.append(f"检测到的按钮：{', '.join(self.top_bar_buttons)}")
        
        lines.append(f"右侧面板：{'已打开' if self.overlay_detected else '未打开'}")
        
        if self.overlay_texts:
            lines.append(f"面板内容：{', '.join(self.overlay_texts[:5])}")  # 限制长度
        
        if self.claim_buttons:
            lines.append(f"领取按钮：{len(self.claim_buttons)} 个")
            for x, y, text in self.claim_buttons:
                lines.append(f"  - '{text}' ({x}, {y})")
        
        if self.interactive_elements:
            lines.append(f"可交互元素:")
            for el in self.interactive_elements[:10]:  # 限制数量
                lines.append(f"  - {el.get('type', '元素')} \"{el.get('text', '')}\" ({el.get('x', 0)}, {el.get('y', 0)})")
        
        if self.description:
            lines.append(f"描述：{self.description}")
        
        return "\n".join(lines)


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
    """检测是否已登出（显示登出对话框）- MaaEnd 式设计"""
    # MaaEnd 式的登出对话框关键词（多语言）
    logout_keywords = [
        # 简体中文
        "登出", "退出", "登录界面", "超时", "重新登录", "会话过期", "自动登出",
        "长时间", "没有操作", "断开连接", "确认", "取消",
        # 繁体中文
        "登入介面", "超時", "重新登入", "會話過期",
        # 英文
        "logout", "log out", "login screen", "timeout", "session expired",
        "re-login", "disconnect",
        # 日文
        "画面に戻りますか", "ログアウト", "ログイン", "タイムアウト",
        # 韩文
        "나가시겠습니까", "로그아웃", "로그인", "시간초과"
    ]
    
    # 合并所有 OCR 文本
    texts = " ".join([e.get("text", "") for e in elements])
    
    # 检查关键词（不区分大小写）
    texts_lower = texts.lower()
    return any(kw.lower() in texts_lower for kw in logout_keywords)


def _check_world_map_topbar(elements: list) -> bool:
    """检测是否显示世界地图顶部栏（探索/返回/商店/活动等按钮）"""
    top_area = [e for e in elements if TOP_BAR_Y_RANGE[0] <= e["cy"] <= TOP_BAR_Y_RANGE[1]]
    top_texts = [e["text"] for e in top_area]
    has_exploration = any("探索" in t for t in top_texts)
    return has_exploration


def _detect_overlay(elements: list) -> Tuple[bool, list]:
    """检测右侧任务面板覆盖层是否打开"""
    overlay_area = _text_in_roi(elements, OVERLAY_ROI)
    if not overlay_area:
        return False, []

    keyword_matches = _find_keyword_matches(overlay_area, OVERLAY_KEYWORDS)
    if keyword_matches:
        return True, keyword_matches

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

    # 收集可交互元素
    for e in elements:
        if e["score"] > 0.5 and e["w"] > 20:
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
        state.description = f"世界地图 (顶部栏：{', '.join(state.top_bar_buttons) or '无'})"
    elif len(elements) >= 5 and any(e["w"] > 100 for e in elements):
        state.page_type = "sub_page"
        keywords_found = _find_keyword_matches(elements, OVERLAY_KEYWORDS)
        if keywords_found:
            state.description = f"子页面 (含 {len(keywords_found)} 个任务关键词)"
        else:
            state.description = f"子页面 ({len(elements)} 个文本元素)"
    else:
        state.page_type = "other"
        state.description = f"其他页面 ({len(elements)} 个文本)"

    state.confidence = min(1.0, len(elements) / 20)
    return state


# ── 导航计划生成 ───────────────────────────────────────────────────

def generate_navigation_plan(state: ScreenState) -> List[Dict]:
    """
    根据当前屏幕状态生成导航计划。

    Args:
        state: 屏幕状态检测结果

    Returns:
        list: 操作步骤列表
    """
    plan = []

    if state.page_type == "title":
        plan.append({
            "type": "tap",
            "params": {"x": 640, "y": 360},
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
        if state.claim_buttons:
            for cx, cy, label in state.claim_buttons:
                plan.append({
                    "type": "tap",
                    "params": {"x": cx, "y": cy, "label": label},
                    "description": f"点击领取按钮：{label}"
                })
                plan.append({
                    "type": "wait",
                    "params": {"duration": 5},
                    "description": "等待领取完成"
                })
        else:
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

    elif state.page_type == "sub_page":
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


class ScreenDecider:
    """屏幕决策器 - 封装 OCR 决策逻辑"""

    def __init__(self):
        self.logger = __import__("logging").getLogger(__name__)

    def detect_screen_state(self, ocr_results: list) -> ScreenState:
        """检测屏幕状态"""
        return detect_screen_state(ocr_results)

    def generate_plan(self, state: ScreenState) -> List[Dict]:
        """生成导航计划"""
        return generate_navigation_plan(state)

    def decide_action(self, ocr_results: list) -> Tuple[ScreenState, List[Dict]]:
        """
        一站式决策：OCR 结果 → 状态检测 → 导航计划

        Returns:
            (ScreenState, navigation_plan)
        """
        state = self.detect_screen_state(ocr_results)
        plan = self.generate_plan(state)
        return state, plan


# ── 独立测试 ──────────────────────────────────────────────────────

def main():
    """独立测试模式"""
    print("=" * 60)
    print("OCR 决策模块 - 测试")
    print("=" * 60)

    # 模拟 OCR 结果
    mock_ocr = [
        {"text": "探索", "box": [30, 10, 60, 30], "score": 0.98},
        {"text": "每日任务", "box": [970, 80, 100, 40], "score": 0.95},
        {"text": "领取", "box": [1020, 300, 60, 30], "score": 0.92},
        {"text": "一键领取", "box": [1000, 350, 100, 40], "score": 0.96},
    ]

    decider = ScreenDecider()
    state, plan = decider.decide_action(mock_ocr)

    print(f"\n页面类型：{state.page_type}")
    print(f"描述：{state.description}")
    print(f"领取按钮：{len(state.claim_buttons)} 个")
    print(f"\n导航计划 ({len(plan)} 步):")
    for i, step in enumerate(plan, 1):
        print(f"  {i}. {step['type']}: {step['description']}")


if __name__ == "__main__":
    main()
