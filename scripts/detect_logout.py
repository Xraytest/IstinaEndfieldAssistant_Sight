#!/usr/bin/env python3
"""
登出对话框检测器 - 多特征融合方案

不依赖 PaddleOCR，使用：
1. 颜色检测（红色警告图标）
2. 布局分析（对话框特征）
3. 模板匹配（确认/取消按钮）
"""

import sys
import os
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()


def detect_logout_dialog(screenshot_path: str) -> dict:
    """
    检测登出对话框
    
    Returns:
        dict: {
            "detected": bool,
            "confidence": float,
            "features": {
                "has_red_warning": bool,
                "has_dialog_layout": bool,
                "has_confirm_cancel": bool,
                "dark_overlay": bool
            }
        }
    """
    import cv2
    import numpy as np
    
    result = {
        "detected": False,
        "confidence": 0.0,
        "features": {
            "has_red_warning": False,
            "has_dialog_layout": False,
            "has_confirm_cancel": False,
            "dark_overlay": False
        }
    }
    
    # 读取截图
    img = cv2.imread(screenshot_path)
    if img is None:
        return result
    
    height, width = img.shape[:2]
    
    # 1. 颜色检测 - 红色警告图标
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # 红色范围
    lower_red1 = np.array([0, 100, 100])
    upper_red1 = np.array([15, 255, 255])
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    
    lower_red2 = np.array([160, 100, 100])
    upper_red2 = np.array([180, 255, 255])
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    
    red_mask = cv2.bitwise_or(mask1, mask2)
    red_pixels = cv2.countNonZero(red_mask)
    red_ratio = red_pixels / (width * height)
    
    # 登出对话框通常有明显的红色警告图标
    result["features"]["has_red_warning"] = red_ratio > 0.001
    
    # 2. 布局分析 - 检测对话框特征
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 检测半透明黑色覆盖层
    dark_threshold = 40
    dark_mask = cv2.inRange(gray, 0, dark_threshold)
    dark_pixels = cv2.countNonZero(dark_mask)
    dark_ratio = dark_pixels / (width * height)
    
    # 登出对话框有大的半透明黑色背景
    result["features"]["dark_overlay"] = dark_ratio > 0.1
    
    # 3. 检测对话框边框（矩形轮廓）
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # 查找大的矩形轮廓（对话框）
    dialog_found = False
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 50000:  # 大的轮廓
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            if len(approx) == 4:  # 四边形
                x, y, w, h = cv2.boundingRect(approx)
                # 对话框通常在屏幕中央
                if width * 0.3 < x < width * 0.7 and height * 0.2 < y < height * 0.6:
                    dialog_found = True
                    break
    
    result["features"]["has_dialog_layout"] = dialog_found
    
    # 4. 检测确认/取消按钮（通常在对话框底部）
    # 按钮特征：矩形、有文字、在对话框底部
    button_area = gray[int(height * 0.5):int(height * 0.8), :]
    button_edges = cv2.Canny(button_area, 100, 200)
    button_contours, _ = cv2.findContours(button_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    button_count = 0
    for contour in button_contours:
        area = cv2.contourArea(contour)
        if 5000 < area < 50000:  # 按钮大小
            x, y, w, h = cv2.boundingRect(contour)
            if 50 < w < 300 and 30 < h < 100:  # 按钮比例
                button_count += 1
    
    # 登出对话框通常有 2 个按钮（确认/取消）
    result["features"]["has_confirm_cancel"] = button_count >= 2
    
    # 综合判断
    score = 0.0
    if result["features"]["has_red_warning"]:
        score += 0.3
    if result["features"]["has_dialog_layout"]:
        score += 0.3
    if result["features"]["has_confirm_cancel"]:
        score += 0.2
    if result["features"]["dark_overlay"]:
        score += 0.2
    
    result["confidence"] = score
    result["detected"] = score >= 0.5
    
    return result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="登出对话框检测器")
    parser.add_argument("--image", type=str, required=True, help="截图路径")
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("登出对话框检测")
    print("="*60)
    print(f"截图：{args.image}")
    
    result = detect_logout_dialog(args.image)
    
    print("\n检测结果:")
    print(f"  检测到登出对话框：{'✓' if result['detected'] else '✗'}")
    print(f"  置信度：{result['confidence']:.2f}")
    
    print("\n特征分析:")
    for feature, value in result["features"].items():
        status = "✓" if value else "✗"
        print(f"  {feature}: {status}")
    
    if result["detected"]:
        print("\n[警告] 检测到登出对话框！需要处理。")
        return 1
    else:
        print("\n[正常] 未检测到登出对话框。")
        return 0


if __name__ == "__main__":
    sys.exit(main())
