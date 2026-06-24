#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
IEA OCR/VLM 閫夋嫨鏈哄埗 鈥?鑷€傚簲褰撳墠娓告垙鐘舵€佸喅绛栨ā鍧椼€?
鏍稿績鐞嗗康锛?  1. OCR 浼樺厛锛氫娇鐢?MaaMCP OCR 蹇€熸娴嬪睆骞曠姸鎬侊紙~1s锛夛紝閬垮厤姣忔璋冪敤 VLM锛垀20-30s锛?  2. 鍒嗙骇鍐崇瓥锛歄CR 鈫?灏忔ā鍨?VLM 鈫?澶фā鍨?VLM锛屾寜闇€鍗囩骇
  3. 鍙充晶闈㈡澘妫€娴嬶細閫氳繃 OCR 妫€娴嬩换鍔￠潰鏉胯鐩栧眰锛堣€岄潪渚濊禆 VLM 鐨?page_type锛?  4. 鍙泦鎴愬埌 MaaPipeline锛氱敓鎴?Pipeline JSON 渚?run_pipeline 浣跨敤

鐢ㄦ硶锛?  python scripts/ocr_decision_module.py                    # 鐙珛娴嬭瘯
  python scripts/ocr_decision_module.py --once             # 鍗曟妫€娴?
  浣滀负妯″潡瀵煎叆:
    from scripts.ocr_decision_module import ScreenDecider
    decider = ScreenDecider()
    state = decider.detect_screen_state(ocr_results)
    if state == "world_map_with_overlay":
        # 闈㈡澘宸叉墦寮€锛岃繘琛岄鍙栨搷浣?"""

import json, time, os, sys, re
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field


# 鈹€鈹€ 甯搁噺瀹氫箟 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

# 灞忓箷鍒嗚鲸鐜囷紙MaaMCP 鎴浘鍧愭爣绌洪棿锛?SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720

# 椤堕儴鏍忓尯鍩燂紙鍩轰簬瀹為檯 OCR 妫€娴嬶級
TOP_BAR_Y_RANGE = (10, 80)

# 鍙充晶闈㈡澘瑕嗙洊灞?ROI锛圤verlay Panel Region锛?# 褰撻潰鏉挎墦寮€鏃讹紝鍙充晶浼氬嚭鐜版繁鑹插崐閫忔槑鍖哄煙锛寈 > 950 宸﹀彸
OVERLAY_ROI = {
    "x_start": 950,    # 闈㈡澘宸﹁竟缂?    "x_end": 1280,     # 鍙宠竟缂?    "y_start": 60,     # 闈㈡澘椤堕儴
    "y_end": 700,      # 闈㈡澘搴曢儴
}

# 椤堕儴鏍忔寜閽鏈熶綅缃紙1280x720 鍧愭爣绌洪棿锛屽熀浜庡疄闄?OCR 妫€娴嬶級
# Endfield 椤堕儴鏍忓浘鏍囦粠鍙冲埌宸︽帓鍒楋紝璁稿鏄函鍥炬爣鏃犳枃瀛?TOP_BAR_BUTTONS = {
    "exploration":  {"label": "鎺㈢储",       "x_range": (30, 120),   "y_range": (10, 45)},
    "back":         {"label": "杩斿洖",       "x_range": (420, 480),  "y_range": (10, 45)},
    "shop":         {"label": "鍟嗗簵",       "x_range": (450, 510),  "y_range": (10, 45)},
    "event":        {"label": "娲诲姩",       "x_range": (480, 540),  "y_range": (10, 45)},
    "signin":       {"label": "绛惧埌",       "x_range": (510, 570),  "y_range": (10, 45)},
    "tasks":        {"label": "浠诲姟",       "x_range": (540, 600),  "y_range": (10, 45)},
    "inventory":    {"label": "鑳屽寘",       "x_range": (570, 630),  "y_range": (10, 45)},
    "settings":     {"label": "璁剧疆",       "x_range": (630, 690),  "y_range": (10, 45)},
}

# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?# 娓告垙瀵艰埅鐭ヨ瘑搴?鈥?鐢卞疄闄呮帰绱㈢Н绱?# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
# 宸茬煡鐨勫姛鑳藉潗鏍囷紙1280x720 MaaMCP 绌洪棿锛?KNOWN_COORDS = {
    # 椤堕儴鏍忥紙浠呭綋鍦ㄤ富涓栫晫鍦板浘鏃跺彲鐢級
    "tasks_button":     (570, 22),   # 浠诲姟鎸夐挳
    "event_button":     (510, 22),   # 娲诲姩鎸夐挳
    "back_button":      (450, 22),   # 杩斿洖鎸夐挳
    "close_overlay_x":  (1170, 22),  # 鍏抽棴闈㈡澘 X 鎸夐挳

    # 绛惧埌椤甸潰
    "claim_all":        (1035, 323), # 涓€閿鍙栵紙宸查獙璇佹垚鍔燂級
    "reward_confirm":   (640, 500),  # 濂栧姳纭寮圭獥鐐瑰嚮浣嶇疆

    # 娲诲姩涓績
    "signin_entry":     (112, 296),  # 绛惧埌鍏ュ彛锛堟椿鍔ㄤ腑蹇冨乏渚у垪琛級

    # 閫€鍑烘父鎴忓璇濇
    "exit_confirm":     (793, 478),  # "纭" 閫€鍑?    "exit_cancel":      (556, 478),  # "鍙栨秷" 閫€鍑?}

# 娓告垙妯″紡鍒囨崲
# Endfield 鏈変袱绉嶄富瑕佹父鎴忔ā寮忥紝閫氳繃宸︿笂瑙掓寜閽垏鎹細
MODE_SWITCH_BUTTON = (75, 21)  # 鍦?"鎺㈢储" 鍜?"宸ヤ笟" 涔嬮棿鍒囨崲

# 椤甸潰绫诲瀷 鈫?瀵艰埅寤鸿鏄犲皠
NAVIGATION_MAP = {
    # (褰撳墠妯″紡, 妫€娴嬪埌鐨勭壒寰? 鈫?鎿嶄綔
    "title": {
        "action": "click",
        "coords": (640, 360),
        "next": "loading",
        "desc": "鏍囬鐢婚潰 鈫?鐐瑰嚮浠绘剰浣嶇疆缁х画",
    },
    "loading": {
        "action": "wait",
        "duration": 15,
        "next": "sub_page_or_world",
        "desc": "鍔犺浇涓?鈫?绛夊緟",
    },
    "sub_page_signin": {
        "action": "claim",
        "claim_coords": [(1035, 323), (914, 586), (1043, 586)],
        "next": "back_to_world",
        "desc": "绛惧埌椤甸潰 鈫?棰嗗彇濂栧姳",
    },
    "mode_exploration": {
        "action": "switch_mode_or_back",
        "desc": "鎺㈢储妯″紡 鈫?鎸夎繑鍥炴垨鍒囨崲妯″紡鍒颁富涓栫晫",
    },
    "mode_industry": {
        "action": "switch_mode",
        "coords": MODE_SWITCH_BUTTON,
        "next": "mode_exploration",
        "desc": "宸ヤ笟妯″紡 鈫?鍒囨崲鍒版帰绱㈡ā寮?,
    },
    "exit_dialog": {
        "action": "click",
        "coords": KNOWN_COORDS["exit_cancel"],
        "desc": "閫€鍑烘父鎴忓璇濇 鈫?鍙栨秷",
    },
}

# 浠诲姟闈㈡澘鍐呭彲鑳藉嚭鐜扮殑鏂囨湰鍏抽敭璇?OVERLAY_KEYWORDS = [
    "姣忔棩", "姣忓懆", "浠诲姟", "鏃ョ▼", "绛惧埌", "浣滄垬姹囨姤",
    "棰嗗彇", "鏀跺彇", "涓€閿鍙?, "瀹屾垚", "鎻愪氦", "棰嗗",
    "杩涜涓?, "宸插畬鎴?, "鍙鍙?, "濂栧姳",
    "娲昏穬搴?, "缁忛獙", "淇＄敤", "鍚堟垚鐜?,
]

# 棰嗗彇鎸夐挳鍏抽敭璇?CLAIM_KEYWORDS = ["棰嗗彇", "鏀跺彇", "涓€閿鍙?, "瀹屾垚", "鎻愪氦", "棰嗗", "CLAIM", "collect"]


# 鈹€鈹€ 鐘舵€佸畾涔?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

