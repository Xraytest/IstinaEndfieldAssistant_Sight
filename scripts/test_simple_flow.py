#!/usr/bin/env python3
"""
标准流测试 - 最终版（不依赖 PaddleOCR）

使用：
1. MaaFw 触控
2. MaaFw 截图
3. 简单的视觉特征分析（不依赖 OCR）
4. MaaEnd 式登出检测逻辑（关键词匹配）
"""

import sys
import os
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
    print("[WARN] MaaFramework 未安装")


class SimplePageAnalyzer:
    """简单的页面分析器（不依赖 OCR）"""
    
    # MaaEnd 式登出关键词
    LOGOUT_KEYWORDS = [
        "登出", "退出", "登录界面", "超时", "重新登录", "会话过期",
        "自动登出", "长时间", "没有操作", "断开连接", "确认", "取消",
        "logout", "timeout", "session", "login"
    ]
    
    def __init__(self):
        pass
    
    def analyze(self, screenshot: bytes) -> dict:
        """
        分析截图（不依赖 OCR）
        
        Returns:
            dict: {
                "page_type": str,
                "has_logout_dialog": bool,
                "features": dict
            }
        """
        try:
            import cv2
            import numpy as np
            from PIL import Image
            import io
            
            # 解码图片
            img = Image.open(io.BytesIO(screenshot))
            img_array = np.array(img)
            cv_img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            height, width = cv_img.shape[:2]
            
            # 1. 检测黄色元素（登出对话框确认按钮）
            hsv = cv2.cvtColor(cv_img, cv2.COLOR_BGR2HSV)
            lower_yellow = np.array([20, 100, 100])
            upper_yellow = np.array([35, 255, 255])
            yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
            yellow_pixels = cv2.countNonZero(yellow_mask)
            yellow_ratio = yellow_pixels / (width * height)
            
            # 2. 检测白色/浅色区域（登出对话框背景）
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            white_mask = cv2.inRange(gray, 200, 255)
            white_pixels = cv2.countNonZero(white_mask)
            white_ratio = white_pixels / (width * height)
            
            # 3. 检测暗色区域（标题画面特征）
            dark_mask = cv2.inRange(gray, 0, 40)
            dark_pixels = cv2.countNonZero(dark_mask)
            dark_ratio = dark_pixels / (width * height)
            
            # 4. 检测左侧导航栏（世界地图特征）
            left_bar = cv_img[:, :100, :]
            left_bar_gray = cv2.cvtColor(left_bar, cv2.COLOR_BGR2GRAY)
            left_bar_brightness = np.mean(left_bar_gray)
            
            # 5. 检测右上角绿色元素（任务/活动图标）
            top_right = cv_img[:200, int(width*0.7):, :]
            top_right_hsv = cv2.cvtColor(top_right, cv2.COLOR_BGR2HSV)
            lower_green = np.array([40, 50, 50])
            upper_green = np.array([80, 255, 255])
            green_mask = cv2.inRange(top_right_hsv, lower_green, upper_green)
            green_pixels = cv2.countNonZero(green_mask)
            
            # 判断页面类型
            # 登出对话框特征：白色背景 + 黄色按钮
            has_logout = white_ratio > 0.3 and yellow_ratio > 0.001
            # 世界地图特征：左侧暗色导航栏 + 右上角绿色元素
            is_world_map = left_bar_brightness < 50 and green_pixels > 100
            # 标题画面特征：大量暗色区域 + 无左侧导航栏
            is_title = dark_ratio > 0.5 and left_bar_brightness > 100 and not has_logout
            
            if has_logout:
                page_type = "logout_dialog"
            elif is_world_map:
                page_type = "world_map"
            elif is_title:
                page_type = "title_screen"
            else:
                page_type = "unknown"
            
            return {
                "page_type": page_type,
                "has_logout_dialog": has_logout,
                "features": {
                    "yellow_ratio": yellow_ratio,
                    "white_ratio": white_ratio,
                    "dark_ratio": dark_ratio,
                    "left_bar_brightness": left_bar_brightness,
                    "green_pixels": green_pixels
                }
            }
            
        except Exception as e:
            print(f"[ERROR] 页面分析失败：{e}")
            return {
                "page_type": "error",
                "has_logout_dialog": False,
                "features": {}
            }


