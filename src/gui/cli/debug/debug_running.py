"""
CLI方法 - 任务链调试运行脚本
与GUI方法共用同一套执行代码，差异仅为调用方式
支持命令行指定任务及其顺序、api_key、触控方案
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
cli_dir = os.path.dirname(current_dir)
entry_dir = os.path.dirname(cli_dir)
project_root = os.path.dirname(entry_dir)
src_dir = os.path.join(project_root, "src")

# 添加必要的路径到sys.path
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入核心组件（使用重构后的路径）
from core.foundation.logger import init_logger, get_logger, LogCategory, LogLevel
from core.capability.device.adb_manager import ADBDeviceManager
from core.capability.screenshot.screen_capture import ScreenCapture
from core.capability.device.touch.touch_manager import TouchManager
from core.capability.device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig

# PC设备支持 - 使用MaaFramework库
PC_CONTROLLER_AVAILABLE = False
try:
    from core.capability.device.touch.maafw_win32_adapter import MaaFwWin32Executor, MaaFwWin32Config
    from maa.define import MaaWin32ScreencapMethodEnum, MaaWin32InputMethodEnum
    PC_CONTROLLER_AVAILABLE = True
except ImportError:
    pass


class CLIDebugRunner:
    """CLI调试运行器 - 复用ExecutionManager执行逻辑"""
    
    def __init__(self,
                 api_key: str,
                 user_id: str,
                 server_host: str = "127.0.0.1",
                 server_port: int = 9999,
                 control_scheme: str = "Win32-Window",
                 window_title: str = "Endfield",
                 output_dir: str = None,
                 screenshot_interval: float = 1.0):
        """
        初始化CLI调试运行器
        
        Args:
            api_key: 用户API密钥
            user_id: 用户ID
            server_host: 服务器地址
            server_port: 服务器端口
            control_scheme: 触控方案 (Win32-Window, Win32-Express, Win32-Front)
            window_title: PC窗口标题
            output_dir: 输出目录
            screenshot_interval: 截图间隔（秒）
        """
        self.api_key = api_key
        self.user_id = user_id
        self.server_host = server_host
        self.server_port = server_port
        self.control_scheme = control_scheme
        self.window_title = window_title
        self.screenshot_interval = screenshot_interval
        
        # 设置输出目录
        if output_dir:
            self.output_dir = output_dir
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_dir = os.path.join(project_root, "debug_output", f"run_{timestamp}")
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 初始化日志
        log_config_path = os.path.join(project_root, "config", "logging_config.json")
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
        
        # PC控制器（MaaFramework）
        self.pc_controller: Optional[MaaFwWin32Executor] = None
        
        # 运行状态
        self.running = False
        self.current_task_name = ""
        self.current_task_variables = {}
        
        # 截图数据（由ExecutionManager管理）
        self.screenshot_data_list: List[Dict[str, Any]] = []
        
    def init_components(self) -> bool:
        """初始化所有组件"""
        try:
            self.logger.info(LogCategory.MAIN, "CLI调试运行器初始化开始")
            
            # 加载配置
            config = self._load_config()
            
            # 初始化通信模块
            self.communicator = ClientCommunicator(
                host=self.server_host,
                port=self.server_port,
                password=config.get('communication', {}).get('password', 'default_password'),
                timeout=300
            )
            
            # 初始化认证管理模块
            self.auth_manager = AuthManager(self.communicator, config)
            
            # 设置登录状态（使用提供的api_key）
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
            # 注意: DeviceManager 没有 set_pc_mode 等方法，PC模式配置需要通过其他方式处理
            
            # 初始化任务管理模块
            self.task_manager = TaskManager(
                config_dir=os.path.join(project_root, "config"),
                data_dir=os.path.join(project_root, "data")
            )
            
            # 初始化任务队列管理模块
            self.task_queue_manager = TaskQueueManager(self.task_manager)
            
            # 初始化屏幕捕获模块（PC模式不需要ADB）
            self.screen_capture = None  # PC模式使用Win32Controller捕获
            
            # 初始化触控执行模块（PC模式不需要）
            self.touch_executor = None
            
            # 初始化执行管理模块
            # 注意：ExecutionManager通过config中的touch_method来识别PC模式
            pc_config = config.copy()
            pc_config['touch'] = {'touch_method': 'pc_foreground'}
            self.execution_manager = ExecutionManager(
                self.device_manager,
                self.screen_capture,
                self.touch_executor,
                self.task_queue_manager,
                self.communicator,
                self.auth_manager,
                config=pc_config
            )
            
            # 初始化PC控制器
            if not self._init_pc_controller():
                self.logger.error(LogCategory.MAIN, "PC控制器初始化失败")
                return False
            
            self.logger.info(LogCategory.MAIN, "CLI调试运行器初始化完成")
            return True
            
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, f"初始化异常: {e}")
            return False
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        config_path = os.path.join(project_root, "config", "client_config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {
                "server": {"host": self.server_host, "port": self.server_port},
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
    
    def _init_pc_controller(self) -> bool:
        """初始化PC控制器（使用MaaFramework库）"""
        if not PC_CONTROLLER_AVAILABLE:
            self.logger.error(LogCategory.MAIN, "PC控制器不可用（MaaFwWin32Executor未安装）")
            return False
        
        try:
            # 根据触控方案创建配置
            if self.control_scheme == "Win32-Window":
                config = MaaFwWin32Config(
                    screencap_method=MaaWin32ScreencapMethodEnum.GDI,
                    mouse_method=MaaWin32InputMethodEnum.SendMessage,
                    keyboard_method=MaaWin32InputMethodEnum.SendMessage
                )
            elif self.control_scheme == "Win32-Express":
                config = MaaFwWin32Config(
                    screencap_method=MaaWin32ScreencapMethodEnum.GDI,
                    mouse_method=MaaWin32InputMethodEnum.PostMessage,
                    keyboard_method=MaaWin32InputMethodEnum.PostMessage
                )
            elif self.control_scheme == "Win32-Front":
                config = MaaFwWin32Config(
                    screencap_method=MaaWin32ScreencapMethodEnum.DXGI_DesktopDup,
                    mouse_method=MaaWin32InputMethodEnum.Seize,
                    keyboard_method=MaaWin32InputMethodEnum.Seize
                )
            else:
                config = MaaFwWin32Config(
                    screencap_method=MaaWin32ScreencapMethodEnum.DXGI_DesktopDup,
                    mouse_method=MaaWin32InputMethodEnum.Seize,
                    keyboard_method=MaaWin32InputMethodEnum.Seize
                )
            
            self.pc_controller = MaaFwWin32Executor(config)
            
            # 连接到游戏窗口
            target_window = self.window_title
            if self.pc_controller.connect(window_title=target_window):
                self.logger.info(LogCategory.MAIN,
                               f"PC控制器连接成功（MaaFramework）: {target_window} ({self.control_scheme})")
                return True
            else:
                self.logger.error(LogCategory.MAIN,
                                f"PC控制器连接失败: 未找到窗口 '{target_window}'")
                return False
                
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, f"PC控制器初始化异常: {e}")
            return False
    
    def _capture_screenshot(self) -> Optional[bytes]:
        """捕获屏幕截图"""
        if self.pc_controller:
            try:
                # 使用Win32Controller捕获屏幕
                image_data = self.pc_controller.screencap()
                if image_data:
                    # 如果返回的是PIL Image，转换为bytes
                    if hasattr(image_data, 'save'):
                        import io
                        buffer = io.BytesIO()
                        image_data.save(buffer, format='PNG')
                        return buffer.getvalue()
                    return image_data
            except Exception as e:
                self.logger.error(LogCategory.MAIN, f"截图失败: {e}")
        return None
    
    def _screenshot_worker(self):
        """截图工作线程"""
        last_capture_time = 0
        
        while self.screenshot_running and self.running:
            current_time = time.time()
            
            # 按指定间隔截图
            if current_time - last_capture_time >= self.screenshot_interval:
                last_capture_time = current_time
                
                try:
                    screenshot_data = self._capture_screenshot()
                    if screenshot_data:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        task_name_safe = self._safe_filename(self.current_task_name)
                        
                        # 保存截图
                        screenshot_filename = f"{timestamp}_{task_name_safe}.png"
                        screenshot_path = os.path.join(self.output_dir, screenshot_filename)
                        
                        with open(screenshot_path, 'wb') as f:
                            f.write(screenshot_data)
                        
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
                        
                except Exception as e:
                    self.logger.error(LogCategory.MAIN, f"截图线程异常: {e}")
            
            time.sleep(0.1)  # 避免CPU占用过高
    
    def _safe_filename(self, name: str) -> str:
        """生成安全的文件名"""
        import re
        # 替换不安全字符
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', name)
        return safe_name[:50] if len(safe_name) > 50 else safe_name
    
    def _update_description_json(self):
        """更新描述JSON文件"""
        description_path = os.path.join(self.output_dir, "task_description.json")
        
        description = {
            "run_start_time": self.run_start_time,
            "control_scheme": self.control_scheme,
            "window_title": self.window_title,
            "screenshot_interval": self.screenshot_interval,
            "screenshots": self.screenshot_data_list
        }
        
        with open(description_path, 'w', encoding='utf-8') as f:
            json.dump(description, f, ensure_ascii=False, indent=2)
    
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
        
        # 设置PC控制器到ExecutionManager
        self.execution_manager.pc_controller = self.pc_controller
        
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
                control_scheme=self.control_scheme,
                window_title=self.window_title
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
    parser = argparse.ArgumentParser(description='CLI调试运行脚本 - 任务链执行')
    parser.add_argument('--api-key', '-k', required=True, help='用户API密钥')
    parser.add_argument('--user-id', '-u', required=True, help='用户ID')
    parser.add_argument('--tasks', '-t', required=True, help='任务ID列表，逗号分隔（按顺序执行）')
    parser.add_argument('--server-host', '-H', default='127.0.0.1', help='服务器地址')
    parser.add_argument('--server-port', '-p', type=int, default=9999, help='服务器端口')
    parser.add_argument('--control-scheme', '-c',
                       choices=['Win32-Window', 'Win32-Express', 'Win32-Front'],
                       default='Win32-Front', help='触控方案（默认使用前台方案）')
    parser.add_argument('--window-title', '-w', default='Endfield', help='PC窗口标题 (硬编码为 Endfield)')
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
    runner = CLIDebugRunner(
        api_key=args.api_key,
        user_id=args.user_id,
        server_host=args.server_host,
        server_port=args.server_port,
        control_scheme=args.control_scheme,
        window_title=args.window_title,
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