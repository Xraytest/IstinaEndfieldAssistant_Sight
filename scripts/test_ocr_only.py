#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佹祴璇?- OCR_Only 妯″紡

涓撻棬娴嬭瘯锛?
1. 鐧诲嚭瀵硅瘽妗嗘娴?
2. 鍔犺浇鐢婚潰妫€娴?
3. 涓栫晫鍦板浘妫€娴?
4. 浠诲姟闈㈡澘妫€娴?

鏁版嵁婧愶細浠呬娇鐢?MaaFw 鍐呯疆 OCR锛屼笉浣跨敤 VLM
"""

import sys
import os
from pathlib import Path

from _path_setup import ensure_path; ensure_path()

from core.capability.ocr.ocr_manager import OCRManager
from core.capability.adb_utils import ADB, list_devices


def test_logout_detection(device_serial: str):
    """娴嬭瘯鐧诲嚭瀵硅瘽妗嗘娴?""
    print("\n" + "="*60)
    print("娴嬭瘯锛氱櫥鍑哄璇濇妫€娴?)
    print("="*60)

    manager = OCRManager()
    
    print("姝ｅ湪鎴浘骞舵墽琛?OCR 璇嗗埆...")
    state = manager.capture_and_recognize(device_serial)
    
    print(f"\nOCR 璇嗗埆缁撴灉:")
    print(f"  椤甸潰绫诲瀷锛歿state.page_type}")
    print(f"  鎻忚堪锛歿state.description}")
    print(f"  椤堕儴鏍忓彲瑙侊細{state.top_bar_visible}")
    print(f"  椤堕儴鏍忔寜閽細{state.top_bar_buttons}")
    print(f"  闈㈡澘瑕嗙洊灞傦細{state.overlay_detected}")
    print(f"  闈㈡澘鏂囨湰锛歿state.overlay_texts[:5]}...")  # 鍙樉绀哄墠 5 涓?
    print(f"  棰嗗彇鎸夐挳锛歿len(state.claim_buttons)} 涓?)
    
    # 妫€鏌ユ槸鍚︽娴嬪埌鐧诲嚭
    if state.page_type == "logout_dialog":
        print("\n[OK] 鎴愬姛妫€娴嬪埌鐧诲嚭瀵硅瘽妗?")
        return True
    elif "logout" in state.page_type.lower() or "鐧诲嚭" in state.description:
        print("\n[OK] 妫€娴嬪埌鐧诲嚭鐩稿叧鎻愮ず!")
        return True
    else:
        print(f"\n[INFO] 褰撳墠椤甸潰锛歿state.page_type}")
        if state.overlay_texts:
            print(f"  闈㈡澘鏂囨湰绀轰緥锛歿state.overlay_texts[:3]}")
        return False


def test_all_page_types(device_serial: str):
    """娴嬭瘯鎵€鏈夐〉闈㈢被鍨嬫娴?""
    print("\n" + "="*60)
    print("娴嬭瘯锛氭墍鏈夐〉闈㈢被鍨嬫娴?)
    print("="*60)

    manager = OCRManager()
    
    print("姝ｅ湪鎴浘骞舵墽琛?OCR 璇嗗埆...")
    state = manager.capture_and_recognize(device_serial)
    
    print(f"\n瀹屾暣妫€娴嬬粨鏋?")
    print(f"  椤甸潰绫诲瀷锛歿state.page_type}")
    print(f"  缃俊搴︼細{state.confidence:.2f}")
    print(f"  鎻忚堪锛歿state.description}")
    print(f"  椤堕儴鏍忓彲瑙侊細{state.top_bar_visible}")
    print(f"  椤堕儴鏍忔寜閽細{state.top_bar_buttons}")
    print(f"  闈㈡澘瑕嗙洊灞傦細{state.overlay_detected}")
    print(f"  闈㈡澘鏂囨湰鏁伴噺锛歿len(state.overlay_texts)}")
    print(f"  棰嗗彇鎸夐挳锛歿len(state.claim_buttons)}")
    print(f"  鍙氦浜掑厓绱狅細{len(state.interactive_elements)}")
    
    # 杈撳嚭鎵€鏈?OCR 鏂囨湰锛堢敤浜庤皟璇曪級
    print(f"\nOCR 鏂囨湰棰勮:")
    for elem in state.interactive_elements[:10]:
        print(f"  - {elem.get('text', 'N/A')} @ ({elem.get('cx', 0)}, {elem.get('cy', 0)})")
    
    return state


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="鏍囧噯娴佹祴璇?- OCR_Only 妯″紡")
    parser.add_argument("--device", type=str, default=None, help="璁惧搴忓垪鍙?)
    parser.add_argument("--test", type=str, choices=["logout", "all"], default="all",
                        help="娴嬭瘯绫诲瀷")
    
    args = parser.parse_args()
    
    # 纭畾璁惧
    device_serial = args.device
    if not device_serial:
        devices = list_devices()
        if not devices:
            print("[ERROR] 鏈壘鍒板彲鐢ㄨ澶?)
            return 1
        device_serial = devices[0]
        print(f"[璁惧] 鑷姩閫夋嫨锛歿device_serial}")
    
    print(f"\n{'='*60}")
    print(f"鏍囧噯娴佹祴璇?- OCR_Only 妯″紡")
    print(f"{'='*60}")
    print(f"璁惧锛歿device_serial}")
    print(f"娴嬭瘯锛歿args.test}")
    print(f"鏁版嵁婧愶細MaaFw 鍐呯疆 OCR (鏈湴)")
    
    if args.test == "logout":
        result = test_logout_detection(device_serial)
    else:
        result = test_all_page_types(device_serial)
    
    print(f"\n{'='*60}")
    print(f"娴嬭瘯瀹屾垚")
    print(f"{'='*60}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

