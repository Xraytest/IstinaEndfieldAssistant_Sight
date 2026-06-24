#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佸畬鏁存祴璇?- OCR_Only 鏁版嵁婧?

鍔熻兘锛?
1. 浣跨敤 MaaFw 鍐呯疆 OCR 杩涜椤甸潰妫€娴?
2. 妫€娴嬬櫥鍑哄璇濇锛圡aaEnd 寮忥級
3. 鎴浘璁板綍
4. 瀹屾暣娴佺▼鎵ц
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()

from core.capability.ocr.ocr_manager import OCRManager
from core.capability.adb_utils import ADB, list_devices, adb_screencap

# MaaFw 瑙︽帶
try:
    from core.capability.device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig
    MAAFW_AVAILABLE = True
except ImportError:
    MaaFwTouchExecutor = None
    MAAFW_AVAILABLE = False


class OCROnlyFlowExecutor:
    """OCR_Only 鏍囧噯娴佹墽琛屽櫒"""

    def __init__(self, device_serial: str):
        self.device_serial = device_serial
        self.adb = ADB(serial=device_serial)
        self.ocr_manager = OCRManager()
        
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
        self.session_dir = PROJECT_ROOT / "cache" / f"flow_{flow_name}_ocr_only_{timestamp}"
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
    
    def check_page(self, expected_type: str = None) -> str:
        """妫€鏌ュ綋鍓嶉〉闈㈢被鍨嬶紙OCR_Only锛?""
        state = self.ocr_manager.capture_and_recognize(self.device_serial)
        
        print(f"\n[椤甸潰妫€娴媇 OCR_Only")
        print(f"  绫诲瀷锛歿state.page_type}")
        print(f"  鎻忚堪锛歿state.description}")
        print(f"  椤堕儴鏍忥細{state.top_bar_buttons}")
        print(f"  闈㈡澘鏂囨湰锛歿len(state.overlay_texts)} 鏉?)
        
        # 妫€鏌ョ櫥鍑哄璇濇
        if state.page_type == "logout_dialog":
            print(f"\n[璀﹀憡] 妫€娴嬪埌鐧诲嚭瀵硅瘽妗嗭紒")
            print(f"  闇€瑕佹墜鍔ㄥ鐞嗘垨鑷姩鍙栨秷")
            return "logout_dialog"
        
        # 妫€鏌ラ鏈熼〉闈?
        if expected_type:
            if state.page_type == expected_type or (expected_type == "world" and "world" in state.page_type):
                print(f"  鉁?椤甸潰鍖归厤棰勬湡锛歿expected_type}")
            else:
                print(f"  鉁?椤甸潰涓嶅尮閰嶏細鏈熸湜={expected_type} 瀹為檯={state.page_type}")
        
        return state.page_type
    
    def tap(self, x: int, y: int, label: str):
        """鐐瑰嚮 - 浣跨敤 MaaFw"""
        print(f"\n[鐐瑰嚮] {label} @ ({x}, {y})")
        if self._maafw and self._maafw.connected:
            self._maafw.safe_press(x, y)
        else:
            # ADB 鍥為€€
            import subprocess
            subprocess.run(["adb", "-s", self.device_serial, "shell", "input", "tap", str(x), str(y)])
        self.adb.wait(1)
        self.capture(f"tap_{label}")
    
    def swipe(self, x1: int, y1: int, x2: int, y2: int, label: str):
        """婊戝姩"""
        print(f"\n[婊戝姩] {label}: ({x1},{y1}) -> ({x2},{y2})")
        self.adb.swipe(x1, y1, x2, y2, 300)
        self.adb.wait(1)
        self.capture(f"swipe_{label}")
    
    def back(self):
        """杩斿洖 - 浣跨敤 MaaFw"""
        print(f"\n[杩斿洖]")
        if self._maafw and self._maafw.connected:
            job = self._maafw.post_keyevent(4)  # KEYCODE_BACK
            if job:
                job.wait()
        else:
            # ADB 鍥為€€
            import subprocess
            subprocess.run(["adb", "-s", self.device_serial, "shell", "input", "keyevent", "4"])
        self.adb.wait(1)
        self.capture("back")
    
    def wait(self, seconds: int):
        """绛夊緟"""
        print(f"\n[绛夊緟] {seconds}s")
        self.adb.wait(seconds)
    
    def export_report(self):
        """瀵煎嚭鎵ц鎶ュ憡"""
        report = {
            "device": self.device_serial,
            "session_dir": str(self.session_dir),
            "screenshots": self.screenshots,
            "screenshot_count": len(self.screenshots),
            "timestamp": datetime.now().isoformat()
        }
        
        report_path = self.session_dir / "report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n[鎶ュ憡] {report_path}")
        return report


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="鏍囧噯娴佸畬鏁存祴璇?- OCR_Only")
    parser.add_argument("--device", type=str, default=None, help="璁惧搴忓垪鍙?)
    parser.add_argument("--flow", type=str, default="daily_quest", help="娴佺▼鍚嶇О")
    args = parser.parse_args()
    
    # 纭畾璁惧
    device_serial = args.device or list_devices()[0]
    print(f"[璁惧] {device_serial}")
    
    # 鍒涘缓鎵ц鍣?
    executor = OCROnlyFlowExecutor(device_serial)
    executor.start_session(args.flow)
    
    print("\n" + "="*60)
    print(f"鏍囧噯娴佹祴璇?- OCR_Only 鏁版嵁婧?)
    print(f"娴佺▼锛歿args.flow}")
    print("="*60)
    
    # 姝ラ 1: 妫€鏌ュ垵濮嬮〉闈?
    print("\n--- 姝ラ 1: 妫€鏌ュ垵濮嬮〉闈?---")
    page_type = executor.check_page(expected_type="world")
    
    if page_type == "logout_dialog":
        print("\n[閿欒] 妫€娴嬪埌鐧诲嚭瀵硅瘽妗嗭紝鏃犳硶缁х画")
        executor.export_report()
        return 1
    
    # 姝ラ 2: 鎵撳紑浠诲姟闈㈡澘
    print("\n--- 姝ラ 2: 鎵撳紑浠诲姟闈㈡澘 ---")
    executor.tap(860, 80, "task_icon")
    
    # 姝ラ 3: 妫€鏌ヤ换鍔￠潰鏉?
    print("\n--- 姝ラ 3: 妫€鏌ヤ换鍔￠潰鏉?---")
    page_type = executor.check_page()
    print(f"  闈㈡澘鏂囨湰绀轰緥锛歿executor.ocr_manager.decider.overlay_texts[:3] if hasattr(executor.ocr_manager.decider, 'overlay_texts') else 'N/A'}")
    
    # 姝ラ 4: 棰嗗彇濂栧姳
    print("\n--- 姝ラ 4: 棰嗗彇濂栧姳 ---")
    executor.tap(810, 900, "claim_all")
    executor.wait(2)
    
    # 姝ラ 5: 杩斿洖
    print("\n--- 姝ラ 5: 杩斿洖鎺㈢储鐣岄潰 ---")
    executor.back()
    
    # 姝ラ 6: 妫€鏌ヨ繑鍥炵粨鏋?
    print("\n--- 姝ラ 6: 妫€鏌ヨ繑鍥炵粨鏋?---")
    page_type = executor.check_page(expected_type="world")
    
    # 瀵煎嚭鎶ュ憡
    executor.export_report()
    
    print("\n" + "="*60)
    print("娴嬭瘯瀹屾垚")
    print("="*60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

