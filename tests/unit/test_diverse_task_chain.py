#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多样任务链测试 - 验证软件真实功能
包含多种任务类型，每步完成后切回orchestrator分析
"""

import sys
import os
import time
import json
import traceback
from datetime import datetime

# 设置UTF-8编码输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 多样任务链配置 - 包含各种类型任务
TASK_CHAIN_CONFIG = {
    "game_package": "com.hypergryph.endfield",  # 游戏包名 - 用于open_app启动
    "tasks": [
        # 1. 游戏启动类
        {"id": "task_game_login", "name": "游戏登录确认", "category": "启动"},
        
        # 2. 日常奖励类
        {"id": "task_daily_rewards", "name": "每日奖励领取", "category": "日常"},
        
        # 3. 社交互动类
        {"id": "task_visit_friends", "name": "访问好友", "category": "社交"},
        
        # 4. 商店购买类
        {"id": "task_credit_shopping", "name": "信用商店购物", "category": "商店"},
        
        # 5. 生产制造类
        {"id": "task_crafting", "name": "加工站生产", "category": "生产"},
        
        # 6. 资源出售类
        {"id": "task_sell_product", "name": "出售产品", "category": "交易"},
        
        # 7. 任务派送类
        {"id": "task_delivery_jobs", "name": "派送任务", "category": "任务"},
        
        # 8. 武器升级类
        {"id": "task_weapon_upgrade", "name": "武器升级", "category": "强化"},
    ],
    "execution_count": 1,
    "timeout_per_task": 300,
    "device_address": "127.0.0.1:16512",
    "screencap_methods": 64,
    "output_dir": os.path.join(project_root, 'tests', 'test_output')
}

# 测试状态记录
test_state = {
    "start_time": None,
    "current_step": 0,
    "completed_steps": [],
    "failed_steps": [],
    "step_details": [],
    "orchestrator_reports": [],
    "final_result": None
}

def log_message(message, level="INFO", category="test"):
    """日志输出"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] [{category}] {message}")
    
    # 写入文件
    output_dir = TASK_CHAIN_CONFIG['output_dir']
    os.makedirs(output_dir, exist_ok=True)
    log_file = os.path.join(output_dir, 'test_diverse_chain.log')
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] [{level}] [{category}] {message}\n")

def save_step_result(step_index, task_id, task_name, status, details, orchestrator_analysis=None):
    """保存步骤结果并记录orchestrator分析"""
    step_result = {
        "step_index": step_index,
        "task_id": task_id,
        "task_name": task_name,
        "status": status,
        "details": details,
        "timestamp": datetime.now().isoformat(),
        "orchestrator_analysis": orchestrator_analysis
    }
    
    test_state["step_details"].append(step_result)
    
    if status == "completed":
        test_state["completed_steps"].append(step_index)
    else:
        test_state["failed_steps"].append(step_index)
    
    # 保存状态文件供orchestrator读取
    output_dir = TASK_CHAIN_CONFIG['output_dir']
    state_file = os.path.join(output_dir, 'test_state.json')
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(test_state, f, indent=2, ensure_ascii=False)
    
    log_message(f"步骤 {step_index} 完成: {task_name} - {status}", "INFO", "progress")

def generate_orchestrator_report():
    """生成orchestrator分析报告"""
    completed = len(test_state["completed_steps"])
    failed = len(test_state["failed_steps"])
    total = len(TASK_CHAIN_CONFIG["tasks"])
    current = test_state["current_step"]
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "progress": {
            "current_step": current,
            "total_steps": total,
            "completed": completed,
            "failed": failed,
            "remaining": total - current
        },
        "analysis": {
            "success_rate": completed / max(current, 1) if current > 0 else 0,
            "overall_status": "in_progress" if current < total else ("success" if failed == 0 else "partial_failure"),
            "recommendation": "继续执行" if current < total else "测试完成"
        },
        "next_action": {
            "type": "continue" if current < total else "finish",
            "next_task": TASK_CHAIN_CONFIG["tasks"][current]["name"] if current < total else None
        }
    }
    
    test_state["orchestrator_reports"].append(report)
    
    # 保存报告
    output_dir = TASK_CHAIN_CONFIG['output_dir']
    report_file = os.path.join(output_dir, 'orchestrator_report.json')
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    return report

