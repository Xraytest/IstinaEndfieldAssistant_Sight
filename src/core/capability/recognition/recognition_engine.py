#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
璇嗗埆寮曟搸 - MaaEnd 寮忓婧愯瀺鍚堣瘑鍒郴缁?

瀹炵幇 MaaEnd 鐨勬牳蹇冭瘑鍒兘鍔涳細
1. 妯℃澘鍖归厤锛圱emplateMatch锛? OpenCV SIFT 鐗瑰緛鍖归厤
2. 棰滆壊鍖归厤锛圕olorMatch锛? OpenCV HSV 棰滆壊杞粨妫€娴?
3. 缁勫悎璇嗗埆锛圓nd/Or锛?
4. OCR 璇嗗埆 - MaaFw Pipeline 鍐呭缓 OCR 寮曟搸

鍙傝€冿細MaaEnd-2/assets/resource/pipeline/Common/
"""

import cv2
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
import sys

from core.foundation.paths import get_project_root, ensure_src_path
ensure_src_path(__file__)


class RecognitionEngine:
    """璇嗗埆寮曟搸锛屾敮鎸?MaaEnd 寮忚妭鐐硅瘑鍒?

    OCR 閫氳繃 MaaFw Pipeline 绯荤粺璋冪敤锛堝唴寤?OCR 寮曟搸锛夈€?
    鏈紩鎿庤礋璐ｏ細妯℃澘鍖归厤銆侀鑹插尮閰嶃€佺粍鍚堥€昏緫銆?
    """

    def __init__(self, assets_dir: str = None):
        self.assets_dir = Path(assets_dir) if assets_dir else Path(get_project_root(__file__)) / "assets"

    # 鈹€鈹€ 涓诲垎鍙?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def recognize(self, img: np.ndarray, node_config: Dict[str, Any]) -> Tuple[bool, Any]:
        """鎵ц鑺傜偣璇嗗埆"""
        node_type = node_config.get("type", "")

        if node_type == "TemplateMatch":
            return self._template_match(img, node_config)
        elif node_type == "ColorMatch":
            return self._color_match(img, node_config)
        elif node_type == "And":
            return self._and_recognize(img, node_config)
        elif node_type == "Or":
            return self._or_recognize(img, node_config)
        elif node_type == "OCR":
            # OCR 閫氳繃 MaaFw Pipeline 鎵ц锛屾澶勮繑鍥炴彁绀?
            return False, {"reason": "OCR 闇€閫氳繃 MaaFw Pipeline 鎵ц锛岃浣跨敤 Tasker.post_recognition()"}
        elif isinstance(node_config, str):
            return False, None
        return False, None

    # 鈹€鈹€ 妯℃澘鍖归厤锛圫IFT 鐗瑰緛鍖归厤锛屽昂搴︿笉鍙橈級鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _template_match(self, img: np.ndarray, config: Dict[str, Any]) -> Tuple[bool, Any]:
        """SIFT 鐗瑰緛鍖归厤 鈥?灏哄害/鏃嬭浆涓嶅彉锛岃繙瓒呬紶缁熸ā鏉垮尮閰?

        config: {template: str, roi: [x,y,w,h], threshold: float (鏈€灏忓尮閰嶇偣鏁?}
        
        杩斿洖鏍煎紡:
        - 鎴愬姛锛?True, {"bbox": [x1, y1, x2, y2], "center": [cx, cy], "matches": int, "confidence": float})
        - 澶辫触锛?False, {"matches": int})
        """
        template_path = config.get("template", "")
        roi = config.get("roi")
        min_matches = config.get("threshold", 10)  # reinterpret as min matches

        if not Path(template_path).is_absolute():
            template_path = self.assets_dir / template_path

        template = cv2.imread(str(template_path))
        if template is None:
            return False, {"error": "template not found"}

        x, y = 0, 0
        if roi:
            rx, ry, rw, rh = roi
            search_img = img[ry:ry+rh, rx:rx+rw]
            x, y = rx, ry
        else:
            search_img = img

        # SIFT 妫€娴嬪櫒
        sift = cv2.SIFT_create()

        # 杞崲涓虹伆搴?
        gray_tmpl = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        gray_src = cv2.cvtColor(search_img, cv2.COLOR_BGR2GRAY)

        kp1, des1 = sift.detectAndCompute(gray_tmpl, None)
        kp2, des2 = sift.detectAndCompute(gray_src, None)

        if des1 is None or des2 is None or len(des1) < 4 or len(des2) < 4:
            return False, {"matches": 0}

        # FLANN 鍖归厤
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        matches = flann.knnMatch(des1, des2, k=2)

        # Lowe's ratio test
        good = []
        for m, n in matches:
            if m.distance < 0.75 * n.distance:
                good.append(m)

        if len(good) >= min_matches:
            # 璁＄畻鍖归厤鍖哄煙杈圭晫妗?
            pts = [kp2[m.trainIdx].pt for m in good]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            
            # 杞崲涓哄叏灞€鍧愭爣
            global_x1 = int(min_x) + x
            global_y1 = int(min_y) + y
            global_x2 = int(max_x) + x
            global_y2 = int(max_y) + y
            
            # 璁＄畻涓績鐐?
            cx = int((global_x1 + global_x2) / 2)
            cy = int((global_y1 + global_y2) / 2)
            
            # 璁＄畻缃俊搴︼紙鍖归厤鐐规暟褰掍竴鍖栵級
            confidence = min(1.0, len(good) / 20.0)
            
            return True, {
                "bbox": [global_x1, global_y1, global_x2, global_y2],
                "center": [cx, cy],
                "matches": len(good),
                "confidence": confidence,
                "template": template_path
            }

        return False, {"matches": len(good)}

    # 鈹€鈹€ 棰滆壊鍖归厤锛堣疆寤撴娴嬶紝闈炲儚绱犲垎甯冿級鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _color_match(self, img: np.ndarray, config: Dict[str, Any]) -> Tuple[bool, Any]:
        """棰滆壊鍏冪礌妫€娴嬶細鍦?ROI 鍐呮煡鎵捐嚦灏?min_contours 涓寚瀹氶鑹茬殑杩為€氬尯鍩?

        config: {roi: [x,y,w,h], lower: [h,s,v], upper: [h,s,v],
                 min_area: int, min_contours: int}
        
        杩斿洖鏍煎紡:
        - 鎴愬姛锛?True, {"contours": int, "bboxes": [[x1,y1,x2,y2],...], "centers": [[cx,cy],...], "total_area": int})
        - 澶辫触锛?False, {"contours": int})
        """
        roi = config.get("roi")
        lower = np.array(config.get("lower"))
        upper = np.array(config.get("upper"))
        min_area = config.get("min_area", 30)
        min_contours = config.get("min_contours", 1)

        x_offset, y_offset = 0, 0
        if roi:
            rx, ry, rw, rh = roi
            img_crop = img[ry:ry+rh, rx:rx+rw]
            x_offset, y_offset = rx, ry
        else:
            img_crop = img

        hsv = cv2.cvtColor(img_crop, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower, upper)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        valid_contours = []
        bboxes = []
        centers = []
        total_area = 0
        
        for c in contours:
            area = cv2.contourArea(c)
            if area >= min_area:
                valid_contours.append(c)
                total_area += area
                
                # 璁＄畻杈圭晫妗?
                x, y, w, h = cv2.boundingRect(c)
                # 杞崲涓哄叏灞€鍧愭爣
                global_x1 = x + x_offset
                global_y1 = y + y_offset
                global_x2 = x + w + x_offset
                global_y2 = y + h + y_offset
                bboxes.append([global_x1, global_y1, global_x2, global_y2])
                
                # 璁＄畻涓績鐐?
                cx = global_x1 + w // 2
                cy = global_y1 + h // 2
                centers.append([cx, cy])

        if len(valid_contours) >= min_contours:
            return True, {
                "contours": len(valid_contours),
                "bboxes": bboxes,
                "centers": centers,
                "total_area": total_area
            }

        return False, {"contours": len(valid_contours)}

    # 鈹€鈹€ 缁勫悎璇嗗埆 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _and_recognize(self, img: np.ndarray, config: Dict[str, Any]) -> Tuple[bool, Any]:
        """And锛氭墍鏈夊瓙鑺傜偣閮藉尮閰嶏紝鑱氬悎鎵€鏈?bbox 淇℃伅"""
        all_bboxes = []
        all_centers = []
        
        for node in config.get("nodes", []):
            ok, result = self.recognize(img, node)
            if not ok:
                return False, None
            # 鑱氬悎 bbox 淇℃伅
            if result:
                if "bbox" in result:
                    all_bboxes.append(result["bbox"])
                if "bboxes" in result:
                    all_bboxes.extend(result["bboxes"])
                if "center" in result:
                    all_centers.append(result["center"])
                if "centers" in result:
                    all_centers.extend(result["centers"])
        
        return True, {"bboxes": all_bboxes, "centers": all_centers}

    def _or_recognize(self, img: np.ndarray, config: Dict[str, Any]) -> Tuple[bool, Any]:
        """Or锛氫换涓€瀛愯妭鐐瑰尮閰嶅嵆鎴愬姛锛堢煭璺眰鍊硷級锛岃繑鍥炵涓€涓尮閰嶇殑瀹屾暣淇℃伅"""
        for node in config.get("nodes", []):
            ok, result = self.recognize(img, node)
            if ok:
                return True, result
        return False, None


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
# MaaFw Pipeline OCR 灏佽
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

class MaaFwPipelineOCR:
    """閫氳繃 MaaFw Tasker + Resource 绠￠亾绯荤粺鎵ц OCR

    鐢ㄦ硶:
        from maa import Tasker, Resource, Controller
        from maa.pipeline import JRecognitionType, JOCR

        # 鍒涘缓 Tasker 骞剁粦瀹?Resource/Controller
        tasker = Tasker()
        resource = Resource()
        controller = Controller()
        tasker.bind(resource, controller)

        # 鎵ц OCR
        ocr_param = JOCR(
            expected=["棰嗗彇", "Claim"],
            roi=(0, 0, 1280, 720)
        )
        job = tasker.post_recognition(JRecognitionType.OCR, ocr_param, image)
        detail = job.get()
    """

    @staticmethod
    def create_ocr_param(expected: List[str], roi: Tuple[int, int, int, int] = (0, 0, 0, 0),
                         threshold: float = 0.3) -> Dict[str, Any]:
        """
        鍒涘缓 OCR 璇嗗埆鍙傛暟锛圝SON 鏍煎紡锛岀敤浜?Pipeline 閰嶇疆锛?

        Args:
            expected: 鏈熸湜鍖归厤鐨勬枃鏈垪琛紙鏀寔姝ｅ垯琛ㄨ揪寮忥級
            roi: 璇嗗埆鍖哄煙 (x, y, w, h)
            threshold: 缃俊搴﹂槇鍊?

        Returns:
            OCR 鍙傛暟瀛楀吀
        """
        return {
            "type": "OCR",
            "param": {
                "expected": expected,
                "roi": list(roi),
                "threshold": threshold
            }
        }

    @staticmethod
    def doc():
        """杩斿洖 MaaFw OCR 浣跨敤鏂囨。"""
        return """
