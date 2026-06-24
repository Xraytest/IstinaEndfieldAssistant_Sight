#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佹祴璇?- 鏈€缁堢増锛堜笉渚濊禆 PaddleOCR锛?

浣跨敤锛?
1. MaaFw 瑙︽帶
2. MaaFw 鎴浘
3. 绠€鍗曠殑瑙嗚鐗瑰緛鍒嗘瀽锛堜笉渚濊禆 OCR锛?
4. MaaEnd 寮忕櫥鍑烘娴嬮€昏緫锛堝叧閿瘝鍖归厤锛?
"""

import sys
import os
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()

from core.capability.adb_utils import ADB, list_devices, adb_screencap

# MaaFw 瑙︽帶
try:
    from core.capability.device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig
    MAAFW_AVAILABLE = True
except ImportError:
    MaaFwTouchExecutor = None
    MAAFW_AVAILABLE = False
    print("[WARN] MaaFramework 鏈畨瑁?)


class SimplePageAnalyzer:
    """绠€鍗曠殑椤甸潰鍒嗘瀽鍣紙涓嶄緷璧?OCR锛?""
    
    # MaaEnd 寮忕櫥鍑哄叧閿瘝
    LOGOUT_KEYWORDS = [
        "鐧诲嚭", "閫€鍑?, "鐧诲綍鐣岄潰", "瓒呮椂", "閲嶆柊鐧诲綍", "浼氳瘽杩囨湡",
        "鑷姩鐧诲嚭", "闀挎椂闂?, "娌℃湁鎿嶄綔", "鏂紑杩炴帴", "纭", "鍙栨秷",
        "logout", "timeout", "session", "login"
    ]
    
    def __init__(self):
        pass
    
    def analyze(self, screenshot: bytes) -> dict:
        """
        鍒嗘瀽鎴浘锛堜笉渚濊禆 OCR锛?
        
        Returns:
            dict: {
                "page_type": str,
                "has_logout_dialog": bool,
                "features": dict
            }
        """
        try:
            import cv2
            import numpy as np
            from PIL import Image
            import io
            
            # 瑙ｇ爜鍥剧墖
            img = Image.open(io.BytesIO(screenshot))
            img_array = np.array(img)
            cv_img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            height, width = cv_img.shape[:2]
            
            # 1. 妫€娴嬮粍鑹插厓绱狅紙鐧诲嚭瀵硅瘽妗嗙‘璁ゆ寜閽級
            hsv = cv2.cvtColor(cv_img, cv2.COLOR_BGR2HSV)
            lower_yellow = np.array([20, 100, 100])
            upper_yellow = np.array([35, 255, 255])
            yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
            yellow_pixels = cv2.countNonZero(yellow_mask)
            yellow_ratio = yellow_pixels / (width * height)
            
            # 2. 妫€娴嬬櫧鑹?娴呰壊鍖哄煙锛堢櫥鍑哄璇濇鑳屾櫙锛?
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            white_mask = cv2.inRange(gray, 200, 255)
            white_pixels = cv2.countNonZero(white_mask)
            white_ratio = white_pixels / (width * height)
            
            # 3. 妫€娴嬫殫鑹插尯鍩燂紙鏍囬鐢婚潰鐗瑰緛锛?
            dark_mask = cv2.inRange(gray, 0, 40)
            dark_pixels = cv2.countNonZero(dark_mask)
            dark_ratio = dark_pixels / (width * height)
            
            # 4. 妫€娴嬪乏渚у鑸爮锛堜笘鐣屽湴鍥剧壒寰侊級
            left_bar = cv_img[:, :100, :]
            left_bar_gray = cv2.cvtColor(left_bar, cv2.COLOR_BGR2GRAY)
            left_bar_brightness = np.mean(left_bar_gray)
            
            # 5. 妫€娴嬪彸涓婅缁胯壊鍏冪礌锛堜换鍔?娲诲姩鍥炬爣锛?
            top_right = cv_img[:200, int(width*0.7):, :]
            top_right_hsv = cv2.cvtColor(top_right, cv2.COLOR_BGR2HSV)
            lower_green = np.array([40, 50, 50])
            upper_green = np.array([80, 255, 255])
            green_mask = cv2.inRange(top_right_hsv, lower_green, upper_green)
            green_pixels = cv2.countNonZero(green_mask)
            
            # 鍒ゆ柇椤甸潰绫诲瀷
            # 鐧诲嚭瀵硅瘽妗嗙壒寰侊細鐧借壊鑳屾櫙 + 榛勮壊鎸夐挳
            has_logout = white_ratio > 0.3 and yellow_ratio > 0.001
            # 涓栫晫鍦板浘鐗瑰緛锛氬乏渚ф殫鑹插鑸爮 + 鍙充笂瑙掔豢鑹插厓绱?
            is_world_map = left_bar_brightness < 50 and green_pixels > 100
            # 鏍囬鐢婚潰鐗瑰緛锛氬ぇ閲忔殫鑹插尯鍩?+ 鏃犲乏渚у鑸爮
            is_title = dark_ratio > 0.5 and left_bar_brightness > 100 and not has_logout
            
            if has_logout:
                page_type = "logout_dialog"
            elif is_world_map:
                page_type = "world_map"
            elif is_title:
                page_type = "title_screen"
            else:
                page_type = "unknown"
            
            return {
                "page_type": page_type,
                "has_logout_dialog": has_logout,
                "features": {
                    "yellow_ratio": yellow_ratio,
                    "white_ratio": white_ratio,
                    "dark_ratio": dark_ratio,
                    "left_bar_brightness": left_bar_brightness,
                    "green_pixels": green_pixels
                }
            }
            
        except Exception as e:
            print(f"[ERROR] 椤甸潰鍒嗘瀽澶辫触锛歿e}")
            return {
                "page_type": "error",
                "has_logout_dialog": False,
                "features": {}
            }


