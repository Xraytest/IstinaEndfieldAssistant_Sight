"""
IEA 游戏坐标与导航常量

集中管理《明日方舟：终末地》所有已知坐标、页面布局参数和导航规则。
坐标空间：1280x720 (MaaMCP)，ADB 调用内部自动映射。

用法:
  from core.foundation.game_data import Coords, NAVIGATION_MAP, OVERLAY_KEYWORDS
  tap_x, tap_y = Coords.tasks_button
"""

from typing import Dict, Tuple, List, Any


# ── 屏幕参数 ──────────────────────────────────────────────────────
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
ADB_WIDTH = 1080   # ADB 竖屏宽（用于坐标映射）
ADB_HEIGHT = 1920   # ADB 竖屏高

TOP_BAR_Y_RANGE = (10, 80)
OVERLAY_ROI = {"x_start": 950, "x_end": 1280, "y_start": 60, "y_end": 700}

# 右侧面板覆盖层 ROI（tuple 格式，供 OCR 扫描器使用）
OVERLAY_ROI_TUPLE: Tuple[int, int, int, int] = (950, 60, 330, 640)  # x, y, w, h


class Coords:
    """游戏内已知功能坐标（1280x720 MaaMCP 空间）"""

    # ── 顶部栏按钮 ──
    tasks_button: Tuple[int, int] = (570, 22)      # 任务按钮
    event_button: Tuple[int, int] = (510, 22)      # 活动按钮
    back_button: Tuple[int, int] = (450, 22)       # 返回按钮
    close_overlay_x: Tuple[int, int] = (1170, 22)  # 关闭面板 X 按钮
    shop_button: Tuple[int, int] = (480, 22)       # 商店
    signin_tab: Tuple[int, int] = (525, 22)        # 签到标签
    inventory_button: Tuple[int, int] = (585, 22)  # 背包
    settings_button: Tuple[int, int] = (645, 22)   # 设置

    # ── 游戏模式 ──
    mode_switch: Tuple[int, int] = (75, 21)        # 探索/工业模式切换

    # ── 签到页面 ──
    claim_all: Tuple[int, int] = (1035, 323)       # 一键领取
    reward_confirm: Tuple[int, int] = (640, 500)   # 奖励确认弹窗

    # ── 活动中心 ──
    signin_entry: Tuple[int, int] = (112, 296)     # 签到入口（左侧列表）

    # ── 退出对话框 ──
    exit_confirm: Tuple[int, int] = (793, 478)     # 确认退出
    exit_cancel: Tuple[int, int] = (556, 478)      # 取消退出

    # ── 实体采集 ──
    title_click: Tuple[int, int] = (640, 360)      # 标题画面"点击任意位置继续"

    # ── 探索常用 ──
    map_center: Tuple[int, int] = (640, 360)       # 地图中心
    swipe_area_left: Tuple[int, int] = (200, 360)  # 滑动起点（向左划）
    swipe_area_right: Tuple[int, int] = (1000, 360)  # 滑动起点（向右划）
    navigate_left: Tuple[int, int] = (65, 235)     # 左侧导航按钮

    # ── 签到流程中的多备选坐标 ──
    claim_alternatives: List[Tuple[int, int]] = [
        (1035, 323), (914, 586), (1043, 586)
    ]


# ── 顶部栏按钮区域定义 ──────────────────────────────────────────────
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


# ── 导航规则 ────────────────────────────────────────────────────────
NAVIGATION_MAP: Dict[str, Dict[str, Any]] = {
    "title": {
        "action": "click",
        "coords": Coords.title_click,
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
        "claim_coords": Coords.claim_alternatives,
        "next": "back_to_world",
        "desc": "签到页面 → 领取奖励",
    },
    "mode_exploration": {
        "action": "switch_mode_or_back",
        "desc": "探索模式 → 按返回或切换模式到主世界",
    },
    "mode_industry": {
        "action": "switch_mode",
        "coords": Coords.mode_switch,
        "next": "mode_exploration",
        "desc": "工业模式 → 切换到探索模式",
    },
    "exit_dialog": {
        "action": "click",
        "coords": Coords.exit_cancel,
        "desc": "退出游戏对话框 → 取消",
    },
}