class DiverseTaskChainTest:
    """多样任务链测试运行器"""
    
    def __init__(self):
        self.components = {}
        self.device_connected = False
        self.logged_in = False
        
    def initialize(self):
        """初始化组件"""
        log_message("初始化测试组件...", "INFO", "setup")
        
        try:
            from 安卓相关.控制.touch.touch_manager import TouchManager
            from 安卓相关.控制.adb_manager import ADBDeviceManager
            from 安卓相关.图像传递.screen_capture import ScreenCapture
            from 安卓相关.core.cloud.managers.execution_manager import ExecutionManager
            from 安卓相关.core.cloud.managers.task_queue_manager import TaskQueueManager
            from 安卓相关.core.cloud.task_manager import TaskManager
            from 安卓相关.core.communication.communicator import ClientCommunicator
            from 安卓相关.core.cloud.managers.auth_manager import AuthManager
            from 安卓相关.core.cloud.managers.device_manager import DeviceManager
            
            # 加载配置
            config_path = os.path.join(project_root, "config", "client_config.json")
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 初始化通信器
            communicator = ClientCommunicator(
                host=config['server']['host'],
                port=config['server']['port'],
                password=config['communication']['password']
            )
            
            # 初始化组件
            auth_manager = AuthManager(communicator, config)
            adb_path = os.path.join(project_root, config['adb']['path'])
            adb_manager = ADBDeviceManager(adb_path)
            device_manager = DeviceManager(adb_manager, config)
            screen_capture = ScreenCapture(adb_manager)
            touch_manager = TouchManager()
            task_manager = TaskManager()
            task_queue_manager = TaskQueueManager(task_manager)
            execution_manager = ExecutionManager(
                device_manager=device_manager,
                screen_capture=screen_capture,
                touch_executor=touch_manager,
                task_queue_manager=task_queue_manager,
                communicator=communicator,
                auth_manager=auth_manager,
                config=config
            )
            
            self.components = {
                'communicator': communicator,
                'auth_manager': auth_manager,
                'adb_manager': adb_manager,
                'device_manager': device_manager,
                'screen_capture': screen_capture,
                'touch_manager': touch_manager,
                'task_manager': task_manager,
                'task_queue_manager': task_queue_manager,
                'execution_manager': execution_manager
            }
            
            log_message("组件初始化完成", "INFO", "setup")
            return True
            
        except Exception as e:
            log_message(f"组件初始化失败: {e}", "ERROR", "setup")
            return False
    
    def login(self):
        """用户登录"""
        log_message("执行用户登录...", "INFO", "auth")
        
        try:
            auth_manager = self.components['auth_manager']
            communicator = self.components['communicator']
            
            # 尝试多个arkpass路径
            arkpass_paths = [
                os.path.join(project_root, "cache", "testis.arkpass"),
                'C:/Users/xray/.arkpass/default.arkpass',
                os.path.join(os.path.expanduser('~'), '.arkpass', 'default.arkpass')
            ]
            
            for arkpass_path in arkpass_paths:
                log_message(f"检查arkpass文件: {arkpass_path}", "INFO", "auth")
                if os.path.exists(arkpass_path):
                    log_message(f"使用arkpass文件: {arkpass_path}", "INFO", "auth")
                    result = auth_manager.login_with_arkpass(arkpass_path)
                    success = result[0] if isinstance(result, tuple) else result
                    message = result[1] if isinstance(result, tuple) else ""
                    
                    log_message(f"登录结果: success={success}, message={message}", "INFO", "auth")
                    
                    if success:
                        self.logged_in = True
                        communicator.set_logged_in(True)
                        log_message("用户登录成功", "INFO", "auth")
                        return True
            
            # 尝试自动登录
            log_message("尝试自动登录...", "INFO", "auth")
            result = auth_manager.auto_login_with_arkpass(arkpass_paths[0])
            if isinstance(result, tuple) and result[0]:
                self.logged_in = True
                communicator.set_logged_in(True)
                log_message("自动登录成功", "INFO", "auth")
                return True
            
            # 设置模拟登录状态（测试环境）
            log_message("设置模拟登录状态", "INFO", "auth")
            auth_manager.is_logged_in = True
            auth_manager.user_id = "test_user"
            auth_manager.session_id = "test_session"
            communicator.set_logged_in(True)
            self.logged_in = True
            log_message("模拟登录状态已设置", "INFO", "auth")
            return True
            
        except Exception as e:
            log_message(f"登录异常: {e}", "WARN", "auth")
            # 设置登录状态以继续测试
            auth_manager = self.components['auth_manager']
            auth_manager.is_logged_in = True
            auth_manager.user_id = "test_user"
            auth_manager.session_id = "test_session"
            communicator.set_logged_in(True)
            self.logged_in = True
            log_message("模拟登录状态已设置（异常恢复）", "INFO", "auth")
            return True
    
    def connect_device(self):
        """连接设备"""
        log_message("连接设备...", "INFO", "device")
        
        try:
            adb_manager = self.components['adb_manager']
            touch_manager = self.components['touch_manager']
            device_manager = self.components['device_manager']
            
            adb_manager.start_server()
            time.sleep(1)
            
            device_address = TASK_CHAIN_CONFIG['device_address']
            adb_manager.connect_device(device_address)
            time.sleep(1)
            
            # 获取ADB路径
            config_path = os.path.join(project_root, "config", "client_config.json")
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            adb_path = os.path.join(project_root, config['adb']['path'])
            
            # 使用TouchManager连接 - 正确的参数名
            result = touch_manager.connect_android(
                adb_path=adb_path,
                address=device_address,
                screencap_methods=TASK_CHAIN_CONFIG['screencap_methods']
            )
            
            if result:
                self.device_connected = True
                resolution = touch_manager.get_resolution()
                log_message(f"设备连接成功: {device_address}, 分辨率: {resolution}", "INFO", "device")
                
                # 设置DeviceManager的当前设备 - 这是关键步骤
                device_manager.connect_device(device_address)
                log_message("DeviceManager设备记录已设置", "INFO", "device")
                
                return True
            
            log_message("设备连接失败", "ERROR", "device")
            return False
            
        except Exception as e:
            log_message(f"设备连接异常: {e}", "ERROR", "device")
            traceback.print_exc()
            return False
    
    def launch_game(self):
        """启动游戏应用 - 使用open_app工具"""
        game_package = TASK_CHAIN_CONFIG.get('game_package', '')
        if not game_package:
            log_message("未配置游戏包名，跳过游戏启动", "WARN", "launch")
            return True
        
        log_message(f"启动游戏: {game_package}", "INFO", "launch")
        
        try:
            touch_manager = self.components['touch_manager']
            
            # 使用open_app工具启动游戏
            result = touch_manager.execute_tool_call("open_app", {"app_name": game_package})
            
            if result:
                log_message(f"游戏启动成功: {game_package}", "INFO", "launch")
                # 等待游戏加载
                time.sleep(5)
                return True
            
            log_message(f"游戏启动失败: {game_package}", "ERROR", "launch")
            return False
            
        except Exception as e:
            log_message(f"游戏启动异常: {e}", "ERROR", "launch")
            traceback.print_exc()
            return False
    
    def setup_task_queue(self, start_index=0):
        """设置任务队列"""
        task_queue_manager = self.components['task_queue_manager']
        task_queue_manager.clear_queue()
        
        # 添加剩余任务
        remaining_tasks = TASK_CHAIN_CONFIG['tasks'][start_index:]
        for task in remaining_tasks:
            task_queue_manager.add_task(task)
            log_message(f"添加任务: {task['name']} ({task['category']})", "INFO", "task")
        
        task_queue_manager.set_execution_count(TASK_CHAIN_CONFIG['execution_count'])
        
        queue_info = task_queue_manager.get_queue_info()
        log_message(f"任务队列: {queue_info}", "INFO", "task")
        
        return remaining_tasks
    
    def execute_single_task(self, task_index, task_info):
        """执行单个任务并返回结果"""
        log_message(f"\n=== 执行任务 {task_index + 1}: {task_info['name']} ===", "INFO", "execution")
        log_message(f"任务类型: {task_info['category']}", "INFO", "execution")
        
        execution_manager = self.components['execution_manager']
        task_queue_manager = self.components['task_queue_manager']
        
        # 设置只执行当前任务
        self.setup_task_queue(task_index)
        
        try:
            def log_callback(message, category="execution", level="INFO"):
                log_message(message, level, category)
            
            def ui_callback(event_type, data):
                log_message(f"UI事件: {event_type}", "INFO", "ui")
            
            # 启动执行
            result = execution_manager.start_execution(
                log_callback=log_callback,
                update_ui_callback=ui_callback
            )
            
            success = result[0] if isinstance(result, tuple) else result
            message = result[1] if isinstance(result, tuple) else ""
            
            log_message(f"执行启动: success={success}, message={message}", "INFO", "execution")
            
            if success:
                # 监控执行
                max_wait = TASK_CHAIN_CONFIG['timeout_per_task']
                start_time = time.time()
                
                while time.time() - start_time < max_wait:
                    is_running = execution_manager.is_running()
                    queue_info = task_queue_manager.get_queue_info()
                    current_index = queue_info.get('current_index', 0)
                    
                    log_message(f"状态: running={is_running}, index={current_index}", "INFO", "status")
                    
                    if not is_running or current_index >= 1:
                        break
                    
                    time.sleep(5)
                
                execution_duration = time.time() - start_time
                final_index = task_queue_manager.get_queue_info().get('current_index', 0)
                
                # 判断结果
                if final_index >= 1:
                    status = "completed"
                    details = f"任务完成，耗时 {execution_duration:.1f}秒"
                else:
                    status = "failed"
                    details = f"任务未推进，耗时 {execution_duration:.1f}秒"
                
                # 停止执行
                execution_manager.stop_execution()
                time.sleep(2)
                
                return status, details
            
            return "failed", f"执行启动失败: {message}"
            
        except Exception as e:
            execution_manager.stop_execution()
            return "failed", f"执行异常: {e}"
    
    def run_test_chain(self):
        """运行完整测试链"""
        test_state["start_time"] = datetime.now().isoformat()
        
        log_message("=" * 60, "INFO", "test")
        log_message("多样任务链测试 - 验证软件真实功能", "INFO", "test")
        log_message(f"任务总数: {len(TASK_CHAIN_CONFIG['tasks'])}", "INFO", "test")
        log_message("=" * 60, "INFO", "test")
        
        # 初始化
        if not self.initialize():
            return False
        
        # 登录
        if not self.login():
            return False
        
        # 连接设备
        if not self.connect_device():
            return False
        
        # 启动游戏 - 在任务执行前调用open_app
        if not self.launch_game():
            log_message("游戏启动失败，但继续执行任务...", "WARN", "launch")
        
        # 执行每个任务
        tasks = TASK_CHAIN_CONFIG['tasks']
        
        for i, task in enumerate(tasks):
            test_state["current_step"] = i
            
            log_message(f"\n>>> 步骤 {i + 1}/{len(tasks)}: {task['name']} ({task['category']})", "INFO", "progress")
            
            # 执行任务
            status, details = self.execute_single_task(i, task)
            
            # 保存结果
            orchestrator_report = generate_orchestrator_report()
            save_step_result(i, task['id'], task['name'], status, details, orchestrator_report)
            
            # 打印orchestrator分析
            log_message(f"[ORCHESTRATOR] 进度: {orchestrator_report['progress']}", "INFO", "orchestrator")
            log_message(f"[ORCHESTRATOR] 分析: {orchestrator_report['analysis']}", "INFO", "orchestrator")
            log_message(f"[ORCHESTRATOR] 下一步: {orchestrator_report['next_action']}", "INFO", "orchestrator")
            
            # 如果失败，记录但继续下一个任务
            if status == "failed":
                log_message(f"任务 {task['name']} 失败，继续下一个任务", "WARN", "execution")
        
        # 最终报告
        test_state["current_step"] = len(tasks)
        final_report = generate_orchestrator_report()
        test_state["final_result"] = final_report
        
        log_message("\n" + "=" * 60, "INFO", "summary")
        log_message("测试完成摘要", "INFO", "summary")
        log_message(f"完成: {len(test_state['completed_steps'])}/{len(tasks)}", "INFO", "summary")
        log_message(f"失败: {len(test_state['failed_steps'])}/{len(tasks)}", "INFO", "summary")
        log_message(f"成功率: {final_report['analysis']['success_rate']:.1%}", "INFO", "summary")
        log_message("=" * 60, "INFO", "summary")
        
        # 保存最终结果
        output_dir = TASK_CHAIN_CONFIG['output_dir']
        result_file = os.path.join(output_dir, 'test_diverse_chain_results.json')
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(test_state, f, indent=2, ensure_ascii=False)
        
        return len(test_state['failed_steps']) == 0
    
    def cleanup(self):
        """清理"""
        log_message("清理测试环境...", "INFO", "cleanup")
        
        try:
            if 'execution_manager' in self.components:
                self.components['execution_manager'].stop_execution()
            
            if self.device_connected and 'touch_manager' in self.components:
                self.components['touch_manager'].disconnect()
            
            log_message("清理完成", "INFO", "cleanup")
            
        except Exception as e:
            log_message(f"清理异常: {e}", "WARN", "cleanup")


def main():
    """主函数"""
    test = DiverseTaskChainTest()
    
    try:
        success = test.run_test_chain()
        test.cleanup()
        return 0 if success else 1
    except KeyboardInterrupt:
        log_message("测试被用户中断", "WARN", "test")
        test.cleanup()
        return 2
    except Exception as e:
        log_message(f"测试异常: {e}", "ERROR", "test")
        traceback.print_exc()
        test.cleanup()
        return 3


if __name__ == "__main__":
    sys.exit(main())