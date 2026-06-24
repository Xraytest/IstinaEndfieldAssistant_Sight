#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鐧诲嚭瀵硅瘽妗嗘娴嬪櫒 - MaaEnd 寮忚璁?
鍙傝€?MaaEnd 鐨勫仛娉曪細
1. 鍦ㄧ壒瀹?ROI 鍖哄煙浣跨敤 OCR 妫€娴嬪叧閿瘝
2. 鏀寔澶氳瑷€鍏抽敭璇?3. 鑷姩澶勭悊鐧诲嚭瀵硅瘽妗?"""

import sys
import os
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()


# MaaEnd 寮忕殑鐧诲嚭瀵硅瘽妗嗗叧閿瘝锛堝璇█锛?LOGOUT_KEYWORDS = [
    # 绠€浣撲腑鏂?    "鐧诲嚭", "閫€鍑?, "鐧诲綍鐣岄潰", "瓒呮椂", "閲嶆柊鐧诲綍", "浼氳瘽杩囨湡", "鑷姩鐧诲嚭",
    "闀挎椂闂?, "娌℃湁鎿嶄綔", "鏂紑杩炴帴", "纭", "鍙栨秷",
    # 绻佷綋涓枃
    "鐧诲嚭", "閫€鍑?, "鐧诲叆浠嬮潰", "瓒呮檪", "閲嶆柊鐧诲叆", "鏈冭┍閬庢湡",
    # 鑻辨枃
    "logout", "log out", "login screen", "timeout", "session expired",
    "re-login", "disconnect", "confirm", "cancel",
    # 鏃ユ枃
    "鐢婚潰銇埢銈娿伨銇欍亱", "銉偘銈偊銉?, "銉偘銈ゃ兂", "銈裤偆銉犮偄銈︺儓",
    # 闊╂枃
    "雮橁皜鞁滉矤鞀惦媹旯?, "搿滉犯鞎勳泝", "搿滉犯鞚?, "鞁滉皠齑堦臣"
]


def detect_logout_dialog_ocr(ocr_results: list) -> bool:
    """
    浣跨敤 OCR 缁撴灉妫€娴嬬櫥鍑哄璇濇锛圡aaEnd 寮忥級
    
    Args:
        ocr_results: OCR 璇嗗埆缁撴灉鍒楄〃锛屾瘡椤瑰寘鍚?text"瀛楁
        
    Returns:
        bool: 鏄惁妫€娴嬪埌鐧诲嚭瀵硅瘽妗?    """
    # 鍚堝苟鎵€鏈?OCR 鏂囨湰
    all_text = " ".join([elem.get("text", "") for elem in ocr_results])
    
    # 妫€鏌ュ叧閿瘝
    for keyword in LOGOUT_KEYWORDS:
        if keyword.lower() in all_text.lower():
            return True
    
    return False


def detect_logout_dialog_roi(ocr_results: list, roi: tuple = None) -> bool:
    """
    鍦ㄧ壒瀹?ROI 鍖哄煙妫€娴嬬櫥鍑哄璇濇锛圡aaEnd 寮忥級
    
    Args:
        ocr_results: OCR 璇嗗埆缁撴灉鍒楄〃锛屾瘡椤瑰寘鍚?text"鍜?box"瀛楁
        roi: ROI 鍖哄煙 (x, y, w, h)锛岄粯璁や负 MaaEnd 浣跨敤鐨勫尯鍩?        
    Returns:
        bool: 鏄惁妫€娴嬪埌鐧诲嚭瀵硅瘽妗?    """
    # MaaEnd 浣跨敤鐨?ROI 鍖哄煙锛?280x720 鍒嗚鲸鐜囷級
    if roi is None:
        roi = (400, 250, 470, 200)  # x, y, w, h
    
    rx, ry, rw, rh = roi
    
    # 绛涢€?ROI 鍖哄煙鍐呯殑 OCR 缁撴灉
    roi_texts = []
    for elem in ocr_results:
        text = elem.get("text", "")
        box = elem.get("box", [])
        
        if len(box) >= 4:
            # box 鏍煎紡锛歔x1, y1, x2, y2] 鎴?[x1, y1, w, h]
            if box[2] > 1000:  # 濡傛灉鏄鏍煎紡
                ex, ey, ew, eh = box
            else:  # 濡傛灉鏄潗鏍囨牸寮?                ex, ey, ew, eh = box[0], box[1], box[2] - box[0], box[3] - box[1]
            
            # 妫€鏌ユ槸鍚﹀湪 ROI 鍐?            if (rx <= ex < rx + rw and ry <= ey < ry + rh):
                roi_texts.append(text)
    
    # 鍚堝苟 ROI 鏂囨湰
    roi_text = " ".join(roi_texts)
    
    # 妫€鏌ュ叧閿瘝
    for keyword in LOGOUT_KEYWORDS:
        if keyword.lower() in roi_text.lower():
            return True
    
    return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="鐧诲嚭瀵硅瘽妗嗘娴嬪櫒 - MaaEnd 寮?)
    parser.add_argument("--test", action="store_true", help="杩愯娴嬭瘯")
    args = parser.parse_args()
    
    if args.test:
        # 娴嬭瘯鏁版嵁
        test_ocr_results = [
            {"text": "妫€娴嬪埌浼氳瘽瓒呮椂", "box": [400, 250, 500, 300]},
            {"text": "璇烽噸鏂扮櫥褰?, "box": [410, 280, 510, 320]},
            {"text": "纭", "box": [450, 350, 500, 400]},
            {"text": "鍙栨秷", "box": [520, 350, 570, 400]},
        ]
        
        result1 = detect_logout_dialog_ocr(test_ocr_results)
        print(f"鍏ㄥ浘 OCR 妫€娴嬶細{'鉁?妫€娴嬪埌鐧诲嚭瀵硅瘽妗? if result1 else '鉁?鏈娴嬪埌'}")
        
        result2 = detect_logout_dialog_roi(test_ocr_results)
        print(f"ROI 鍖哄煙妫€娴嬶細{'鉁?妫€娴嬪埌鐧诲嚭瀵硅瘽妗? if result2 else '鉁?鏈娴嬪埌'}")
        
        print(f"\n鍏抽敭璇嶅垪琛?({len(LOGOUT_KEYWORDS)} 涓?:")
        for kw in LOGOUT_KEYWORDS[:10]:
            print(f"  - {kw}")
        if len(LOGOUT_KEYWORDS) > 10:
            print(f"  ... 浠ュ強 {len(LOGOUT_KEYWORDS) - 10} 涓洿澶?)
    else:
        print("鐧诲嚭瀵硅瘽妗嗘娴嬪櫒 - MaaEnd 寮忚璁?)
        print(f"鏀寔 {len(LOGOUT_KEYWORDS)} 涓叧閿瘝锛堝璇█锛?)
        print("\n浣跨敤鏂规硶:")
        print("  python scripts/detect_logout_maaend.py --test")


if __name__ == "__main__":
    main()

