#!/usr/bin/env python3
"""
标准流完整测试 - 最终版

功能:
1. 登出对话框检测和自动处理
2. 完整的每日任务流程
3. 截图记录
4. 执行报告
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()

from core.adb_utils import ADB, list_devices, adb_screencap

# MaaFw 触控
try:
    from device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig
    MAAFW_AVAILABLE = True
except ImportError:
    MaaFwTouchExecutor = None
    MAAFW_AVAILABLE = False
    print("[WARN] MaaFramework 未安装")


class FlowExecutor:
    """标准流执行器"""
    
    def __init__(self, device_serial: str):
        self.device_serial = device_serial
        self.adb = ADB(serial=device_serial)
        
        # 初始化 MaaFw 触控
        self._maafw = None
        if MAAFW_AVAILABLE:
            try:
                maafw_config = MaaFwTouchConfig(
                    adb_path=str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"),
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
        
    def start_session(self, flow_name: str):
        """开始执行会话"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = PROJECT_ROOT / "cache" / f"flow_{flow_name}_final_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        (self.session_dir / "screenshots").mkdir(exist_ok=True)
        print(f"[会话] {self.session_dir}")
        
    def capture(self, label: str) -> bytes:
        """截图并保存"""
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
            
            # 登出对话框特征：白色背景 + 黄色按钮
            return white_ratio > 0.3 and yellow_ratio > 0.001
            
        except Exception as e:
            print(f"[ERROR] 登出检测失败：{e}")
            return False
    
    def click_logout_confirm(self):
        """点击登出确认按钮"""
        print(f"\n[点击] 登出确认按钮")
        # 登出对话框确认按钮位置（1280x720 逻辑坐标）
        confirm_x, confirm_y = 640, 580
        
        if self._maafw and self._maafw.connected:
            self._maafw.safe_press(confirm_x, confirm_y)
        else:
            import subprocess
            subprocess.run(["adb", "-s", self.device_serial, "shell", "input", "tap", str(confirm_x), str(confirm_y)])
        
        self.adb.wait(2)
        self.capture("logout_confirm")
    
    def tap(self, x: int, y: int, label: str):
        """点击"""
        print(f"\n[点击] {label} @ ({x}, {y})")
        
        if self._maafw and self._maafw.connected:
            self._maafw.safe_press(x, y)
        else:
            import subprocess
            subprocess.run(["adb", "-s", self.device_serial, "shell", "input", "tap", str(x), str(y)])
        
        self.adb.wait(1)
        self.capture(f"tap_{label}")
        self.steps_log.append({"step": label, "action": "tap", "coords": [x, y], "status": "OK"})
    
    def back(self):
        """返回"""
        print(f"\n[返回]")
        
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
        """等待"""
        print(f"\n[等待] {seconds}s")
        self.adb.wait(seconds)
    
    def export_report(self):
        """导出执行报告"""
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
        
        print(f"\n[报告] {report_path}")
        return report


def run_daily_quest(executor: FlowExecutor):
    """执行每日任务流程"""
    
    print("\n" + "="*60)
    print("标准流测试 - 每日任务")
    print("="*60)
    
    # 步骤 0: 检查并处理登出对话框
    print("\n--- 步骤 0: 检查登出对话框 ---")
    if executor.check_logout_dialog():
        print("[警告] 检测到登出对话框！")
        executor.click_logout_confirm()
        executor.wait(3)
        print("[OK] 已处理登出对话框")
    
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


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="标准流完整测试 - 最终版")
    parser.add_argument("--device", type=str, default=None, help="设备序列号")
    parser.add_argument("--flow", type=str, default="daily_quest", help="流程名称")
    args = parser.parse_args()
    
    # 确定设备
    device_serial = args.device or list_devices()[0]
    print(f"[设备] {device_serial}")
    
    # 创建执行器
    executor = FlowExecutor(device_serial)
    executor.start_session(args.flow)
    
    # 执行流程
    if args.flow == "daily_quest":
        run_daily_quest(executor)
    else:
        print(f"[ERROR] 未知流程：{args.flow}")
        return 1
    
    # 导出报告
    executor.export_report()
    
    print("\n" + "="*60)
    print("测试完成")
    print(f"步骤数量：{len(executor.steps_log)}")
    print(f"截图数量：{len(executor.screenshots)}")
    print(f"会话目录：{executor.session_dir}")
    print("="*60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
