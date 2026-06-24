#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IEA 本地版综合测试脚本

测试所有核心模块和 CLI 命令，确保本地版本正常工作。
"""

import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime

# 设置项目路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        
    def add_pass(self, name):
        self.passed += 1
        print(f"  ✅ {name}")
        
    def add_fail(self, name, reason):
        self.failed += 1
        self.errors.append((name, reason))
        print(f"  ❌ {name}: {reason}")
        
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"测试结果：{self.passed}/{total} 通过")
        if self.failed > 0:
            print(f"失败项:")
            for name, reason in self.errors:
                print(f"  - {name}: {reason}")
        return self.failed == 0

result = TestResult()

print("="*50)
print("IEA 本地版综合测试")
print(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"项目路径：{PROJECT_ROOT}")
print("="*50)

# ========== 测试 1: 依赖检查 ==========
print("\n[测试 1] 依赖检查")

# 1.1 检查无云端依赖
print("  检查云端依赖...")
try:
    # 尝试导入已删除的模块，应该失败
    try:
        from core.communication.communicator import ClientCommunicator
        result.add_fail("云端依赖检查", "ClientCommunicator 仍存在")
    except ImportError:
        result.add_pass("云端依赖已移除")
except Exception as e:
    result.add_fail("云端依赖检查", str(e))

# 1.2 检查本地模块存在
print("  检查本地模块...")
local_modules = [
    ("core.element_analysis.element_analyzer", "ElementAnalyzer"),
    ("core.cloud.agent_executor", "AgentExecutor"),
    ("core.cloud.managers.local_log_manager", "LocalLogManager"),
    ("core.cloud.managers.exception_detector", "ArknightsEndfieldExceptionDetector"),
]

for module_name, class_name in local_modules:
    try:
        module = __import__(module_name, fromlist=[class_name])
        getattr(module, class_name)
        result.add_pass(f"{class_name} 模块")
    except Exception as e:
        result.add_fail(f"{class_name} 模块", str(e))

# 1.3 检查核心模块
print("  检查核心模块...")
core_modules = [
    "core.adb_utils",
    "core.game_coords",
    "core.logger",
    "core.local_inference.inference_manager",
]

for module_name in core_modules:
    try:
        __import__(module_name)
        result.add_pass(f"{module_name}")
    except Exception as e:
        result.add_fail(f"{module_name}", str(e))

# ========== 测试 2: 配置测试 ==========
print("\n[测试 2] 配置测试")

# 2.1 检查配置文件存在
config_path = PROJECT_ROOT / "config" / "client_config.json"
if config_path.exists():
    result.add_pass("配置文件存在")
    try:
        with open(config_path) as f:
            config = json.load(f)
        result.add_pass("配置文件格式正确")
        
        # 2.2 检查配置内容
        if config.get("inference", {}).get("mode") == "local":
            result.add_pass("推理模式配置正确")
        else:
            result.add_fail("推理模式配置", "应为 local")
            
    except Exception as e:
        result.add_fail("配置文件解析", str(e))
else:
    result.add_fail("配置文件", "不存在")

# ========== 测试 3: 核心模块功能测试 ==========
print("\n[测试 3] 核心模块功能测试")

# 3.1 LocalLogManager 测试
print("  测试 LocalLogManager...")
try:
    from core.cloud.managers.local_log_manager import LocalLogManager
    
    log_dir = PROJECT_ROOT / "logs" / "test"
    lm = LocalLogManager(str(log_dir), session_id="test_session")
    
    # 测试日志记录
    lm.info("TEST", "测试信息", {"key": "value"})
    lm.warning("TEST", "测试警告")
    lm.error("TEST", "测试错误")
    
    # 测试日志读取
    logs = lm.get_logs()
    if len(logs) >= 3:
        result.add_pass("LocalLogManager 功能")
    else:
        result.add_fail("LocalLogManager 功能", "日志记录不完整")
        
except Exception as e:
    result.add_fail("LocalLogManager", str(e))

# 3.2 ADB 工具测试
print("  测试 ADB 工具...")
try:
    from core.adb_utils import ADB, check_device, list_devices
    
    adb = ADB()
    
    # 检查设备连接（可能失败，因为模拟器可能未启动）
    if check_device():
        result.add_pass("ADB 设备连接")
    else:
        print("  ⚠️  ADB 设备未连接（模拟器可能未启动）")
        result.add_pass("ADB 工具加载（设备未连接）")
        
except Exception as e:
    result.add_fail("ADB 工具", str(e))

# 3.3 VLM 分析接口测试（不实际调用推理）
print("  测试 vlm_analyze 接口...")
try:
    from core.vlm_utils import vlm_analyze, VLMOptions

    # 测试无 vlm_client 时返回 None
    opts = VLMOptions()
    resp = vlm_analyze(b"fake_image", "test", opts=opts, vlm_client=None)

    if resp is None:
        result.add_pass("vlm_analyze 接口（无 client 返回 None）")
    else:
        result.add_fail("vlm_analyze 接口", "应返回 None")

except Exception as e:
    result.add_fail("vlm_analyze 接口", str(e))

# ========== 测试 4: CLI 命令测试 ==========
print("\n[测试 4] CLI 命令测试")

cli_tests = [
    ("system doctor", ["system", "doctor"]),
    ("system env", ["system", "env"]),
    ("system disk", ["system", "disk"]),
]

for test_name, args in cli_tests:
    try:
        cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "istina.py")] + args
        result_proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=PROJECT_ROOT)
        
        if result_proc.returncode == 0:
            result.add_pass(f"CLI: {test_name}")
        else:
            error_msg = result_proc.stderr[:100] if result_proc.stderr else "未知错误"
            result.add_fail(f"CLI: {test_name}", error_msg)
            
    except subprocess.TimeoutExpired:
        result.add_fail(f"CLI: {test_name}", "超时")
    except Exception as e:
        result.add_fail(f"CLI: {test_name}", str(e))

# ========== 测试 5: 文件结构检查 ==========
print("\n[测试 5] 文件结构检查")

required_files = [
    "src/core/adb_utils.py",
    "src/core/vlm_utils.py",
    "src/core/state_detector.py",
    "src/core/state_recovery.py",
    "src/core/element_analysis/element_analyzer.py",
    "src/core/cloud/agent_executor.py",
    "src/core/cloud/managers/local_log_manager.py",
    "src/cli/system_cli.py",
    "src/cli/scenario_cli.py",
    "scripts/istina.py",
    "config/client_config.json",
    "start.bat",
    "README.md",
]

for file_path in required_files:
    if (PROJECT_ROOT / file_path).exists():
        result.add_pass(f"文件：{file_path}")
    else:
        result.add_fail(f"文件：{file_path}", "不存在")

# 检查已删除的文件
deleted_files = [
    "src/core/communication",
    "src/gui/pyqt6/pages/auth_page.py",
    "src/gui/pyqt6/pages/cloud_page.py",
]

for file_path in deleted_files:
    if not (PROJECT_ROOT / file_path).exists():
        result.add_pass(f"已删除：{file_path}")
    else:
        result.add_fail(f"已删除：{file_path}", "仍存在")

# ========== 测试总结 ==========
success = result.summary()

print(f"\n{'='*50}")
if success:
    print("✅ 所有测试通过！")
else:
    print("❌ 部分测试失败，请检查上述错误")
print(f"{'='*50}")

sys.exit(0 if success else 1)
