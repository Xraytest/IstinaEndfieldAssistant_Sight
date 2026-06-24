#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鐧诲嚭瀵硅瘽妗嗘娴嬫祴璇?- 浣跨敤鎴浘鍒嗘瀽

鍒嗘瀽锛?1. 涓轰粈涔?OCR 娌℃娴嬪埌鐧诲嚭瀵硅瘽妗?2. 鐧诲嚭瀵硅瘽妗嗙殑鐗瑰緛
3. 濡備綍鏀硅繘妫€娴?"""

import sys
import os
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

def analyze_screenshot():
    """鍒嗘瀽鎴浘涓殑鐧诲嚭瀵硅瘽妗?""
    print("\n" + "="*60)
    print("鐧诲嚭瀵硅瘽妗嗗垎鏋?)
    print("="*60)
    
    # 璇诲彇鎴浘
    screenshot_path = PROJECT_ROOT / "cache" / "flow_daily_quest_20260616_172418" / "screenshots" / "preamble_08_1781601969_9da8b863.png"
    
    if not screenshot_path.exists():
        print(f"[ERROR] 鎴浘涓嶅瓨鍦細{screenshot_path}")
        return
    
    print(f"\n鎴浘璺緞锛歿screenshot_path}")
    
    # 浣跨敤 OpenCV 鍒嗘瀽鎴浘
    try:
        import cv2
        import numpy as np
        
        img = cv2.imread(str(screenshot_path))
        if img is None:
            print("[ERROR] 鏃犳硶璇诲彇鎴浘")
            return
        
        print(f"鎴浘灏哄锛歿img.shape[1]}x{img.shape[0]}")
        
        # 杞崲涓?HSV 妫€娴嬬孩鑹诧紙鐧诲嚭瀵硅瘽妗嗛€氬父鏈夌孩鑹插厓绱狅級
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # 绾㈣壊鑼冨洿 1
        lower_red1 = np.array([0, 70, 50])
        upper_red1 = np.array([10, 255, 255])
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        
        # 绾㈣壊鑼冨洿 2
        lower_red2 = np.array([170, 70, 50])
        upper_red2 = np.array([180, 255, 255])
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        
        mask = cv2.bitwise_or(mask1, mask2)
        red_pixels = cv2.countNonZero(mask)
        
        print(f"绾㈣壊鍍忕礌鏁伴噺锛歿red_pixels}")
        
        # 妫€娴嬪璇濇鍖哄煙锛堥€氬父鏄崐閫忔槑榛戣壊鑳屾櫙锛?        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # 鏌ユ壘鏆楄壊鍖哄煙
        dark_mask = cv2.inRange(gray, 0, 50)
        dark_pixels = cv2.countNonZero(dark_mask)
        
        print(f"鏆楄壊鍍忕礌鏁伴噺锛歿dark_pixels}")
        
        # 璁＄畻鏁翠綋浜害
        brightness = np.mean(gray)
        print(f"骞冲潎浜害锛歿brightness:.2f}")
        
        # 妫€娴嬫枃瀛楀尯鍩燂紙楂樺姣斿害锛?        edges = cv2.Canny(gray, 50, 150)
        edge_pixels = cv2.countNonZero(edges)
        print(f"杈圭紭鍍忕礌鏁伴噺锛歿edge_pixels}")
        
        # 淇濆瓨鍒嗘瀽缁撴灉
        output_path = PROJECT_ROOT / "cache" / "logout_analysis.png"
        cv2.imwrite(str(output_path), mask)
        print(f"\n绾㈣壊鎺╄啘宸蹭繚瀛橈細{output_path}")
        
        # 鍒ゆ柇鏄惁鏈夌櫥鍑哄璇濇
        # 鐧诲嚭瀵硅瘽妗嗙壒寰侊細
        # 1. 鏈夋槑鏄剧殑绾㈣壊鍏冪礌锛堣鍛婂浘鏍囷級
        # 2. 鏈夊崐閫忔槑榛戣壊鑳屾櫙
        # 3. 鏈夋枃瀛?鐧诲嚭"銆?瓒呮椂"銆?纭"銆?鍙栨秷"绛?        
        has_red = red_pixels > 1000
        has_dark = dark_pixels > 50000
        has_text = edge_pixels > 10000
        
        print(f"\n鐧诲嚭瀵硅瘽妗嗙壒寰?")
        print(f"  绾㈣壊鍏冪礌锛歿'鉁? if has_red else '鉁?} ({red_pixels} 鍍忕礌)")
        print(f"  鏆楄壊鑳屾櫙锛歿'鉁? if has_dark else '鉁?} ({dark_pixels} 鍍忕礌)")
        print(f"  鏂囧瓧杈圭紭锛歿'鉁? if has_text else '鉁?} ({edge_pixels} 鍍忕礌)")
        
        if has_red and has_dark:
            print(f"\n[鍙兘] 妫€娴嬪埌鐧诲嚭瀵硅瘽妗嗙壒寰?)
        else:
            print(f"\n[姝ｅ父] 鏈娴嬪埌鐧诲嚭瀵硅瘽妗嗙壒寰?)
            
    except ImportError:
        print("[ERROR] OpenCV 鏈畨瑁?)
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()


def analyze_ocr_keywords():
    """鍒嗘瀽 OCR 鍏抽敭璇嶆娴?""
    print("\n" + "="*60)
    print("OCR 鍏抽敭璇嶅垎鏋?)
    print("="*60)
    
    # 鐧诲嚭瀵硅瘽妗嗗彲鑳界殑鍏抽敭璇?    logout_keywords = [
        "鐧诲嚭", "瓒呮椂", "閲嶆柊鐧诲綍", "浼氳瘽杩囨湡",
        "鑷姩鐧诲嚭", "闀挎椂闂?, "娌℃湁鎿嶄綔", "鏂紑杩炴帴",
        "纭", "鍙栨秷", "LOGOUT", "TIMEOUT", "SESSION"
    ]
    
    print("\n鐧诲嚭瀵硅瘽妗嗗叧閿瘝:")
    for kw in logout_keywords:
        print(f"  - {kw}")
    
    print("\n闂:")
    print("  1. OCR 鍙兘鏃犳硶璇嗗埆妯＄硦/灏忓瓧鍙锋枃瀛?)
    print("  2. 鐧诲嚭瀵硅瘽妗嗗彲鑳戒娇鐢ㄥ浘鏍囪€岄潪鏂囧瓧")
    print("  3. PaddleOCR 鏂扮増鏈湁鍏煎鎬ч棶棰?)
    
    print("\n瑙ｅ喅鏂规:")
    print("  1. 浣跨敤妯℃澘鍖归厤妫€娴嬬櫥鍑哄璇濇鍥炬爣")
    print("  2. 浣跨敤棰滆壊妫€娴嬶紙绾㈣壊璀﹀憡鍥炬爣锛?)
    print("  3. 浣跨敤澶氱壒寰佽瀺鍚堬紙棰滆壊 + 甯冨眬 + OCR锛?)


if __name__ == "__main__":
    analyze_screenshot()
    analyze_ocr_keywords()