# ── 任务面板关键词 ──────────────────────────────────────────────────
OVERLAY_KEYWORDS = [
    "每日", "每周", "任务", "日程", "签到", "作战汇报",
    "领取", "收取", "一键领取", "完成", "提交", "领奖",
    "进行中", "已完成", "可领取", "奖励",
    "活跃度", "经验", "信用", "合成玉",
]


# ── 已知功能坐标（供 OCR/导航直接引用） ────────────────────────────
KNOWN_COORDS: Dict[str, Tuple[int, int]] = {
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


# ── 模式切换 ──────────────────────────────────────────────────────
MODE_SWITCH_BUTTON: Tuple[int, int] = (75, 21)  # 在 "探索" 和 "工业" 之间切换


# ── 领取按钮关键词 ────────────────────────────────────────────────
CLAIM_KEYWORDS: List[str] = [
    "领取", "收取", "一键领取", "完成", "提交", "领奖", "CLAIM", "collect",
]


# ── 顶部栏按钮坐标（快速点击用，与 TOP_BAR_BUTTONS 区域定义互补） ──
TOP_BAR: Dict[str, Tuple[int, int]] = {
    "close_x":    (1170, 22),   # 关闭弹窗
    "settings":   (630, 22),    # 设置
    "inventory":  (570, 22),    # 背包
    "tasks":      (540, 22),    # 任务
    "signin":     (510, 22),    # 签到/日历
    "event":      (480, 22),    # 活动
    "shop":       (450, 22),    # 商店
}


# ── 退出对话框 ────────────────────────────────────────────────────
EXIT_DIALOG: Dict[str, Tuple[int, int]] = {
    "confirm": (793, 478),      # 确认退出
    "cancel":  (556, 478),      # 取消退出
}


# ── 签到页面 ──────────────────────────────────────────────────────
SIGNIN_PAGE: Dict[str, Any] = {
    "claim_all":        (1035, 323),                    # 一键领取（已验证）
    "reward_close":     (640, 500),                     # 奖励弹窗确认
    "individual_claim": [(914, 586), (1043, 586)],      # 单个领取
}


# ── 活动中心 ──────────────────────────────────────────────────────
EVENT_CENTER: Dict[str, Any] = {
    "signin_entry":  (112, 296),   # 左侧签到入口
    "scroll_area_x": 120,           # 左侧列表滚动区域
}


# ── 页面类型映射 ────────────────────────────────────────────────────
PAGE_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "world_map":              ["塔卫二", "大地图", "世界地图", "导航"],
    "signin":                 ["签到", "寻奇探幽", "限时签到"],
    "tasks_daily":            ["每日任务", "日程", "活跃度"],
    "tasks_weekly":           ["每周任务"],
    "event_center":           ["活动中心", "当前活动", "限时活动"],
    "combat_report":          ["作战汇报", "战斗报告"],
    "announcement":           ["公告", "版本更新", "维护预告"],
    "dialog":                 ["确认", "取消", "是否"],
    "loading":                ["加载中", "NOW LOADING", "资源检查"],
    "title_screen":           ["点击任意位置继续", "ENDFIELD", "ARKNIGHTS"],
}


def xy_str(coords: Tuple[int, int]) -> str:
    """坐标转可读字符串"""
    return f"({coords[0]}, {coords[1]})"


def lookup_button(label: str) -> Tuple[int, int]:
    """根据标签名查找按钮坐标（模糊匹配）"""
    label_lower = label.lower()
    for name, info in TOP_BAR_BUTTONS.items():
        if name in label_lower or info["label"] in label:
            cx = (info["x_range"][0] + info["x_range"][1]) // 2
            cy = (info["y_range"][0] + info["y_range"][1]) // 2
            return (cx, cy)
    return Coords.tasks_button  # 默认回退


def coords_for_model(model_tag: str) -> Dict[str, Tuple[int, int]]:
    """返回模型标签对应的坐标集（供 VLM 参考）"""
    return {k: v for k, v in vars(Coords).items()
            if not k.startswith("_") and isinstance(v, tuple) and len(v) == 2}