@dataclass
class ScreenState:
    """灞忓箷鐘舵€佹娴嬬粨鏋?""
    page_type: str = "unknown"           # world_map / world_map_with_overlay / dialog / loading / login / title / other
    confidence: float = 0.0
    top_bar_visible: bool = False
    top_bar_buttons: List[str] = field(default_factory=list)
    overlay_detected: bool = False
    overlay_texts: List[str] = field(default_factory=list)
    claim_buttons: List[Tuple[int, int, str]] = field(default_factory=list)
    interactive_elements: List[Dict] = field(default_factory=list)
    description: str = ""


# 鈹€鈹€ 妫€娴嬪嚱鏁?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _normalize_ocr(ocr_results: list) -> list:
    """褰掍竴鍖?OCR 缁撴灉锛岀‘淇濇瘡涓厓绱犳湁鏍囧噯瀛楁"""
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
    """绛涢€夊湪 ROI 鍖哄煙鍐呯殑 OCR 鏂囨湰"""
    x_start, x_end = roi.get("x_start", 0), roi.get("x_end", SCREEN_WIDTH)
    y_start, y_end = roi.get("y_start", 0), roi.get("y_end", SCREEN_HEIGHT)
    return [e for e in elements
            if x_start <= e["cx"] <= x_end and y_start <= e["cy"] <= y_end]


def _find_keyword_matches(elements: list, keywords: list) -> list:
    """鍦?OCR 鏂囨湰涓煡鎵惧叧閿瘝"""
    matches = []
    for e in elements:
        for kw in keywords:
            if kw in e["text"]:
                matches.append(e)
                break
    return matches


def _find_button_at(elements: list, x_range: tuple, y_range: tuple) -> Optional[Dict]:
    """鏌ユ壘鍦ㄦ寚瀹氬潗鏍囪寖鍥村唴鐨勬寜閽枃鏈?""
    for e in elements:
        if x_range[0] <= e["cx"] <= x_range[1] and y_range[0] <= e["cy"] <= y_range[1]:
            return e
    return None


def _get_text_at(elements: list, x: int, y: int, radius: int = 30) -> Optional[str]:
    """鑾峰彇鎸囧畾鍧愭爣闄勮繎 OCR 鏂囨湰"""
    for e in elements:
        if abs(e["cx"] - x) <= radius and abs(e["cy"] - y) <= radius:
            return e["text"]
    return None


# 鈹€鈹€ 椤甸潰绫诲瀷妫€娴?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _check_title_screen(elements: list) -> bool:
    """妫€娴嬫槸鍚︽槸鏍囬/鐧诲綍鐢婚潰"""
    texts = [e["text"] for e in elements]
    keywords_found = sum(1 for t in texts if any(k in t for k in [
        "鏄庢棩鏂硅垷", "缁堟湯鍦?, "鐐瑰嚮浠绘剰浣嶇疆缁х画", "璐︽埛鐧诲嚭",
        "鍏憡", "璁剧疆", "淇", "閫傞緞鎻愮ず"
    ]))
    return keywords_found >= 3


def _check_loading_screen(elements: list) -> bool:
    """妫€娴嬫槸鍚︽槸鍔犺浇鐢婚潰"""
    texts = [e["text"] for e in elements]
    has_loading = any("LOADING" in t.upper() or "鍔犺浇" in t for t in texts)
    has_tips = any("TIPS" in t.upper() or "鎻愮ず" in t for t in texts)
    has_uid = any("UID" in t.upper() for t in texts)
    has_version = any("REL_" in t for t in texts)
    return (has_loading and has_tips) or (has_loading and has_uid and not has_version)


