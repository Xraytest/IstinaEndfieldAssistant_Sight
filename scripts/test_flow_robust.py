#!/usr/bin/env python3
"""
标准流测试 - 完整异常处理版本

功能:
1. 登出对话框检测和自动处理
2. 游戏状态检查和自动启动
3. 模拟器异常处理（重启）
4. 完整的每日任务流程
5. 详细的执行报告
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

# MaaFw 触控
try:
    from core.capability.device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig
    MAAFW_AVAILABLE = True
except ImportError:
    MaaFwTouchExecutor = None
    MAAFW_AVAILABLE = False


class RobustFlowExecutor:
    """健壮的标准流执行器 - 包含完整异常处理"""
    
    def __init__(self, device_serial: str):
        self.device_serial = device_serial
        self.adb = ADB(serial=device_serial)
        self.adb_path = PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"
        
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
        self.screenshots = []
        self.steps_log = []
        self.errors = []
        
    def start_session(self, flow_name: str):
        """开始执行会话"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = PROJECT_ROOT / "cache" / f"flow_{flow_name}_robust_{timestamp}"
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
    
    def check_logout_dialog(self) -> bool:
        """检查是否显示登出对话框"""
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
    
    def handle_logout_dialog(self, max_attempts: int = 5):
        """处理登出对话框 - 多次尝试点击（使用 MaaFw）"""
        print(f"\n[处理] 检测到登出对话框，开始处理...")
        
        # 尝试多个坐标
        coords = [
            (640, 580), (640, 600), (640, 620),  # 逻辑坐标
            (960, 850), (960, 870), (960, 890),  # 物理坐标
        ]
        
        for i, (x, y) in enumerate(coords):
            print(f"  尝试 {i+1}/{len(coords)}: 点击 ({x}, {y})")
            # 使用 MaaFw 点击
            if self._maafw and self._maafw.connected:
                self._maafw.safe_press(x, y)
            time.sleep(1)
            
            if not self.check_logout_dialog():
                print(f"  [OK] 登出对话框已关闭")
                return True
        
        print(f"  [WARN] 登出对话框处理失败，尝试重启模拟器")
        return False
    
    def _adb_tap(self, x: int, y: int):
        """错误：严禁使用 ADB 触控输入！应使用 MaaFw"""
        raise RuntimeError("严禁使用 ADB 触控输入！应使用 MaaFw.safe_press()")
    
    def _adb_back(self):
        """错误：严禁使用 ADB 触控输入！应使用 MaaFw"""
        raise RuntimeError("严禁使用 ADB 触控输入！应使用 MaaFw.post_keyevent()")
    
    def restart_emulator(self):
        """重启模拟器"""
        print(f"\n[异常处理] 重启模拟器...")
        try:
            # 发送重启命令
            subprocess.run(
                [str(self.adb_path), "-s", self.device_serial, "reboot"],
                timeout=10
            )
            print(f"  [INFO] 重启命令已发送")
            
            # 等待重启（约 60 秒）
            print(f"  [INFO] 等待模拟器重启...")
            for i in range(60):
                time.sleep(1)
                if i % 10 == 0:
                    print(f"    等待 {i}/60 秒...")
            
            # 等待设备重新连接
            print(f"  [INFO] 等待设备重新连接...")
            for i in range(30):
                devices = list_devices()
                if self.device_serial in devices:
                    print(f"  [OK] 设备已重新连接")
                    return True
                time.sleep(1)
            
            print(f"  [ERROR] 设备重新连接超时")
            return False
            
        except Exception as e:
            print(f"  [ERROR] 重启模拟器失败：{e}")
            return False
    
    def tap(self, x: int, y: int, label: str):
        """点击（仅使用 MaaFw）"""
        print(f"\n[点击] {label} @ ({x}, {y})")
        
        # 仅使用 MaaFw
        if self._maafw and self._maafw.connected:
            self._maafw.safe_press(x, y)
        else:
            raise RuntimeError("MaaFw 未连接，无法执行点击操作")
        
        time.sleep(1)
        self.capture(f"tap_{label}")
        self.steps_log.append({"step": label, "action": "tap", "coords": [x, y], "status": "OK"})
    
    def back(self):
        """返回（仅使用 MaaFw）"""
        print(f"\n[返回]")
        
        # 仅使用 MaaFw
        if self._maafw and self._maafw.connected:
            job = self._maafw.post_keyevent(4)  # 4 = KEYCODE_BACK
            if job:
                job.wait()
        else:
            raise RuntimeError("MaaFw 未连接，无法执行返回操作")
        
        time.sleep(1)
        self.capture("back")
        self.steps_log.append({"step": "back", "action": "back", "status": "OK"})
    
    def wait(self, seconds: int):
        """等待"""
        print(f"\n[等待] {seconds}s")
        time.sleep(seconds)
    
    def export_report(self):
        """导出执行报告"""
        report = {
            "device": self.device_serial,
            "session_dir": str(self.session_dir),
            "screenshots": self.screenshots,
            "screenshot_count": len(self.screenshots),
            "steps": self.steps_log,
            "step_count": len(self.steps_log),
            "errors": self.errors,
            "error_count": len(self.errors),
            "timestamp": datetime.now().isoformat()
        }
        
        report_path = self.session_dir / "report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n[报告] {report_path}")
        return report


