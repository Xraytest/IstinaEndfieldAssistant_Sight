#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""浣跨敤 VLM 鍒嗘瀽褰撳墠椤甸潰鐘舵€?""
import sys, os, base64, cv2, numpy as np
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

from core.capability.adb_utils import ADB
from core.foundation.logger import init_logger

# 鍒濆鍖栨棩蹇?core_init_logger()

def analyze_with_vlm():
    """浣跨敤 VLM 鍒嗘瀽褰撳墠鎴浘"""
    adb = ADB()
    
    # 鎴浘
    print("[鎴浘] 鑾峰彇褰撳墠鐢婚潰...")
    img_bytes = adb.screencap(dedup=False)
    if img_bytes is None:
        print("[ERROR] 鎴浘澶辫触")
        return
    
    # 淇濆瓨鎴浘
    with open(PROJECT_ROOT / "data" / "analysis" / "vlm_analysis_input.png", "wb") as f:
        f.write(img_bytes)
    print(f"[淇濆瓨] 鎴浘宸蹭繚瀛?)
    
    # VLM 鍒嗘瀽
    print("\n[VLM] 寮€濮嬪垎鏋愰〉闈?..")
    result = adb.vlm_analyze(
        image_bytes=img_bytes,
        instruction="""鍒嗘瀽褰撳墠娓告垙鐢婚潰锛屽洖绛斾互涓嬮棶棰橈細
1. 褰撳墠鏄粈涔堥〉闈紵锛堢櫥褰曠晫闈?涓昏彍鍗?涓栫晫鍦板浘/浠诲姟闈㈡澘/閫€鍑哄璇濇/鍔犺浇鐣岄潰/鍏朵粬锛?2. 鐢婚潰涓湁鍝簺鍙氦浜掔殑鎸夐挳鎴栧浘鏍囷紵
3. 濡備綍瀵艰埅鍒颁笘鐣屽湴鍥鹃〉闈紵
4. 濡傛灉鏈夊脊绐楁垨瀵硅瘽妗嗭紝鏄粈涔堝唴瀹癸紵

璇风敤涓枃鍥炵瓟锛岀畝娲佹槑浜嗐€?"",
        communicator=None
    )
    
    if result and result.get("status") == "success":
        response = result.get("response", "")
        print(f"\n[VLM 鍒嗘瀽缁撴灉]:")
        print(response)
        return response
    else:
        print(f"\n[VLM] 鍒嗘瀽澶辫触锛歿result}")
        return None

if __name__ == "__main__":
    analyze_with_vlm()