def _check_logged_out_screen(elements: list) -> bool:
    """妫€娴嬫槸鍚﹀凡鐧诲嚭锛堟樉绀虹櫥鍑哄璇濇锛?""
    texts = " ".join([e["text"] for e in elements])
    return any(k in texts for k in ["鐧诲嚭", "瓒呮椂", "閲嶆柊鐧诲綍", "浼氳瘽杩囨湡"])


def _check_world_map_topbar(elements: list) -> bool:
    """妫€娴嬫槸鍚︽樉绀轰笘鐣屽湴鍥鹃《閮ㄦ爮锛堟帰绱?杩斿洖/鍟嗗簵/娲诲姩绛夋寜閽級"""
    # 妫€鏌ラ《閮ㄥ尯鍩熸湁娌℃湁"鎺㈢储"鏂囨湰
    top_area = [e for e in elements if TOP_BAR_Y_RANGE[0] <= e["cy"] <= TOP_BAR_Y_RANGE[1]]
    top_texts = [e["text"] for e in top_area]

    # 涓讳笘鐣屽湴鍥剧壒寰侊細鏈?鎺㈢储"鍦ㄥ乏涓婅
    has_exploration = any("鎺㈢储" in t for t in top_texts)
    return has_exploration


def _detect_overlay(elements: list) -> Tuple[bool, list]:
    """妫€娴嬪彸渚т换鍔￠潰鏉胯鐩栧眰鏄惁鎵撳紑"""
    # 闈㈡澘鍖哄煙鍐呯殑鏂囨湰
    overlay_area = _text_in_roi(elements, OVERLAY_ROI)
    if not overlay_area:
        return False, []

    # 鏌ユ壘浠诲姟鍏抽敭璇?    keyword_matches = _find_keyword_matches(overlay_area, OVERLAY_KEYWORDS)
    if keyword_matches:
        return True, keyword_matches

    # 濡傛灉闈㈡澘鍖哄煙鏈夊涓枃鏈厓绱狅紙>3锛夛紝涔熷彲鑳借〃绀洪潰鏉挎墦寮€
    if len(overlay_area) >= 3:
        return True, overlay_area

    return False, []


def _find_claim_buttons(elements: list) -> List[Tuple[int, int, str]]:
    """鍦?OCR 缁撴灉涓煡鎵炬墍鏈夐鍙栨寜閽?""
    buttons = []
    for e in elements:
        for kw in CLAIM_KEYWORDS:
            if kw in e["text"]:
                buttons.append((e["cx"], e["cy"], e["text"]))
                break
    return buttons


