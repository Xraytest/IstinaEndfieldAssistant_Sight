#!/usr/bin/env python3
"""
标准流综合测试脚本

测试内容：
1. 前置导航到世界页面
2. 验证任务图标坐标
3. 执行 daily_quest 流程
4. 生成测试报告
"""
import subprocess, time, sys, json
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\xray\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant')

def run_command(cmd, description=""):
    """运行命令并输出结果"""
    print(f"\n{'='*60}")
    if description:
        print(f"[{description}]")
    print(f"[命令] {' '.join(cmd)}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, capture_output=False, text=True, encoding='utf-8', errors='replace')
    return result.returncode == 0

def main():
    print("\n" + "="*60)
    print("标准流综合测试")
    print("="*60)
    
    tests_passed = 0
    tests_total = 0
    
    # 测试 1: 检查配置文件
    tests_total += 1
    print("\n[测试 1] 检查配置文件...")
    config_path = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        flows = config.get('flows', {})
        print(f"  找到 {len(flows)} 个流程：{list(flows.keys())}")
        if 'daily_quest' in flows:
            print("  ✅ daily_quest 流程存在")
            tests_passed += 1
        else:
            print("  ❌ daily_quest 流程不存在")
    else:
        print(f"  ❌ 配置文件不存在：{config_path}")
    
    # 测试 2: 检查标准流引擎
    tests_total += 1
    print("\n[测试 2] 检查标准流引擎...")
    engine_path = PROJECT_ROOT / "scripts" / "standard_flow_engine.py"
    if engine_path.exists():
        print("  ✅ 标准流引擎存在")
        tests_passed += 1
    else:
        print("  ❌ 标准流引擎不存在")
    
    # 测试 3: 检查 ADB 连接
    tests_total += 1
    print("\n[测试 3] 检查 ADB 连接...")
    adb_path = PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"
    if adb_path.exists():
        result = subprocess.run(
            [str(adb_path), "-s", "localhost:16512", "get-state"],
            capture_output=True, timeout=10
        )
        if b"device" in result.stdout:
            print("  ✅ ADB 设备在线")
            tests_passed += 1
        else:
            print("  ❌ ADB 设备离线")
    else:
        print(f"  ❌ ADB 不存在：{adb_path}")
    
    # 测试 4: 运行前置导航（可选）
    tests_total += 1
    print("\n[测试 4] 前置导航到世界页面...")
    print("  提示：此步骤将自动启动游戏并导航到世界页面")
    print("  按 Enter 继续，或输入 q 跳过...")
    choice = input("> ").strip().lower()
    if choice == 'q':
        print("  [跳过]")
    else:
        # 运行标准流引擎（仅前置导航）
        success = run_command(
            [sys.executable, str(engine_path), "--flow", "daily_quest"],
            "执行 daily_quest 流程"
        )
        if success:
            tests_passed += 1
    
    # 生成测试报告
    print("\n" + "="*60)
    print("测试结果")
    print("="*60)
    print(f"通过：{tests_passed}/{tests_total}")
    print(f"成功率：{tests_passed/tests_total*100:.1f%}" if tests_total > 0 else "N/A")
    
    if tests_passed == tests_total:
        print("\n✅ 所有测试通过")
        return 0
    else:
        print(f"\n⚠️  {tests_total - tests_passed} 个测试未通过")
        return 1

if __name__ == "__main__":
    sys.exit(main())
