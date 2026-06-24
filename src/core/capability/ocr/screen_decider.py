#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
Screen policy module - determines page state and recovery actions based on OCR results.

Replaces VLM image input with fast MaaMCP OCR (~1s), reducing VLM calls from every step to only when needed.
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


@dataclass
class ScreenState:
    """Screen state detection result"""
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
        """Convert to dictionary format (for generating LLM prompts)"""
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
        """Convert to LLM prompt format"""
        lines = [
            f"Page type: {self.page_type}",
            f"Confidence: {self.confidence:.2f}",
            f"Top bar visible: {'Yes' if self.top_bar_visible else 'No'}",
        ]
        
        if self.top_bar_buttons:
            lines.append(f"Top bar buttons detected: {', '.join(self.top_bar_buttons)}")
        
        lines.append(f"Overlay panel: {'Expanded' if self.overlay_detected else 'Not expanded'}")
        
        if self.overlay_texts:
            lines.append(f"Overlay content: {', '.join(self.overlay_texts[:5])}")  # limited length
        
        if self.claim_buttons:
            lines.append(f"Claim buttons: {len(self.claim_buttons)} found")
            for x, y, text in self.claim_buttons:
                lines.append(f"  - '{text}' ({x}, {y})")
        
        if self.interactive_elements:
            lines.append(f"Interactive elements:")
            for el in self.interactive_elements[:10]:  # limited count
                lines.append(f"  - {el.get('type', 'element')} \"{el.get('text', '')}\" ({el.get('x', 0)}, {el.get('y', 0)})")
        
        if self.description:
            lines.append(f"Description: {self.description}")
        
        return "\n".join(lines)


def _normalize_ocr(ocr_results: list) -> list:
    """Normalize OCR results, ensuring each element has standard fields"""
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
    """Filter OCR text within ROI region"""
    x_start, x_end = roi.get("x_start", 0), roi.get("x_end", SCREEN_WIDTH)
    y_start, y_end = roi.get("y_start", 0), roi.get("y_end", SCREEN_HEIGHT)
    return [e for e in elements
            if x_start <= e["cx"] <= x_end and y_start <= e["cy"] <= y_end]


def _find_keyword_matches(elements: list, keywords: list) -> list:
    """Find matching keywords in OCR text"""
    matches = []
    for e in elements:
        for kw in keywords:
            if kw in e["text"]:
                matches.append(e)
                break
    return matches


def _find_button_at(elements: list, x_range: tuple, y_range: tuple) -> Optional[Dict]:
    """Find button text within specified coordinate region"""
    for e in elements:
        if x_range[0] <= e["cx"] <= x_range[1] and y_range[0] <= e["cy"] <= y_range[1]:
            return e
    return None


def _check_title_screen(elements: list) -> bool:
    """Check if it is title/login screen"""
    texts = [e["text"] for e in elements]
    keywords_found = sum(1 for t in texts if any(k in t for k in [
        "StartGame", "QuitGame", "TapToContinue", "Logout",
        "Settings", "Confirm", "Restart", "Warning"
    ]))
    return keywords_found >= 3


def _check_loading_screen(elements: list) -> bool:
    """Check if it is loading screen"""
    texts = [e["text"] for e in elements]
    has_loading = any("LOADING" in t.upper() or "Loading" in t for t in texts)
    has_tips = any("TIPS" in t.upper() or "Tips" in t for t in texts)
    has_uid = any("UID" in t.upper() for t in texts)
    has_version = any("REL_" in t for t in texts)
    return (has_loading and has_tips) or (has_loading and has_uid and not has_version)