MaaFw Pipeline OCR 浣跨敤鎸囧崡
==========================

1. 閫氳繃 Tasker.post_recognition() 鎵ц OCR:
   from maa import Tasker, JRecognitionType
   from maa.pipeline import JOCR

   ocr_param = JOCR(
       expected=["棰嗗彇", "Claim", "(?i)collect"],  # 鏀寔姝ｅ垯
       roi=(0, 0, 1280, 720),
       threshold=0.3
   )
   job = tasker.post_recognition(JRecognitionType.OCR, ocr_param, image)

2. 鍦?Pipeline JSON 涓厤缃?OCR:
   {
       "CheckClaimButton": {
           "recognition": {
               "type": "OCR",
               "param": {
                   "expected": ["棰嗗彇", "涓€閿鍙?, "Claim"],
                   "roi": [950, 60, 330, 640],
                   "threshold": 0.3
               }
           },
           "action": {"type": "Click"}
       }
   }

3. OCR 缁撴灉鏍煎紡锛堥噸瑕侊細鍖呭惈瀹屾暣鍧愭爣淇℃伅渚?LLM 鍐崇瓥锛?
   RecognitionDetail(
       hit: bool,                          # 鏄惁鍖归厤鏈熸湜鏂囨湰
       box: (x, y, w, h),                  # 鍖归厤浣嶇疆杈圭晫妗?
       all_results: list[RecognitionResult],  # 鎵€鏈夎瘑鍒粨鏋?
       best_result: RecognitionResult       # 鏈€浣冲尮閰嶇粨鏋?
   )
   
   RecognitionResult 鍖呭惈:
   - text: str              # 璇嗗埆鐨勬枃鏈?
   - bbox: [x1, y1, x2, y2] # 鏂囨湰杈圭晫妗嗭紙鍏ㄥ眬鍧愭爣锛?
   - center: [cx, cy]       # 鏂囨湰涓績鐐?
   - confidence: float      # 缃俊搴?

4. 鏀寔鐨勭壒鎬?
   - 澶氳瑷€鑷姩妫€娴嬶紙涓枃/鑻辨枃/鏃ユ枃/闊╂枃锛?
   - 姝ｅ垯琛ㄨ揪寮忓尮閰嶏紙濡?(?i) 涓嶅尯鍒嗗ぇ灏忓啓锛?
   - ROI 鍖哄煙璇嗗埆
   - 缃俊搴﹂槇鍊艰繃婊?
   - 鏂囨湰鎺掑簭锛圚orizontal/Vertical/Area 绛夛級
   - **杩斿洖瀹屾暣鍧愭爣淇℃伅锛孡LM 鍙牴鎹潗鏍囪嚜琛屽喅瀹氱偣鍑讳綅缃?*
"""


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
# 棰勫畾涔夌姸鎬佽妭鐐癸紙鍙傝€?MaaEnd锛岄€傞厤 OpenCV 瀹炵幇锛?
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

PREDEFINED_STATES = {
    # 鈹€鈹€ 鍙栨秷鎸夐挳锛堝璇濇鍖哄煙 SIFT锛岄槇鍊?5 鏈€灏忓尮閰嶇偣锛?鈹€鈹€
    "CancelButton": {
        "type": "Or",
        "nodes": [
            {
                "type": "TemplateMatch",
                "template": "Common/Button/CancelButtonType1.png",
                "roi": [200, 500, 700, 500],
                "threshold": 5
            },
            {
                "type": "TemplateMatch",
                "template": "Common/Button/CancelButtonType2.png",
                "roi": [200, 500, 700, 500],
                "threshold": 5
            }
        ]
    },

    # 鈹€鈹€ 涓栫晫椤甸潰锛堝乏涓婅灏?ROI SIFT锛?鈹€鈹€
    "InWorld": {
        "type": "Or",
        "nodes": [
            {
                "type": "TemplateMatch",
                "template": "SceneManager/WorldMenu.png",
                "roi": [0, 0, 200, 200],
                "threshold": 5
            },
            {
                "type": "TemplateMatch",
                "template": "Common/Button/RegionalDevelopmentButton.png",
                "roi": [0, 0, 300, 100],
                "threshold": 5
            }
        ]
    },

    # 鈹€鈹€ 浠诲姟鍥炬爣锛堝彸涓婅 ROI锛岄珮闃堝€奸槻璇尮閰嶏級 鈹€鈹€
    "TaskIcon": {
        "type": "TemplateMatch",
        "template": "SceneManager/TaskIcon.png",
        "roi": [700, 30, 300, 150],
        "threshold": 15
    },

    # 鈹€鈹€ 榛勮壊纭鎸夐挳锛堥鑹茶疆寤?+ 妯℃澘鍙岄獙璇侊級 鈹€鈹€
    "YellowConfirmButton": {
        "type": "And",
        "nodes": [
            {
                "type": "ColorMatch",
                "roi": [200, 500, 700, 500],
                "lower": [28, 100, 100],
                "upper": [29, 255, 255],
                "min_area": 100,
                "min_contours": 1
            },
            {
                "type": "TemplateMatch",
                "template": "Common/Button/YellowConfirmButtonType1.png",
                "roi": [200, 500, 700, 500],
                "threshold": 5
            }
        ]
    },

    # 鈹€鈹€ 鑿滃崟鍒楄〃锛堥鑹查獙璇侊紝OCR 闇€ MaaFw Pipeline锛?鈹€鈹€
    "InMenuList": {
        "type": "And",
        "nodes": [
            {
                "type": "ColorMatch",
                "roi": [0, 1760, 200, 200],
                "lower": [90, 35, 35],
                "upper": [191, 83, 85],
                "min_area": 30,
                "min_contours": 2
            }
        ],
        "note": "OCR 閮ㄥ垎闇€閫氳繃 MaaFw Pipeline 鎵ц"
    },

    # 鈹€鈹€ 琛屽姩鎵嬪唽锛圤CR 闇€ MaaFw Pipeline锛?鈹€鈹€
    "InOperationalManual": {
        "note": "闇€閫氳繃 MaaFw Pipeline OCR 鎵ц:\n" +
                "  ocr_param = JOCR(expected=['琛屽姩鎵嬪唽', 'Operational Manual'], roi=(0, 0, 215, 60))"
    }
}


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
# 娴嬭瘯浠ｇ爜
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

if __name__ == "__main__":
    from pathlib import Path

    # recognition_engine.py 鍦?src/core/recognition/
    SRC_DIR = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(SRC_DIR))

    print("=" * 60)
    print("璇嗗埆寮曟搸娴嬭瘯锛圡aaFw OCR + OpenCV 妯℃澘/棰滆壊鍖归厤锛?)
    print("=" * 60)

    # 鎵撳嵃 MaaFw OCR 浣跨敤鏂囨。
    print("\nMaaFw OCR 浣跨敤鎸囧崡:")
    print(MaaFwPipelineOCR.doc())

    # 娴嬭瘯棰勫畾涔夌姸鎬?
    print("\n棰勫畾涔夌姸鎬佽妭鐐?")
    for name, config in PREDEFINED_STATES.items():
        print(f"  - {name}: {config.get('type', 'N/A')}")

