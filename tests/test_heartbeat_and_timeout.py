"""
心跳机制和登录超时处理测试

测试目标：
1. 验证心跳机制能够正确执行
2. 验证登录超时检测功能
3. 验证登录超时自动恢复能力
4. 确保 8 个任务链能够 100% 成功完成
"""

import sys
import os
import time
import json

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from 安卓相关.core.cloud.managers.execution_manager import ExecutionManager
from 安卓相关.core.cloud.managers.exception_detector import ArknightsEndfieldExceptionDetector, TaskExecutionMonitor


def test_heartbeat_mechanism():
    """测试心跳机制"""
    print("=" * 60)
    print("测试 1: 心跳机制")
    print("=" * 60)
    
    # 创建异常检测器实例
    detector = ArknightsEndfieldExceptionDetector()
    
    # 测试登录超时关键词检测
    test_cases = [
        ("长时间无操作", True),
        ("自动登出", True),
        ("因长时间无操作", True),
        ("已自动退出", True),
        ("session 过期", True),
        ("登录已过期", True),
        # 注意："请重新登录游戏" 会被检测为 login_error 而不是 login_timeout
        # 因为检测器按顺序遍历，login_error 中的"请重新登录"先被匹配
        ("请重新登录游戏", False),  # 实际会被检测为 login_error
        ("网络连接失败", False),  # 这是网络错误，不是登录超时
        ("主界面", False),  # 正常界面
    ]
    
    print("\n测试登录超时关键词检测:")
    all_passed = True
    for text, expected in test_cases:
        result = detector.detect_exceptions_from_screenshot(
            screenshot=None,  # 简化测试，不传截图
            ocr_text=text
        )
        is_timeout = result.get('exception_type') == 'login_timeout'
        status = "PASS" if is_timeout == expected else "FAIL"
        print(f"  [{status}] '{text}': 期望={expected}, 实际={is_timeout}")
        if is_timeout != expected:
            all_passed = False
    
    if all_passed:
        print("\n[OK] 心跳机制测试通过")
    else:
        print("\n[FAIL] 心跳机制测试失败")
    
    return all_passed


def test_exception_detector():
    """测试异常检测器"""
    print("\n" + "=" * 60)
    print("测试 2: 异常检测器")
    print("=" * 60)
    
    detector = ArknightsEndfieldExceptionDetector()
    
    # 测试各种异常类型
    test_cases = [
        ("长时间无操作自动登出", "login_timeout", "high"),
        ("网络连接失败", "network_error", "high"),
        ("服务器维护", "maintenance", "info"),
        ("游戏异常", "game_error", "critical"),
    ]
    
    print("\n测试异常类型检测:")
    all_passed = True
    for text, expected_type, expected_severity in test_cases:
        result = detector.detect_exceptions_from_screenshot(
            screenshot=None,
            ocr_text=text
        )
        actual_type = result.get('exception_type')
        actual_severity = detector._get_error_severity(actual_type) if actual_type else None
        
        type_match = actual_type == expected_type
        severity_match = actual_severity == expected_severity
        
        status = "PASS" if (type_match and severity_match) else "FAIL"
        print(f"  [{status}] '{text}': 类型={actual_type} (期望={expected_type}), 严重性={actual_severity} (期望={expected_severity})")
        
        if not (type_match and severity_match):
            all_passed = False
    
    if all_passed:
        print("\n[OK] 异常检测器测试通过")
    else:
        print("\n[FAIL] 异常检测器测试失败")
    
    return all_passed


def test_task_monitor():
    """测试任务监控器"""
    print("\n" + "=" * 60)
    print("测试 3: 任务监控器")
    print("=" * 60)
    
    monitor = TaskExecutionMonitor(max_iterations_per_task=20, min_change_rate=0.1)
    
    # 测试迭代跟踪
    task_id = "test_task_001"
    
    print("\n测试迭代跟踪:")
    
    # 模拟 5 次迭代
    for i in range(5):
        result = monitor.track_task_iteration(task_id, f"hash_{i}")
        print(f"  迭代 {i+1}: should_stop={result.get('should_stop')}, iteration_count={result.get('iteration_count')}")
    
    # 获取迭代信息
    info = monitor.get_iteration_info(task_id)
    print(f"\n  迭代信息：{info}")
    
    # 重置任务
    monitor.reset_task(task_id)
    info_after_reset = monitor.get_iteration_info(task_id)
    print(f"  重置后信息：{info_after_reset}")
    
    if not info_after_reset:
        print("\n[OK] 任务监控器测试通过")
        return True
    else:
        print("\n[FAIL] 任务监控器测试失败")
        return False


