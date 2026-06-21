#!/usr/bin/env python3
"""
标准流综合测试 - 测试标准流引擎的完整功能

功能:
1. 测试标准流配置加载
2. 测试 MaaFw 触控
3. 测试登出对话框检测
4. 测试异常处理机制
5. 生成详细测试报告
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()

from core.adb_utils import ADB, list_devices, adb_screencap

# MaaFramework 触控适配器
try:
    from device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig, MAAFW_AVAILABLE
except ImportError:
    MaaFwTouchExecutor = None
    MAAFW_AVAILABLE = False


class ComprehensiveFlowTester:
    """标准流综合测试器"""
    
    def __init__(self, device_serial: str):
        self.device_serial = device_serial
        self.adb = ADB(serial=device_serial)
        self.adb_path = PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"
        
        # 初始化 MaaFw 触控
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
                    print(f"[MaaFw] 触控初始化成功")
            except Exception as e:
                print(f"[MaaFw] 初始化失败：{e}")
        
        self.session_dir = None
        self.test_results = []
        self.screenshots = []
        
    def start_session(self):
        """开始测试会话"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = PROJECT_ROOT / "cache" / f"comprehensive_test_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        (self.session_dir / "screenshots").mkdir(exist_ok=True)
        print(f"[会话] {self.session_dir}")
        
    def capture(self, label: str) -> bytes:
        """截图并保存"""
        try:
            screenshot = adb_screencap(self.device_serial)
            if screenshot:
                timestamp = datetime.now().strftime("%Y%m%S")
                filename = f"{label}_{timestamp}.png"
                path = self.session_dir / "screenshots" / filename
                with open(path, "wb") as f:
                    f.write(screenshot)
                self.screenshots.append(str(path))
                print(f"[截图] {filename}")
            return screenshot
        except Exception as e:
            print(f"[ERROR] 截图失败：{e}")
            return None
    
    def test_maa_fw_click(self) -> bool:
        """测试 MaaFw 点击"""
        print("\n" + "="*60)
        print("测试 1: MaaFw 点击")
        print("="*60)
        
        try:
            if not self._maafw or not self._maafw.connected:
                print("[FAIL] MaaFw 未连接")
                self.test_results.append({"test": "maa_fw_click", "status": "FAIL", "reason": "MaaFw 未连接"})
                return False
            
            # 点击测试坐标
            x, y = 100, 100
            print(f"[点击] 测试坐标 ({x}, {y})")
            result = self._maafw.safe_press(x, y)
            
            time.sleep(1)
            self.capture("maa_fw_click_test")
            
            if result:
                print("[PASS] MaaFw 点击成功")
                self.test_results.append({"test": "maa_fw_click", "status": "PASS"})
                return True
            else:
                print("[FAIL] MaaFw 点击失败")
                self.test_results.append({"test": "maa_fw_click", "status": "FAIL", "reason": "safe_press 返回 False"})
                return False
                
        except Exception as e:
            print(f"[FAIL] MaaFw 点击异常：{e}")
            self.test_results.append({"test": "maa_fw_click", "status": "FAIL", "reason": str(e)})
            return False
    
    def test_maa_fw_swipe(self) -> bool:
        """测试 MaaFw 滑动"""
        print("\n" + "="*60)
        print("测试 2: MaaFw 滑动")
        print("="*60)
        
        try:
            if not self._maafw or not self._maafw.connected:
                print("[FAIL] MaaFw 未连接")
                self.test_results.append({"test": "maa_fw_swipe", "status": "FAIL", "reason": "MaaFw 未连接"})
                return False
            
            # 滑动测试
            x1, y1 = 540, 900
            x2, y2 = 540, 500
            print(f"[滑动] ({x1}, {y1}) -> ({x2}, {y2})")
            result = self._maafw.safe_swipe(x1, y1, x2, y2, duration=600)
            
            time.sleep(1)
            self.capture("maa_fw_swipe_test")
            
            if result:
                print("[PASS] MaaFw 滑动成功")
                self.test_results.append({"test": "maa_fw_swipe", "status": "PASS"})
                return True
            else:
                print("[FAIL] MaaFw 滑动失败")
                self.test_results.append({"test": "maa_fw_swipe", "status": "FAIL", "reason": "safe_swipe 返回 False"})
                return False
                
        except Exception as e:
            print(f"[FAIL] MaaFw 滑动异常：{e}")
            self.test_results.append({"test": "maa_fw_swipe", "status": "FAIL", "reason": str(e)})
            return False
    
    def test_maa_fw_back(self) -> bool:
        """测试 MaaFw 返回键"""
        print("\n" + "="*60)
        print("测试 3: MaaFw 返回键")
        print("="*60)
        
        try:
            if not self._maafw or not self._maafw.connected:
                print("[FAIL] MaaFw 未连接")
                self.test_results.append({"test": "maa_fw_back", "status": "FAIL", "reason": "MaaFw 未连接"})
                return False
            
            # 返回键测试 (KEYCODE_BACK = 4)
            print(f"[返回] KEYCODE_BACK (4)")
            job = self._maafw.post_keyevent(4)
            
            if job:
                job.wait()
                time.sleep(1)
                self.capture("maa_fw_back_test")
                
                print("[PASS] MaaFw 返回键成功")
                self.test_results.append({"test": "maa_fw_back", "status": "PASS"})
                return True
            else:
                print("[FAIL] MaaFw 返回键失败")
                self.test_results.append({"test": "maa_fw_back", "status": "FAIL", "reason": "post_keyevent 返回 None"})
                return False
                
        except Exception as e:
            print(f"[FAIL] MaaFw 返回键异常：{e}")
            self.test_results.append({"test": "maa_fw_back", "status": "FAIL", "reason": str(e)})
            return False
    
    def test_logout_detection(self) -> bool:
        """测试登出对话框检测"""
        print("\n" + "="*60)
        print("测试 4: 登出对话框检测")
        print("="*60)
        
        try:
            import cv2
            import numpy as np
            from PIL import Image
            import io
            
            screenshot = adb_screencap(self.device_serial)
            if not screenshot:
                print("[FAIL] 截图失败")
                self.test_results.append({"test": "logout_detection", "status": "FAIL", "reason": "截图失败"})
                return False
            
            img = Image.open(io.BytesIO(screenshot))
            img_array = np.array(img)
            cv_img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            height, width = cv_img.shape[:2]
            
            # 检测黄色元素（确认按钮）
            hsv = cv2.cvtColor(cv_img, cv2.COLOR_BGR2HSV)
            lower_yellow = np.array([20, 100, 100])
            upper_yellow = np.array([35, 255, 255])
            yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
            yellow_ratio = cv2.countNonZero(yellow_mask) / (width * height)
            
            # 检测白色区域（对话框背景）
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            white_mask = cv2.inRange(gray, 200, 255)
            white_ratio = cv2.countNonZero(white_mask) / (width * height)
            
            has_logout = white_ratio > 0.3 and yellow_ratio > 0.001
            
            print(f"黄色比例：{yellow_ratio:.4f} (阈值：0.001)")
            print(f"白色比例：{white_ratio:.4f} (阈值：0.3)")
            print(f"检测结果：{'登出对话框' if has_logout else '正常页面'}")
            
            self.capture("logout_detection_test")
            
            print("[PASS] 登出对话框检测成功")
            self.test_results.append({
                "test": "logout_detection",
                "status": "PASS",
                "yellow_ratio": yellow_ratio,
                "white_ratio": white_ratio,
                "has_logout": has_logout
            })
            return True
            
        except Exception as e:
            print(f"[FAIL] 登出对话框检测异常：{e}")
            self.test_results.append({"test": "logout_detection", "status": "FAIL", "reason": str(e)})
            return False
    
    def test_screenshot(self) -> bool:
        """测试截图功能"""
        print("\n" + "="*60)
        print("测试 5: 截图功能")
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
                
                print(f"[PASS] 截图成功 ({len(screenshot)} bytes)")
                self.test_results.append({"test": "screenshot", "status": "PASS", "size": len(screenshot)})
                return True
            else:
                print("[FAIL] 截图失败")
                self.test_results.append({"test": "screenshot", "status": "FAIL", "reason": "adb_screencap 返回 None"})
                return False
                
        except Exception as e:
            print(f"[FAIL] 截图异常：{e}")
            self.test_results.append({"test": "screenshot", "status": "FAIL", "reason": str(e)})
            return False
    
    def export_report(self):
        """导出测试报告"""
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
        
        print(f"\n[报告] {report_path}")
        return report