class SimpleFlowExecutor:
    """简单标准流执行器（不依赖 OCR）"""
    
    def __init__(self, device_serial: str):
        self.device_serial = device_serial
        self.adb = ADB(serial=device_serial)
        self.analyzer = SimplePageAnalyzer()
        
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
        self.session_dir = PROJECT_ROOT / "cache" / f"flow_{flow_name}_simple_{timestamp}"
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
    
    def check_page(self) -> str:
        """检查当前页面类型（不依赖 OCR）"""
        screenshot = adb_screencap(self.device_serial)
        if not screenshot:
            return "error"
        
        result = self.analyzer.analyze(screenshot)
        page_type = result["page_type"]
        features = result["features"]
        
        print(f"\n[页面检测] 视觉分析（不依赖 OCR）")
        print(f"  类型：{page_type}")
        print(f"  黄色按钮：{features.get('yellow_ratio', 0):.4f}")
        print(f"  白色背景：{features.get('white_ratio', 0):.4f}")
        print(f"  暗色区域：{features.get('dark_ratio', 0):.4f}")
        print(f"  左侧亮度：{features.get('left_bar_brightness', 0):.1f}")
        print(f"  绿色像素：{features.get('green_pixels', 0)}")
        
        if result["has_logout_dialog"]:
            print(f"\n[警告] 检测到登出对话框！")
            return "logout_dialog"
        
        return page_type
    
    def tap(self, x: int, y: int, label: str):
        """点击（仅使用 MaaFw，严禁 ADB 触控）"""
        print(f"\n[点击] {label} @ ({x}, {y})")
        if self._maafw and self._maafw.connected:
            self._maafw.safe_press(x, y)
        else:
            raise RuntimeError("MaaFw 未连接，无法执行点击操作")
        self.adb.wait(1)
        self.capture(f"tap_{label}")

    def back(self):
        """返回（仅使用 MaaFw，严禁 ADB 触控）"""
        print(f"\n[返回]")
        if self._maafw and self._maafw.connected:
            job = self._maafw.post_keyevent(4)
            if job:
                job.wait()
        else:
            raise RuntimeError("MaaFw 未连接，无法执行返回操作")
        self.adb.wait(1)
        self.capture("back")
    
    def handle_logout_dialog(self):
        """处理退出游戏对话框 - 点击取消按钮（不是确认按钮！）"""
        print(f"\n[处理] 检测到退出游戏对话框，点击取消按钮...")

        # 退出游戏对话框特征：
        # - 白色背景
        # - 左侧灰色"取消"按钮
        # - 右侧黄色"确认"按钮
        # 我们需要点击"取消"按钮来继续游戏
        
        # 截图尺寸：1920x1080，MaaFw 逻辑坐标：1280x720
        # 从截图估算：取消按钮在对话框底部左侧
        # 1920x1080 坐标：约 (800, 700)
        # 转换为 1280x720: (800/1920*1280, 700/1080*720) ≈ (533, 467)
        
        # 尝试多个坐标
        coords = [
            (533, 467),  # 估算坐标
            (540, 470),  # 微调
            (520, 460),  # 偏左
            (550, 480),  # 偏右
            (533, 450),  # 偏上
            (533, 480),  # 偏下
        ]
        
        for x, y in coords:
            print(f"  点击取消按钮 @ ({x}, {y})")
            self.tap(x, y, "exit_cancel")
            self.wait(2)
            
            # 检查是否已退出对话框
            page_type = self.check_page()
            if page_type != "logout_dialog":
                print(f"  [OK] 已退出对话框，当前页面：{page_type}")
                return True
        
        print(f"  [WARN] 仍在对话框，可能需要手动处理")
        return False
    
    def wait(self, seconds: int):
        """等待"""
        print(f"\n[等待] {seconds}s")
        self.adb.wait(seconds)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="标准流测试 - 简单版（不依赖 OCR）")
    parser.add_argument("--device", type=str, default=None, help="设备序列号")
    parser.add_argument("--flow", type=str, default="daily_quest", help="流程名称")
    args = parser.parse_args()
    
    # 确定设备
    device_serial = args.device or list_devices()[0]
    print(f"[设备] {device_serial}")
    
    # 创建执行器
    executor = SimpleFlowExecutor(device_serial)
    executor.start_session(args.flow)
    
    print("\n" + "="*60)
    print(f"标准流测试 - 简单版（不依赖 OCR）")
    print(f"流程：{args.flow}")
    print("="*60)
    
    # 步骤 1: 检查初始页面
    print("\n--- 步骤 1: 检查初始页面 ---")
    page_type = executor.check_page()
    
    # 处理登出对话框
    if page_type == "logout_dialog":
        print("\n[登出] 检测到登出对话框，尝试处理...")
        success = executor.handle_logout_dialog()

        if not success:
            print("\n[错误] 登出对话框处理失败，需要手动处理")
        
        # 重新检查页面
        page_type = executor.check_page()

    # 处理标题画面
    max_title_attempts = 5
    for attempt in range(max_title_attempts):
        if page_type == "title_screen":
            print(f"\n[标题] 检测到标题画面，点击中央继续 ({attempt+1}/{max_title_attempts})...")
            executor.tap(640, 360, "title_continue")
            executor.wait(5)
            page_type = executor.check_page()
        else:
            break
    
    # 如果还在标题画面，尝试重新启动游戏
    if page_type == "title_screen":
        print("\n[警告] 标题画面无法跳过，尝试重新启动游戏...")
        # 这里可以添加游戏重启逻辑
    
    # 步骤 2: 打开任务面板
    print("\n--- 步骤 2: 打开任务面板 ---")

    # 先检查是否有登出对话框
    page_type = executor.check_page()
    if page_type == "logout_dialog":
        print("\n[警告] 检测到登出对话框，尝试处理...")
        executor.handle_logout_dialog()
        executor.wait(3)

    # 尝试多个任务图标坐标（右上角）
    # 从截图分析：1920x1080 分辨率，任务图标在右上角
    # 转换为 1280x720 逻辑坐标
    # 1920x1080 坐标约 (1700, 80) → 1280x720: (1133, 53)
    task_coords = [
        (1133, 53),   # 右上角任务图标
        (1140, 60),   # 微调
        (1120, 50),   # 稍左
        (1150, 60),   # 稍右
        (1133, 45),   # 稍上
        (1133, 65),   # 稍下
    ]
    
    task_opened = False
    for x, y in task_coords:
        print(f"\n[尝试] 点击任务图标 @ ({x}, {y})")
        executor.tap(x, y, "task_icon")
        executor.wait(2)
        
        # 检查页面变化
        page_type = executor.check_page()
        # 如果页面类型变化或不再显示退出对话框，认为任务面板已打开
        if page_type != "logout_dialog":
            print(f"  [OK] 任务面板可能已打开，当前页面：{page_type}")
            task_opened = True
            break
    
    if not task_opened:
        print("\n[警告] 任务图标点击失败，继续执行流程...")

    # 步骤 3: 检查任务面板
    print("\n--- 步骤 3: 检查任务面板 ---")
    page_type = executor.check_page()

    # 检查是否有登出对话框
    if page_type == "logout_dialog":
        print("\n[警告] 检测到登出对话框，尝试处理...")
        executor.handle_logout_dialog()
        executor.wait(3)

    # 步骤 4: 领取奖励
    print("\n--- 步骤 4: 领取奖励 ---")
    # 尝试多个领取按钮坐标
    claim_coords = [
        (1100, 650),  # 右下角
        (1150, 680),  # 更靠右下
        (1050, 620),  # 稍左
    ]
    
    for x, y in claim_coords:
        print(f"\n[尝试] 点击领取按钮 @ ({x}, {y})")
        executor.tap(x, y, "claim_all")
        executor.wait(2)
        break  # 只尝试一次，避免多次点击
    
    # 再次检查登出对话框
    page_type = executor.check_page()
    if page_type == "logout_dialog":
        print("\n[警告] 检测到登出对话框，尝试处理...")
        executor.handle_logout_dialog()
        executor.wait(3)

    # 步骤 5: 返回
    print("\n--- 步骤 5: 返回探索界面 ---")
    executor.back()
    executor.wait(2)
    
    # 再次检查登出对话框
    page_type = executor.check_page()
    if page_type == "logout_dialog":
        print("\n[警告] 检测到登出对话框，尝试处理...")
        executor.handle_logout_dialog()
        executor.wait(3)

    # 步骤 6: 检查返回结果
    print("\n--- 步骤 6: 检查返回结果 ---")
    page_type = executor.check_page()
    
    # 最终检查登出对话框
    if page_type == "logout_dialog":
        print("\n[警告] 检测到登出对话框，需要手动处理")


if __name__ == "__main__":
    sys.exit(main())
