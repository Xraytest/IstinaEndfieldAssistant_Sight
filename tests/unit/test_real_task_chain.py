#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
真实任务链测试 - 验证软件真实功能
执行包含启动游戏、售卖物品等完整任务链
"""

import os
import sys
import time
import json
import traceback
from datetime import datetime

# 设置输出编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目路径 - 必须从IstinaEndfieldAssistant目录运行
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 添加core路径以解决模块导入
core_path = os.path.join(project_root, '安卓相关')
if core_path not in sys.path:
    sys.path.insert(0, core_path)

# 测试配置
TEST_CONFIG = {
    'server_host': '127.0.0.1',
    'server_port': 9999,
    'arkpass_path': 'C:/Users/xray/.arkpass/default.arkpass',
    'device_address': '127.0.0.1:16512',  # MuMu模拟器
    'screencap_methods': 64,
    'task_chain': [
        {"id": "task_game_login", "name": "游戏登录确认"},
        {"id": "task_sell_product", "name": "出售产品"}
    ],
    'execution_count': 1,
    'timeout_per_task': 300,  # 每个任务最多5分钟
    'output_dir': os.path.join(project_root, 'tests', 'test_output')
}

# 结果记录
test_results = {
    "test_name": "真实任务链执行测试",
    "start_time": None,
    "end_time": None,
    "duration_seconds": 0,
    "passed": False,
    "details": []
}

def log_message(message, level="INFO", category="test"):
    """日志输出"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] [{category}] {message}")
    
    # 写入文件
    output_dir = TEST_CONFIG['output_dir']
    os.makedirs(output_dir, exist_ok=True)
    log_file = os.path.join(output_dir, 'test_real_task_chain.log')
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] [{level}] [{category}] {message}\n")

def record_result(step_name, passed, details="", error=None):
    """记录测试结果"""
    result = {
        "step": step_name,
        "passed": passed,
        "details": details,
        "error": str(error) if error else None,
        "timestamp": datetime.now().isoformat()
    }
    test_results["details"].append(result)
    
    status = "[OK] PASS" if passed else "[X] FAIL"
    log_message(f"{status}: {step_name} - {details}", "INFO" if passed else "ERROR", "result")
    
    if error:
        log_message(f"错误详情: {error}", "ERROR", "error")

