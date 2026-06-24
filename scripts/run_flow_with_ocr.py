#!/usr/bin/env python3
"""
标准流执行器 - 集成 OCR + 状态机版本

在真实设备上执行标准流，支持：
1. PaddleOCR 本地识别
2. 状态机扩展（loop/check/find_and_click）
3. 视觉分析
"""

import sys
import os
import argparse
from pathlib import Path

from _path_setup import PROJECT_ROOT as _PROJECT_ROOT, SRC_DIR as _SRC_DIR, ensure_path
ensure_path()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

from standard_flow_engine import FlowConfig, StandardFlowExecutor, FlowRecorder, Local2BEngine
from core.capability.adb_utils import ADB, list_devices


def main():
    parser = argparse.ArgumentParser(description="标准流执行器 - 集成 OCR + 状态机")
    parser.add_argument("--flow", type=str, default="daily_quest", help="要执行的流程")
    parser.add_argument("--device", type=str, default=None, help="设备序列号")
    parser.add_argument("--use-ocr", action="store_true", help="启用 OCR 管理器（PaddleOCR）")
    parser.add_argument("--use-state-machine", action="store_true", help="启用状态机扩展")
    parser.add_argument("--list-devices", action="store_true", help="列出可用设备")
    
    args = parser.parse_args()
    
    # 列出设备
    if args.list_devices:
        devices = list_devices()
        print("可用设备:")
        for d in devices:
            print(f"  - {d}")
        return 0
    
    # 确定设备
    device_serial = args.device
    if not device_serial:
        devices = list_devices()
        if not devices:
            print("[ERROR] 未找到可用设备")
            return 1
        device_serial = devices[0]
        print(f"[设备] 自动选择：{device_serial}")
    else:
        print(f"[设备] 使用指定：{device_serial}")
    
    # 检查设备连接
    adb = ADB(serial=device_serial)
    if not adb.check_connection():
        print(f"[ERROR] 设备 {device_serial} 未连接")
        return 1
    print(f"[OK] 设备已连接")
    
    # 加载配置
    config = FlowConfig()
    flow_name = args.flow
    
    flow = config.get_flow(flow_name)
    if not flow:
        print(f"[ERROR] 未找到流程：{flow_name}")
        return 1
    
    print(f"\n{'='*60}")
    print(f"标准流执行器 - 集成 OCR + 状态机")
    print(f"{'='*60}")
    print(f"流程：{flow_name}")
    print(f"设备：{device_serial}")
    print(f"OCR: {'启用' if args.use_ocr else '禁用'}")
    print(f"状态机：{'启用' if args.use_state_machine else '禁用'}")
    print(f"{'='*60}\n")
    
    # 初始化模型引擎
    engine = Local2BEngine()
    if not engine.load():
        print("[WARN] 模型加载失败，使用 API 模式")
    
    # 初始化记录器
    recorder = FlowRecorder(
        session_name=f"{flow_name}_ocr_sm",
        record_video=True,
        device_serial=device_serial
    )
    
    # 创建执行器
    try:
        executor = StandardFlowExecutor(
            config=config,
            model_engine=engine,
            recorder=recorder,
            device_serial=device_serial,
            use_ocr=args.use_ocr,
            use_state_machine=args.use_state_machine
        )
        
        print(f"[OK] 执行器初始化成功")
        print(f"  OCR 管理器：{executor.ocr_manager.ocr_mode if executor.ocr_manager else '未启用'}")
        print(f"  状态机：{'已启用' if executor.state_machine else '未启用'}")
        
    except Exception as e:
        print(f"[ERROR] 执行器初始化失败：{e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # 执行流程
    print(f"\n开始执行流程...")
    success = executor.execute_flow(flow_name)
    
    # 导出报告
    if recorder:
        report = recorder.export_report()
        report_path = os.path.join(recorder.session_dir, "execution_report.json")
        import json
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n执行报告已保存：{report_path}")
    
    print(f"\n流程完成：{'成功' if success else '有失败步骤'}")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
