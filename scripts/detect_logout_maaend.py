#!/usr/bin/env python3
"""
登出对话框检测器 - MaaEnd 式设计

参考 MaaEnd 的做法：
1. 在特定 ROI 区域使用 OCR 检测关键词
2. 支持多语言关键词
3. 自动处理登出对话框
"""

import sys
import os
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()


# MaaEnd 式的登出对话框关键词（多语言）
LOGOUT_KEYWORDS = [
    # 简体中文
    "登出", "退出", "登录界面", "超时", "重新登录", "会话过期", "自动登出",
    "长时间", "没有操作", "断开连接", "确认", "取消",
    # 繁体中文
    "登出", "退出", "登入介面", "超時", "重新登入", "會話過期",
    # 英文
    "logout", "log out", "login screen", "timeout", "session expired",
    "re-login", "disconnect", "confirm", "cancel",
    # 日文
    "画面に戻りますか", "ログアウト", "ログイン", "タイムアウト",
    # 韩文
    "나가시겠습니까", "로그아웃", "로그인", "시간초과"
]


def detect_logout_dialog_ocr(ocr_results: list) -> bool:
    """
    使用 OCR 结果检测登出对话框（MaaEnd 式）
    
    Args:
        ocr_results: OCR 识别结果列表，每项包含"text"字段
        
    Returns:
        bool: 是否检测到登出对话框
    """
    # 合并所有 OCR 文本
    all_text = " ".join([elem.get("text", "") for elem in ocr_results])
    
    # 检查关键词
    for keyword in LOGOUT_KEYWORDS:
        if keyword.lower() in all_text.lower():
            return True
    
    return False


def detect_logout_dialog_roi(ocr_results: list, roi: tuple = None) -> bool:
    """
    在特定 ROI 区域检测登出对话框（MaaEnd 式）
    
    Args:
        ocr_results: OCR 识别结果列表，每项包含"text"和"box"字段
        roi: ROI 区域 (x, y, w, h)，默认为 MaaEnd 使用的区域
        
    Returns:
        bool: 是否检测到登出对话框
    """
    # MaaEnd 使用的 ROI 区域（1280x720 分辨率）
    if roi is None:
        roi = (400, 250, 470, 200)  # x, y, w, h
    
    rx, ry, rw, rh = roi
    
    # 筛选 ROI 区域内的 OCR 结果
    roi_texts = []
    for elem in ocr_results:
        text = elem.get("text", "")
        box = elem.get("box", [])
        
        if len(box) >= 4:
            # box 格式：[x1, y1, x2, y2] 或 [x1, y1, w, h]
            if box[2] > 1000:  # 如果是宽格式
                ex, ey, ew, eh = box
            else:  # 如果是坐标格式
                ex, ey, ew, eh = box[0], box[1], box[2] - box[0], box[3] - box[1]
            
            # 检查是否在 ROI 内
            if (rx <= ex < rx + rw and ry <= ey < ry + rh):
                roi_texts.append(text)
    
    # 合并 ROI 文本
    roi_text = " ".join(roi_texts)
    
    # 检查关键词
    for keyword in LOGOUT_KEYWORDS:
        if keyword.lower() in roi_text.lower():
            return True
    
    return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="登出对话框检测器 - MaaEnd 式")
    parser.add_argument("--test", action="store_true", help="运行测试")
    args = parser.parse_args()
    
    if args.test:
        # 测试数据
        test_ocr_results = [
            {"text": "检测到会话超时", "box": [400, 250, 500, 300]},
            {"text": "请重新登录", "box": [410, 280, 510, 320]},
            {"text": "确认", "box": [450, 350, 500, 400]},
            {"text": "取消", "box": [520, 350, 570, 400]},
        ]
        
        result1 = detect_logout_dialog_ocr(test_ocr_results)
        print(f"全图 OCR 检测：{'✓ 检测到登出对话框' if result1 else '✗ 未检测到'}")
        
        result2 = detect_logout_dialog_roi(test_ocr_results)
        print(f"ROI 区域检测：{'✓ 检测到登出对话框' if result2 else '✗ 未检测到'}")
        
        print(f"\n关键词列表 ({len(LOGOUT_KEYWORDS)} 个):")
        for kw in LOGOUT_KEYWORDS[:10]:
            print(f"  - {kw}")
        if len(LOGOUT_KEYWORDS) > 10:
            print(f"  ... 以及 {len(LOGOUT_KEYWORDS) - 10} 个更多")
    else:
        print("登出对话框检测器 - MaaEnd 式设计")
        print(f"支持 {len(LOGOUT_KEYWORDS)} 个关键词（多语言）")
        print("\n使用方法:")
        print("  python scripts/detect_logout_maaend.py --test")


if __name__ == "__main__":
    main()
