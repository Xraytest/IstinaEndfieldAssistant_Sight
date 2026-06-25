#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
HighPrecisionPageAnalyzer v2 - based on MaaEnd multi-template fusion recognition

Fully uses color distribution/element counting. Features:
1. TemplateMatch - template matching to determine UI elements (returns bbox+center)
2. ColorMatch (HSV) - uses HSV color space intervals as UI elements (returns bboxes+centers)
3. And/Or combination - multi-condition fusion

Reference: MaaEnd-2/assets/resource/pipeline/Common/
"""

import cv2
import numpy as np
from typing import Dict, Any, Tuple
from pathlib import Path
import sys

from core.foundation.paths import get_src_dir, ensure_src_path
ensure_src_path(__file__)

from core.capability.recognition import RecognitionEngine


class HighPrecisionPageAnalyzerV2:
    """Page analyzer v2 - highly multi-template fusion, no color distribution

    All recognition results return bbox/center coordinate info for LLM decision use.
    """

    def __init__(self):
        self.engine = RecognitionEngine()

    def analyze(self, img: np.ndarray) -> Dict[str, Any]:
        """Multi-shortcut template matching. Priority: template first, then color: svm

        Return format:
        {
            "page_type": str,
            "confidence": float,
            "detail": {
                "method": str,
                "bbox": [x1, y1, x2, y2],  # bounding box
                "center": [cx, cy],         # center coordinates
                ...
            },
            "features": {...}
        }
        """
        h, w = img.shape[:2]  # 1080x1920
        features = self._extract_features(img, w, h)
        checks = [
            ("exit_dialog", self._check_exit_dialog),
            ("quest_panel", self._check_quest_panel),
            ("world", self._check_world),
            ("enter_game_prompt", self._check_enter_game),
            ("menu", self._check_menu),
        ]
        for name, check_fn in checks:
            ok, detail = check_fn(img, w, h)
            if ok:
                return {"page_type": name, "confidence": 0.85, "detail": detail,
                        "features": features}

        # All page checks failed -> check if in game
        in_game = self._check_in_game(img, w, h)
        if not in_game:
            return {"page_type": "not_in_game", "confidence": 0.9,
                    "detail": {"reason": "no Endfield UI elements detected"},
                    "features": features}

        return {"page_type": "unknown", "confidence": 0.3, "detail": {},
                "features": features}

    def _extract_features(self, img: np.ndarray, w: int, h: int) -> Dict[str, Any]:
        """Extract features needed for VLM prompts"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Left sidebar brightness
        left_bar = gray[:, max(0, w//20):w//6]
        left_bar_brightness = float(np.mean(left_bar)) if left_bar.size > 0 else 0

        # Top-right green pixels
        green_lower = np.array([35, 50, 50])
        green_upper = np.array([85, 255, 255])
        green_mask = cv2.inRange(hsv, green_lower, green_upper)
        top_right_green = green_mask[0:h//5, max(0, w*3//4):w]
        green_pixels_top_right = int(cv2.countNonZero(top_right_green))

        # Full screen brightness
        full_brightness = float(np.mean(gray))

        return {
            "left_bar_brightness": left_bar_brightness,
            "green_pixels_top_right": green_pixels_top_right,
            "full_brightness": full_brightness,
        }

    # ============================================================
    # Page checks
    # ============================================================

    def _check_exit_dialog(self, img, w, h):
        """Exit dialog detection (CancelButton SIFT + green pixel verification)

        Returns content bbox and center coordinate info.
        """
        ok_color, rc = self.engine.recognize(img, {
            "type": "ColorMatch",
            "roi": [200, 400, min(700, w-200), min(600, h-400)],
            "lower": [15, 80, 100],
            "upper": [35, 255, 255],
            "min_area": 50,
            "min_contours": 1
        })

        ok_sift, rs = self.engine.recognize(img, {
            "type": "TemplateMatch",
            "template": "Common/Button/CancelButtonType1.png",
            "roi": [200, 500, min(700, w-200), min(500, h-500)],
            "threshold": 4
        })

        if ok_color and ok_sift:
            return True, {
                "method": "CancelButton+SIFT+Color",
                "bbox": rs.get("bbox"),
                "center": rs.get("center"),
                "contours": rc.get("contours", 0),
                "color_bboxes": rc.get("bboxes", []),
                "color_centers": rc.get("centers", [])
            }

        if ok_sift:
            return True, {
                "method": "CancelButton+SIFT",
                "bbox": rs.get("bbox"),
                "center": rs.get("center"),
                "confidence": rs.get("confidence", 0)
            }

        return False, {}

    def _check_quest_panel(self, img, w, h):
        """Quest panel: TaskIcon SIFT

        Returns content bbox and center coordinate info.
        """
        ok, r = self.engine.recognize(img, {
            "type": "TemplateMatch",
            "template": "SceneManager/TaskIcon.png",
            "roi": [min(700, w-300), 30, min(280, w-700), min(120, h-30)],
            "threshold": 6
        })
        if ok:
            return True, {
                "method": "TaskIcon",
                "bbox": r.get("bbox"),
                "center": r.get("center"),
                "confidence": r.get("confidence", 0)
            }

        # Fallback: gold color region
        ok_color, rc = self.engine.recognize(img, {
            "type": "ColorMatch",
            "roi": [min(600, w-400), 30, min(400, w-600), min(250, h-30)],
            "lower": [15, 80, 100],
            "upper": [35, 255, 255],
            "min_area": 40,
            "min_contours": 3
        })
        if ok_color:
            return True, {
                "method": "QuestGoldContours",
                "contours": rc.get("contours"),
                "bboxes": rc.get("bboxes", []),
                "centers": rc.get("centers", [])
            }
        return False, {}

    def _check_world(self, img, w, h):
        """World page: WorldMenu SIFT match and green resource icon

        Returns content bbox and center coordinate info.
        """
        ok, r = self.engine.recognize(img, {
            "type": "TemplateMatch",
            "template": "SceneManager/WorldMenu.png",
            "roi": [0, 0, min(200, w), min(200, h)],
            "threshold": 4
        })
        if ok:
            return True, {
                "method": "WorldMenu",
                "bbox": r.get("bbox"),
                "center": r.get("center"),
                "confidence": r.get("confidence", 0)
            }

        # Method B: top-right green resource icon map (HSV check)
        rx = max(0, w-500)
        ok_green, rc = self.engine.recognize(img, {
            "type": "ColorMatch",
            "roi": [rx, 0, min(500, w-rx), min(150, h)],
            "lower": [35, 80, 80],
            "upper": [85, 255, 200],
            "min_area": 50,
            "min_contours": 1
        })
        if ok_green:
            return True, {
                "method": "GreenResourceIcon",
                "contours": rc.get("contours"),
                "bboxes": rc.get("bboxes", []),
                "centers": rc.get("centers", [])
            }

        return False, {}

    def _check_menu(self, img, w, h):
        """System menu: bottom-left gold color

        Returns bboxes and centers coordinate info.
        """
        ry = max(0, h-500)
        ok, rc = self.engine.recognize(img, {
            "type": "ColorMatch",
            "roi": [200, ry, min(1500, w-200), min(500, h-ry)],
            "lower": [15, 100, 200],
            "upper": [35, 255, 255],
            "min_area": 80,
            "min_contours": 3
        })
        if ok:
            return True, {
                "method": "MenuGoldContours",
                "contours": rc.get("contours"),
                "bboxes": rc.get("bboxes", []),
                "centers": rc.get("centers", [])
            }
        return False, {}

    def _check_enter_game(self, img, w, h):
        """Game start preparation screen: hard to recognize, skip directly"""
        return False, {}

    def _check_in_game(self, img, w, h):
        """Check if in Endfield game: full screen yellow-green UI elements"""
        ok, r = self.engine.recognize(img, {
            "type": "ColorMatch",
            "roi": [0, 0, w, h],
            "lower": [15, 80, 100],
            "upper": [35, 255, 255],
            "min_area": 50,
            "min_contours": 2
        })
        return ok

# Backward compatible alias
HighPrecisionPageAnalyzer = HighPrecisionPageAnalyzerV2

if __name__ == "__main__":
    import subprocess
    from pathlib import Path

    PROJECT = Path(__file__).resolve().parent.parent.parent
    ADB = PROJECT / '3rd-part' / 'adb' / 'adb.exe'

    r = subprocess.run([str(ADB), "-s", "localhost:16512", "exec-out", "screencap", "-p"],
                      capture_output=True, timeout=10)
    if r.returncode == 0 and len(r.stdout) > 1000:
        img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
        analyzer = HighPrecisionPageAnalyzerV2()
        result = analyzer.analyze(img)
        print(f"[Page] {result['page_type']} (confidence: {result['confidence']:.2f})")
        print(f"[Detail] {result['detail']}")
    else:
        print("[Error] Screenshot failed")