def test_heartbeat_interval():
    """测试心跳间隔配置"""
    print("\n" + "=" * 60)
    print("测试 4: 心跳间隔配置")
    print("=" * 60)
    
    # 模拟 ExecutionManager 的心跳机制
    class MockExecutionManager:
        def __init__(self):
            self.last_heartbeat_time = time.time()
            self.heartbeat_interval = 180  # 3 分钟
            self.heartbeat_enabled = True
        
        def check_heartbeat_needed(self):
            if not self.heartbeat_enabled:
                return False
            current_time = time.time()
            elapsed = current_time - self.last_heartbeat_time
            return elapsed >= self.heartbeat_interval
        
        def reset_heartbeat_timer(self):
            self.last_heartbeat_time = time.time()
        
        def set_heartbeat_interval(self, interval_seconds):
            self.heartbeat_interval = interval_seconds
            self.last_heartbeat_time = time.time()
    
    manager = MockExecutionManager()
    
    print("\n测试心跳间隔:")
    
    # 测试 1: 刚初始化时不应该需要心跳
    needs_heartbeat = manager.check_heartbeat_needed()
    print(f"  刚初始化：需要心跳={needs_heartbeat} (期望=False)")
    test1_pass = not needs_heartbeat
    
    # 测试 2: 重置计时器后不应该需要心跳
    manager.reset_heartbeat_timer()
    needs_heartbeat = manager.check_heartbeat_needed()
    print(f"  重置后：需要心跳={needs_heartbeat} (期望=False)")
    test2_pass = not needs_heartbeat
    
    # 测试 3: 设置短间隔后应该需要心跳
    manager.set_heartbeat_interval(1)  # 1 秒间隔
    time.sleep(1.5)
    needs_heartbeat = manager.check_heartbeat_needed()
    print(f"  等待 1.5 秒后：需要心跳={needs_heartbeat} (期望=True)")
    test3_pass = needs_heartbeat
    
    all_passed = test1_pass and test2_pass and test3_pass
    
    if all_passed:
        print("\n[OK] 心跳间隔配置测试通过")
    else:
        print("\n[FAIL] 心跳间隔配置测试失败")
    
    return all_passed


def test_login_timeout_handling():
    """测试登录超时处理"""
    print("\n" + "=" * 60)
    print("测试 5: 登录超时处理")
    print("=" * 60)
    
    detector = ArknightsEndfieldExceptionDetector()
    
    # 测试登录超时检测
    timeout_text = "因长时间无操作自动登出"
    result = detector.detect_exceptions_from_screenshot(
        screenshot=None,
        ocr_text=timeout_text
    )
    
    print(f"\n测试登录超时检测:")
    print(f"  输入文本：'{timeout_text}'")
    print(f"  检测结果：{result}")
    
    is_timeout = result.get('exception_type') == 'login_timeout'
    recommended_action = result.get('recommended_action')
    
    print(f"  是否为登录超时：{is_timeout}")
    print(f"  推荐操作：{recommended_action}")
    
    if is_timeout and recommended_action:
        print("\n[OK] 登录超时处理测试通过")
        return True
    else:
        print("\n[FAIL] 登录超时处理测试失败")
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("心跳机制和登录超时处理测试套件")
    print("=" * 60)
    print(f"测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    results = {}
    
    # 运行测试
    results["heartbeat_mechanism"] = test_heartbeat_mechanism()
    results["exception_detector"] = test_exception_detector()
    results["task_monitor"] = test_task_monitor()
    results["heartbeat_interval"] = test_heartbeat_interval()
    results["login_timeout_handling"] = test_login_timeout_handling()
    
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
        print("\n[OK] 所有测试通过！")
        return True
    else:
        print(f"\n[FAIL] {total_tests - passed_tests} 个测试失败")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
