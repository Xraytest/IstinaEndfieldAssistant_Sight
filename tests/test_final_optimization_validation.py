"""
最终优化验证测试
验证心跳机制、VLM 响应解析、登录超时处理和武器升级任务的改进
"""
import time
import json
import sys
import os

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
CLIENT_DIR = os.path.join(PROJECT_ROOT, 'IstinaEndfieldAssistant')
SERVER_DIR = os.path.join(PROJECT_ROOT, 'IstinaPlatform')

# 添加项目目录到路径
sys.path.insert(0, CLIENT_DIR)
sys.path.insert(0, SERVER_DIR)

def print_section(title):
    """打印测试章节标题"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)

def log_test(name, status, message):
    """记录测试结果"""
    status_icon = "[PASS]" if status == "PASS" else "[FAIL]"
    print(f"  {status_icon} {name}: {message}")
    return status == "PASS"

def test_heartbeat_interval():
    """测试 1: 心跳间隔已缩短至 120 秒"""
    print_section("测试 1: 心跳间隔配置验证")
    
    from 安卓相关.core.cloud.managers.execution_manager import ExecutionManager
    
    # 检查默认心跳间隔
    # 创建一个模拟的 ExecutionManager 实例来检查默认值
    import inspect
    source = inspect.getsource(ExecutionManager.__init__)
    
    if "heartbeat_interval = 120" in source:
        log_test("心跳间隔配置", "PASS", "心跳间隔已设置为 120 秒")
        return True
    elif "heartbeat_interval = 180" in source:
        log_test("心跳间隔配置", "FAIL", "心跳间隔仍为 180 秒，未更新")
        return False
    else:
        log_test("心跳间隔配置", "FAIL", "无法找到心跳间隔配置")
        return False

def test_heartbeat_check_frequency():
    """测试 2: 心跳检查频率增强"""
    print_section("测试 2: 心跳检查频率验证")
    
    import inspect
    from 安卓相关.core.cloud.managers.execution_manager import ExecutionManager
    
    source = inspect.getsource(ExecutionManager.run_automation)
    
    # 检查是否每 3 次迭代检查一次心跳
    if "iteration_count % 3 == 0" in source and "check_heartbeat_needed" in source:
        log_test("心跳检查频率", "PASS", "每 3 次迭代检查一次心跳")
        return True
    else:
        log_test("心跳检查频率", "FAIL", "心跳检查频率未增强")
        return False

def test_vlm_coordinate_normalization():
    """测试 3: VLM 响应坐标归一化"""
    print_section("测试 3: VLM 坐标归一化验证")
    
    import inspect
    
    # 直接读取文件内容检查
    provider_adapter_path = os.path.join(SERVER_DIR, 'core', 'provider_adapter.py')
    with open(provider_adapter_path, 'r', encoding='utf-8') as f:
        source = f.read()
    
    # 检查是否包含坐标归一化逻辑
    has_normalization = "/ 1920" in source or "/ 1080" in source
    has_validation = "max(0" in source or "min(1" in source
    
    if has_normalization and has_validation:
        log_test("坐标归一化", "PASS", "包含坐标归一化和验证逻辑")
        return True
    else:
        log_test("坐标归一化", "FAIL", f"归一化={has_normalization}, 验证={has_validation}")
        return False

def test_login_timeout_detection():
    """测试 4: 登录超时检测增强"""
    print_section("测试 4: 登录超时检测验证")
    
    from 安卓相关.core.cloud.managers.exception_detector import ArknightsEndfieldExceptionDetector
    
    detector = ArknightsEndfieldExceptionDetector()
    
    # 测试多种登录超时关键词
    test_cases = [
        ("长时间无操作自动登出", True),
        ("因长时间无操作", True),
        ("连接断开", True),
        ("网络超时", True),
        ("普通游戏文本", False),
    ]
    
    all_passed = True
    for text, expected in test_cases:
        result = detector.detect_exceptions_from_screenshot(
            screenshot=None,
            ocr_text=text
        )
        is_timeout = result.get('exception_type') == 'login_timeout'
        
        if is_timeout == expected:
            log_test(f"检测'{text}'", "PASS", f"正确识别为{'登录超时' if is_timeout else '正常'}")
        else:
            log_test(f"检测'{text}'", "FAIL", f"期望={expected}, 实际={is_timeout}")
            all_passed = False
    
    return all_passed

def test_weapon_upgrade_task_structure():
    """测试 5: 武器升级任务结构简化"""
    print_section("测试 5: 武器升级任务结构验证")
    
    task_path = os.path.join(
        SERVER_DIR, 'storage', 'service_data', 'tasks', 'task_weapon_upgrade.json'
    )
    
    try:
        with open(task_path, 'r', encoding='utf-8') as f:
            task = json.load(f)
        
        phases = task.get('workflow', {}).get('phases', [])
        phase_ids = [p['id'] for p in phases]
        
        # 检查是否简化为 3 个主要阶段
        has_navigate = 'phase_navigate' in phase_ids
        has_upgrade_loop = 'phase_upgrade_loop' in phase_ids
        has_complete = 'phase_complete' in phase_ids
        has_checkpoints = 'checkpoints' in task.get('workflow', {})
        
        if has_navigate and has_upgrade_loop and has_complete and has_checkpoints:
            log_test("任务结构简化", "PASS", f"包含{len(phases)}个阶段和检查点")
            return True
        else:
            log_test("任务结构简化", "FAIL", f"navigate={has_navigate}, loop={has_upgrade_loop}, complete={has_complete}, checkpoints={has_checkpoints}")
            return False
    except Exception as e:
        log_test("任务结构简化", "FAIL", f"读取任务文件失败：{e}")
        return False

def test_coordinate_edge_cases():
    """测试 6: 坐标边界情况处理"""
    print_section("测试 6: 坐标边界情况测试")
    
    # 直接检查代码中是否包含坐标验证逻辑
    provider_adapter_path = os.path.join(SERVER_DIR, 'core', 'provider_adapter.py')
    with open(provider_adapter_path, 'r', encoding='utf-8') as f:
        source = f.read()
    
    # 检查坐标验证逻辑
    has_clip = "max(0.0, min(1.0" in source
    has_normalize = "min(1.0, coords[0] / 1920.0)" in source
    
    if has_clip and has_normalize:
        log_test("坐标边界处理", "PASS", "包含坐标裁剪和归一化逻辑")
        return True
    else:
        log_test("坐标边界处理", "FAIL", f"裁剪={has_clip}, 归一化={has_normalize}")
        return False

def run_all_tests():
    """运行所有测试"""
    print("\n" + "#" * 60)
    print("# 最终优化验证测试套件")
    print("#" * 60)
    print(f"测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    results = {}
    
    # 运行测试
    results["heartbeat_interval"] = test_heartbeat_interval()
    results["heartbeat_frequency"] = test_heartbeat_check_frequency()
    results["coordinate_normalization"] = test_vlm_coordinate_normalization()
    results["login_timeout_detection"] = test_login_timeout_detection()
    results["weapon_upgrade_structure"] = test_weapon_upgrade_task_structure()
    results["coordinate_edge_cases"] = test_coordinate_edge_cases()
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}: {test_name}")
    
    print(f"\n总计：{passed_tests}/{total_tests} 通过")
    
    if passed_tests == total_tests:
        print("\n[OK] 所有优化验证通过！")
        return True
    else:
        print(f"\n[FAIL] {total_tests - passed_tests} 个测试失败")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
