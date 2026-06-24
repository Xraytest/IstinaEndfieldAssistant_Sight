#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佺患鍚堟祴璇?- 娴嬭瘯鏍囧噯娴佸紩鎿庣殑瀹屾暣鍔熻兘

鍔熻兘:
1. 娴嬭瘯鏍囧噯娴侀厤缃姞杞?
2. 娴嬭瘯 MaaFw 瑙︽帶
3. 娴嬭瘯鐧诲嚭瀵硅瘽妗嗘娴?
4. 娴嬭瘯寮傚父澶勭悊鏈哄埗
5. 鐢熸垚璇︾粏娴嬭瘯鎶ュ憡
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

# MaaFramework 瑙︽帶閫傞厤鍣?
try:
    from core.capability.device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig, MAAFW_AVAILABLE
except ImportError:
    MaaFwTouchExecutor = None
    MAAFW_AVAILABLE = False


class ComprehensiveFlowTester:
    """鏍囧噯娴佺患鍚堟祴璇曞櫒"""
    
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
        self.session_dir = PROJECT_ROOT / "cache" / f"comprehensive_test_{timestamp}"
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
    
    def test_maa_fw_click(self) -> bool:
        """娴嬭瘯 MaaFw 鐐瑰嚮"""
        print("\n" + "="*60)
        print("娴嬭瘯 1: MaaFw 鐐瑰嚮")
        print("="*60)
        
        try:
            if not self._maafw or not self._maafw.connected:
                print("[FAIL] MaaFw 鏈繛鎺?)
                self.test_results.append({"test": "maa_fw_click", "status": "FAIL", "reason": "MaaFw 鏈繛鎺?})
                return False
            
            # 鐐瑰嚮娴嬭瘯鍧愭爣
            x, y = 100, 100
            print(f"[鐐瑰嚮] 娴嬭瘯鍧愭爣 ({x}, {y})")
            result = self._maafw.safe_press(x, y)
            
            time.sleep(1)
            self.capture("maa_fw_click_test")
            
            if result:
                print("[PASS] MaaFw 鐐瑰嚮鎴愬姛")
                self.test_results.append({"test": "maa_fw_click", "status": "PASS"})
                return True
            else:
                print("[FAIL] MaaFw 鐐瑰嚮澶辫触")
                self.test_results.append({"test": "maa_fw_click", "status": "FAIL", "reason": "safe_press 杩斿洖 False"})
                return False
                
        except Exception as e:
            print(f"[FAIL] MaaFw 鐐瑰嚮寮傚父锛歿e}")
            self.test_results.append({"test": "maa_fw_click", "status": "FAIL", "reason": str(e)})
            return False
    
    def test_maa_fw_swipe(self) -> bool:
        """娴嬭瘯 MaaFw 婊戝姩"""
        print("\n" + "="*60)
        print("娴嬭瘯 2: MaaFw 婊戝姩")
        print("="*60)
        
        try:
            if not self._maafw or not self._maafw.connected:
                print("[FAIL] MaaFw 鏈繛鎺?)
                self.test_results.append({"test": "maa_fw_swipe", "status": "FAIL", "reason": "MaaFw 鏈繛鎺?})
                return False
            
            # 婊戝姩娴嬭瘯
            x1, y1 = 540, 900
            x2, y2 = 540, 500
            print(f"[婊戝姩] ({x1}, {y1}) -> ({x2}, {y2})")
            result = self._maafw.safe_swipe(x1, y1, x2, y2, duration=600)
            
            time.sleep(1)
            self.capture("maa_fw_swipe_test")
            
            if result:
                print("[PASS] MaaFw 婊戝姩鎴愬姛")
                self.test_results.append({"test": "maa_fw_swipe", "status": "PASS"})
                return True
            else:
                print("[FAIL] MaaFw 婊戝姩澶辫触")
                self.test_results.append({"test": "maa_fw_swipe", "status": "FAIL", "reason": "safe_swipe 杩斿洖 False"})
                return False
                
        except Exception as e:
            print(f"[FAIL] MaaFw 婊戝姩寮傚父锛歿e}")
            self.test_results.append({"test": "maa_fw_swipe", "status": "FAIL", "reason": str(e)})
            return False
    
    def test_maa_fw_back(self) -> bool:
        """娴嬭瘯 MaaFw 杩斿洖閿?""
        print("\n" + "="*60)
        print("娴嬭瘯 3: MaaFw 杩斿洖閿?)
        print("="*60)
        
        try:
            if not self._maafw or not self._maafw.connected:
                print("[FAIL] MaaFw 鏈繛鎺?)
                self.test_results.append({"test": "maa_fw_back", "status": "FAIL", "reason": "MaaFw 鏈繛鎺?})
                return False
            
            # 杩斿洖閿祴璇?(KEYCODE_BACK = 4)
            print(f"[杩斿洖] KEYCODE_BACK (4)")
            job = self._maafw.post_keyevent(4)
            
            if job:
                job.wait()
                time.sleep(1)
                self.capture("maa_fw_back_test")
                
                print("[PASS] MaaFw 杩斿洖閿垚鍔?)
                self.test_results.append({"test": "maa_fw_back", "status": "PASS"})
                return True
            else:
                print("[FAIL] MaaFw 杩斿洖閿け璐?)
                self.test_results.append({"test": "maa_fw_back", "status": "FAIL", "reason": "post_keyevent 杩斿洖 None"})
                return False
                
        except Exception as e:
            print(f"[FAIL] MaaFw 杩斿洖閿紓甯革細{e}")
            self.test_results.append({"test": "maa_fw_back", "status": "FAIL", "reason": str(e)})
            return False
    
    def test_logout_detection(self) -> bool:
        """娴嬭瘯鐧诲嚭瀵硅瘽妗嗘娴?""
        print("\n" + "="*60)
        print("娴嬭瘯 4: 鐧诲嚭瀵硅瘽妗嗘娴?)
        print("="*60)
        
        try:
            import cv2
            import numpy as np
            from PIL import Image
            import io
            
            screenshot = adb_screencap(self.device_serial)
            if not screenshot:
                print("[FAIL] 鎴浘澶辫触")
                self.test_results.append({"test": "logout_detection", "status": "FAIL", "reason": "鎴浘澶辫触"})
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
            
            has_logout = white_ratio > 0.3 and yellow_ratio > 0.001
            
            print(f"榛勮壊姣斾緥锛歿yellow_ratio:.4f} (闃堝€硷細0.001)")
            print(f"鐧借壊姣斾緥锛歿white_ratio:.4f} (闃堝€硷細0.3)")
            print(f"妫€娴嬬粨鏋滐細{'鐧诲嚭瀵硅瘽妗? if has_logout else '姝ｅ父椤甸潰'}")
            
            self.capture("logout_detection_test")
            
            print("[PASS] 鐧诲嚭瀵硅瘽妗嗘娴嬫垚鍔?)
            self.test_results.append({
                "test": "logout_detection",
                "status": "PASS",
                "yellow_ratio": yellow_ratio,
                "white_ratio": white_ratio,
                "has_logout": has_logout
            })
            return True
            
        except Exception as e:
            print(f"[FAIL] 鐧诲嚭瀵硅瘽妗嗘娴嬪紓甯革細{e}")
            self.test_results.append({"test": "logout_detection", "status": "FAIL", "reason": str(e)})
            return False
    
    def test_screenshot(self) -> bool:
        """娴嬭瘯鎴浘鍔熻兘"""
        print("\n" + "="*60)
        print("娴嬭瘯 5: 鎴浘鍔熻兘")
        print("="*60)
        
        try:
            screenshot = adb_screencap(self.device_serial)
            if screenshot:
                timestamp = datetime.now().strftime("%Y%m%S")
                filename = f"screenshot_test_{timestamp}.png"
                path = self.session_dir / "screenshots" / filename
                with open(path, "wb") as f:
                    f.write(screenshot)
                self.screenshots.append(str(path))
                
                print(f"[PASS] 鎴浘鎴愬姛 ({len(screenshot)} bytes)")
                self.test_results.append({"test": "screenshot", "status": "PASS", "size": len(screenshot)})
                return True
            else:
                print("[FAIL] 鎴浘澶辫触")
                self.test_results.append({"test": "screenshot", "status": "FAIL", "reason": "adb_screencap 杩斿洖 None"})
                return False
                
        except Exception as e:
            print(f"[FAIL] 鎴浘寮傚父锛歿e}")
            self.test_results.append({"test": "screenshot", "status": "FAIL", "reason": str(e)})
            return False
    
    def export_report(self):
        """瀵煎嚭娴嬭瘯鎶ュ憡"""
        report = {
            "device": self.device_serial,
            "session_dir": str(self.session_dir),
            "timestamp": datetime.now().isoformat(),
            "test_count": len(self.test_results),
            "pass_count": sum(1 for r in self.test_results if r.get("status") == "PASS"),
            "fail_count": sum(1 for r in self.test_results if r.get("status") == "FAIL"),
            "screenshot_count": len(self.screenshots),
            "tests": self.test_results
        }
        
        report_path = self.session_dir / "report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n[鎶ュ憡] {report_path}")
        return report


def run_comprehensive_tests(executor: ComprehensiveFlowTester):
    """杩愯鎵€鏈夋祴璇?""
    
    print("\n" + "="*60)
    print("鏍囧噯娴佺患鍚堟祴璇?)
    print("="*60)
    
    # 娴嬭瘯 1: MaaFw 鐐瑰嚮
    executor.test_maa_fw_click()
    
    # 娴嬭瘯 2: MaaFw 婊戝姩
    executor.test_maa_fw_swipe()
    
    # 娴嬭瘯 3: MaaFw 杩斿洖閿?
    executor.test_maa_fw_back()
    
    # 娴嬭瘯 4: 鐧诲嚭瀵硅瘽妗嗘娴?
    executor.test_logout_detection()
    
    # 娴嬭瘯 5: 鎴浘鍔熻兘
    executor.test_screenshot()
    
    print("\n" + "="*60)
    print("娴嬭瘯瀹屾垚")
    print("="*60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="鏍囧噯娴佺患鍚堟祴璇?)
    parser.add_argument("--device", type=str, default=None, help="璁惧搴忓垪鍙?)
    args = parser.parse_args()
    
    # 纭畾璁惧
    device_serial = args.device or list_devices()[0]
    print(f"[璁惧] {device_serial}")
    
    # 鍒涘缓娴嬭瘯鍣?
    executor = ComprehensiveFlowTester(device_serial)
    executor.start_session()
    
    # 杩愯娴嬭瘯
    run_comprehensive_tests(executor)
    
    # 瀵煎嚭鎶ュ憡
    report = executor.export_report()
    
    # 鎵撳嵃鎽樿
    print("\n" + "="*60)
    print("娴嬭瘯鎽樿")
    print("="*60)
    print(f"鎬绘祴璇曟暟锛歿report['test_count']}")
    print(f"閫氳繃鏁帮細{report['pass_count']}")
    print(f"澶辫触鏁帮細{report['fail_count']}")
    print(f"鎴浘鏁帮細{report['screenshot_count']}")
    print(f"鎴愬姛鐜囷細{report['pass_count']/report['test_count']*100:.1f}%")
    print(f"浼氳瘽鐩綍锛歿executor.session_dir}")
    print("="*60)
    
    return 0 if report['fail_count'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

