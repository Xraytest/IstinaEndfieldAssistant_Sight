#!/usr/bin/env python3
"""
标准流完整测试 - OCR_Only 数据源

功能：
1. 使用 MaaFw 内置 OCR 进行页面检测
2. 检测登出对话框（MaaEnd 式）
3. 截图记录
4. 完整流程执行
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()

from core.ocr.ocr_manager import OCRManager
from core.adb_utils import ADB, list_devices, adb_screencap

# MaaFw 触控
try:
    from device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig
    MAAFW_AVAILABLE = True
except ImportError:
    MaaFwTouchExecutor = None
    MAAFW_AVAILABLE = False


class OCROnlyFlowExecutor:
    """OCR_Only 标准流执行器"""

    def __init__(self, device_serial: str):
        self.device_serial = device_serial
        self.adb = ADB(serial=device_serial)
        self.ocr_manager = OCRManager()
        
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
        
    def start_session(self, flow_name: str):
        """开始执行会话"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = PROJECT_ROOT / "cache" / f"flow_{flow_name}_ocr_only_{timestamp}"
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
    
    def check_page(self, expected_type: str = None) -> str:
        """检查当前页面类型（OCR_Only）"""
        state = self.ocr_manager.capture_and_recognize(self.device_serial)
        
        print(f"\n[页面检测] OCR_Only")
        print(f"  类型：{state.page_type}")
        print(f"  描述：{state.description}")
        print(f"  顶部栏：{state.top_bar_buttons}")
        print(f"  面板文本：{len(state.overlay_texts)} 条")
        
        # 检查登出对话框
        if state.page_type == "logout_dialog":
            print(f"\n[警告] 检测到登出对话框！")
            print(f"  需要手动处理或自动取消")
            return "logout_dialog"
        
        # 检查预期页面
        if expected_type:
            if state.page_type == expected_type or (expected_type == "world" and "world" in state.page_type):
                print(f"  ✓ 页面匹配预期：{expected_type}")
            else:
                print(f"  ✗ 页面不匹配：期望={expected_type} 实际={state.page_type}")
        
        return state.page_type
    
    def tap(self, x: int, y: int, label: str):
        """点击 - 使用 MaaFw"""
        print(f"\n[点击] {label} @ ({x}, {y})")
        if self._maafw and self._maafw.connected:
            self._maafw.safe_press(x, y)
        else:
            # ADB 回退
            import subprocess
            subprocess.run(["adb", "-s", self.device_serial, "shell", "input", "tap", str(x), str(y)])
        self.adb.wait(1)
        self.capture(f"tap_{label}")
    
    def swipe(self, x1: int, y1: int, x2: int, y2: int, label: str):
        """滑动"""
        print(f"\n[滑动] {label}: ({x1},{y1}) -> ({x2},{y2})")
        self.adb.swipe(x1, y1, x2, y2, 300)
        self.adb.wait(1)
        self.capture(f"swipe_{label}")
    
    def back(self):
        """返回 - 使用 MaaFw"""
        print(f"\n[返回]")
        if self._maafw and self._maafw.connected:
            job = self._maafw.post_keyevent(4)  # KEYCODE_BACK
            if job:
                job.wait()
        else:
            # ADB 回退
            import subprocess
            subprocess.run(["adb", "-s", self.device_serial, "shell", "input", "keyevent", "4"])
        self.adb.wait(1)
        self.capture("back")
    
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
            "timestamp": datetime.now().isoformat()
        }
        
        report_path = self.session_dir / "report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n[报告] {report_path}")
        return report


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="标准流完整测试 - OCR_Only")
    parser.add_argument("--device", type=str, default=None, help="设备序列号")
    parser.add_argument("--flow", type=str, default="daily_quest", help="流程名称")
    args = parser.parse_args()
    
    # 确定设备
    device_serial = args.device or list_devices()[0]
    print(f"[设备] {device_serial}")
    
    # 创建执行器
    executor = OCROnlyFlowExecutor(device_serial)
    executor.start_session(args.flow)
    
    print("\n" + "="*60)
    print(f"标准流测试 - OCR_Only 数据源")
    print(f"流程：{args.flow}")
    print("="*60)
    
    # 步骤 1: 检查初始页面
    print("\n--- 步骤 1: 检查初始页面 ---")
    page_type = executor.check_page(expected_type="world")
    
    if page_type == "logout_dialog":
        print("\n[错误] 检测到登出对话框，无法继续")
        executor.export_report()
        return 1
    
    # 步骤 2: 打开任务面板
    print("\n--- 步骤 2: 打开任务面板 ---")
    executor.tap(860, 80, "task_icon")
    
    # 步骤 3: 检查任务面板
    print("\n--- 步骤 3: 检查任务面板 ---")
    page_type = executor.check_page()
    print(f"  面板文本示例：{executor.ocr_manager.decider.overlay_texts[:3] if hasattr(executor.ocr_manager.decider, 'overlay_texts') else 'N/A'}")
    
    # 步骤 4: 领取奖励
    print("\n--- 步骤 4: 领取奖励 ---")
    executor.tap(810, 900, "claim_all")
    executor.wait(2)
    
    # 步骤 5: 返回
    print("\n--- 步骤 5: 返回探索界面 ---")
    executor.back()
    
    # 步骤 6: 检查返回结果
    print("\n--- 步骤 6: 检查返回结果 ---")
    page_type = executor.check_page(expected_type="world")
    
    # 导出报告
    executor.export_report()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
