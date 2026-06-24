#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
楂樼簿搴﹂〉闈㈠垎鏋愬櫒 v2 鈥?鍩轰簬 MaaEnd 寮忓婧愯瀺鍚堣瘑鍒?

瀹屽叏寮冪敤棰滆壊鍒嗗竷/鍍忕礌璁℃暟銆備娇鐢細
1. TemplateMatch 鈥?妯℃澘鍖归厤瀹氫綅鐗瑰畾 UI 鍏冪礌锛堣繑鍥?bbox+center锛?
2. ColorMatch (杞粨) 鈥?妫€娴嬬壒瀹氶鑹茬殑杩為€氬尯鍩熶綔涓?UI 鍏冪礌锛堣繑鍥?bboxes+centers锛?
3. And/Or 缁勫悎 鈥?澶氭潯浠惰瀺鍚?

鍙傝€冿細MaaEnd-2/assets/resource/pipeline/Common/
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
    """椤甸潰鍒嗘瀽鍣?v2 鈥?鍏ㄩ噺澶氭簮铻嶅悎锛屾棤棰滆壊鍒嗗竷
    
    鎵€鏈夎瘑鍒粨鏋滆繑鍥?bbox/center 鍧愭爣淇℃伅锛屼緵 LLM 鍐崇瓥浣跨敤銆?
    """

    def __init__(self):
        self.engine = RecognitionEngine()

    def analyze(self, img: np.ndarray) -> Dict[str, Any]:
        """澶氳妭鐐圭煭璺尮閰嶃€傚厛绮剧‘鍚庡娉涳細妯℃澘浼樺厛浜庨鑹茶疆寤?
        
        杩斿洖鏍煎紡锛?
        {
            "page_type": str,
            "confidence": float,
            "detail": {
                "method": str,
                "bbox": [x1, y1, x2, y2],  # 杈圭晫妗?
                "center": [cx, cy],         # 涓績鐐?
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

        # 鎵€鏈夐〉闈㈡娴嬪け璐?鈫?妫€鏌ユ槸鍚﹀湪娓告垙鍐?
        in_game = self._check_in_game(img, w, h)
        if not in_game:
            return {"page_type": "not_in_game", "confidence": 0.9,
                    "detail": {"reason": "no Endfield UI elements detected"},
                    "features": features}

        return {"page_type": "unknown", "confidence": 0.3, "detail": {},
                "features": features}

    def _extract_features(self, img: np.ndarray, w: int, h: int) -> Dict[str, Any]:
        """鎻愬彇 VLM 鎻愮ず璇嶆墍闇€鐨勭敾闈㈢壒寰?""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # 宸︿晶杈规爮浜害
        left_bar = gray[:, max(0, w//20):w//6]
        left_bar_brightness = float(np.mean(left_bar)) if left_bar.size > 0 else 0

        # 鍙充笂瑙掔豢鑹插儚绱?
        green_lower = np.array([35, 50, 50])
        green_upper = np.array([85, 255, 255])
        green_mask = cv2.inRange(hsv, green_lower, green_upper)
        top_right_green = green_mask[0:h//5, max(0, w*3//4):w]
        green_pixels_top_right = int(cv2.countNonZero(top_right_green))

        # 鍏ㄥ睆浜害
        full_brightness = float(np.mean(gray))

        return {
            "left_bar_brightness": left_bar_brightness,
            "green_pixels_top_right": green_pixels_top_right,
            "full_brightness": full_brightness,
        }

    # 鈹€鈹€ 鍚勯〉闈㈡娴?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _check_exit_dialog(self, img, w, h):
        """閫€鍑哄璇濇锛欳ancelButton SIFT + 閲戣壊杞粨鍙岄獙璇?
        
        杩斿洖鍖呭惈 bbox 鍜?center 鍧愭爣淇℃伅銆?
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
        """浠诲姟闈㈡澘锛歍askIcon SIFT
        
        杩斿洖鍖呭惈 bbox 鍜?center 鍧愭爣淇℃伅銆?
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
        
        # 鍥為€€锛氶噾鑹茶疆寤?
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
        """涓栫晫椤甸潰锛歐orldMenu SIFT 鍖归厤 鎴?缁胯壊璧勬簮鍥炬爣
        
        杩斿洖鍖呭惈 bbox 鍜?center 鍧愭爣淇℃伅銆?
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

        # 鏂瑰紡 B: 鍙充笂瑙掔豢鑹茶祫婧愬浘鏍囷紙杞粨妫€娴嬶級
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
        """绯荤粺鑿滃崟锛氬簳閮ㄩ噾榛勮壊杞粨
        
        杩斿洖鍖呭惈 bboxes 鍜?centers 鍧愭爣淇℃伅銆?
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
        """杩涘叆娓告垙鍑嗗鐢婚潰锛氬皻鏃犲彲闈犳娴嬫柟寮忥紝鏆傝烦杩?""
        return False, {}

    def _check_in_game(self, img, w, h):
        """妫€鏌ユ槸鍚﹀湪 Endfield 娓告垙鍐咃細鍏ㄥ睆鎼滅储閲戣壊 UI 鍏冪礌"""
        ok, r = self.engine.recognize(img, {
            "type": "ColorMatch",
            "roi": [0, 0, w, h],
            "lower": [15, 80, 100],
            "upper": [35, 255, 255],
            "min_area": 50,
            "min_contours": 2
        })
        return ok

# 鍚戝悗鍏煎鍒悕
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
        print(f"[椤甸潰] {result['page_type']} (缃俊搴?{result['confidence']:.2f})")
        print(f"[璇︽儏] {result['detail']}")
    else:
        print("[閿欒] 鎴浘澶辫触")