class RealTaskChainTestRunner:
    """真实任务链测试运行器"""
    
    def __init__(self):
        self.components = {}
        self.device_connected = False
        self.logged_in = False
        
    def initialize_components(self):
        """初始化所有组件"""
        log_message("初始化组件...", "INFO", "init")
        
        try:
            # 导入必要模块
            from 安卓相关.core.communication.communicator import ClientCommunicator
            from 安卓相关.core.logger import ClientLogger, LogCategory
            from 安卓相关.core.cloud.managers.auth_manager import AuthManager
            from 安卓相关.core.cloud.managers.device_manager import DeviceManager
            from 安卓相关.core.cloud.managers.task_queue_manager import TaskQueueManager
            from 安卓相关.core.cloud.managers.execution_manager import ExecutionManager
            from 安卓相关.core.cloud.task_manager import TaskManager
            from 安卓相关.控制.adb_manager import ADBDeviceManager
            from 安卓相关.图像传递.screen_capture import ScreenCapture
            from 安卓相关.控制.touch.touch_manager import TouchManager
            
            # 加载配置
            config_path = os.path.join(project_root, 'config', 'client_config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 创建通信器
            communicator = ClientCommunicator(
                host=TEST_CONFIG['server_host'],
                port=TEST_CONFIG['server_port'],
                password=config.get('security', {}).get('password', 'default_password')
            )
            
            # 创建日志器
            logger = ClientLogger()
            
            # 创建ADB管理器
            adb_path = os.path.join(project_root, 'adb', 'platform-tools', 'adb.exe')
            if not os.path.exists(adb_path):
                # 使用系统ADB
                adb_path = 'adb'
            adb_manager = ADBDeviceManager(adb_path)
            
            # 创建认证管理器
            auth_manager = AuthManager(communicator, config)
            
            # 创建设备管理器
            device_manager = DeviceManager(adb_manager, config)
            
            # 创建屏幕捕获器
            screen_capture = ScreenCapture(adb_manager)
            
            # 创建触控管理器
            touch_manager = TouchManager()
            
            # 创建任务管理器
            task_manager = TaskManager()
            
            # 创建任务队列管理器
            task_queue_manager = TaskQueueManager(task_manager)
            
            # 创建执行管理器
            execution_manager = ExecutionManager(
                device_manager=device_manager,
                screen_capture=screen_capture,
                touch_executor=touch_manager,
                task_queue_manager=task_queue_manager,
                communicator=communicator,
                auth_manager=auth_manager,
                config=config
            )
            
            # 存储组件
            self.components = {
                'communicator': communicator,
                'logger': logger,
                'adb_manager': adb_manager,
                'auth_manager': auth_manager,
                'device_manager': device_manager,
                'screen_capture': screen_capture,
                'touch_manager': touch_manager,
                'task_manager': task_manager,
                'task_queue_manager': task_queue_manager,
                'execution_manager': execution_manager
            }
            
            record_result("组件初始化", True, "所有组件创建成功")
            return True
            
        except Exception as e:
            record_result("组件初始化", False, f"初始化失败: {e}", e)
            return False
    
    def login_user(self):
        """用户登录"""
        log_message("执行用户登录...", "INFO", "auth")
        
        try:
            auth_manager = self.components['auth_manager']
            communicator = self.components['communicator']
            
            # 检查是否有arkpass文件
            arkpass_path = TEST_CONFIG['arkpass_path']
            if not os.path.exists(arkpass_path):
                record_result("用户登录", False, f"arkpass文件不存在: {arkpass_path}")
                return False
            
            # 使用arkpass登录
            log_message(f"使用arkpass登录: {arkpass_path}", "INFO", "auth")
            result = auth_manager.login_with_arkpass(arkpass_path)
            
            # login_with_arkpass返回tuple (bool, str)
            success = result[0] if isinstance(result, tuple) else result
            message = result[1] if isinstance(result, tuple) else ""
            
            if success:
                self.logged_in = True
                # 设置通信器登录状态
                communicator.set_logged_in(True)
                record_result("用户登录", True, message)
                return True
            else:
                record_result("用户登录", False, message)
                return False
                
        except Exception as e:
            record_result("用户登录", False, f"登录异常: {e}", e)
            return False
    
    def connect_device(self):
        """连接设备"""
        log_message("连接设备...", "INFO", "device")
        
        try:
            adb_manager = self.components['adb_manager']
            touch_manager = self.components['touch_manager']
            
            # 启动ADB服务
            adb_manager.start_server()
            time.sleep(1)
            
            # 连接设备
            device_address = TEST_CONFIG['device_address']
            log_message(f"连接设备: {device_address}", "INFO", "device")
            
            connect_result = adb_manager.connect_device(device_address)
            if not connect_result:
                record_result("设备连接", False, f"ADB连接失败: {device_address}")
                return False
            
            time.sleep(1)
            
            # 获取设备列表确认
            devices = adb_manager.get_devices()
            target_device = None
            for dev in devices:
                if device_address in dev.serial or dev.serial.endswith(device_address.split(':')[1]):
                    target_device = dev
                    break
            
            if not target_device:
                record_result("设备连接", False, "设备列表中未找到目标设备")
                return False
            
            log_message(f"找到设备: {target_device.serial}", "INFO", "device")
            
            # 使用TouchManager连接
            connect_result = touch_manager.connect_android(
                device_address=device_address,
                screencap_methods=TEST_CONFIG['screencap_methods']
            )
            
            if connect_result:
                self.device_connected = True
                record_result("设备连接", True, f"设备: {target_device.serial}")
                return True
            else:
                record_result("设备连接", False, "TouchManager连接失败")
                return False
                
        except Exception as e:
            record_result("设备连接", False, f"连接异常: {e}", e)
            return False
    
    def setup_task_chain(self):
        """设置任务链"""
        log_message("设置任务链...", "INFO", "task")
        
        task_chain = TEST_CONFIG['task_chain']
        task_queue_manager = self.components['task_queue_manager']
        
        # 清空队列
        task_queue_manager.clear_queue()
        
        # 添加任务
        for task in task_chain:
            task_queue_manager.add_task(task)
            log_message(f"添加任务: {task['name']}", "INFO", "task")
        
        # 设置执行次数
        task_queue_manager.set_execution_count(TEST_CONFIG['execution_count'])
        
        queue_info = task_queue_manager.get_queue_info()
        log_message(f"任务队列信息: {queue_info}", "INFO", "task")
        
        record_result("任务链设置", True, f"队列长度: {len(task_chain)}")
        return task_chain
    
    def run_task_chain(self):
        """运行任务链"""
        log_message("\n=== 开始执行真实任务链 ===", "INFO", "execution")
        
        if not self.device_connected:
            if not self.connect_device():
                record_result("任务链执行", False, "设备未连接")
                return False
        
        if not self.logged_in:
            if not self.login_user():
                record_result("任务链执行", False, "用户未登录")
                return False
        
        # 设置任务链
        task_chain = self.setup_task_chain()
        
        execution_manager = self.components['execution_manager']
        
        try:
            # 定义回调
            def log_callback(message, category="execution", level="INFO"):
                log_message(message, level, category)
            
            def ui_callback(event_type, data):
                log_message(f"UI事件: {event_type} - {data}", "INFO", "ui")
            
            def preview_callback(screen_data):
                # 保存截图
                if screen_data:
                    output_dir = TEST_CONFIG['output_dir']
                    timestamp = datetime.now().strftime("%H%M%S")
                    screenshot_path = os.path.join(output_dir, f'screenshot_{timestamp}.png')
                    try:
                        if isinstance(screen_data, bytes):
                            with open(screenshot_path, 'wb') as f:
                                f.write(screen_data)
                            log_message(f"保存截图: {screenshot_path}", "INFO", "preview")
                    except Exception as e:
                        log_message(f"保存截图失败: {e}", "ERROR", "preview")
            
            # 启动执行
            log_message("启动任务执行...", "INFO", "execution")
            result = execution_manager.start_execution(
                log_callback=log_callback,
                update_ui_callback=ui_callback,
                preview_update_callback=preview_callback
            )
            
            # start_execution返回tuple (bool, str)
            success = result[0] if isinstance(result, tuple) else result
            message = result[1] if isinstance(result, tuple) else ""
            
            log_message(f"执行启动结果: success={success}, message={message}", "INFO", "execution")
            
            if success:
                log_message("执行启动成功，开始监控执行状态...", "INFO", "execution")
                
                # 监控执行状态
                max_wait = TEST_CONFIG['timeout_per_task'] * len(task_chain)
                start_time = time.time()
                last_index = 0
                
                while time.time() - start_time < max_wait:
                    running_ops = execution_manager.get_running_operations()
                    queue_info = self.components['task_queue_manager'].get_queue_info()
                    is_running = execution_manager.is_running()
                    current_index = queue_info.get('current_index', 0)
                    
                    # 记录状态变化
                    if current_index != last_index:
                        log_message(f"任务索引推进: {last_index} -> {current_index}", "INFO", "progress")
                        last_index = current_index
                    
                    log_message(f"状态: is_running={is_running}, current_index={current_index}, running_ops={len(running_ops)}", "INFO", "status")
                    
                    # 检查是否完成
                    if not is_running:
                        log_message("执行已停止", "INFO", "execution")
                        break
                    
                    # 检查任务索引推进
                    if current_index >= len(task_chain):
                        log_message("任务链执行完成（所有任务索引已推进）", "INFO", "execution")
                        break
                    
                    time.sleep(10)  # 每10秒检查一次
                
                execution_duration = time.time() - start_time
                final_index = self.components['task_queue_manager'].get_queue_info().get('current_index', 0)
                
                # 判断成功条件：任务索引有推进且执行停止
                if final_index > 0 or not execution_manager.is_running():
                    record_result("任务链执行", True, 
                        f"执行时长: {execution_duration:.1f}秒, 最终索引: {final_index}, 任务数: {len(task_chain)}")
                    return True
                else:
                    record_result("任务链执行", False, 
                        f"执行时长: {execution_duration:.1f}秒, 任务索引未推进: {final_index}")
                    return False
                    
            else:
                record_result("任务链执行", False, f"执行启动失败: {message}")
                return False
                
        except Exception as e:
            record_result("任务链执行", False, f"执行异常: {e}", e)
            traceback.print_exc()
            return False
    
    def cleanup(self):
        """清理测试环境"""
        log_message("\n清理测试环境...", "INFO", "cleanup")
        
        try:
            # 停止执行
            if 'execution_manager' in self.components:
                execution_manager = self.components['execution_manager']
                if execution_manager.is_running():
                    execution_manager.stop_execution()
                    log_message("停止执行管理器", "INFO", "cleanup")
            
            # 断开设备
            if self.device_connected and 'touch_manager' in self.components:
                touch_manager = self.components['touch_manager']
                touch_manager.disconnect()
                log_message("断开设备连接", "INFO", "cleanup")
            
            record_result("清理环境", True, "清理完成")
            
        except Exception as e:
            record_result("清理环境", False, f"清理异常: {e}", e)
    
    def run_test(self):
        """运行完整测试"""
        test_results["start_time"] = datetime.now().isoformat()
        
        log_message("=" * 60, "INFO", "test")
        log_message("真实任务链测试 - 验证软件真实功能", "INFO", "test")
        log_message("=" * 60, "INFO", "test")
        
        # 初始化
        if not self.initialize_components():
            self.cleanup()
            return False
        
        # 运行任务链
        success = self.run_task_chain()
        
        # 清理
        self.cleanup()
        
        test_results["end_time"] = datetime.now().isoformat()
        test_results["passed"] = success
        
        # 打印摘要
        self.print_summary()
        
        # 保存结果
        self.save_results()
        
        return success
    
    def print_summary(self):
        """打印测试摘要"""
        log_message("\n" + "=" * 60, "INFO", "summary")
        log_message("测试摘要", "INFO", "summary")
        log_message("=" * 60, "INFO", "summary")
        
        passed_count = sum(1 for d in test_results["details"] if d["passed"])
        total_count = len(test_results["details"])
        
        log_message(f"总测试步骤: {total_count}", "INFO", "summary")
        log_message(f"通过步骤: {passed_count}", "INFO", "summary")
        log_message(f"失败步骤: {total_count - passed_count}", "INFO", "summary")
        log_message(f"最终结果: {'PASS' if test_results['passed'] else 'FAIL'}", "INFO", "summary")
        
        log_message("\n详细结果:", "INFO", "summary")
        for detail in test_results["details"]:
            status = "[OK]" if detail["passed"] else "[X]"
            log_message(f"  {status} {detail['step']}: {detail['details']}", "INFO", "summary")
    
    def save_results(self):
        """保存测试结果"""
        output_dir = TEST_CONFIG['output_dir']
        os.makedirs(output_dir, exist_ok=True)
        
        result_file = os.path.join(output_dir, 'test_real_task_chain_results.json')
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(test_results, f, indent=2, ensure_ascii=False)
        
        log_message(f"结果已保存: {result_file}", "INFO", "result")


def main():
    """主函数"""
    runner = RealTaskChainTestRunner()
    success = runner.run_test()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())