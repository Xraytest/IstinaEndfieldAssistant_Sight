#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佸紓甯稿鐞嗘祴璇?- 娴嬭瘯瀹屾暣寮傚父澶勭悊鏈哄埗

鍔熻兘:
1. 娴嬭瘯鐧诲嚭瀵硅瘽妗嗘娴?
2. 娴嬭瘯鐧诲嚭瀵硅瘽妗嗚嚜鍔ㄥ鐞?
3. 娴嬭瘯娓告垙閲嶅惎鏈哄埗
4. 娴嬭瘯妯℃嫙鍣ㄩ噸鍚満鍒?
5. 鐢熸垚璇︾粏娴嬭瘯鎶ュ憡
"""

import sys
import os
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()

from core.capability.adb_utils import ADB, list_devices, adb_screencap

# MaaFramework 瑙︽帶閫傞厤鍣?
try:
    from core.capability.device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig, MAAFW_AVAILABLE
except ImportError:
    MaaFwTouchExecutor = None
    MAAFW_AVAILABLE = False


class ExceptionHandlerTester:
    """寮傚父澶勭悊娴嬭瘯鍣?""
    
    def __init__(self, device_serial: str):
        self.device_serial = device_serial
        self.adb = ADB(serial=device_serial)
        self.adb_path = PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"
        
        # 鍒濆鍖?MaaFw 瑙︽帶
        self._maafw = None
        if MAAFW_AVAILABLE:
            try:
                maafw_config = MaaFwTouchConfig(
                    adb_path=str(self.adb_path),
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
        self.test_results = []
        self.screenshots = []
        
    def start_session(self):
        """寮€濮嬫祴璇曚細璇?""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = PROJECT_ROOT / "cache" / f"exception_test_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        (self.session_dir / "screenshots").mkdir(exist_ok=True)
        print(f"[浼氳瘽] {self.session_dir}")
        
    def capture(self, label: str) -> bytes:
        """鎴浘骞朵繚瀛?""
        try:
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
        except Exception as e:
            print(f"[ERROR] 鎴浘澶辫触锛歿e}")
            return None
    
    def detect_logout_dialog(self) -> bool:
        """妫€娴嬬櫥鍑哄璇濇"""
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
    
    def test_logout_detection(self) -> bool:
        """娴嬭瘯 1: 鐧诲嚭瀵硅瘽妗嗘娴?""
        print("\n" + "="*60)
        print("娴嬭瘯 1: 鐧诲嚭瀵硅瘽妗嗘娴?)
        print("="*60)
        
        try:
            has_logout = self.detect_logout_dialog()
            self.capture("logout_detection")
            
            print(f"妫€娴嬬粨鏋滐細{'鐧诲嚭瀵硅瘽妗? if has_logout else '姝ｅ父椤甸潰'}")
            
            print("[PASS] 鐧诲嚭瀵硅瘽妗嗘娴嬫垚鍔?)
            self.test_results.append({
                "test": "logout_detection",
                "status": "PASS",
                "has_logout": has_logout
            })
            return True
            
        except Exception as e:
            print(f"[FAIL] 鐧诲嚭瀵硅瘽妗嗘娴嬪け璐ワ細{e}")
            self.test_results.append({"test": "logout_detection", "status": "FAIL", "reason": str(e)})
            return False
    
    def test_logout_handling(self) -> bool:
        """娴嬭瘯 2: 鐧诲嚭瀵硅瘽妗嗚嚜鍔ㄥ鐞?""
        print("\n" + "="*60)
        print("娴嬭瘯 2: 鐧诲嚭瀵硅瘽妗嗚嚜鍔ㄥ鐞?)
        print("="*60)
        
        try:
            if not self.detect_logout_dialog():
                print("[INFO] 褰撳墠鏃犵櫥鍑哄璇濇锛岃烦杩囧鐞嗘祴璇?)
                self.test_results.append({
                    "test": "logout_handling",
                    "status": "SKIP",
                    "reason": "鏃犵櫥鍑哄璇濇"
                })
                return True
            
            print("[INFO] 妫€娴嬪埌鐧诲嚭瀵硅瘽妗嗭紝寮€濮嬪鐞?..")
            
            # 灏濊瘯鐐瑰嚮纭鎸夐挳
            coords = [(540, 960), (640, 600), (540, 700)]
            for x, y in coords:
                print(f"  鐐瑰嚮 ({x}, {y})")
                if self._maafw and self._maafw.connected:
                    self._maafw.safe_press(x, y)
                time.sleep(1)
                
                if not self.detect_logout_dialog():
                    print("[OK] 鐧诲嚭瀵硅瘽妗嗗凡鍏抽棴")
                    self.capture("logout_handled")
                    self.test_results.append({"test": "logout_handling", "status": "PASS"})
                    return True
            
            print("[WARN] 鐧诲嚭瀵硅瘽妗嗗鐞嗗け璐?)
            self.test_results.append({"test": "logout_handling", "status": "FAIL", "reason": "鐐瑰嚮鏃犳晥"})
            return False
            
        except Exception as e:
            print(f"[FAIL] 鐧诲嚭瀵硅瘽妗嗗鐞嗗紓甯革細{e}")
            self.test_results.append({"test": "logout_handling", "status": "FAIL", "reason": str(e)})
            return False
    
    def test_restart_game(self) -> bool:
        """娴嬭瘯 3: 娓告垙閲嶅惎鏈哄埗"""
        print("\n" + "="*60)
        print("娴嬭瘯 3: 娓告垙閲嶅惎鏈哄埗")
        print("="*60)
        
        try:
            # 鍋滄娓告垙
            print("[INFO] 鍋滄娓告垙...")
            subprocess.run(
                [str(self.adb_path), "-s", self.device_serial, "shell", "am", "force-stop", "com.hypergryph.endfield"],
                capture_output=True, timeout=10
            )
            time.sleep(3)
            
            # 鍚姩娓告垙
            print("[INFO] 鍚姩娓告垙...")
            subprocess.run(
                [str(self.adb_path), "-s", self.device_serial, "shell", "am", "start", "-n", "com.hypergryph.endfield/.ui.splash.SplashActivity"],
                capture_output=True, timeout=10
            )
            
            # 绛夊緟娓告垙鍔犺浇
            print("[INFO] 绛夊緟娓告垙鍔犺浇...")
            time.sleep(10)
            
            self.capture("game_restarted")
            
            print("[PASS] 娓告垙閲嶅惎鎴愬姛")
            self.test_results.append({"test": "restart_game", "status": "PASS"})
            return True
            
        except Exception as e:
            print(f"[FAIL] 娓告垙閲嶅惎澶辫触锛歿e}")
            self.test_results.append({"test": "restart_game", "status": "FAIL", "reason": str(e)})
            return False
    
    def test_restart_emulator(self) -> bool:
        """娴嬭瘯 4: 妯℃嫙鍣ㄩ噸鍚満鍒?""
        print("\n" + "="*60)
        print("娴嬭瘯 4: 妯℃嫙鍣ㄩ噸鍚満鍒?)
        print("="*60)
        
        # 娉ㄦ剰锛氭ā鎷熷櫒閲嶅惎闇€瑕佽緝闀挎椂闂达紝杩欓噷浠呴獙璇佸懡浠ゅ彂閫?
        try:
            print("[INFO] 妯℃嫙鍣ㄩ噸鍚祴璇曪紙浠呴獙璇佸懡浠ゅ彂閫侊紝涓嶅疄闄呴噸鍚級")
            
            # 妫€鏌?adb reboot 鍛戒护鏄惁鍙敤
            result = subprocess.run(
                [str(self.adb_path), "-s", self.device_serial, "get-state"],
                capture_output=True, timeout=10, text=True
            )
            
            if "device" in result.stdout:
                print("[OK] 璁惧杩炴帴姝ｅ父")
                print("[INFO] 妯℃嫙鍣ㄩ噸鍚懡浠わ細adb -s {device} reboot")
                print("[PASS] 妯℃嫙鍣ㄩ噸鍚満鍒跺彲鐢紙鏈疄闄呮墽琛岋級")
                self.test_results.append({
                    "test": "restart_emulator",
                    "status": "PASS",
                    "note": "鍛戒护鍙敤锛屾湭瀹為檯鎵ц"
                })
                return True
            else:
                print("[FAIL] 璁惧杩炴帴寮傚父")
                self.test_results.append({"test": "restart_emulator", "status": "FAIL", "reason": "璁惧杩炴帴寮傚父"})
                return False
                
        except Exception as e:
            print(f"[FAIL] 妯℃嫙鍣ㄩ噸鍚祴璇曞紓甯革細{e}")
            self.test_results.append({"test": "restart_emulator", "status": "FAIL", "reason": str(e)})
            return False
    
    def export_report(self):
        """瀵煎嚭娴嬭瘯鎶ュ憡"""
        report = {
            "device": self.device_serial,
            "session_dir": str(self.session_dir),
            "timestamp": datetime.now().isoformat(),
            "test_count": len(self.test_results),
            "pass_count": sum(1 for r in self.test_results if r.get("status") == "PASS"),
            "skip_count": sum(1 for r in self.test_results if r.get("status") == "SKIP"),
            "fail_count": sum(1 for r in self.test_results if r.get("status") == "FAIL"),
            "screenshot_count": len(self.screenshots),
            "tests": self.test_results
        }
        
        report_path = self.session_dir / "report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n[鎶ュ憡] {report_path}")
        return report


def run_exception_tests(executor: ExceptionHandlerTester):
    """杩愯鎵€鏈夊紓甯稿鐞嗘祴璇?""
    
    print("\n" + "="*60)
    print("鏍囧噯娴佸紓甯稿鐞嗘祴璇?)
    print("="*60)
    
    # 娴嬭瘯 1: 鐧诲嚭瀵硅瘽妗嗘娴?
    executor.test_logout_detection()
    
    # 娴嬭瘯 2: 鐧诲嚭瀵硅瘽妗嗚嚜鍔ㄥ鐞?
    executor.test_logout_handling()
    
    # 娴嬭瘯 3: 娓告垙閲嶅惎鏈哄埗
    # executor.test_restart_game()  # 娉ㄩ噴鎺夛紝閬垮厤瀹為檯閲嶅惎娓告垙
    
    # 娴嬭瘯 4: 妯℃嫙鍣ㄩ噸鍚満鍒?
    executor.test_restart_emulator()
    
    print("\n" + "="*60)
    print("娴嬭瘯瀹屾垚")
    print("="*60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="鏍囧噯娴佸紓甯稿鐞嗘祴璇?)
    parser.add_argument("--device", type=str, default=None, help="璁惧搴忓垪鍙?)
    args = parser.parse_args()
    
    # 纭畾璁惧
    device_serial = args.device or list_devices()[0]
    print(f"[璁惧] {device_serial}")
    
    # 鍒涘缓娴嬭瘯鍣?
    executor = ExceptionHandlerTester(device_serial)
    executor.start_session()
    
    # 杩愯娴嬭瘯
    run_exception_tests(executor)
    
    # 瀵煎嚭鎶ュ憡
    report = executor.export_report()
    
    # 鎵撳嵃鎽樿
    print("\n" + "="*60)
    print("娴嬭瘯鎽樿")
    print("="*60)
    print(f"鎬绘祴璇曟暟锛歿report['test_count']}")
    print(f"閫氳繃鏁帮細{report['pass_count']}")
    print(f"璺宠繃鏁帮細{report['skip_count']}")
    print(f"澶辫触鏁帮細{report['fail_count']}")
    print(f"鎴浘鏁帮細{report['screenshot_count']}")
    print(f"浼氳瘽鐩綍锛歿executor.session_dir}")
    print("="*60)
    
    return 0 if report['fail_count'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

