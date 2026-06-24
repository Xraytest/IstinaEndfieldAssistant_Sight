#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佸畬鏁存祴璇?- 鍖呭惈娓告垙鍚姩鍜屽紓甯稿鐞?

鍔熻兘:
1. 鍚姩娓告垙
2. 绛夊緟娓告垙鍔犺浇
3. 鐧诲嚭瀵硅瘽妗嗘娴嬪拰澶勭悊
4. 瀹屾暣鐨勬瘡鏃ヤ换鍔℃祦绋?
5. 寮傚父澶勭悊锛堥噸鍚父鎴?妯℃嫙鍣級
"""

import sys
import os
import json
import time
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


class CompleteFlowExecutor:
    """瀹屾暣鏍囧噯娴佹墽琛屽櫒"""
    
    def __init__(self, device_serial: str):
        self.device_serial = device_serial
        self.adb = ADB(serial=device_serial)
        self.attempt = 0
        
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
        self.session_dir = PROJECT_ROOT / "cache" / f"flow_{flow_name}_complete_{timestamp}"
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
            
            return white_ratio > 0.3 and yellow_ratio > 0.001
            
        except Exception as e:
            print(f"[ERROR] 鐧诲嚭妫€娴嬪け璐ワ細{e}")
            return False
    
    def check_game_running(self) -> bool:
        """妫€鏌ユ父鎴忔槸鍚︽鍦ㄨ繍琛?""
        try:
            import subprocess
            adb_path = PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"

            # 妫€鏌ユ父鎴忚繘绋嬶紙涓嶄娇鐢?shell=True锛?
            result = subprocess.run(
                [str(adb_path), "-s", self.device_serial, "shell", "ps"],
                capture_output=True,
                text=True,
                shell=False
            )

            # 鍦?Python 涓繃婊よ緭鍑?
            return "com.yoozoo.zmd" in result.stdout
        except:
            return False
    
    def launch_game(self):
        """鍚姩娓告垙"""
        print(f"\n[鍚姩] 鍚姩鏄庢棩鏂硅垷锛氱粓鏈湴")
        
        try:
            import subprocess
            adb_path = PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"

            # 鍚姩娓告垙鍖呭悕
            result = subprocess.run(
                [str(adb_path), "-s", self.device_serial, "shell", "monkey", "-p", "com.yoozoo.zmd", "-c", "android.intent.category.LAUNCHER"],
                capture_output=True,
                text=True
            )
            
            print(f"  鍚姩鍛戒护鎵ц锛歿result.returncode}")
            
            # 绛夊緟娓告垙鍔犺浇
            print(f"  绛夊緟娓告垙鍔犺浇...")
            for i in range(30):
                time.sleep(2)
                if self.check_game_running():
                    print(f"  [OK] 娓告垙宸插惎鍔?)
                    return True
            
            print(f"  [WARN] 娓告垙鍚姩瓒呮椂")
            return False
            
        except Exception as e:
            print(f"  [ERROR] 鍚姩娓告垙澶辫触锛歿e}")
            return False
    
    def handle_logout_dialog(self, max_attempts: int = 3):
        """澶勭悊鐧诲嚭瀵硅瘽妗?""
        print(f"\n[澶勭悊] 妫€娴嬪埌鐧诲嚭瀵硅瘽妗嗭紝灏濊瘯澶勭悊...")
        
        for attempt in range(max_attempts):
            print(f"  灏濊瘯 {attempt + 1}/{max_attempts}")
            
            # 鐐瑰嚮纭鎸夐挳锛堝绉嶅潗鏍囧皾璇曪級
            coords = [
                (640, 580),   # 閫昏緫鍧愭爣
                (640, 600),   # 绋嶄綆涓€鐐?
                (640, 620),   # 鏇翠綆
            ]
            
            for x, y in coords:
                print(f"  鐐瑰嚮 ({x}, {y})")
                self.tap(x, y, f"logout_confirm_{attempt}")
                time.sleep(1)
            
            # 妫€鏌ユ槸鍚﹀凡閫€鍑虹櫥鍑哄璇濇
            if not self.check_logout_dialog():
                print(f"  [OK] 宸查€€鍑虹櫥鍑哄璇濇")
                return True
            
            time.sleep(1)
        
        print(f"  [WARN] 鐧诲嚭瀵硅瘽妗嗗鐞嗗け璐?)
        return False
    
    def tap(self, x: int, y: int, label: str):
        """鐐瑰嚮锛堜粎浣跨敤 MaaFw锛?""
        print(f"\n[鐐瑰嚮] {label} @ ({x}, {y})")

        # 浠呬娇鐢?MaaFw锛屼弗绂?ADB 瑙︽帶
        if self._maafw and self._maafw.connected:
            self._maafw.safe_press(x, y)
        else:
            raise RuntimeError("MaaFw 鏈繛鎺ワ紝鏃犳硶鎵ц鐐瑰嚮鎿嶄綔")

        self.adb.wait(1)
        self.capture(f"tap_{label}")
        self.steps_log.append({"step": label, "action": "tap", "coords": [x, y], "status": "OK"})

    def back(self):
        """杩斿洖锛堜粎浣跨敤 MaaFw锛?""
        print(f"\n[杩斿洖]")

        # 浠呬娇鐢?MaaFw锛屼弗绂?ADB 瑙︽帶
        if self._maafw and self._maafw.connected:
            job = self._maafw.post_keyevent(4)  # 4 = KEYCODE_BACK
            if job:
                job.wait()
        else:
            raise RuntimeError("MaaFw 鏈繛鎺ワ紝鏃犳硶鎵ц杩斿洖鎿嶄綔")

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


def run_complete_flow(executor: CompleteFlowExecutor):
    """杩愯瀹屾暣鏍囧噯娴?""
    
    print("\n" + "="*60)
    print("鏍囧噯娴佹祴璇?- 瀹屾暣娴佺▼")
    print("="*60)
    
    # 姝ラ 0: 妫€鏌ユ父鎴忔槸鍚﹁繍琛?
    print("\n--- 姝ラ 0: 妫€鏌ユ父鎴忕姸鎬?---")
    if not executor.check_game_running():
        print("[INFO] 娓告垙鏈繍琛岋紝鍚姩娓告垙...")
        if not executor.launch_game():
            print("[ERROR] 娓告垙鍚姩澶辫触")
            return False
        executor.wait(5)
    else:
        print("[OK] 娓告垙姝ｅ湪杩愯")
    
    # 姝ラ 1: 妫€鏌ュ苟澶勭悊鐧诲嚭瀵硅瘽妗?
    print("\n--- 姝ラ 1: 妫€鏌ョ櫥鍑哄璇濇 ---")
    if executor.check_logout_dialog():
        print("[璀﹀憡] 妫€娴嬪埌鐧诲嚭瀵硅瘽妗嗭紒")
        if not executor.handle_logout_dialog():
            print("[閿欒] 鐧诲嚭瀵硅瘽妗嗗鐞嗗け璐?)
            return False
        executor.wait(3)
    else:
        print("[OK] 鏃犵櫥鍑哄璇濇")
    
    # 姝ラ 2: 鐐瑰嚮浠诲姟鍥炬爣
    print("\n--- 姝ラ 2: 鎵撳紑浠诲姟闈㈡澘 ---")
    executor.tap(860, 80, "task_icon")
    
    # 姝ラ 3: 棰嗗彇姣忔棩浠诲姟濂栧姳
    print("\n--- 姝ラ 3: 棰嗗彇姣忔棩浠诲姟濂栧姳 ---")
    executor.tap(810, 900, "claim_daily")
    executor.wait(2)
    
    # 姝ラ 4: 杩斿洖
    print("\n--- 姝ラ 4: 杩斿洖鎺㈢储鐣岄潰 ---")
    executor.back()
    
    print("\n" + "="*60)
    print("娴佺▼瀹屾垚")
    print("="*60)
    
    return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="鏍囧噯娴佸畬鏁存祴璇?- 鍖呭惈娓告垙鍚姩鍜屽紓甯稿鐞?)
    parser.add_argument("--device", type=str, default=None, help="璁惧搴忓垪鍙?)
    parser.add_argument("--flow", type=str, default="daily_quest", help="娴佺▼鍚嶇О")
    args = parser.parse_args()
    
    # 纭畾璁惧
    device_serial = args.device or list_devices()[0]
    print(f"[璁惧] {device_serial}")
    
    # 鍒涘缓鎵ц鍣?
    executor = CompleteFlowExecutor(device_serial)
    executor.start_session(args.flow)
    
    # 鎵ц娴佺▼
    success = run_complete_flow(executor)
    
    # 瀵煎嚭鎶ュ憡
    executor.export_report()
    
    print("\n" + "="*60)
    print("娴嬭瘯瀹屾垚")
    print(f"姝ラ鏁伴噺锛歿len(executor.steps_log)}")
    print(f"鎴浘鏁伴噺锛歿len(executor.screenshots)}")
    print(f"浼氳瘽鐩綍锛歿executor.session_dir}")
    print(f"鐘舵€侊細{'鎴愬姛' if success else '澶辫触'}")
    print("="*60)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

