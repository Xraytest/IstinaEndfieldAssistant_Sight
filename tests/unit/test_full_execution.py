# -*- coding: utf-8 -*-
"""
完整执行流程测试 - 测试任务链执行和触控操作
"""
import sys
import os
import json
import time

# 设置路径
istina_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
安卓相关_dir = os.path.join(istina_root, "安卓相关")
入口_dir = os.path.join(istina_root, "入口")

if 安卓相关_dir not in sys.path:
    sys.path.insert(0, 安卓相关_dir)
if 入口_dir not in sys.path:
    sys.path.insert(0, 入口_dir)

print("=== 完整执行流程测试 ===")

# 1. 测试TouchManager连接和触控操作
print("\n=== 测试1: TouchManager触控操作 ===")
from 控制.touch.touch_manager import TouchManager
from 控制.adb_manager import ADBDeviceManager

adb_path = os.path.join(istina_root, "3rd-part", "ADB", "adb.exe")
if not os.path.exists(adb_path):
    adb_path = "adb"

target_address = "127.0.0.1:16512"

# 创建TouchManager
touch_manager = TouchManager()

# 连接设备
print(f"连接设备 {target_address}...")
result = touch_manager.connect_android(
    adb_path=adb_path,
    address=target_address
)
print(f"连接结果: {result}, 状态: {touch_manager.connected}")

if touch_manager.connected:
    # 获取分辨率
    resolution = touch_manager.get_resolution()
    print(f"分辨率: {resolution}")
    
    # 测试截图
    print("\n测试截图...")
    image = touch_manager.screencap()
    if image is not None:
        print(f"截图成功: type={type(image)}, shape={image.shape}")
    else:
        print("截图失败")
    
    # 测试点击操作（点击屏幕中心）
    print("\n测试点击操作...")
    center_x = resolution[0] // 2
    center_y = resolution[1] // 2
    click_result = touch_manager.safe_press(center_x, center_y, duration=50)
    print(f"点击({center_x}, {center_y})结果: {click_result}")
    
    # 等待一下
    time.sleep(1)
    
    # 测试滑动操作
    print("\n测试滑动操作...")
    swipe_result = touch_manager.safe_swipe(
        center_x, center_y + 100,
        center_x, center_y - 100,
        duration=300
    )
    print(f"滑动结果: {swipe_result}")
    
    time.sleep(1)
    
    # 再次截图确认操作效果
    print("\n再次截图确认...")
    image2 = touch_manager.screencap()
    if image2 is not None:
        print(f"截图成功: shape={image2.shape}")
    
    # 断开连接
    print("\n断开连接...")
    touch_manager.disconnect()
    print(f"断开后状态: {touch_manager.connected}")

else:
    print("TouchManager连接失败，跳过触控测试")

# 2. 测试ExecutionManager完整流程
print("\n=== 测试2: ExecutionManager完整流程 ===")
from core.cloud.managers.execution_manager import ExecutionManager
from core.cloud.managers.device_manager import DeviceManager
from core.cloud.managers.task_queue_manager import TaskQueueManager
from core.cloud.managers.auth_manager import AuthManager
from core.cloud.task_manager import TaskManager
from core.communication.communicator import ClientCommunicator
from 图像传递.screen_capture import ScreenCapture

# 加载配置
config_path = os.path.join(istina_root, "config", "client_config.json")
with open(config_path, 'r', encoding='utf-8') as f:
    client_config = json.load(f)

# 创建通信器
communicator = ClientCommunicator(
    host=client_config['server']['host'],
    port=client_config['server']['port'],
    password=client_config.get('communication', {}).get('password', 'default_password')
)

# 创建认证管理器
auth_manager = AuthManager(communicator, client_config)

# 尝试自动登录
print("尝试自动登录...")
arkpass_path = os.path.join(istina_root, "data", "testis.arkpass")
if os.path.exists(arkpass_path):
    login_result = auth_manager.auto_login_with_arkpass(arkpass_path)
    print(f"登录结果: {login_result}")
else:
    print(f"ArkPass文件不存在: {arkpass_path}")

# 创建ADB管理器
adb_manager = ADBDeviceManager(adb_path)