def _check_logged_out_screen(elements: list) -> bool:
    """Check if logged out (showing login dialog, special handling for MaaEnd)"""
    # Keywords for MaaEnd login dialog
    logout_keywords = [
        # Chinese simplified
        "Logout", "Exit", "LoginPage", "Timeout", "ReLogin", "SessionExpired", "AutoLogout",
        "TimeOut", "NoOperation", "Reconnect", "Confirm", "Cancel",
        # Chinese traditional
        "登出", "登入頁面", "重新登入", "連線逾時",
        # English
        "logout", "log out", "login screen", "timeout", "session expired",
        "re-login", "disconnect",
        # Japanese
        "ログアウト", "ログイン画面", "セッション期限切れ",
        # Korean
        "로그아웃", "로그인", "세션만료"
    ]
    
    # Combine all OCR text
    texts = " ".join([e.get("text", "") for e in elements])
    
    # Check keywords (case-insensitive)
    texts_lower = texts.lower()
    return any(kw.lower() in texts_lower for kw in logout_keywords)


def _check_world_map_topbar(elements: list) -> bool:
    """Check if world map top bar is visible (return/shop/activity buttons)"""
    top_area = [e for e in elements if TOP_BAR_Y_RANGE[0] <= e["cy"] <= TOP_BAR_Y_RANGE[1]]
    top_texts = [e["text"] for e in top_area]
    has_exploration = any("Explore" in t for t in top_texts)
    return has_exploration


def _detect_overlay(elements: list) -> Tuple[bool, list]:
    """Check if right-side overlay panel is expanded"""
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
    """Find all claim buttons in OCR results"""
    buttons = []
    for e in elements:
        for kw in CLAIM_KEYWORDS:
            if kw in e["text"]:
                buttons.append((e["cx"], e["cy"], e["text"]))
                break
    return buttons


def detect_screen_state(ocr_results: list) -> ScreenState:
    """
    Detect current screen state based on OCR results.

    Args:
        ocr_results: List of results from MaaMCP OCR

    Returns:
        ScreenState: Screen state detection result
    """
    if not ocr_results:
        return ScreenState(description="OCR no results")

    elements = _normalize_ocr(ocr_results)
    if not elements:
        return ScreenState(description="OCR no text found")

    state = ScreenState()
    state.top_bar_visible = _check_world_map_topbar(elements)

    # Check top bar buttons
    if state.top_bar_visible:
        for name, cfg in TOP_BAR_BUTTONS.items():
            btn = _find_button_at(elements, cfg["x_range"], cfg["y_range"])
            if btn:
                state.top_bar_buttons.append(name)

    # Check right-side overlay panel
    overlay_detected, overlay_elems = _detect_overlay(elements)
    state.overlay_detected = overlay_detected
    if overlay_detected:
        state.overlay_texts = [e["text"] for e in overlay_elems]

    # Check claim buttons
    state.claim_buttons = _find_claim_buttons(elements)

    # Collect interactive elements
    for e in elements:
        if e["score"] > 0.5 and e["w"] > 20:
            state.interactive_elements.append(e)

    # Determine page type
    if _check_title_screen(elements):
        state.page_type = "title"
        state.description = "Title/Login screen"
    elif _check_loading_screen(elements):
        state.page_type = "loading"
        state.description = "Game loading"
    elif _check_logged_out_screen(elements):
        state.page_type = "logout_dialog"
        state.description = "Logout/Timeout dialog"
    elif state.overlay_detected and state.top_bar_visible:
        state.page_type = "world_map_with_overlay"
        state.description = f"World map + overlay (detected {len(state.overlay_texts)} overlay texts)"
        if state.claim_buttons:
            state.description += f", {len(state.claim_buttons)} claim buttons"
    elif state.top_bar_visible:
        state.page_type = "world_map"
        state.description = f"World map (top bar: {', '.join(state.top_bar_buttons) or 'none'})"
    elif len(elements) >= 5 and any(e["w"] > 100 for e in elements):
        state.page_type = "sub_page"
        keywords_found = _find_keyword_matches(elements, OVERLAY_KEYWORDS)
        if keywords_found:
            state.description = f"Sub-page (has {len(keywords_found)} overlay keywords)"
        else:
            state.description = f"Sub-page ({len(elements)} text elements)"
    else:
        state.page_type = "other"
        state.description = f"Other page ({len(elements)} text elements)"

    state.confidence = min(1.0, len(elements) / 20)
    return state


