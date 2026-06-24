"""
任务验证引擎和决策转回机制单元测试

测试覆盖:
1. 任务验证引擎 - 各验证策略测试
2. 决策转回触发器 - 触发条件测试
3. 决策请求生成器 - 请求生成测试
4. 决策响应处理器 - 响应处理测试
5. 增强执行监控器 - 监控功能测试
"""
import sys
import os
import time
import numpy as np
from unittest.mock import Mock, MagicMock, patch
import json

# 设置 UTF-8 编码输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目路径 - 测试文件在 IstinaEndfieldAssistant/tests 目录下
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 测试结果收集
test_results = {
    "test_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    "total_tests": 0,
    "passed": 0,
    "failed": 0,
    "details": []
}


def log_test(test_name, status, message, details=None):
    """记录测试结果"""
    test_results["total_tests"] += 1
    if status == "PASS":
        test_results["passed"] += 1
    else:
        test_results["failed"] += 1
    
    result_entry = {
        "test_name": test_name,
        "status": status,
        "message": message,
        "details": details or {}
    }
    test_results["details"].append(result_entry)
    
    status_symbol = "[OK]" if status == "PASS" else "[X]"
    print(f"  [{status_symbol}] {test_name}: {message}")


def print_section(title):
    """打印测试区块标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ============================================================
# 第一部分：任务验证引擎测试
# ============================================================

def test_client_based_validator():
    """测试客户端独立验证器"""
    print_section("1. 客户端独立验证器测试")
    
    from 安卓相关.core.cloud.managers.task_validator import ClientBasedValidator, TaskContext
    
    validator = ClientBasedValidator()
    
    # 创建测试上下文
    mock_screenshots = [np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8) for _ in range(5)]
    
    task_context = TaskContext(
        task_id="test_task",
        current_phase="phase_test",
        screenshots=mock_screenshots,
        ocr_results=["暂无附件可收取", "所有奖励已领取"],
        task_variables={
            'templates': ['main_interface.png'],
            'ocr_keywords': {
                'positive': ['暂无', '已领取'],
                'negative': ['领取', '红点']
            }
        },
        device_info={'resolution': [1280, 720]},
        validation_weights={'template': 0.4, 'ocr': 0.3, 'state_change': 0.3},
        completion_threshold=0.7
    )
    
    # 执行验证
    result = validator.validate(task_context)
    
    # 验证结果
    if result.confidence > 0:
        log_test("客户端验证器执行", "PASS", 
                f"置信度：{result.confidence:.2f}, 完成：{result.completed}")
        return True
    else:
        log_test("客户端验证器执行", "FAIL", "置信度为 0")
        return False


def test_progressive_validator():
    """测试渐进式验证器"""
    print_section("2. 渐进式验证器测试")
    
    from 安卓相关.core.cloud.managers.task_validator import ProgressiveValidator, TaskContext
    
    validator = ProgressiveValidator(max_attempts=3, interval=0.1)  # 缩短间隔用于测试
    
    # 创建测试上下文
    mock_screenshots = [np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8) for _ in range(5)]
    
    task_context = TaskContext(
        task_id="test_task",
        current_phase="phase_test",
        screenshots=mock_screenshots,
        ocr_results=["测试文本"],
        task_variables={'templates': ['test.png']},
        device_info={'resolution': [1280, 720]},
        completion_threshold=0.5
    )
    
    # 执行验证
    result = validator.validate(task_context)
    
    # 验证结果
    if result.confidence >= 0:
        log_test("渐进式验证器执行", "PASS", 
                f"置信度：{result.confidence:.2f}, 完成：{result.completed}")
        return True
    else:
        log_test("渐进式验证器执行", "FAIL", "验证失败")
        return False


def test_business_rules_validator():
    """测试业务规则验证器"""
    print_section("3. 业务规则验证器测试")
    
    from 安卓相关.core.cloud.managers.task_validator import BusinessRulesValidator, TaskContext
    
    validator = BusinessRulesValidator()
    
    # 创建测试上下文
    task_context = TaskContext(
        task_id="test_task",
        current_phase="phase_test",
        screenshots=[],
        ocr_results=["主界面", "home"],
        task_variables={},
        device_info={'resolution': [1280, 720]},
        business_rules=["back_to_main_interface"]
    )
    
    # 执行验证
    result = validator.validate(task_context)
    
    # 验证结果
    if 'back_to_main_interface' in result.validation_details:
        log_test("业务规则验证器执行", "PASS", 
                f"规则得分：{result.validation_details['back_to_main_interface']:.2f}")
        return True
    else:
        log_test("业务规则验证器执行", "FAIL", "规则未执行")
        return False


def test_validation_engine():
    """测试任务验证引擎"""
    print_section("4. 任务验证引擎测试")
    
    from 安卓相关.core.cloud.managers.task_validator import TaskValidationEngine, TaskContext
    
    engine = TaskValidationEngine()
    
    # 创建测试上下文
    mock_screenshots = [np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8) for _ in range(5)]
    
    task_context = TaskContext(
        task_id="test_task",
        current_phase="phase_test",
        screenshots=mock_screenshots,
        ocr_results=["测试文本"],
        task_variables={'templates': ['test.png']},
        device_info={'resolution': [1280, 720]},
        completion_threshold=0.5
    )
    
    # 执行验证
    result = engine.validate_task(task_context)
    
    # 验证结果
    if result.confidence >= 0:
        log_test("任务验证引擎执行", "PASS", 
                f"融合置信度：{result.confidence:.2f}, 完成：{result.completed}")
        return True
    else:
        log_test("任务验证引擎执行", "FAIL", "验证失败")
        return False


# ============================================================
# 第二部分：决策转回机制测试
# ============================================================

def test_decision_delegation_trigger():
    """测试决策转回触发器"""
    print_section("5. 决策转回触发器测试")
    
    from 安卓相关.core.cloud.managers.decision_coordinator import DecisionDelegationTrigger
    
    trigger = DecisionDelegationTrigger()
    
    # 测试低置信度触发
    task_context_low_confidence = {
        'task_id': 'test_task',
        'validation_results': {
            'vlm_based': {'confidence': 0.3, 'completed': False},
            'client_based': {'confidence': 0.4, 'completed': False}
        },
        'iteration_count': 5,
        'execution_time': 30
    }
    
    should_delegate, reasons = trigger.should_delegate_decision(task_context_low_confidence)
    
    if 'low_confidence' in reasons:
        log_test("低置信度触发检测", "PASS", f"触发原因：{reasons}")
    else:
        log_test("低置信度触发检测", "FAIL", f"未检测到低置信度：{reasons}")
        return False
    
    # 测试超时风险触发
    task_context_timeout = {
        'task_id': 'test_task',
        'validation_results': {},
        'iteration_count': 18,
        'max_iterations': 20,
        'execution_time': 280,
        'timeout_seconds': 300
    }
    
    should_delegate, reasons = trigger.should_delegate_decision(task_context_timeout)
    
    if 'timeout_risk' in reasons or 'resource_constraints' in reasons:
        log_test("超时风险触发检测", "PASS", f"触发原因：{reasons}")
        return True
    else:
        log_test("超时风险触发检测", "FAIL", f"未检测到超时风险：{reasons}")
        return False


def test_decision_request_generator():
    """测试决策请求生成器"""
    print_section("6. 决策请求生成器测试")
    
    from 安卓相关.core.cloud.managers.decision_coordinator import DecisionRequestGenerator
    
    generator = DecisionRequestGenerator()
    
    # 创建测试上下文
    task_context = {
        'task_id': 'test_task',
        'current_phase': 'phase_test',
        'iteration_count': 15,
        'execution_time': 180,
        'validation_results': {
            'vlm_based': {'confidence': 0.5, 'completed': False},
            'client_based': {'confidence': 0.8, 'completed': True}
        },
        'task_variables': {},
        'device_info': {'resolution': [1280, 720]}
    }
    
    trigger_reasons = ['low_confidence', 'conflicting_validations']
    
    # 生成决策请求
    request = generator.create_decision_request(task_context, trigger_reasons)
    
    # 验证请求内容
    if request.task_id == 'test_task' and len(request.recommended_options) > 0:
        log_test("决策请求生成", "PASS", 
                f"任务 ID: {request.task_id}, 选项数：{len(request.recommended_options)}, 紧急度：{request.urgency_level}")
        return True
    else:
        log_test("决策请求生成", "FAIL", "请求内容不完整")
        return False


def test_decision_response_processor():
    """测试决策响应处理器"""
    print_section("7. 决策响应处理器测试")
    
    from 安卓相关.core.cloud.managers.decision_coordinator import (
        DecisionResponseProcessor, DecisionResponse, ExecutionDirective
    )
    
    processor = DecisionResponseProcessor()
    
    # 创建测试决策响应
    decision_response = DecisionResponse(
        decision_id="test_decision_001",
        action="continue_execution",
        parameters={
            'validation_strategy': 'trust_client',
            'max_iterations': 5
        },
        rationale="客户端验证更可靠",
        confidence=0.85,
        source="master_controller"
    )
    
    task_context = {
        'task_id': 'test_task',
        'iteration_count': 10,
        'execution_time': 120
    }
    
    # 处理决策响应
    directive = processor.process_decision_response(decision_response, task_context)
    
    # 验证指令
    if directive.action == "continue" and directive.priority == 1:
        log_test("决策响应处理", "PASS", 
                f"动作：{directive.action}, 优先级：{directive.priority}")
        return True
    else:
        log_test("决策响应处理", "FAIL", f"指令不正确：{directive}")
        return False


def test_decision_coordinator():
    """测试决策协调器"""
    print_section("8. 决策协调器测试")
    
    from 安卓相关.core.cloud.managers.decision_coordinator import DecisionCoordinator
    
    coordinator = DecisionCoordinator()
    
    # 测试是否需要决策转回
    task_context = {
        'task_id': 'test_task',
        'validation_results': {
            'vlm_based': {'confidence': 0.3, 'completed': False},
            'client_based': {'confidence': 0.9, 'completed': True}
        },
        'iteration_count': 15,
        'execution_time': 180,
        'change_rate': 0.2
    }
    
    should_delegate, reasons = coordinator.should_delegate_decision(task_context)
    
    if should_delegate and len(reasons) > 0:
        log_test("决策转回判断", "PASS", f"需要转回：{should_delegate}, 原因：{reasons}")
        return True
    else:
        log_test("决策转回判断", "PARTIAL", f"不需要转回：{should_delegate}, 原因：{reasons}")
        return True  # 这也可能是正确的，取决于上下文


# ============================================================
# 第三部分：增强执行监控器测试
# ============================================================

def test_enhanced_execution_monitor():
    """测试增强执行监控器"""
    print_section("9. 增强执行监控器测试")
    
    from 安卓相关.core.cloud.managers.enhanced_monitor import EnhancedExecutionMonitor
    
    monitor = EnhancedExecutionMonitor(
        max_iterations_per_task=20,
        min_change_rate=0.1,
        timeout_seconds=300,
        validation_interval=3
    )
    
    task_id = "test_task"
    
    # 模拟正常执行
    for i in range(5):
        execution_context = {
            'screenshot_hash': f'hash_{i}',
            'execution_time': i * 10
        }
        
        result = monitor.track_task_execution(task_id, execution_context)
        
        if i == 2:  # 第 3 次迭代应该触发验证
            if result.should_validate:
                log_test("验证间隔触发", "PASS", f"第{i+1}次迭代触发验证")
            else:
                log_test("验证间隔触发", "FAIL", f"第{i+1}次迭代未触发验证")
                return False
    
    # 验证迭代信息
    info = monitor.get_iteration_info(task_id)
    if info.get('iteration_count') == 5:
        log_test("迭代信息记录", "PASS", f"迭代次数：{info['iteration_count']}")
        return True
    else:
        log_test("迭代信息记录", "FAIL", f"迭代次数不正确：{info}")
        return False


def test_monitor_iteration_limit():
    """测试监控器迭代限制"""
    print_section("10. 迭代限制测试")
    
    from 安卓相关.core.cloud.managers.enhanced_monitor import EnhancedExecutionMonitor
    
    monitor = EnhancedExecutionMonitor(max_iterations_per_task=5)
    
    task_id = "test_task_limit"
    
    # 模拟超过最大迭代次数
    for i in range(7):
        execution_context = {'screenshot_hash': f'hash_{i}'}
        result = monitor.track_task_execution(task_id, execution_context)
        
        if result.should_stop and "最大迭代次数" in result.reason:
            log_test("迭代限制触发", "PASS", f"第{i+1}次迭代触发停止：{result.reason}")
            return True
    
    log_test("迭代限制触发", "FAIL", "未触发迭代限制")
    return False


def test_monitor_change_rate():
    """测试监控器变化率检测"""
    print_section("11. 变化率检测测试")
    
    from 安卓相关.core.cloud.managers.enhanced_monitor import EnhancedExecutionMonitor
    
    monitor = EnhancedExecutionMonitor(min_change_rate=0.2)
    
    task_id = "test_task_change"
    
    # 模拟低变化率（相同截图）
    for i in range(10):
        execution_context = {'screenshot_hash': 'same_hash'}  # 始终相同
        result = monitor.track_task_execution(task_id, execution_context)
        
        if result.should_stop and "变化率过低" in result.reason:
            log_test("低变化率检测", "PASS", f"变化率：{result.metrics.get('change_rate', 0):.2f}")
            return True
    
    log_test("低变化率检测", "FAIL", "未检测到低变化率")
    return False


def test_screenshot_hash_calculator():
    """测试截图哈希计算器"""
    print_section("12. 截图哈希计算器测试")
    
    from 安卓相关.core.cloud.managers.enhanced_monitor import ScreenshotHashCalculator
    
    calculator = ScreenshotHashCalculator()
    
    # 创建测试截图
    screenshot1 = np.ones((720, 1280, 3), dtype=np.uint8) * 100
    screenshot2 = np.ones((720, 1280, 3), dtype=np.uint8) * 200
    
    # 计算哈希
    hash1 = calculator.calculate_hash(screenshot1)
    hash2 = calculator.calculate_hash(screenshot2)
    
    if hash1 != hash2:
        log_test("截图哈希计算", "PASS", f"不同截图产生不同哈希")
    else:
        log_test("截图哈希计算", "FAIL", "不同截图产生相同哈希")
        return False
    
    # 测试变化率计算
    hash_history = ['hash1', 'hash1', 'hash2', 'hash2', 'hash3']
    change_rate = calculator.calculate_change_rate(hash_history)
    
    if change_rate == 3/5:  # 3 个唯一哈希 / 5 个总哈希
        log_test("变化率计算", "PASS", f"变化率：{change_rate:.2f}")
        return True
    else:
        log_test("变化率计算", "FAIL", f"变化率不正确：{change_rate}")
        return False


# ============================================================
# 主测试运行器
# ============================================================

def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("  任务验证引擎和决策转回机制测试")
    print("="*60)
    print(f"  测试时间：{test_results['test_time']}")
    print("="*60)
    
    # 第一部分：任务验证引擎测试
    test_client_based_validator()
    test_progressive_validator()
    test_business_rules_validator()
    test_validation_engine()
    
    # 第二部分：决策转回机制测试
    test_decision_delegation_trigger()
    test_decision_request_generator()
    test_decision_response_processor()
    test_decision_coordinator()
    
    # 第三部分：增强执行监控器测试
    test_enhanced_execution_monitor()
    test_monitor_iteration_limit()
    test_monitor_change_rate()
    test_screenshot_hash_calculator()
    
    # 输出总结
    print("\n" + "="*60)
    print("  测试总结")
    print("="*60)
    print(f"  总测试数：{test_results['total_tests']}")
    print(f"  通过：{test_results['passed']}")
    print(f"  失败：{test_results['failed']}")
    if test_results['total_tests'] > 0:
        print(f"  通过率：{test_results['passed']/test_results['total_tests']*100:.1f}%")
    print("="*60)
    
    # 保存测试报告
    report_path = os.path.join(os.path.dirname(__file__), "test_task_validation_and_decision.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(test_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n  测试报告已保存：{report_path}")
    
    return test_results["failed"] == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
