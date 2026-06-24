#!/usr/bin/env python3
"""
登出对话框检测测试 - 使用截图分析

分析：
1. 为什么 OCR 没检测到登出对话框
2. 登出对话框的特征
3. 如何改进检测
"""

import sys
import os
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

def analyze_screenshot():
    """分析截图中的登出对话框"""
    print("\n" + "="*60)
    print("登出对话框分析")
    print("="*60)
    
    # 读取截图
    screenshot_path = PROJECT_ROOT / "cache" / "flow_daily_quest_20260616_172418" / "screenshots" / "preamble_08_1781601969_9da8b863.png"
    
    if not screenshot_path.exists():
        print(f"[ERROR] 截图不存在：{screenshot_path}")
        return
    
    print(f"\n截图路径：{screenshot_path}")
    
    # 使用 OpenCV 分析截图
    try:
        import cv2
        import numpy as np
        
        img = cv2.imread(str(screenshot_path))
        if img is None:
            print("[ERROR] 无法读取截图")
            return
        
        print(f"截图尺寸：{img.shape[1]}x{img.shape[0]}")
        
        # 转换为 HSV 检测红色（登出对话框通常有红色元素）
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # 红色范围 1
        lower_red1 = np.array([0, 70, 50])
        upper_red1 = np.array([10, 255, 255])
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        
        # 红色范围 2
        lower_red2 = np.array([170, 70, 50])
        upper_red2 = np.array([180, 255, 255])
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        
        mask = cv2.bitwise_or(mask1, mask2)
        red_pixels = cv2.countNonZero(mask)
        
        print(f"红色像素数量：{red_pixels}")
        
        # 检测对话框区域（通常是半透明黑色背景）
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # 查找暗色区域
        dark_mask = cv2.inRange(gray, 0, 50)
        dark_pixels = cv2.countNonZero(dark_mask)
        
        print(f"暗色像素数量：{dark_pixels}")
        
        # 计算整体亮度
        brightness = np.mean(gray)
        print(f"平均亮度：{brightness:.2f}")
        
        # 检测文字区域（高对比度）
        edges = cv2.Canny(gray, 50, 150)
        edge_pixels = cv2.countNonZero(edges)
        print(f"边缘像素数量：{edge_pixels}")
        
        # 保存分析结果
        output_path = PROJECT_ROOT / "cache" / "logout_analysis.png"
        cv2.imwrite(str(output_path), mask)
        print(f"\n红色掩膜已保存：{output_path}")
        
        # 判断是否有登出对话框
        # 登出对话框特征：
        # 1. 有明显的红色元素（警告图标）
        # 2. 有半透明黑色背景
        # 3. 有文字"登出"、"超时"、"确认"、"取消"等
        
        has_red = red_pixels > 1000
        has_dark = dark_pixels > 50000
        has_text = edge_pixels > 10000
        
        print(f"\n登出对话框特征:")
        print(f"  红色元素：{'✓' if has_red else '✗'} ({red_pixels} 像素)")
        print(f"  暗色背景：{'✓' if has_dark else '✗'} ({dark_pixels} 像素)")
        print(f"  文字边缘：{'✓' if has_text else '✗'} ({edge_pixels} 像素)")
        
        if has_red and has_dark:
            print(f"\n[可能] 检测到登出对话框特征")
        else:
            print(f"\n[正常] 未检测到登出对话框特征")
            
    except ImportError:
        print("[ERROR] OpenCV 未安装")
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()


def analyze_ocr_keywords():
    """分析 OCR 关键词检测"""
    print("\n" + "="*60)
    print("OCR 关键词分析")
    print("="*60)
    
    # 登出对话框可能的关键词
    logout_keywords = [
        "登出", "超时", "重新登录", "会话过期",
        "自动登出", "长时间", "没有操作", "断开连接",
        "确认", "取消", "LOGOUT", "TIMEOUT", "SESSION"
    ]
    
    print("\n登出对话框关键词:")
    for kw in logout_keywords:
        print(f"  - {kw}")
    
    print("\n问题:")
    print("  1. OCR 可能无法识别模糊/小字号文字")
    print("  2. 登出对话框可能使用图标而非文字")
    print("  3. PaddleOCR 新版本有兼容性问题")
    
    print("\n解决方案:")
    print("  1. 使用模板匹配检测登出对话框图标")
    print("  2. 使用颜色检测（红色警告图标）")
    print("  3. 使用多特征融合（颜色 + 布局 + OCR）")


if __name__ == "__main__":
    analyze_screenshot()
    analyze_ocr_keywords()
