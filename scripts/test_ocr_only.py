#!/usr/bin/env python3
"""
标准流测试 - OCR_Only 模式

专门测试：
1. 登出对话框检测
2. 加载画面检测
3. 世界地图检测
4. 任务面板检测

数据源：仅使用 MaaFw 内置 OCR，不使用 VLM
"""

import sys
import os
from pathlib import Path

from _path_setup import ensure_path; ensure_path()

from core.capability.ocr.ocr_manager import OCRManager
from core.capability.adb_utils import ADB, list_devices


def test_logout_detection(device_serial: str):
    """测试登出对话框检测"""
    print("\n" + "="*60)
    print("测试：登出对话框检测")
    print("="*60)

    manager = OCRManager()
    
    print("正在截图并执行 OCR 识别...")
    state = manager.capture_and_recognize(device_serial)
    
    print(f"\nOCR 识别结果:")
    print(f"  页面类型：{state.page_type}")
    print(f"  描述：{state.description}")
    print(f"  顶部栏可见：{state.top_bar_visible}")
    print(f"  顶部栏按钮：{state.top_bar_buttons}")
    print(f"  面板覆盖层：{state.overlay_detected}")
    print(f"  面板文本：{state.overlay_texts[:5]}...")  # 只显示前 5 个
    print(f"  领取按钮：{len(state.claim_buttons)} 个")
    
    # 检查是否检测到登出
    if state.page_type == "logout_dialog":
        print("\n[OK] 成功检测到登出对话框!")
        return True
    elif "logout" in state.page_type.lower() or "登出" in state.description:
        print("\n[OK] 检测到登出相关提示!")
        return True
    else:
        print(f"\n[INFO] 当前页面：{state.page_type}")
        if state.overlay_texts:
            print(f"  面板文本示例：{state.overlay_texts[:3]}")
        return False


def test_all_page_types(device_serial: str):
    """测试所有页面类型检测"""
    print("\n" + "="*60)
    print("测试：所有页面类型检测")
    print("="*60)

    manager = OCRManager()
    
    print("正在截图并执行 OCR 识别...")
    state = manager.capture_and_recognize(device_serial)
    
    print(f"\n完整检测结果:")
    print(f"  页面类型：{state.page_type}")
    print(f"  置信度：{state.confidence:.2f}")
    print(f"  描述：{state.description}")
    print(f"  顶部栏可见：{state.top_bar_visible}")
    print(f"  顶部栏按钮：{state.top_bar_buttons}")
    print(f"  面板覆盖层：{state.overlay_detected}")
    print(f"  面板文本数量：{len(state.overlay_texts)}")
    print(f"  领取按钮：{len(state.claim_buttons)}")
    print(f"  可交互元素：{len(state.interactive_elements)}")
    
    # 输出所有 OCR 文本（用于调试）
    print(f"\nOCR 文本预览:")
    for elem in state.interactive_elements[:10]:
        print(f"  - {elem.get('text', 'N/A')} @ ({elem.get('cx', 0)}, {elem.get('cy', 0)})")
    
    return state


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="标准流测试 - OCR_Only 模式")
    parser.add_argument("--device", type=str, default=None, help="设备序列号")
    parser.add_argument("--test", type=str, choices=["logout", "all"], default="all",
                        help="测试类型")
    
    args = parser.parse_args()
    
    # 确定设备
    device_serial = args.device
    if not device_serial:
        devices = list_devices()
        if not devices:
            print("[ERROR] 未找到可用设备")
            return 1
        device_serial = devices[0]
        print(f"[设备] 自动选择：{device_serial}")
    
    print(f"\n{'='*60}")
    print(f"标准流测试 - OCR_Only 模式")
    print(f"{'='*60}")
    print(f"设备：{device_serial}")
    print(f"测试：{args.test}")
    print(f"数据源：MaaFw 内置 OCR (本地)")
    
    if args.test == "logout":
        result = test_logout_detection(device_serial)
    else:
        result = test_all_page_types(device_serial)
    
    print(f"\n{'='*60}")
    print(f"测试完成")
    print(f"{'='*60}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
