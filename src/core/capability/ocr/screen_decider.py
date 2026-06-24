#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
灞忓箷鍐崇瓥妯″潡 - 鍩轰簬 OCR 缁撴灉杩涜椤甸潰鐘舵€佸喅绛?

浠?IstinaEndfieldAssistant_Sight 杩佺Щ锛岀敤浜庢浛浠?VLM 鍥惧儚杈撳叆銆?
浣跨敤 MaaMCP OCR 蹇€熸娴嬪睆骞曠姸鎬侊紙~1s锛夛紝閬垮厤姣忔璋冪敤 VLM锛垀20-30s锛?
"""

import sys
import os
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field

from core.foundation.logger import get_logger, LogCategory
from core.foundation.game_coords import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    TOP_BAR_Y_RANGE, OVERLAY_ROI,
    TOP_BAR_BUTTONS, KNOWN_COORDS,
    MODE_SWITCH_BUTTON,
    OVERLAY_KEYWORDS, CLAIM_KEYWORDS,
)


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

    def to_dict(self) -> Dict[str, Any]:
        """杞崲涓哄瓧鍏告牸寮忥紙鐢ㄤ簬鏋勫缓 LLM 鎻愮ず璇嶏級"""
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
        """杞崲涓?LLM 鎻愮ず璇嶆牸寮?""
        lines = [
            f"椤甸潰绫诲瀷锛歿self.page_type}",
            f"缃俊搴︼細{self.confidence:.2f}",
            f"椤堕儴鏍忓彲瑙侊細{'鏄? if self.top_bar_visible else '鍚?}",
        ]
        
        if self.top_bar_buttons:
            lines.append(f"妫€娴嬪埌鐨勬寜閽細{', '.join(self.top_bar_buttons)}")
        
        lines.append(f"鍙充晶闈㈡澘锛歿'宸叉墦寮€' if self.overlay_detected else '鏈墦寮€'}")
        
        if self.overlay_texts:
            lines.append(f"闈㈡澘鍐呭锛歿', '.join(self.overlay_texts[:5])}")  # 闄愬埗闀垮害
        
        if self.claim_buttons:
            lines.append(f"棰嗗彇鎸夐挳锛歿len(self.claim_buttons)} 涓?)
            for x, y, text in self.claim_buttons:
                lines.append(f"  - '{text}' ({x}, {y})")
        
        if self.interactive_elements:
            lines.append(f"鍙氦浜掑厓绱?")
            for el in self.interactive_elements[:10]:  # 闄愬埗鏁伴噺
                lines.append(f"  - {el.get('type', '鍏冪礌')} \"{el.get('text', '')}\" ({el.get('x', 0)}, {el.get('y', 0)})")
        
        if self.description:
            lines.append(f"鎻忚堪锛歿self.description}")
        
        return "\n".join(lines)


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
    """妫€娴嬫槸鍚﹀凡鐧诲嚭锛堟樉绀虹櫥鍑哄璇濇锛? MaaEnd 寮忚璁?""
    # MaaEnd 寮忕殑鐧诲嚭瀵硅瘽妗嗗叧閿瘝锛堝璇█锛?
    logout_keywords = [
        # 绠€浣撲腑鏂?
        "鐧诲嚭", "閫€鍑?, "鐧诲綍鐣岄潰", "瓒呮椂", "閲嶆柊鐧诲綍", "浼氳瘽杩囨湡", "鑷姩鐧诲嚭",
        "闀挎椂闂?, "娌℃湁鎿嶄綔", "鏂紑杩炴帴", "纭", "鍙栨秷",
        # 绻佷綋涓枃
        "鐧诲叆浠嬮潰", "瓒呮檪", "閲嶆柊鐧诲叆", "鏈冭┍閬庢湡",
        # 鑻辨枃
        "logout", "log out", "login screen", "timeout", "session expired",
        "re-login", "disconnect",
        # 鏃ユ枃
        "鐢婚潰銇埢銈娿伨銇欍亱", "銉偘銈偊銉?, "銉偘銈ゃ兂", "銈裤偆銉犮偄銈︺儓",
        # 闊╂枃
        "雮橁皜鞁滉矤鞀惦媹旯?, "搿滉犯鞎勳泝", "搿滉犯鞚?, "鞁滉皠齑堦臣"
    ]
    
    # 鍚堝苟鎵€鏈?OCR 鏂囨湰
    texts = " ".join([e.get("text", "") for e in elements])
    
    # 妫€鏌ュ叧閿瘝锛堜笉鍖哄垎澶у皬鍐欙級
    texts_lower = texts.lower()
    return any(kw.lower() in texts_lower for kw in logout_keywords)


def _check_world_map_topbar(elements: list) -> bool:
    """妫€娴嬫槸鍚︽樉绀轰笘鐣屽湴鍥鹃《閮ㄦ爮锛堟帰绱?杩斿洖/鍟嗗簵/娲诲姩绛夋寜閽級"""
    top_area = [e for e in elements if TOP_BAR_Y_RANGE[0] <= e["cy"] <= TOP_BAR_Y_RANGE[1]]
    top_texts = [e["text"] for e in top_area]
    has_exploration = any("鎺㈢储" in t for t in top_texts)
    return has_exploration


def _detect_overlay(elements: list) -> Tuple[bool, list]:
    """妫€娴嬪彸渚т换鍔￠潰鏉胯鐩栧眰鏄惁鎵撳紑"""
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
        ScreenState: 灞忓箷鐘舵€佹娴嬬粨鏋?
    """
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

    # 妫€娴嬮鍙栨寜閽?
    state.claim_buttons = _find_claim_buttons(elements)

    # 鏀堕泦鍙氦浜掑厓绱?
    for e in elements:
        if e["score"] > 0.5 and e["w"] > 20:
            state.interactive_elements.append(e)

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
        state.description = f"涓栫晫鍦板浘 (椤堕儴鏍忥細{', '.join(state.top_bar_buttons) or '鏃?})"
    elif len(elements) >= 5 and any(e["w"] > 100 for e in elements):
        state.page_type = "sub_page"
        keywords_found = _find_keyword_matches(elements, OVERLAY_KEYWORDS)
        if keywords_found:
            state.description = f"瀛愰〉闈?(鍚?{len(keywords_found)} 涓换鍔″叧閿瘝)"
        else:
            state.description = f"瀛愰〉闈?({len(elements)} 涓枃鏈厓绱?"
    else:
        state.page_type = "other"
        state.description = f"鍏朵粬椤甸潰 ({len(elements)} 涓枃鏈?"

    state.confidence = min(1.0, len(elements) / 20)
    return state


# 鈹€鈹€ 瀵艰埅璁″垝鐢熸垚 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def generate_navigation_plan(state: ScreenState) -> List[Dict]:
    """
    鏍规嵁褰撳墠灞忓箷鐘舵€佺敓鎴愬鑸鍒掋€?

    Args:
        state: 灞忓箷鐘舵€佹娴嬬粨鏋?

    Returns:
        list: 鎿嶄綔姝ラ鍒楄〃
    """
    plan = []

    if state.page_type == "title":
        plan.append({
            "type": "tap",
            "params": {"x": 640, "y": 360},
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
        plan.append({
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
        if state.claim_buttons:
            for cx, cy, label in state.claim_buttons:
                plan.append({
                    "type": "tap",
                    "params": {"x": cx, "y": cy, "label": label},
                    "description": f"鐐瑰嚮棰嗗彇鎸夐挳锛歿label}"
                })
                plan.append({
                    "type": "wait",
                    "params": {"duration": 5},
                    "description": "绛夊緟棰嗗彇瀹屾垚"
                })
        else:
            plan.append({
                "type": "swipe",
                "params": {"x1": 1100, "y1": 300, "x2": 1100, "y2": 600, "duration": 500},
                "description": "鍚戜笅婊戝姩闈㈡澘"
            })
            plan.append({
                "type": "wait",
                "params": {"duration": 3},
                "description": "绛夊緟婊戝姩瀹屾垚"
            })

    elif state.page_type == "sub_page":
        plan.append({
            "type": "back",
            "description": "杩斿洖涓婁竴绾?
        })
        plan.append({
            "type": "wait",
            "params": {"duration": 3},
            "description": "绛夊緟杩斿洖瀹屾垚"
        })

    return plan


class ScreenDecider:
    """灞忓箷鍐崇瓥鍣?- 灏佽 OCR 鍐崇瓥閫昏緫"""

    def __init__(self):
        self.logger = get_logger()

    def detect_screen_state(self, ocr_results: list) -> ScreenState:
        """妫€娴嬪睆骞曠姸鎬?""
        return detect_screen_state(ocr_results)

    def generate_plan(self, state: ScreenState) -> List[Dict]:
        """鐢熸垚瀵艰埅璁″垝"""
        return generate_navigation_plan(state)

    def decide_action(self, ocr_results: list) -> Tuple[ScreenState, List[Dict]]:
        """
        涓€绔欏紡鍐崇瓥锛歄CR 缁撴灉 鈫?鐘舵€佹娴?鈫?瀵艰埅璁″垝

        Returns:
            (ScreenState, navigation_plan)
        """
        state = self.detect_screen_state(ocr_results)
        plan = self.generate_plan(state)
        return state, plan


# 鈹€鈹€ 鐙珛娴嬭瘯 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def main():
    """鐙珛娴嬭瘯妯″紡"""
    print("=" * 60)
    print("OCR 鍐崇瓥妯″潡 - 娴嬭瘯")
    print("=" * 60)

    # 妯℃嫙 OCR 缁撴灉
    mock_ocr = [
        {"text": "鎺㈢储", "box": [30, 10, 60, 30], "score": 0.98},
        {"text": "姣忔棩浠诲姟", "box": [970, 80, 100, 40], "score": 0.95},
        {"text": "棰嗗彇", "box": [1020, 300, 60, 30], "score": 0.92},
        {"text": "涓€閿鍙?, "box": [1000, 350, 100, 40], "score": 0.96},
    ]

    decider = ScreenDecider()
    state, plan = decider.decide_action(mock_ocr)

    print(f"\n椤甸潰绫诲瀷锛歿state.page_type}")
    print(f"鎻忚堪锛歿state.description}")
    print(f"棰嗗彇鎸夐挳锛歿len(state.claim_buttons)} 涓?)
    print(f"\n瀵艰埅璁″垝 ({len(plan)} 姝?:")
    for i, step in enumerate(plan, 1):
        print(f"  {i}. {step['type']}: {step['description']}")


if __name__ == "__main__":
    main()