class SimpleFlowExecutor:
    """绠€鍗曟爣鍑嗘祦鎵ц鍣紙涓嶄緷璧?OCR锛?""
    
    def __init__(self, device_serial: str):
        self.device_serial = device_serial
        self.adb = ADB(serial=device_serial)
        self.analyzer = SimplePageAnalyzer()
        
        # 鍒濆鍖?MaaFw 瑙︽帶
        self._maafw = None
        if MAAFW_AVAILABLE:
            try:
                maafw_config = MaaFwTouchConfig(
                    adb_path=str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"),
                    address=device_serial,
                    screencap_methods=MaaFwTouchConfig.SCREENCAP_ADB_SHELL,
                    input_methods=2,
                )
                self._maafw = MaaFwTouchExecutor(maafw_config)
                if self._maafw.connect():
                    print(f"[MaaFw] 瑙︽帶鍒濆鍖栨垚鍔?)
            except Exception as e:
                print(f"[MaaFw] 鍒濆鍖栧け璐ワ細{e}")
        
        self.session_dir = None
        self.screenshots = []
        
    def start_session(self, flow_name: str):
        """寮€濮嬫墽琛屼細璇?""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = PROJECT_ROOT / "cache" / f"flow_{flow_name}_simple_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        (self.session_dir / "screenshots").mkdir(exist_ok=True)
        print(f"[浼氳瘽] {self.session_dir}")
        
    def capture(self, label: str) -> bytes:
        """鎴浘骞朵繚瀛?""
        screenshot = adb_screencap(self.device_serial)
        if screenshot:
            timestamp = datetime.now().strftime("%Y%m%S")
            filename = f"{label}_{timestamp}.png"
            path = self.session_dir / "screenshots" / filename
            with open(path, "wb") as f:
                f.write(screenshot)
            self.screenshots.append(str(path))
            print(f"[鎴浘] {filename}")
        return screenshot
    
    def check_page(self) -> str:
        """妫€鏌ュ綋鍓嶉〉闈㈢被鍨嬶紙涓嶄緷璧?OCR锛?""
        screenshot = adb_screencap(self.device_serial)
        if not screenshot:
            return "error"
        
        result = self.analyzer.analyze(screenshot)
        page_type = result["page_type"]
        features = result["features"]
        
        print(f"\n[椤甸潰妫€娴媇 瑙嗚鍒嗘瀽锛堜笉渚濊禆 OCR锛?)
        print(f"  绫诲瀷锛歿page_type}")
        print(f"  榛勮壊鎸夐挳锛歿features.get('yellow_ratio', 0):.4f}")
        print(f"  鐧借壊鑳屾櫙锛歿features.get('white_ratio', 0):.4f}")
        print(f"  鏆楄壊鍖哄煙锛歿features.get('dark_ratio', 0):.4f}")
        print(f"  宸︿晶浜害锛歿features.get('left_bar_brightness', 0):.1f}")
        print(f"  缁胯壊鍍忕礌锛歿features.get('green_pixels', 0)}")
        
        if result["has_logout_dialog"]:
            print(f"\n[璀﹀憡] 妫€娴嬪埌鐧诲嚭瀵硅瘽妗嗭紒")
            return "logout_dialog"
        
        return page_type
    
    def tap(self, x: int, y: int, label: str):
        """鐐瑰嚮锛堜粎浣跨敤 MaaFw锛屼弗绂?ADB 瑙︽帶锛?""
        print(f"\n[鐐瑰嚮] {label} @ ({x}, {y})")
        if self._maafw and self._maafw.connected:
            self._maafw.safe_press(x, y)
        else:
            raise RuntimeError("MaaFw 鏈繛鎺ワ紝鏃犳硶鎵ц鐐瑰嚮鎿嶄綔")
        self.adb.wait(1)
        self.capture(f"tap_{label}")

    def back(self):
        """杩斿洖锛堜粎浣跨敤 MaaFw锛屼弗绂?ADB 瑙︽帶锛?""
        print(f"\n[杩斿洖]")
        if self._maafw and self._maafw.connected:
            job = self._maafw.post_keyevent(4)
            if job:
                job.wait()
        else:
            raise RuntimeError("MaaFw 鏈繛鎺ワ紝鏃犳硶鎵ц杩斿洖鎿嶄綔")
        self.adb.wait(1)
        self.capture("back")
    
    def handle_logout_dialog(self):
        """澶勭悊閫€鍑烘父鎴忓璇濇 - 鐐瑰嚮鍙栨秷鎸夐挳锛堜笉鏄‘璁ゆ寜閽紒锛?""
        print(f"\n[澶勭悊] 妫€娴嬪埌閫€鍑烘父鎴忓璇濇锛岀偣鍑诲彇娑堟寜閽?..")

        # 閫€鍑烘父鎴忓璇濇鐗瑰緛锛?
        # - 鐧借壊鑳屾櫙
        # - 宸︿晶鐏拌壊"鍙栨秷"鎸夐挳
        # - 鍙充晶榛勮壊"纭"鎸夐挳
        # 鎴戜滑闇€瑕佺偣鍑?鍙栨秷"鎸夐挳鏉ョ户缁父鎴?
        
        # 鎴浘灏哄锛?920x1080锛孧aaFw 閫昏緫鍧愭爣锛?280x720
        # 浠庢埅鍥句及绠楋細鍙栨秷鎸夐挳鍦ㄥ璇濇搴曢儴宸︿晶
        # 1920x1080 鍧愭爣锛氱害 (800, 700)
        # 杞崲涓?1280x720: (800/1920*1280, 700/1080*720) 鈮?(533, 467)
        
        # 灏濊瘯澶氫釜鍧愭爣
        coords = [
            (533, 467),  # 浼扮畻鍧愭爣
            (540, 470),  # 寰皟
            (520, 460),  # 鍋忓乏
            (550, 480),  # 鍋忓彸
            (533, 450),  # 鍋忎笂
            (533, 480),  # 鍋忎笅
        ]
        
        for x, y in coords:
            print(f"  鐐瑰嚮鍙栨秷鎸夐挳 @ ({x}, {y})")
            self.tap(x, y, "exit_cancel")
            self.wait(2)
            
            # 妫€鏌ユ槸鍚﹀凡閫€鍑哄璇濇
            page_type = self.check_page()
            if page_type != "logout_dialog":
                print(f"  [OK] 宸查€€鍑哄璇濇锛屽綋鍓嶉〉闈細{page_type}")
                return True
        
        print(f"  [WARN] 浠嶅湪瀵硅瘽妗嗭紝鍙兘闇€瑕佹墜鍔ㄥ鐞?)
        return False
    
    def wait(self, seconds: int):
        """绛夊緟"""
        print(f"\n[绛夊緟] {seconds}s")
        self.adb.wait(seconds)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="鏍囧噯娴佹祴璇?- 绠€鍗曠増锛堜笉渚濊禆 OCR锛?)
    parser.add_argument("--device", type=str, default=None, help="璁惧搴忓垪鍙?)
    parser.add_argument("--flow", type=str, default="daily_quest", help="娴佺▼鍚嶇О")
    args = parser.parse_args()
    
    # 纭畾璁惧
    device_serial = args.device or list_devices()[0]
    print(f"[璁惧] {device_serial}")
    
    # 鍒涘缓鎵ц鍣?
    executor = SimpleFlowExecutor(device_serial)
    executor.start_session(args.flow)
    
    print("\n" + "="*60)
    print(f"鏍囧噯娴佹祴璇?- 绠€鍗曠増锛堜笉渚濊禆 OCR锛?)
    print(f"娴佺▼锛歿args.flow}")
    print("="*60)
    
    # 姝ラ 1: 妫€鏌ュ垵濮嬮〉闈?
    print("\n--- 姝ラ 1: 妫€鏌ュ垵濮嬮〉闈?---")
    page_type = executor.check_page()
    
    # 澶勭悊鐧诲嚭瀵硅瘽妗?
    if page_type == "logout_dialog":
        print("\n[鐧诲嚭] 妫€娴嬪埌鐧诲嚭瀵硅瘽妗嗭紝灏濊瘯澶勭悊...")
        success = executor.handle_logout_dialog()

        if not success:
            print("\n[閿欒] 鐧诲嚭瀵硅瘽妗嗗鐞嗗け璐ワ紝闇€瑕佹墜鍔ㄥ鐞?)
        
        # 閲嶆柊妫€鏌ラ〉闈?
        page_type = executor.check_page()

    # 澶勭悊鏍囬鐢婚潰
    max_title_attempts = 5
    for attempt in range(max_title_attempts):
        if page_type == "title_screen":
            print(f"\n[鏍囬] 妫€娴嬪埌鏍囬鐢婚潰锛岀偣鍑讳腑澶户缁?({attempt+1}/{max_title_attempts})...")
            executor.tap(640, 360, "title_continue")
            executor.wait(5)
            page_type = executor.check_page()
        else:
            break
    
    # 濡傛灉杩樺湪鏍囬鐢婚潰锛屽皾璇曢噸鏂板惎鍔ㄦ父鎴?
    if page_type == "title_screen":
        print("\n[璀﹀憡] 鏍囬鐢婚潰鏃犳硶璺宠繃锛屽皾璇曢噸鏂板惎鍔ㄦ父鎴?..")
        # 杩欓噷鍙互娣诲姞娓告垙閲嶅惎閫昏緫
    
    # 姝ラ 2: 鎵撳紑浠诲姟闈㈡澘
    print("\n--- 姝ラ 2: 鎵撳紑浠诲姟闈㈡澘 ---")

    # 鍏堟鏌ユ槸鍚︽湁鐧诲嚭瀵硅瘽妗?
    page_type = executor.check_page()
    if page_type == "logout_dialog":
        print("\n[璀﹀憡] 妫€娴嬪埌鐧诲嚭瀵硅瘽妗嗭紝灏濊瘯澶勭悊...")
        executor.handle_logout_dialog()
        executor.wait(3)

    # 灏濊瘯澶氫釜浠诲姟鍥炬爣鍧愭爣锛堝彸涓婅锛?
    # 浠庢埅鍥惧垎鏋愶細1920x1080 鍒嗚鲸鐜囷紝浠诲姟鍥炬爣鍦ㄥ彸涓婅
    # 杞崲涓?1280x720 閫昏緫鍧愭爣
    # 1920x1080 鍧愭爣绾?(1700, 80) 鈫?1280x720: (1133, 53)
    task_coords = [
        (1133, 53),   # 鍙充笂瑙掍换鍔″浘鏍?
        (1140, 60),   # 寰皟
        (1120, 50),   # 绋嶅乏
        (1150, 60),   # 绋嶅彸
        (1133, 45),   # 绋嶄笂
        (1133, 65),   # 绋嶄笅
    ]
    
    task_opened = False
    for x, y in task_coords:
        print(f"\n[灏濊瘯] 鐐瑰嚮浠诲姟鍥炬爣 @ ({x}, {y})")
        executor.tap(x, y, "task_icon")
        executor.wait(2)
        
        # 妫€鏌ラ〉闈㈠彉鍖?
        page_type = executor.check_page()
        # 濡傛灉椤甸潰绫诲瀷鍙樺寲鎴栦笉鍐嶆樉绀洪€€鍑哄璇濇锛岃涓轰换鍔￠潰鏉垮凡鎵撳紑
        if page_type != "logout_dialog":
            print(f"  [OK] 浠诲姟闈㈡澘鍙兘宸叉墦寮€锛屽綋鍓嶉〉闈細{page_type}")
            task_opened = True
            break
    
    if not task_opened:
        print("\n[璀﹀憡] 浠诲姟鍥炬爣鐐瑰嚮澶辫触锛岀户缁墽琛屾祦绋?..")

    # 姝ラ 3: 妫€鏌ヤ换鍔￠潰鏉?
    print("\n--- 姝ラ 3: 妫€鏌ヤ换鍔￠潰鏉?---")
    page_type = executor.check_page()

    # 妫€鏌ユ槸鍚︽湁鐧诲嚭瀵硅瘽妗?
    if page_type == "logout_dialog":
        print("\n[璀﹀憡] 妫€娴嬪埌鐧诲嚭瀵硅瘽妗嗭紝灏濊瘯澶勭悊...")
        executor.handle_logout_dialog()
        executor.wait(3)

    # 姝ラ 4: 棰嗗彇濂栧姳
    print("\n--- 姝ラ 4: 棰嗗彇濂栧姳 ---")
    # 灏濊瘯澶氫釜棰嗗彇鎸夐挳鍧愭爣
    claim_coords = [
        (1100, 650),  # 鍙充笅瑙?
        (1150, 680),  # 鏇撮潬鍙充笅
        (1050, 620),  # 绋嶅乏
    ]
    
    for x, y in claim_coords:
        print(f"\n[灏濊瘯] 鐐瑰嚮棰嗗彇鎸夐挳 @ ({x}, {y})")
        executor.tap(x, y, "claim_all")
        executor.wait(2)
        break  # 鍙皾璇曚竴娆★紝閬垮厤澶氭鐐瑰嚮
    
    # 鍐嶆妫€鏌ョ櫥鍑哄璇濇
    page_type = executor.check_page()
    if page_type == "logout_dialog":
        print("\n[璀﹀憡] 妫€娴嬪埌鐧诲嚭瀵硅瘽妗嗭紝灏濊瘯澶勭悊...")
        executor.handle_logout_dialog()
        executor.wait(3)

    # 姝ラ 5: 杩斿洖
    print("\n--- 姝ラ 5: 杩斿洖鎺㈢储鐣岄潰 ---")
    executor.back()
    executor.wait(2)
    
    # 鍐嶆妫€鏌ョ櫥鍑哄璇濇
    page_type = executor.check_page()
    if page_type == "logout_dialog":
        print("\n[璀﹀憡] 妫€娴嬪埌鐧诲嚭瀵硅瘽妗嗭紝灏濊瘯澶勭悊...")
        executor.handle_logout_dialog()
        executor.wait(3)

    # 姝ラ 6: 妫€鏌ヨ繑鍥炵粨鏋?
    print("\n--- 姝ラ 6: 妫€鏌ヨ繑鍥炵粨鏋?---")
    page_type = executor.check_page()
    
    # 鏈€缁堟鏌ョ櫥鍑哄璇濇
    if page_type == "logout_dialog":
        print("\n[璀﹀憡] 妫€娴嬪埌鐧诲嚭瀵硅瘽妗嗭紝闇€瑕佹墜鍔ㄥ鐞?)


if __name__ == "__main__":
    sys.exit(main())