# 创建设备管理器
device_manager = DeviceManager(adb_manager, client_config)

# 创建屏幕捕获
screen_capture = ScreenCapture(adb_manager)

# 创建任务管理器
task_manager = TaskManager(
    config_dir=os.path.join(istina_root, "config"),
    data_dir=os.path.join(istina_root, "data")
)

# 创建任务队列管理器
task_queue_manager = TaskQueueManager(task_manager)

# 加载任务定义
print("\n加载任务定义...")
platform_tasks_dir = os.path.join(os.path.dirname(istina_root), "IstinaPlatform", "storage", "service_data", "tasks")
if os.path.exists(platform_tasks_dir):
    task_files = [f for f in os.listdir(platform_tasks_dir) if f.startswith("task_") and f.endswith(".json")]
    print(f"发现 {len(task_files)} 个任务文件")
    
    # 加载几个任务到队列
    for task_file in task_files[:3]:
        task_path = os.path.join(platform_tasks_dir, task_file)
        with open(task_path, 'r', encoding='utf-8') as f:
            task_def = json.load(f)
        task_queue_manager.add_task(task_def)
        print(f"  添加任务: {task_def.get('task_id', task_file)}")

# 创建触控执行器（使用TouchManager）
touch_executor = TouchManager()

# 创建执行管理器
print("\n创建ExecutionManager...")
execution_manager = ExecutionManager(
    device_manager=device_manager,
    screen_capture=screen_capture,
    touch_executor=touch_executor,
    task_queue_manager=task_queue_manager,
    communicator=communicator,
    auth_manager=auth_manager,
    config=client_config
)
print("ExecutionManager创建成功")

# 设置执行次数
task_queue_manager.set_execution_count(1)
print(f"执行次数: {task_queue_manager.execution_count}")

# 获取队列信息
queue_info = task_queue_manager.get_queue_info()
print(f"队列信息: {queue_info}")

# 3. 测试CLI模式运行
print("\n=== 测试3: CLI模式运行测试 ===")
# 注意：CLI目录名使用连字符(cli-method)，Python不支持直接导入，需要使用importlib
import importlib.util
cli_method_dir = os.path.join(入口_dir, "CLI", "cli-method")
debug_running_path = os.path.join(cli_method_dir, "debug_running.py")

if os.path.exists(debug_running_path):
    spec = importlib.util.spec_from_file_location("debug_running", debug_running_path)
    debug_running_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(debug_running_module)
    CLIDebugRunner = debug_running_module.CLIDebugRunner
    print("CLI模块动态导入成功")
else:
    print(f"CLI模块文件不存在: {debug_running_path}")
    CLIDebugRunner = None

if CLIDebugRunner:
    # 创建CLI运行器 - 使用正确的参数签名
    # CLIDebugRunner(api_key, user_id, server_host, server_port, control_scheme, ...)
    print("创建CLIDebugRunner实例...")
    cli_runner = CLIDebugRunner(
        api_key="",  # 需要API密钥
        user_id="test_user",  # 测试用户ID
        server_host=client_config['server']['host'],
        server_port=client_config['server']['port'],
        control_scheme="ADB"  # 使用ADB控制方案
    )
    print("CLIDebugRunner实例创建成功")

    # 初始化组件
    print("初始化CLI组件...")
    init_result = cli_runner.init_components()
    print(f"初始化结果: {init_result}")

    if init_result:
        # 设置任务链
        print("\n设置任务链...")
        task_chain = []
        for task_file in task_files[:2]:
            task_path = os.path.join(platform_tasks_dir, task_file)
            task_def = cli_runner.load_task_from_file(task_path)
            if task_def:
                task_chain.append(task_def)
        
        cli_runner.set_task_chain(task_chain)
        print(f"任务链设置完成，共 {len(task_chain)} 个任务")
        
        # 注意：实际运行需要VLM服务端支持，这里只测试设置
        print("\n注意: 实际执行需要VLM服务端支持，此处仅测试初始化和设置")
    else:
        print("CLI组件初始化失败")
else:
    print("CLIDebugRunner导入失败，跳过CLI测试")

print("\n=== 测试完成 ===")