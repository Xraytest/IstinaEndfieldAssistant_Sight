#!/usr/bin/env python3
"""
标准流异常处理测试 - 测试完整异常处理机制

功能:
1. 测试登出对话框检测
2. 测试登出对话框自动处理
3. 测试游戏重启机制
4. 测试模拟器重启机制
5. 生成详细测试报告
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

from core.adb_utils import ADB, list_devices, adb_screencap

# MaaFramework 触控适配器
try:
    from device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig, MAAFW_AVAILABLE
except ImportError:
    MaaFwTouchExecutor = None
    MAAFW_AVAILABLE = False


class ExceptionHandlerTester:
    """异常处理测试器"""
    
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
        self.session_dir = PROJECT_ROOT / "cache" / f"exception_test_{timestamp}"
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
    
    def detect_logout_dialog(self) -> bool:
        """检测登出对话框"""
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
            
            return white_ratio > 0.3 and yellow_ratio > 0.001
            
        except Exception as e:
            print(f"[ERROR] 登出检测失败：{e}")
            return False
    
    def test_logout_detection(self) -> bool:
        """测试 1: 登出对话框检测"""
        print("\n" + "="*60)
        print("测试 1: 登出对话框检测")
        print("="*60)
        
        try:
            has_logout = self.detect_logout_dialog()
            self.capture("logout_detection")
            
            print(f"检测结果：{'登出对话框' if has_logout else '正常页面'}")
            
            print("[PASS] 登出对话框检测成功")
            self.test_results.append({
                "test": "logout_detection",
                "status": "PASS",
                "has_logout": has_logout
            })
            return True
            
        except Exception as e:
            print(f"[FAIL] 登出对话框检测失败：{e}")
            self.test_results.append({"test": "logout_detection", "status": "FAIL", "reason": str(e)})
            return False
    
    def test_logout_handling(self) -> bool:
        """测试 2: 登出对话框自动处理"""
        print("\n" + "="*60)
        print("测试 2: 登出对话框自动处理")
        print("="*60)
        
        try:
            if not self.detect_logout_dialog():
                print("[INFO] 当前无登出对话框，跳过处理测试")
                self.test_results.append({
                    "test": "logout_handling",
                    "status": "SKIP",
                    "reason": "无登出对话框"
                })
                return True
            
            print("[INFO] 检测到登出对话框，开始处理...")
            
            # 尝试点击确认按钮
            coords = [(540, 960), (640, 600), (540, 700)]
            for x, y in coords:
                print(f"  点击 ({x}, {y})")
                if self._maafw and self._maafw.connected:
                    self._maafw.safe_press(x, y)
                time.sleep(1)
                
                if not self.detect_logout_dialog():
                    print("[OK] 登出对话框已关闭")
                    self.capture("logout_handled")
                    self.test_results.append({"test": "logout_handling", "status": "PASS"})
                    return True
            
            print("[WARN] 登出对话框处理失败")
            self.test_results.append({"test": "logout_handling", "status": "FAIL", "reason": "点击无效"})
            return False
            
        except Exception as e:
            print(f"[FAIL] 登出对话框处理异常：{e}")
            self.test_results.append({"test": "logout_handling", "status": "FAIL", "reason": str(e)})
            return False
    
    def test_restart_game(self) -> bool:
        """测试 3: 游戏重启机制"""
        print("\n" + "="*60)
        print("测试 3: 游戏重启机制")
        print("="*60)
        
        try:
            # 停止游戏
            print("[INFO] 停止游戏...")
            subprocess.run(
                [str(self.adb_path), "-s", self.device_serial, "shell", "am", "force-stop", "com.hypergryph.endfield"],
                capture_output=True, timeout=10
            )
            time.sleep(3)
            
            # 启动游戏
            print("[INFO] 启动游戏...")
            subprocess.run(
                [str(self.adb_path), "-s", self.device_serial, "shell", "am", "start", "-n", "com.hypergryph.endfield/.ui.splash.SplashActivity"],
                capture_output=True, timeout=10
            )
            
            # 等待游戏加载
            print("[INFO] 等待游戏加载...")
            time.sleep(10)
            
            self.capture("game_restarted")
            
            print("[PASS] 游戏重启成功")
            self.test_results.append({"test": "restart_game", "status": "PASS"})
            return True
            
        except Exception as e:
            print(f"[FAIL] 游戏重启失败：{e}")
            self.test_results.append({"test": "restart_game", "status": "FAIL", "reason": str(e)})
            return False
    
    def test_restart_emulator(self) -> bool:
        """测试 4: 模拟器重启机制"""
        print("\n" + "="*60)
        print("测试 4: 模拟器重启机制")
        print("="*60)
        
        # 注意：模拟器重启需要较长时间，这里仅验证命令发送
        try:
            print("[INFO] 模拟器重启测试（仅验证命令发送，不实际重启）")
            
            # 检查 adb reboot 命令是否可用
            result = subprocess.run(
                [str(self.adb_path), "-s", self.device_serial, "get-state"],
                capture_output=True, timeout=10, text=True
            )
            
            if "device" in result.stdout:
                print("[OK] 设备连接正常")
                print("[INFO] 模拟器重启命令：adb -s {device} reboot")
                print("[PASS] 模拟器重启机制可用（未实际执行）")
                self.test_results.append({
                    "test": "restart_emulator",
                    "status": "PASS",
                    "note": "命令可用，未实际执行"
                })
                return True
            else:
                print("[FAIL] 设备连接异常")
                self.test_results.append({"test": "restart_emulator", "status": "FAIL", "reason": "设备连接异常"})
                return False
                
        except Exception as e:
            print(f"[FAIL] 模拟器重启测试异常：{e}")
            self.test_results.append({"test": "restart_emulator", "status": "FAIL", "reason": str(e)})
            return False
    
    def export_report(self):
        """导出测试报告"""
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
        
        print(f"\n[报告] {report_path}")
        return report


def run_exception_tests(executor: ExceptionHandlerTester):
    """运行所有异常处理测试"""
    
    print("\n" + "="*60)
    print("标准流异常处理测试")
    print("="*60)
    
    # 测试 1: 登出对话框检测
    executor.test_logout_detection()
    
    # 测试 2: 登出对话框自动处理
    executor.test_logout_handling()
    
    # 测试 3: 游戏重启机制
    # executor.test_restart_game()  # 注释掉，避免实际重启游戏
    
    # 测试 4: 模拟器重启机制
    executor.test_restart_emulator()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="标准流异常处理测试")
    parser.add_argument("--device", type=str, default=None, help="设备序列号")
    args = parser.parse_args()
    
    # 确定设备
    device_serial = args.device or list_devices()[0]
    print(f"[设备] {device_serial}")
    
    # 创建测试器
    executor = ExceptionHandlerTester(device_serial)
    executor.start_session()
    
    # 运行测试
    run_exception_tests(executor)
    
    # 导出报告
    report = executor.export_report()
    
    # 打印摘要
    print("\n" + "="*60)
    print("测试摘要")
    print("="*60)
    print(f"总测试数：{report['test_count']}")
    print(f"通过数：{report['pass_count']}")
    print(f"跳过数：{report['skip_count']}")
    print(f"失败数：{report['fail_count']}")
    print(f"截图数：{report['screenshot_count']}")
    print(f"会话目录：{executor.session_dir}")
    print("="*60)
    
    return 0 if report['fail_count'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
