#!/usr/bin/env python3
"""使用 VLM 分析当前页面状态"""
import sys, os, base64, cv2, numpy as np
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

from core.capability.adb_utils import ADB
from core.foundation.logger import init_logger

# 初始化日志
core_init_logger()

def analyze_with_vlm():
    """使用 VLM 分析当前截图"""
    adb = ADB()
    
    # 截图
    print("[截图] 获取当前画面...")
    img_bytes = adb.screencap(dedup=False)
    if img_bytes is None:
        print("[ERROR] 截图失败")
        return
    
    # 保存截图
    with open(PROJECT_ROOT / "data" / "analysis" / "vlm_analysis_input.png", "wb") as f:
        f.write(img_bytes)
    print(f"[保存] 截图已保存")
    
    # VLM 分析
    print("\n[VLM] 开始分析页面...")
    result = adb.vlm_analyze(
        image_bytes=img_bytes,
        instruction="""分析当前游戏画面，回答以下问题：
1. 当前是什么页面？（登录界面/主菜单/世界地图/任务面板/退出对话框/加载界面/其他）
2. 画面中有哪些可交互的按钮或图标？
3. 如何导航到世界地图页面？
4. 如果有弹窗或对话框，是什么内容？

请用中文回答，简洁明了。""",
        communicator=None
    )
    
    if result and result.get("status") == "success":
        response = result.get("response", "")
        print(f"\n[VLM 分析结果]:")
        print(response)
        return response
    else:
        print(f"\n[VLM] 分析失败：{result}")
        return None

if __name__ == "__main__":
    analyze_with_vlm()
