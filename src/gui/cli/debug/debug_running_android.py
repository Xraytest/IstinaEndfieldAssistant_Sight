"""
CLI方法 - 任务链调试运行脚本（安卓设备版本）
与GUI方法共用同一套执行代码，差异仅为调用方式
支持命令行指定任务及其顺序、api_key、设备地址
按时间+任务名输出截图（1Hz），每个输出夹配一份json描述
"""
import os
import sys
import json
import time
import argparse
import threading
import base64
from datetime import datetime
from typing import Optional, Dict, Any, List

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
client_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(client_dir)
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入核心组件（使用重构后的路径）
from core.foundation.logger import init_logger, get_logger, LogCategory, LogLevel
from core.capability.device.adb_manager import ADBDeviceManager
from core.capability.screenshot.screen_capture import ScreenCapture
from core.capability.device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig


class CLIDebugRunnerAndroid:
    """CLI调试运行器 - 安卓设备版本"""
    
    def __init__(self,
                 api_key: str,
                 user_id: str,
                 server_host: str = "127.0.0.1",
                 server_port: int = 9999,
                 device_address: str = "127.0.0.1:16512",
                 output_dir: str = None,
                 screenshot_interval: float = 1.0):
        """
        初始化CLI调试运行器（安卓设备）
        
        Args:
            api_key: 用户API密钥
            user_id: 用户ID
            server_host: 服务器地址
            server_port: 服务器端口
            device_address: 安卓设备地址
            output_dir: 输出目录
            screenshot_interval: 截图间隔（秒）
        """
        self.api_key = api_key
        self.user_id = user_id
        self.server_host = server_host
        self.server_port = server_port
        self.device_address = device_address
        self.screenshot_interval = screenshot_interval
        
        # 设置输出目录
        if output_dir:
            self.output_dir = output_dir
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_dir = os.path.join(client_dir, "debug_output", f"run_android_{timestamp}")
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 初始化日志
        log_config_path = os.path.join(client_dir, "config", "logging_config.json")
        if os.path.exists(log_config_path):
            init_logger(log_config_path)
        self.logger = get_logger()
        
        # 核心组件
        self.adb_manager = None
        self.screen_capture = None
        self.touch_executor = None
        self.task_manager = None
        self.communicator = None
        self.auth_manager = None
        self.device_manager = None
        self.task_queue_manager = None
        self.execution_manager = None
        
        # 运行状态
        self.running = False
        self.current_task_name = ""
        self.current_task_variables = {}
        self.run_start_time = ""
        
        # 截图数据
        self.screenshot_data_list: List[Dict[str, Any]] = []
        self.screenshot_running = False
        self.screenshot_thread = None
        
    def init_components(self) -> bool:
        """初始化所有组件（安卓设备版本）"""
        try:
            self.logger.info(LogCategory.MAIN, "CLI调试运行器（安卓设备）初始化开始")
            
            # 加载配置
            config = self._load_config()
            
            # 初始化ADB管理器
            adb_path = os.path.join(client_dir, "3rd-part", "ADB", "adb.exe")
            self.adb_manager = ADBDeviceManager(
                adb_path=adb_path,
                timeout=config.get('adb', {}).get('timeout', 10)
            )
            
            # 连接设备
            if not self.adb_manager.connect_device_manual(self.device_address):
                self.logger.error(LogCategory.ADB, f"无法连接到设备: {self.device_address}")
                return False
            
            # 初始化通信模块
            self.communicator = ClientCommunicator(
                host=self.server_host,
                port=self.server_port,
                password=config.get('communication', {}).get('password', 'default_password'),
                timeout=300
            )
            
            # 初始化认证管理模块
            cache_dir = os.path.join(client_dir, "cache")
            self.auth_manager = AuthManager(self.communicator, config)
            self.auth_manager.is_logged_in = True
            self.auth_manager.user_id = self.user_id
            self.auth_manager.session_id = ""  # 将在登录后获取
            
            # 先登录获取session_id
            login_success, login_msg = self._login_with_api_key()
            if not login_success:
                self.logger.error(LogCategory.AUTHENTICATION, f"登录失败: {login_msg}")
                return False
            
            # 初始化设备管理模块
            self.device_manager = DeviceManager(self.adb_manager, config)
            self.device_manager.current_device = self.device_address
            
            # 初始化屏幕捕获模块
            self.screen_capture = ScreenCapture(self.adb_manager)
            
            # 初始化触控执行模块（MaaFramework方案）
            touch_config = config.get('touch', {})
            maa_style_config = touch_config.get('maa_style', {})
            fail_on_error = touch_config.get('fail_on_error', True)
            maa_config = MaaFwTouchConfig(
                press_duration_ms=maa_style_config.get('press_duration_ms', 50),
                press_jitter_px=maa_style_config.get('press_jitter_px', 2),
                swipe_delay_min_ms=maa_style_config.get('swipe_delay_min_ms', 100),
                swipe_delay_max_ms=maa_style_config.get('swipe_delay_max_ms', 300),
                use_normalized_coords=maa_style_config.get('use_normalized_coords', True),
                fail_on_error=fail_on_error
            )
            self.logger.info(LogCategory.MAIN, '触控配置加载完成（MaaFramework方案）')
            self.touch_executor = TouchExecutor(
                adb_manager=self.adb_manager,
                config=maa_config
            )
            self.logger.info(LogCategory.MAIN, '触控执行器初始化完成（MaaFramework方案）',
                press_duration_ms=maa_config.press_duration_ms,
                jitter_px=maa_config.press_jitter_px,
                normalized_coords=maa_config.use_normalized_coords
            )
            
            # 初始化任务管理模块
            self.task_manager = TaskManager(
                config_dir=os.path.join(client_dir, "config"),
                data_dir=os.path.join(client_dir, "data")
            )
            
            # 初始化任务队列管理模块
            self.task_queue_manager = TaskQueueManager(self.task_manager)
            
            # 初始化执行管理模块
            self.execution_manager = ExecutionManager(
                self.device_manager,
                self.screen_capture,
                self.touch_executor,
                self.task_queue_manager,
                self.communicator,
                self.auth_manager,
                config=config
            )
            
            self.logger.info(LogCategory.MAIN, "CLI调试运行器（安卓设备）初始化完成")
            return True
            
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, f"初始化异常: {e}")
            return False
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        config_path = os.path.join(client_dir, "config", "client_config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {
                "server": {"host": self.server_host, "port": self.server_port},
                "adb": {"path": "3rd-part/ADB/adb.exe", "timeout": 10},
                "communication": {"password": "default_password"}
            }
    
    def _login_with_api_key(self) -> tuple:
        """使用API密钥登录"""
        try:
            response = self.communicator.send_request("login", {
                "user_id": self.user_id,
                "key": self.api_key
            })
            
            if response is None:
                return False, "网络连接异常"
            
            if response.get('status') == 'success':
                session_id = response.get('session_id')
                if session_id:
                    self.auth_manager.session_id = session_id
                    self.auth_manager.is_logged_in = True
                    if self.communicator:
                        self.communicator.set_logged_in(True)
                    return True, None
                return False, "服务器响应中缺少会话ID"
            else:
                return False, response.get('message', '未知错误')
                
        except Exception as e:
            return False, str(e)
    
    def _capture_screenshot(self, screen_data=None) -> Optional[str]:
        """捕获屏幕截图（Base64格式字符串）并保存到文件
        
        Args:
            screen_data: 可选的屏幕数据，如果提供则直接使用
        """
        try:
            # 如果已经提供了screen_data，直接使用
            if screen_data:
                # screen_data可能是bytes或str，需要转换为str
                if isinstance(screen_data, bytes):
                    base64_str = screen_data.decode('utf-8')
                else:
                    base64_str = screen_data
                # 保存截图到文件
                self._save_screenshot_to_file(base64_str)
                return screen_data
            # 否则主动捕获
            screenshot_data = self.screen_capture.capture_screen(self.device_address)
            if screenshot_data:
                # screenshot_data是bytes，需要解码为str
                if isinstance(screenshot_data, bytes):
                    base64_str = screenshot_data.decode('utf-8')
                else:
                    base64_str = screenshot_data
                # 保存截图到文件
                self._save_screenshot_to_file(base64_str)
                return screenshot_data
        except Exception as e:
            self.logger.error(LogCategory.MAIN, f"截图失败: {e}")
        return None
    
    def _save_screenshot_to_file(self, base64_data: str) -> bool:
        """将Base64截图数据保存到文件
        
        Args:
            base64_data: Base64编码的截图数据
            
        Returns:
            是否保存成功
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            task_name_safe = self._safe_filename(self.current_task_name)
            
            # 保存截图
            screenshot_filename = f"{timestamp}_{task_name_safe}.png"
            screenshot_path = os.path.join(self.output_dir, screenshot_filename)
            
            # 解码Base64并保存
            image_data = base64.b64decode(base64_data)
            with open(screenshot_path, 'wb') as f:
                f.write(image_data)
            
            # 记录截图信息
            screenshot_info = {
                "timestamp": timestamp,
                "datetime": datetime.now().isoformat(),
                "task_name": self.current_task_name,
                "task_variables": self.current_task_variables.copy(),
                "screenshot_file": screenshot_filename
            }
            self.screenshot_data_list.append(screenshot_info)
            
            # 更新JSON描述文件
            self._update_description_json()
            
            self.logger.info(LogCategory.MAIN, f"截图已保存: {screenshot_filename}")
            return True
            
        except Exception as e:
            self.logger.error(LogCategory.MAIN, f"保存截图失败: {e}")
            return False
    
    def _safe_filename(self, name: str) -> str:
        """将字符串转换为安全的文件名"""
        if not name:
            return "unknown"
        # 替换不安全的字符
        safe_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in name)
        return safe_name[:50]  # 限制长度
    
    def _update_description_json(self):
        """更新任务描述JSON文件"""
        try:
            description = {
                "run_start_time": self.run_start_time,
                "device_address": self.device_address,
                "screenshot_interval": self.screenshot_interval,
                "screenshots": self.screenshot_data_list
            }
            
            json_path = os.path.join(self.output_dir, "task_description.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(description, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.error(LogCategory.MAIN, f"更新描述文件失败: {e}")
    
    def set_task_chain(self, tasks: List[Dict[str, Any]]):
        """
        设置任务链
        
        Args:
            tasks: 任务列表，每个任务包含 id, name, variables
        """
        self.task_queue_manager.clear_queue()
        
        for task in tasks:
            task_info = {
                'id': task.get('id'),
                'name': task.get('name', task.get('id')),
                'custom_variables': task.get('variables', {})
            }
            self.task_queue_manager.add_task(task_info)
        
        self.logger.info(LogCategory.MAIN, f"任务链设置完成，共 {len(tasks)} 个任务")
    
    def load_task_from_file(self, task_file: str) -> Dict[str, Any]:
        """从文件加载任务定义"""
        if os.path.exists(task_file):
            with open(task_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def run(self, execution_count: int = 1) -> bool:
        """
        运行任务链 - 使用ExecutionManager统一执行逻辑
        
        Args:
            execution_count: 执行次数，-1表示无限循环
            
        Returns:
            是否成功完成
        """
        if not self.execution_manager:
            self.logger.error(LogCategory.MAIN, "执行管理器未初始化")
            return False
        
        self.running = True
        self.run_start_time = datetime.now().isoformat()
        
        # 配置ExecutionManager的CLI模式
        self.execution_manager.set_cli_mode(
            enabled=True,
            screenshot_callback=self._capture_screenshot,
            output_dir=self.output_dir
        )
        
        # 定义日志回调
        def log_callback(message: str, category: str, level: str):
            if level == "ERROR":
                self.logger.error(LogCategory.MAIN, message)
            elif level == "WARNING":
                self.logger.warning(LogCategory.MAIN, message)
            else:
                self.logger.info(LogCategory.MAIN, message)
        
        try:
            # 使用ExecutionManager的CLI执行方法
            success = self.execution_manager.run_cli_automation(
                log_callback=log_callback,
                execution_count=execution_count,
                control_scheme="ADB",
                window_title=self.device_address
            )
            
            # 获取截图数据
            self.screenshot_data_list = self.execution_manager.get_cli_screenshot_data()
            
            self.logger.info(LogCategory.MAIN, "任务链执行结束")
            return success
            
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, f"执行异常: {e}")
            return False
        finally:
            self.running = False
    
    def stop(self):
        """停止运行"""
        self.running = False
        if self.execution_manager:
            self.execution_manager.client_running = False


def load_task_definitions(task_ids: List[str]) -> List[Dict[str, Any]]:
    """从服务器任务目录加载任务定义"""
    tasks = []
    server_task_dir = os.path.join(project_root, "server", "server", "data", "tasks")
    
    for task_id in task_ids:
        task_file = os.path.join(server_task_dir, f"{task_id}.json")
        if os.path.exists(task_file):
            with open(task_file, 'r', encoding='utf-8') as f:
                task_def = json.load(f)
                tasks.append({
                    'id': task_def.get('id', task_id),
                    'name': task_def.get('name', task_id),
                    'description': task_def.get('description', ''),
                    'variables': {}
                })
        else:
            print(f"警告: 任务文件不存在: {task_file}")
            tasks.append({
                'id': task_id,
                'name': task_id,
                'variables': {}
            })
    
    return tasks


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='CLI调试运行脚本 - 安卓设备任务链执行')
    parser.add_argument('--api-key', '-k', required=True, help='用户API密钥')
    parser.add_argument('--user-id', '-u', required=True, help='用户ID')
    parser.add_argument('--tasks', '-t', required=True, help='任务ID列表，逗号分隔（按顺序执行）')
    parser.add_argument('--server-host', '-H', default='127.0.0.1', help='服务器地址')
    parser.add_argument('--server-port', '-p', type=int, default=9999, help='服务器端口')
    parser.add_argument('--device-address', '-d', default='127.0.0.1:16512', help='安卓设备地址')
    parser.add_argument('--output-dir', '-o', default=None, help='输出目录')
    parser.add_argument('--screenshot-interval', '-i', type=float, default=1.0, help='截图间隔（秒）')
    parser.add_argument('--execution-count', '-n', type=int, default=1, 
                       help='执行次数，-1表示无限循环')
    parser.add_argument('--variables', '-v', default=None, 
                       help='任务变量，JSON格式字符串，例如: \'{"task_id": {"变量名": "值"}}\'')
    
    args = parser.parse_args()
    
    # 解析任务列表
    task_ids = [t.strip() for t in args.tasks.split(',')]
    
    # 加载任务定义
    tasks = load_task_definitions(task_ids)
    
    # 解析任务变量
    if args.variables:
        try:
            variables = json.loads(args.variables)
            # 应用变量到对应任务
            for task in tasks:
                if task['id'] in variables:
                    task['variables'] = variables[task['id']]
        except json.JSONDecodeError as e:
            print(f"变量解析失败: {e}")
            return 1
    
    # 创建运行器
    runner = CLIDebugRunnerAndroid(
        api_key=args.api_key,
        user_id=args.user_id,
        server_host=args.server_host,
        server_port=args.server_port,
        device_address=args.device_address,
        output_dir=args.output_dir,
        screenshot_interval=args.screenshot_interval
    )
    
    # 初始化
    if not runner.init_components():
        print("初始化失败")
        return 1
    
    # 设置任务链
    runner.set_task_chain(tasks)
    
    # 运行
    print(f"开始执行任务链，输出目录: {runner.output_dir}")
    success = runner.run(execution_count=args.execution_count)
    
    print(f"任务链执行{'成功' if success else '失败'}")
    print(f"输出目录: {runner.output_dir}")
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())