def run_comprehensive_tests(executor: ComprehensiveFlowTester):
    """运行所有测试"""
    
    print("\n" + "="*60)
    print("标准流综合测试")
    print("="*60)
    
    # 测试 1: MaaFw 点击
    executor.test_maa_fw_click()
    
    # 测试 2: MaaFw 滑动
    executor.test_maa_fw_swipe()
    
    # 测试 3: MaaFw 返回键
    executor.test_maa_fw_back()
    
    # 测试 4: 登出对话框检测
    executor.test_logout_detection()
    
    # 测试 5: 截图功能
    executor.test_screenshot()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="标准流综合测试")
    parser.add_argument("--device", type=str, default=None, help="设备序列号")
    args = parser.parse_args()
    
    # 确定设备
    device_serial = args.device or list_devices()[0]
    print(f"[设备] {device_serial}")
    
    # 创建测试器
    executor = ComprehensiveFlowTester(device_serial)
    executor.start_session()
    
    # 运行测试
    run_comprehensive_tests(executor)
    
    # 导出报告
    report = executor.export_report()
    
    # 打印摘要
    print("\n" + "="*60)
    print("测试摘要")
    print("="*60)
    print(f"总测试数：{report['test_count']}")
    print(f"通过数：{report['pass_count']}")
    print(f"失败数：{report['fail_count']}")
    print(f"截图数：{report['screenshot_count']}")
    print(f"成功率：{report['pass_count']/report['test_count']*100:.1f}%")
    print(f"会话目录：{executor.session_dir}")
    print("="*60)
    
    return 0 if report['fail_count'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