# 鈹€鈹€ 涓诲喅绛栧嚱鏁?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def detect_screen_state(ocr_results: list) -> ScreenState:
    """
    鏍规嵁 OCR 缁撴灉妫€娴嬪綋鍓嶅睆骞曠姸鎬併€?
    Args:
        ocr_results: MaaMCP OCR 杩斿洖鐨勭粨鏋滃垪琛?
    Returns:
        ScreenState: 灞忓箷鐘舵€佹娴嬬粨鏋?    """
    if not ocr_results:
        return ScreenState(description="OCR 鏃犵粨鏋?)

    elements = _normalize_ocr(ocr_results)
    if not elements:
        return ScreenState(description="OCR 鏃犳湁鏁堟枃鏈?)

    state = ScreenState()
    state.top_bar_visible = _check_world_map_topbar(elements)

    # 妫€娴嬮《閮ㄦ爮鎸夐挳
    if state.top_bar_visible:
        for name, cfg in TOP_BAR_BUTTONS.items():
            btn = _find_button_at(elements, cfg["x_range"], cfg["y_range"])
            if btn:
                state.top_bar_buttons.append(name)

    # 妫€娴嬪彸渚ч潰鏉胯鐩栧眰
    overlay_detected, overlay_elems = _detect_overlay(elements)
    state.overlay_detected = overlay_detected
    if overlay_detected:
        state.overlay_texts = [e["text"] for e in overlay_elems]

    # 妫€娴嬮鍙栨寜閽?    state.claim_buttons = _find_claim_buttons(elements)

    # 鏀堕泦鍙氦浜掑厓绱狅紙鍦ㄩ《閮ㄦ爮鍜岄潰鏉垮尯鍩熺殑闈炲櫔澹版枃鏈級
    for e in elements:
        if e["score"] > 0.5 and e["w"] > 20:  # 鎺掗櫎杩囧皬鐨勫櫔澹?            state.interactive_elements.append(e)

    # 鈹€鈹€ 纭畾椤甸潰绫诲瀷 鈹€鈹€
    if _check_title_screen(elements):
        state.page_type = "title"
        state.description = "鏍囬/鐧诲綍鐢婚潰"
    elif _check_loading_screen(elements):
        state.page_type = "loading"
        state.description = "娓告垙鍔犺浇涓?
    elif _check_logged_out_screen(elements):
        state.page_type = "logout_dialog"
        state.description = "鐧诲嚭/瓒呮椂瀵硅瘽妗?
    elif state.overlay_detected and state.top_bar_visible:
        state.page_type = "world_map_with_overlay"
        state.description = f"涓栫晫鍦板浘 + 鍙充晶闈㈡澘 (妫€娴嬪埌 {len(state.overlay_texts)} 涓潰鏉挎枃鏈?"
        if state.claim_buttons:
            state.description += f"锛寋len(state.claim_buttons)} 涓鍙栨寜閽?
    elif state.top_bar_visible:
        state.page_type = "world_map"
        state.description = f"涓栫晫鍦板浘 (椤堕儴鏍? {', '.join(state.top_bar_buttons) or '鏃?})"
    elif len(elements) >= 5 and any(e["w"] > 100 for e in elements):
        # 澶ч噺鏂囨湰浣嗘病鏈夐《閮ㄦ爮 鈫?鍙兘鏄换鍔?娲诲姩椤甸潰
        state.page_type = "sub_page"
        keywords_found = _find_keyword_matches(elements, OVERLAY_KEYWORDS)
        if keywords_found:
            state.description = f"瀛愰〉闈?(鍚?{len(keywords_found)} 涓换鍔″叧閿瘝)"
        else:
            state.description = f"瀛愰〉闈?({len(elements)} 涓枃鏈厓绱?"
    else:
        state.page_type = "other"
        state.description = f"鍏朵粬椤甸潰 ({len(elements)} 涓枃鏈?"

    state.confidence = min(1.0, len(elements) / 20)  # 鏂囨湰瓒婂缃俊搴﹁秺楂?    return state


# 鈹€鈹€ Pipeline JSON 鐢熸垚 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def generate_overlay_pipeline(claim_coords: List[Tuple[int, int, str]] = None) -> dict:
    """
    鐢熸垚妫€娴嬪拰鐐瑰嚮浠诲姟闈㈡澘瑕嗙洊灞傜殑 Pipeline JSON銆?
    杩欎釜 Pipeline:
    1. 鐐瑰嚮"浠诲姟"鎸夐挳鎵撳紑闈㈡澘
    2. OCR 妫€娴嬪彸渚ч潰鏉垮尯鍩熸槸鍚︽湁浠诲姟鏂囨湰
    3. 濡傛灉鏈夐潰鏉?鈫?鏌ユ壘棰嗗彇鎸夐挳骞剁偣鍑?    4. 鍏抽棴闈㈡澘杩斿洖

    Returns:
        dict: Pipeline JSON
    """
    pipeline = {}

    # 鈹€鈹€ 鍏ュ彛锛氭墦寮€浠诲姟闈㈡澘 鈹€鈹€
    pipeline["OpenTaskPanel"] = {
        "recognition": "DirectHit",
        "action": "Click",
        "target": [810, 25],  # 浠诲姟鎸夐挳鍧愭爣 (1280x720 绌洪棿)
        "post_delay": 3000,   # 绛夊緟闈㈡澘鍔ㄧ敾
        "next": ["DetectOverlay"]
    }

    # 鈹€鈹€ 妫€娴嬮潰鏉挎槸鍚︽墦寮€ 鈹€鈹€
    pipeline["DetectOverlay"] = {
        "recognition": "OCR",
        "expected": "姣忔棩|姣忓懆|浠诲姟|鏃ョ▼|绛惧埌|棰嗗彇",
        "roi": [950, 60, 330, 640],  # 鍙充晶闈㈡澘鍖哄煙
        "action": "DoNothing",
        "next": ["SwipePanelDown", "CloseOverlay"]
    }

    # 鈹€鈹€ 鍚戜笅婊戝姩闈㈡澘 鈹€鈹€
    pipeline["SwipePanelDown"] = {
        "recognition": "DirectHit",
        "action": "Swipe",
        "begin": [1100, 400],
        "end": [1100, 600],
        "duration": 500,
        "post_delay": 2000,
        "next": ["ClaimRewards", "BruteForceClaim"]
    }

    # 鈹€鈹€ 棰嗗彇濂栧姳 鈹€鈹€
    pipeline["ClaimRewards"] = {
        "recognition": "OCR",
        "expected": "棰嗗彇|鏀跺彇|涓€閿鍙東瀹屾垚|鎻愪氦|棰嗗",
        "roi": [950, 60, 330, 640],
        "action": "Click",
        "target": True,
        "post_delay": 5000,
        "next": ["ClaimRewards", "SwipePanelUp"]  # 鍙兘杩樻湁鏇村濂栧姳
    }

    # 鈹€鈹€ 鏆村姏鐐瑰嚮棰嗗彇鍖哄煙 鈹€鈹€
    pipeline["BruteForceClaim"] = {
        "recognition": "DirectHit",
        "action": "DoNothing",
        "next": []  # 濡傛灉瑕佺敤鏆村姏鐐瑰嚮锛屽湪澶栭儴鑴氭湰涓鐞?    }

    # 鈹€鈹€ 涓婃粦鍥炲埌闈㈡澘椤堕儴 鈹€鈹€
    pipeline["SwipePanelUp"] = {
        "recognition": "DirectHit",
        "action": "Swipe",
        "begin": [1100, 600],
        "end": [1100, 300],
        "duration": 500,
        "post_delay": 1000,
        "next": ["CloseOverlay"]
    }

    # 鈹€鈹€ 鍏抽棴闈㈡澘 鈹€鈹€
    pipeline["CloseOverlay"] = {
        "recognition": "DirectHit",
        "action": "ClickKey",
        "key": 4,  # Android 杩斿洖閿?        "post_delay": 2000,
        "next": []
    }

    return pipeline


# 鈹€鈹€ 涓绘祦绋?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def generate_navigation_plan(state: ScreenState) -> List[Dict]:
    """
    鏍规嵁褰撳墠灞忓箷鐘舵€佺敓鎴愬鑸鍒掋€?
    Args:
        state: 灞忓箷鐘舵€佹娴嬬粨鏋?
    Returns:
        list: 鎿嶄綔姝ラ鍒楄〃锛屾瘡姝ュ寘鍚?type/params/description
    """
    plan = []

    if state.page_type == "title":
        plan.append({
            "type": "tap",
            "params": {"x": 640, "y": 360},  # 鐐瑰嚮浠绘剰浣嶇疆缁х画
            "description": "鐐瑰嚮鏍囬鐢婚潰杩涘叆娓告垙"
        })
        plan.append({
            "type": "wait",
            "params": {"duration": 10},
            "description": "绛夊緟鍔犺浇"
        })

    elif state.page_type == "loading":
        plan.append({
            "type": "wait",
            "params": {"duration": 10},
            "description": "绛夊緟鍔犺浇瀹屾垚"
        })

    elif state.page_type == "logout_dialog":
        plan.append({
            "type": "tap",
            "params": {"label": "confirm"},
            "description": "纭閲嶆柊鐧诲綍"
        })

    elif state.page_type == "world_map":
        # 鍦ㄤ笘鐣屽湴鍥?鈫?鎵撳紑浠诲姟闈㈡澘锛堜娇鐢?MaaMCP 1280x720 鍧愭爣锛?        # 椤堕儴鏍忔寜閽緢澶氭槸绾浘鏍囷紝鐢ㄥ凡鐭ュ潗鏍囩偣鍑?        plan.append({
            "type": "tap",
            "params": {"x": KNOWN_COORDS["tasks_button"][0],
                       "y": KNOWN_COORDS["tasks_button"][1],
                       "label": "浠诲姟鎸夐挳"},
            "description": "鐐瑰嚮椤堕儴浠诲姟鎸夐挳鎵撳紑闈㈡澘"
        })
        plan.append({
            "type": "wait",
            "params": {"duration": 5},
            "description": "绛夊緟闈㈡澘鎵撳紑"
        })

    elif state.page_type == "world_map_with_overlay":
        # 闈㈡澘宸叉墦寮€ 鈫?灏濊瘯棰嗗彇
        if state.claim_buttons:
            for cx, cy, label in state.claim_buttons:
                plan.append({
                    "type": "tap",
                    "params": {"x": cx, "y": cy, "label": label},
                    "description": f"鐐瑰嚮棰嗗彇鎸夐挳: {label}"
                })
                plan.append({
                    "type": "wait",
                    "params": {"duration": 5},
                    "description": "绛夊緟棰嗗彇瀹屾垚"
                })
        else:
            # 闈㈡澘宸叉墦寮€浣嗘病鏈夐鍙栨寜閽?鈫?婊戝姩鎵炬洿澶氬唴瀹?            plan.append({
                "type": "swipe",
                "params": {"x1": 1100, "y1": 300, "x2": 1100, "y2": 600, "duration": 500},
                "description": "鍚戜笅婊戝姩闈㈡澘"
            })
            plan.append({
                "type": "wait",
                "params": {"duration": 3},
                "description": "绛夊緟婊戝姩瀹屾垚"
            })
            # 婊戝姩鍚庡啀妫€娴?            plan.append({
                "type": "detect",
                "description": "閲嶆柊妫€娴嬮潰鏉垮唴瀹?
            })

        # 瀵艰埅璁″垝涓嶈嚜鍔ㄥ叧闂潰鏉匡紙鐣欑粰鍚庣画姝ラ澶勭悊锛?
    elif state.page_type == "sub_page":
        # 鍦ㄥ瓙椤甸潰 鈫?鍏堣繑鍥?        plan.append({
            "type": "back",
            "description": "杩斿洖涓婁竴绾?
        })
        plan.append({
            "type": "wait",
            "params": {"duration": 3},
            "description": "绛夊緟杩斿洖瀹屾垚"
        })

    return plan