def generate_navigation_plan(state: ScreenState) -> List[Dict]:
    """
    Generate navigation plan based on current screen state.

    Args:
        state: Screen state detection result

    Returns:
        list: Operation step list
    """
    plan = []

    if state.page_type == "title":
        plan.append({
            "type": "tap",
            "params": {"x": 640, "y": 360},
            "description": "Tap title screen to enter game"
        })
        plan.append({
            "type": "wait",
            "params": {"duration": 10},
            "description": "Wait for loading"
        })

    elif state.page_type == "loading":
        plan.append({
            "type": "wait",
            "params": {"duration": 10},
            "description": "Wait for loading complete"
        })

    elif state.page_type == "logout_dialog":
        plan.append({
            "type": "tap",
            "params": {"label": "confirm"},
            "description": "Confirm re-login"
        })

    elif state.page_type == "world_map":
        plan.append({
            "type": "tap",
            "params": {"x": KNOWN_COORDS["tasks_button"][0],
                       "y": KNOWN_COORDS["tasks_button"][1],
                       "label": "tasks_button"},
            "description": "Tap top bar tasks button to open panel"
        })
        plan.append({
            "type": "wait",
            "params": {"duration": 5},
            "description": "Wait for panel to open"
        })

    elif state.page_type == "world_map_with_overlay":
        if state.claim_buttons:
            for cx, cy, label in state.claim_buttons:
                plan.append({
                    "type": "tap",
                    "params": {"x": cx, "y": cy, "label": label},
                    "description": f"Tap claim button: {label}"
                })
                plan.append({
                    "type": "wait",
                    "params": {"duration": 5},
                    "description": "Wait for claim complete"
                })
        else:
            plan.append({
                "type": "swipe",
                "params": {"x1": 1100, "y1": 300, "x2": 1100, "y2": 600, "duration": 500},
                "description": "Swipe down overlay panel"
            })
            plan.append({
                "type": "wait",
                "params": {"duration": 3},
                "description": "Wait for swipe complete"
            })

    elif state.page_type == "sub_page":
        plan.append({
            "type": "back",
            "description": "Return to previous level"
        })
        plan.append({
            "type": "wait",
            "params": {"duration": 3},
            "description": "Wait for return complete"
        })

    return plan


class ScreenDecider:
    """Screen decision module - encapsulates OCR policy logic"""

    def __init__(self):
        self.logger = get_logger()

    def detect_screen_state(self, ocr_results: list) -> ScreenState:
        """Detect screen state"""
        return detect_screen_state(ocr_results)

    def generate_plan(self, state: ScreenState) -> List[Dict]:
        """Generate navigation plan"""
        return generate_navigation_plan(state)

    def decide_action(self, ocr_results: list) -> Tuple[ScreenState, List[Dict]]:
        """
        One-step decision: OCR results -> state detection -> navigation plan

        Returns:
            (ScreenState, navigation_plan)
        """
        state = self.detect_screen_state(ocr_results)
        plan = self.generate_plan(state)
        return state, plan


def main():
    """Test module"""
    print("=" * 60)
    print("OCR policy module - test")
    print("=" * 60)

    # Mock OCR results
    mock_ocr = [
        {"text": "Explore", "box": [30, 10, 60, 30], "score": 0.98},
        {"text": "DailyQuests", "box": [970, 80, 100, 40], "score": 0.95},
        {"text": "Claim", "box": [1020, 300, 60, 30], "score": 0.92},
        {"text": "OneKeyClaim", "box": [1000, 350, 100, 40], "score": 0.96},
    ]

    decider = ScreenDecider()
    state, plan = decider.decide_action(mock_ocr)

    print(f"\nPage type: {state.page_type}")
    print(f"Description: {state.description}")
    print(f"Claim buttons: {len(state.claim_buttons)} found")
    print(f"\nNavigation plan ({len(plan)} steps):")
    for i, step in enumerate(plan, 1):
        print(f"  {i}. {step['type']}: {step['description']}")


if __name__ == "__main__":
    main()