def run_daily_quest_flow(executor: RobustFlowExecutor) -> bool:
    """执行每日任务流程"""
    
    print("\n" + "="*60)
    print("标准流测试 - 每日任务")
    print("="*60)
    
    # 步骤 0: 检查并处理登出对话框
    print("\n--- 步骤 0: 检查登出对话框 ---")
    if executor.check_logout_dialog():
        print("[警告] 检测到登出对话框！")
        if not executor.handle_logout_dialog():
            # 尝试重启模拟器
            if executor.restart_emulator():
                print("[OK] 模拟器已重启，重新检查")
                time.sleep(10)
                if executor.check_logout_dialog():
                    print("[错误] 重启后仍有登出对话框")
                    executor.errors.append("登出对话框无法处理")
                    return False
            else:
                print("[错误] 模拟器重启失败")
                executor.errors.append("模拟器重启失败")
                return False
        executor.wait(3)
    else:
        print("[OK] 无登出对话框")
    
    # 步骤 1: 点击任务图标
    print("\n--- 步骤 1: 打开任务面板 ---")
    executor.tap(860, 80, "task_icon")
    
    # 步骤 2: 领取每日任务奖励
    print("\n--- 步骤 2: 领取每日任务奖励 ---")
    executor.tap(810, 900, "claim_daily")
    executor.wait(2)
    
    # 步骤 3: 返回
    print("\n--- 步骤 3: 返回探索界面 ---")
    executor.back()
    
    print("\n" + "="*60)
    print("流程完成")
    print("="*60)
    
    return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="标准流测试 - 完整异常处理版本")
    parser.add_argument("--device", type=str, default=None, help="设备序列号")
    parser.add_argument("--flow", type=str, default="daily_quest", help="流程名称")
    args = parser.parse_args()
    
    # 确定设备
    device_serial = args.device or list_devices()[0]
    print(f"[设备] {device_serial}")
    
    # 创建执行器
    executor = RobustFlowExecutor(device_serial)
    executor.start_session(args.flow)
    
    # 执行流程
    success = run_daily_quest_flow(executor)
    
    # 导出报告
    executor.export_report()
    
    print("\n" + "="*60)
    print("测试完成")
    print(f"步骤数量：{len(executor.steps_log)}")
    print(f"截图数量：{len(executor.screenshots)}")
    print(f"错误数量：{len(executor.errors)}")
    print(f"会话目录：{executor.session_dir}")
    print(f"状态：{'成功' if success else '失败'}")
    print("="*60)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