# 鈹€鈹€ 鐙珛杩愯 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def main():
    """鐙珛娴嬭瘯锛氳繛鎺ュ埌 MaaMCP 骞舵娴嬪綋鍓嶅睆骞?""
    print("=" * 60)
    print("IEA OCR 鍐崇瓥妯″潡 鈥?灞忓箷鐘舵€佹娴?)
    print("=" * 60)

    # 灏濊瘯閫氳繃 MaaMCP OCR 鑾峰彇缁撴灉
    # 娉細鍦ㄧ嫭绔嬭繍琛屾椂锛岀洿鎺ラ€氳繃 ADB 鎴浘骞剁敤鏈湴 OCR
    try:
        import subprocess
        import base64
        adb = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                          "3rd-part", "adb", "adb.exe")
        dev = "localhost:16512"

        r = subprocess.run([adb, "-s", dev, "exec-out", "screencap", "-p"],
                          capture_output=True, timeout=15)
        if r.returncode != 0:
            print("ADB 鎴浘澶辫触")
            return

        print(f"鎴浘: {len(r.stdout)} bytes")

        # 妯℃嫙 OCR 缁撴灉锛堝湪瀹為檯浣跨敤涓敱 MaaMCP OCR 鎻愪緵锛?        # 杩欓噷鎴戜滑灏濊瘯鐢?ADB + 绠€鍗曟枃鏈娴?        # 瀹夎 pytesseract 鐨勮瘽鍙互鏈湴 OCR
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(r.stdout))
            print(f"鍥惧儚灏哄: {img.size}")

            # 妫€鏌ュ彸渚у尯鍩熶寒搴﹀彉鍖栵紙浣滀负闈㈡澘鏄惁鎵撳紑鐨勬寚鏍囷級
            right_strip = img.crop((950, 60, 1280, 700))
            avg_brightness = sum(
                sum(right_strip.getpixel((x, y))[:3]) / 3
                for x in range(0, right_strip.width, 10)
                for y in range(0, right_strip.height, 10)
            ) / max(1, (right_strip.width // 10) * (right_strip.height // 10))

            print(f"鍙充晶闈㈡澘鍖哄煙骞冲潎浜害: {avg_brightness:.1f}")
            print(f"(浜害 < 100 = 娣辫壊闈㈡澘鍙兘鎵撳紑)")
        except ImportError:
            print("PIL 涓嶅彲鐢紝璺宠繃鍥惧儚鍒嗘瀽")

        print()
        print("浣跨敤鏂规硶:")
        print("  灏嗘妯″潡闆嗘垚鍒拌剼鏈腑:")
        print("    from scripts.ocr_decision_module import detect_screen_state")
        print("    state = detect_screen_state(ocr_results)")
        print("    plan = generate_navigation_plan(state)")
        print()
        print("  Pipeline JSON 淇濆瓨:")
        print("    pipeline = generate_overlay_pipeline()")
        print("    with open('overlay_pipeline.json', 'w') as f:")
        print("        json.dump(pipeline, f, indent=2)")

    except Exception as e:
        print(f"妫€娴嬪紓甯? {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 娴嬭瘯妯″紡
    if "--once" in sys.argv:
        # 鍗曚竴妫€娴嬫ā寮?        import subprocess, base64
        adb = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                          "3rd-part", "adb", "adb.exe")
        dev = "localhost:16512"
        r = subprocess.run([adb, "-s", dev, "exec-out", "screencap", "-p"],
                          capture_output=True, timeout=15)
        if r.returncode == 0:
            print(f"鎴浘: {len(r.stdout)} bytes")
            print("闇€閫氳繃 MaaMCP OCR 鑾峰彇鏂囨湰缁撴灉鍚庡啀璋冪敤 detect_screen_state()")
    else:
        main()

