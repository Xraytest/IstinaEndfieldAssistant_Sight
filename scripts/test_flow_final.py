#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佸畬鏁存祴璇?- 鏈€缁堢増

鍔熻兘:
1. 鐧诲嚭瀵硅瘽妗嗘娴嬪拰鑷姩澶勭悊
2. 瀹屾暣鐨勬瘡鏃ヤ换鍔℃祦绋?
3. 鎴浘璁板綍
4. 鎵ц鎶ュ憡
"""

import sys
import os
import json
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


class FlowExecutor:
    """鏍囧噯娴佹墽琛屽櫒"""
    
    def __init__(self, device_serial: str):
        self.device_serial = device_serial
        self.adb = ADB(serial=device_serial)
        
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
        self.steps_log = []
        
    def start_session(self, flow_name: str):
        """寮€濮嬫墽琛屼細璇?""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = PROJECT_ROOT / "cache" / f"flow_{flow_name}_final_{timestamp}"
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
    
    def check_logout_dialog(self) -> bool:
        """妫€鏌ユ槸鍚︽樉绀虹櫥鍑哄璇濇"""
        try:
            import cv2
            import numpy as np
            from PIL import Image
            import io
            
            screenshot = adb_screencap(self.device_serial)
            if not screenshot:
                return False
            
            img = Image.open(io.BytesIO(screenshot))
            img_array = np.array(img)
            cv_img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            height, width = cv_img.shape[:2]
            
            # 妫€娴嬮粍鑹插厓绱狅紙纭鎸夐挳锛?
            hsv = cv2.cvtColor(cv_img, cv2.COLOR_BGR2HSV)
            lower_yellow = np.array([20, 100, 100])
            upper_yellow = np.array([35, 255, 255])
            yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
            yellow_ratio = cv2.countNonZero(yellow_mask) / (width * height)
            
            # 妫€娴嬬櫧鑹插尯鍩燂紙瀵硅瘽妗嗚儗鏅級
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            white_mask = cv2.inRange(gray, 200, 255)
            white_ratio = cv2.countNonZero(white_mask) / (width * height)
            
            # 鐧诲嚭瀵硅瘽妗嗙壒寰侊細鐧借壊鑳屾櫙 + 榛勮壊鎸夐挳
            return white_ratio > 0.3 and yellow_ratio > 0.001
            
        except Exception as e:
            print(f"[ERROR] 鐧诲嚭妫€娴嬪け璐ワ細{e}")
            return False
    
    def click_logout_confirm(self):
        """鐐瑰嚮鐧诲嚭纭鎸夐挳"""
        print(f"\n[鐐瑰嚮] 鐧诲嚭纭鎸夐挳")
        # 鐧诲嚭瀵硅瘽妗嗙‘璁ゆ寜閽綅缃紙1280x720 閫昏緫鍧愭爣锛?
        confirm_x, confirm_y = 640, 580
        
        if self._maafw and self._maafw.connected:
            self._maafw.safe_press(confirm_x, confirm_y)
        else:
            import subprocess
            subprocess.run(["adb", "-s", self.device_serial, "shell", "input", "tap", str(confirm_x), str(confirm_y)])
        
        self.adb.wait(2)
        self.capture("logout_confirm")
    
    def tap(self, x: int, y: int, label: str):
        """鐐瑰嚮"""
        print(f"\n[鐐瑰嚮] {label} @ ({x}, {y})")
        
        if self._maafw and self._maafw.connected:
            self._maafw.safe_press(x, y)
        else:
            import subprocess
            subprocess.run(["adb", "-s", self.device_serial, "shell", "input", "tap", str(x), str(y)])
        
        self.adb.wait(1)
        self.capture(f"tap_{label}")
        self.steps_log.append({"step": label, "action": "tap", "coords": [x, y], "status": "OK"})
    
    def back(self):
        """杩斿洖"""
        print(f"\n[杩斿洖]")
        
        if self._maafw and self._maafw.connected:
            try:
                job = self._maafw.post_keyevent(4)
                if job:
                    job.wait()
            except:
                pass
        else:
            import subprocess
            subprocess.run(["adb", "-s", self.device_serial, "shell", "input", "keyevent", "4"])
        
        self.adb.wait(1)
        self.capture("back")
        self.steps_log.append({"step": "back", "action": "back", "status": "OK"})
    
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
            "steps": self.steps_log,
            "step_count": len(self.steps_log),
            "timestamp": datetime.now().isoformat()
        }
        
        report_path = self.session_dir / "report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n[鎶ュ憡] {report_path}")
        return report


def run_daily_quest(executor: FlowExecutor):
    """鎵ц姣忔棩浠诲姟娴佺▼"""
    
    print("\n" + "="*60)
    print("鏍囧噯娴佹祴璇?- 姣忔棩浠诲姟")
    print("="*60)
    
    # 姝ラ 0: 妫€鏌ュ苟澶勭悊鐧诲嚭瀵硅瘽妗?
    print("\n--- 姝ラ 0: 妫€鏌ョ櫥鍑哄璇濇 ---")
    if executor.check_logout_dialog():
        print("[璀﹀憡] 妫€娴嬪埌鐧诲嚭瀵硅瘽妗嗭紒")
        executor.click_logout_confirm()
        executor.wait(3)
        print("[OK] 宸插鐞嗙櫥鍑哄璇濇")
    
    # 姝ラ 1: 鐐瑰嚮浠诲姟鍥炬爣
    print("\n--- 姝ラ 1: 鎵撳紑浠诲姟闈㈡澘 ---")
    executor.tap(860, 80, "task_icon")
    
    # 姝ラ 2: 棰嗗彇姣忔棩浠诲姟濂栧姳
    print("\n--- 姝ラ 2: 棰嗗彇姣忔棩浠诲姟濂栧姳 ---")
    executor.tap(810, 900, "claim_daily")
    executor.wait(2)
    
    # 姝ラ 3: 杩斿洖
    print("\n--- 姝ラ 3: 杩斿洖鎺㈢储鐣岄潰 ---")
    executor.back()
    
    print("\n" + "="*60)
    print("娴佺▼瀹屾垚")
    print("="*60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="鏍囧噯娴佸畬鏁存祴璇?- 鏈€缁堢増")
    parser.add_argument("--device", type=str, default=None, help="璁惧搴忓垪鍙?)
    parser.add_argument("--flow", type=str, default="daily_quest", help="娴佺▼鍚嶇О")
    args = parser.parse_args()
    
    # 纭畾璁惧
    device_serial = args.device or list_devices()[0]
    print(f"[璁惧] {device_serial}")
    
    # 鍒涘缓鎵ц鍣?
    executor = FlowExecutor(device_serial)
    executor.start_session(args.flow)
    
    # 鎵ц娴佺▼
    if args.flow == "daily_quest":
        run_daily_quest(executor)
    else:
        print(f"[ERROR] 鏈煡娴佺▼锛歿args.flow}")
        return 1
    
    # 瀵煎嚭鎶ュ憡
    executor.export_report()
    
    print("\n" + "="*60)
    print("娴嬭瘯瀹屾垚")
    print(f"姝ラ鏁伴噺锛歿len(executor.steps_log)}")
    print(f"鎴浘鏁伴噺锛歿len(executor.screenshots)}")
    print(f"浼氳瘽鐩綍锛歿executor.session_dir}")
    print("="*60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

