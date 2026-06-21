#!/usr/bin/env python3
"""
测试动作执行 - 验证标准流引擎能否正确执行ADB命令
"""

import sys
import os
from pathlib import Path

from _path_setup import ensure_path; ensure_path()

from scripts.standard_flow_engine import FlowConfig, Local2BEngine, FlowRecorder, StandardFlowExecutor
from core.adb_utils import ADB

def test_adb_connection():
    """测试ADB连接"""
    print("=" * 60)
    print("测试1: ADB连接")
    print("=" * 60)

    adb = ADB()
    connected = adb.check_connection()
    print(f"ADB连接状态: {'✓ 已连接' if connected else '✗ 未连接'}")

    if connected:
        print(f"设备序列: {adb.serial}")
    return connected

def test_action_mapping():
    """测试动作映射"""
    print("\n" + "=" * 60)
    print("测试2: 动作执行逻辑")
    print("=" * 60)

    config = FlowConfig()
    engine = Local2BEngine()
    engine.load()
    recorder = FlowRecorder(session_name="action_test", record_video=False)
    executor = StandardFlowExecutor(config, engine, recorder)

    # 模拟执行一个tap动作
    print("\n模拟执行tap动作:")
    test_data = {"action": "tap", "coords": [500, 1000]}
    success, error, _ = executor._execute_action("tap", test_data)
    print(f"  结果: {'成功' if success else '失败'}")
    if error:
        print(f"  错误: {error}")

    # 模拟执行back动作
    print("\n模拟执行back动作:")
    success, error, _ = executor._execute_action("back", {})
    print(f"  结果: {'成功' if success else '失败'}")
    if error:
        print(f"  错误: {error}")

    # 模拟执行claim动作
    print("\n模拟执行claim动作:")
    success, error, _ = executor._execute_action("claim", {})
    print(f"  结果: {'成功' if success else '失败'}")
    if error:
        print(f"  错误: {error}")

def test_json_parsing():
    """测试JSON解析"""
    print("\n" + "=" * 60)
    print("测试3: JSON解析")
    print("=" * 60)

    executor = StandardFlowExecutor(FlowConfig(), Local2BEngine())

    # 测试正常JSON
    test_json = '{"action": "tap", "coords": [100, 200]}'
    import json
    parsed = executor._extract_json(test_json)
    print(f"正常JSON: {parsed}")

    # 测试带think标签的JSON
    test_with_think = '''<think>分析中...</think>
    {"action": "back", "result": "success"}'''
    cleaned = re.sub(r'<think>[\s\S]*?</think>', '', test_with_think).strip()
    parsed = executor._extract_json(cleaned)
    print(f"带think标签: {parsed}")

def main():
    print("动作执行测试\n")

    # 测试ADB连接
    if not test_adb_connection():
        print("\n[ERROR] ADB未连接，请检查设备")
        return 1

    # 测试动作映射
    test_action_mapping()

    # 测试JSON解析
    import re
    test_json_parsing()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

    print("\n下一步:")
    print("1. 运行实际流程: python scripts/standard_flow_engine.py --flow daily_quest --no-record")
    print("2. 观察ADB命令是否被执行（检查设备屏幕是否响应）")
    print("3. 查看cache目录下的截图确认记录")

    return 0

if __name__ == "__main__":
    sys.exit(main())
