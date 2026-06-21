#!/usr/bin/env python3
"""
测试新标准流引擎 - 验证配置加载和执行
"""

import sys
import os

# 设置路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
from _path_setup import ensure_path; ensure_path()

# 直接导入
from scripts.standard_flow_engine import FlowConfig, Local2BEngine, FlowRecorder

def test_config():
    """测试配置加载"""
    print("=" * 60)
    print("测试1: 配置加载")
    print("=" * 60)

    config = FlowConfig()
    print(f"配置文件: {config.config_path}")

    # 列出所有流程
    flows = config.all_flows
    print(f"\n可用流程 ({len(flows)}):")
    for flow in flows:
        enabled = config.is_flow_enabled(flow)
        print(f"  - {flow}: {'启用' if enabled else '禁用'}")

    # 测试变量替换
    print("\n测试变量替换:")
    test_prompt = "点击签到按钮: {{coords.signin_entry}}"
    result = config.substitute_variables(test_prompt)
    print(f"  输入: {test_prompt}")
    print(f"  输出: {result}")

    # 获取特定流程
    daily = config.get_flow("daily_quest")
    if daily:
        print(f"\ndaily_quest 流程:")
        print(f"  描述: {daily.get('description')}")
        print(f"  步骤数: {len(daily.get('steps', []))}")
        for i, step in enumerate(daily.get('steps', [])):
            print(f"  {i+1}. {step['id']}: {step['description'][:50]}...")

    return config

def test_model():
    """测试2B模型加载"""
    print("\n" + "=" * 60)
    print("测试2: 本地2B模型")
    print("=" * 60)

    engine = Local2BEngine()
    ok = engine.load()
    print(f"加载结果: {'成功' if ok else '失败'}")
    if ok:
        print(f"运行模式: {'本地' if engine.is_local() else 'API'}")

    return engine

def test_recorder():
    """测试记录器"""
    print("\n" + "=" * 60)
    print("测试3: 流程记录器")
    print("=" * 60)

    recorder = FlowRecorder(session_name="test_session", record_video=True)
    print(f"会话目录: {recorder.session_dir}")

    # 模拟记录步骤
    recorder.record_step(
        step_id=1,
        step_key="test_step",
        action="test_action",
        description="测试描述",
        prompt="测试提示词",
        decision='{"action": "none"}',
        success=True
    )

    print(f"已记录步骤: {len(recorder.steps)}")

    # 导出报告
    report = recorder.export_report()
    print(f"报告步骤数: {report['total_steps']}")
    print(f"成功: {report['success_count']}, 失败: {report['fail_count']}")

    return recorder

def main():
    print("标准流引擎测试套件\n")

    try:
        config = test_config()
        engine = test_model()
        recorder = test_recorder()

        print("\n" + "=" * 60)
        print("所有测试完成")
        print("=" * 60)

        print("\n下一步:")
        print("1. 运行完整流程: python scripts/standard_flow_engine.py --flow daily_quest --local-only")
        print("2. 运行所有流程: python scripts/standard_flow_engine.py --flow all")
        print("3. 仅分析已有记录: python scripts/standard_flow_engine.py --flow daily_quest --analyze-only")
        print("4. 启用自动优化: python scripts/standard_flow_engine.py --flow daily_quest --optimize-prompts")

        return 0
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
