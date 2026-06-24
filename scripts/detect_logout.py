#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鐧诲嚭瀵硅瘽妗嗘娴嬪櫒 - 澶氱壒寰佽瀺鍚堟柟妗?
涓嶄緷璧?PaddleOCR锛屼娇鐢細
1. 棰滆壊妫€娴嬶紙绾㈣壊璀﹀憡鍥炬爣锛?2. 甯冨眬鍒嗘瀽锛堝璇濇鐗瑰緛锛?3. 妯℃澘鍖归厤锛堢‘璁?鍙栨秷鎸夐挳锛?"""

import sys
import os
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()


def detect_logout_dialog(screenshot_path: str) -> dict:
    """
    妫€娴嬬櫥鍑哄璇濇
    
    Returns:
        dict: {
            "detected": bool,
            "confidence": float,
            "features": {
                "has_red_warning": bool,
                "has_dialog_layout": bool,
                "has_confirm_cancel": bool,
                "dark_overlay": bool
            }
        }
    """
    import cv2
    import numpy as np
    
    result = {
        "detected": False,
        "confidence": 0.0,
        "features": {
            "has_red_warning": False,
            "has_dialog_layout": False,
            "has_confirm_cancel": False,
            "dark_overlay": False
        }
    }
    
    # 璇诲彇鎴浘
    img = cv2.imread(screenshot_path)
    if img is None:
        return result
    
    height, width = img.shape[:2]
    
    # 1. 棰滆壊妫€娴?- 绾㈣壊璀﹀憡鍥炬爣
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # 绾㈣壊鑼冨洿
    lower_red1 = np.array([0, 100, 100])
    upper_red1 = np.array([15, 255, 255])
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    
    lower_red2 = np.array([160, 100, 100])
    upper_red2 = np.array([180, 255, 255])
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    
    red_mask = cv2.bitwise_or(mask1, mask2)
    red_pixels = cv2.countNonZero(red_mask)
    red_ratio = red_pixels / (width * height)
    
    # 鐧诲嚭瀵硅瘽妗嗛€氬父鏈夋槑鏄剧殑绾㈣壊璀﹀憡鍥炬爣
    result["features"]["has_red_warning"] = red_ratio > 0.001
    
    # 2. 甯冨眬鍒嗘瀽 - 妫€娴嬪璇濇鐗瑰緛
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 妫€娴嬪崐閫忔槑榛戣壊瑕嗙洊灞?    dark_threshold = 40
    dark_mask = cv2.inRange(gray, 0, dark_threshold)
    dark_pixels = cv2.countNonZero(dark_mask)
    dark_ratio = dark_pixels / (width * height)
    
    # 鐧诲嚭瀵硅瘽妗嗘湁澶х殑鍗婇€忔槑榛戣壊鑳屾櫙
    result["features"]["dark_overlay"] = dark_ratio > 0.1
    
    # 3. 妫€娴嬪璇濇杈规锛堢煩褰㈣疆寤擄級
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # 鏌ユ壘澶х殑鐭╁舰杞粨锛堝璇濇锛?    dialog_found = False
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 50000:  # 澶х殑杞粨
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            if len(approx) == 4:  # 鍥涜竟褰?                x, y, w, h = cv2.boundingRect(approx)
                # 瀵硅瘽妗嗛€氬父鍦ㄥ睆骞曚腑澶?                if width * 0.3 < x < width * 0.7 and height * 0.2 < y < height * 0.6:
                    dialog_found = True
                    break
    
    result["features"]["has_dialog_layout"] = dialog_found
    
    # 4. 妫€娴嬬‘璁?鍙栨秷鎸夐挳锛堥€氬父鍦ㄥ璇濇搴曢儴锛?    # 鎸夐挳鐗瑰緛锛氱煩褰€佹湁鏂囧瓧銆佸湪瀵硅瘽妗嗗簳閮?    button_area = gray[int(height * 0.5):int(height * 0.8), :]
    button_edges = cv2.Canny(button_area, 100, 200)
    button_contours, _ = cv2.findContours(button_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    button_count = 0
    for contour in button_contours:
        area = cv2.contourArea(contour)
        if 5000 < area < 50000:  # 鎸夐挳澶у皬
            x, y, w, h = cv2.boundingRect(contour)
            if 50 < w < 300 and 30 < h < 100:  # 鎸夐挳姣斾緥
                button_count += 1
    
    # 鐧诲嚭瀵硅瘽妗嗛€氬父鏈?2 涓寜閽紙纭/鍙栨秷锛?    result["features"]["has_confirm_cancel"] = button_count >= 2
    
    # 缁煎悎鍒ゆ柇
    score = 0.0
    if result["features"]["has_red_warning"]:
        score += 0.3
    if result["features"]["has_dialog_layout"]:
        score += 0.3
    if result["features"]["has_confirm_cancel"]:
        score += 0.2
    if result["features"]["dark_overlay"]:
        score += 0.2
    
    result["confidence"] = score
    result["detected"] = score >= 0.5
    
    return result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="鐧诲嚭瀵硅瘽妗嗘娴嬪櫒")
    parser.add_argument("--image", type=str, required=True, help="鎴浘璺緞")
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("鐧诲嚭瀵硅瘽妗嗘娴?)
    print("="*60)
    print(f"鎴浘锛歿args.image}")
    
    result = detect_logout_dialog(args.image)
    
    print("\n妫€娴嬬粨鏋?")
    print(f"  妫€娴嬪埌鐧诲嚭瀵硅瘽妗嗭細{'鉁? if result['detected'] else '鉁?}")
    print(f"  缃俊搴︼細{result['confidence']:.2f}")
    
    print("\n鐗瑰緛鍒嗘瀽:")
    for feature, value in result["features"].items():
        status = "鉁? if value else "鉁?
        print(f"  {feature}: {status}")
    
    if result["detected"]:
        print("\n[璀﹀憡] 妫€娴嬪埌鐧诲嚭瀵硅瘽妗嗭紒闇€瑕佸鐞嗐€?)
        return 1
    else:
        print("\n[姝ｅ父] 鏈娴嬪埌鐧诲嚭瀵硅瘽妗嗐€?)
        return 0


if __name__ == "__main__":
    sys.exit(main())

