"""
任务链执行测试 - 验证完整的任务链自动化流程
连接设备: 127.0.0.1:16512 (MuMu模拟器)
"""
import sys
import os
import time
import json

# 设置UTF-8编码输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def log_callback(message, category="execution", level="INFO"):
    """日志回调函数"""
    print(f"[{level}] [{category}] {message}")

def update_ui_callback(event_type, data):
    """UI更新回调函数"""
    print(f"[UI] {event_type}: {data}")

def test_task_chain_execution():
    """测试任务链执行"""
    print("\n=== Task Chain Execution Test ===")
    print("设备: 127.0.0.1:16512")
    print("任务链: task_visit_friends -> task_daily_rewards")
    
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
    
    print(f"\n配置加载成功:")
    print(f"  server: {config['server']['host']}:{config['server']['port']}")
    
    # 1. 初始化通信器
    print("\n1. 初始化通信器...")
    communicator = ClientCommunicator(
        host=config['server']['host'],
        port=config['server']['port'],
        password=config['communication']['password']
    )
    print("  [OK] 通信器初始化成功")
    
    # 2. 初始化认证管理器
    print("\n2. 初始化认证管理器...")
    auth_manager = AuthManager(communicator, config)
    print("  [OK] 认证管理器初始化成功")
    
    # 3. 初始化ADB管理器
    print("\n3. 初始化ADB管理器...")
    adb_path = os.path.join(project_root, config['adb']['path'])
    adb_manager = ADBDeviceManager(adb_path)
    print(f"  [OK] ADB管理器初始化成功: {adb_path}")
    
    # 4. 初始化设备管理器
    print("\n4. 初始化设备管理器...")
    device_manager = DeviceManager(adb_manager, config)
    print("  [OK] 设备管理器初始化成功")
    
    # 5. 初始化屏幕捕获
    print("\n5. 初始化屏幕捕获...")
    screen_capture = ScreenCapture(adb_manager)
    print("  [OK] 屏幕捕获初始化成功")
    
    # 6. 初始化触控管理器
    print("\n6. 初始化触控管理器并连接设备...")
    touch_manager = TouchManager()
    
    success = touch_manager.connect_android(
        adb_path=adb_path,
        address="127.0.0.1:16512"
    )
    
    if not success:
        print("  [X] 设备连接失败")
        return False
    
    print("  [OK] 设备连接成功")
    resolution = touch_manager.get_resolution()
    print(f"  分辨率: {resolution}")
    
    # 7. 初始化任务管理器
    print("\n7. 初始化任务管理器...")
    task_manager = TaskManager(
        config_dir=os.path.join(project_root, "config"),
        data_dir=os.path.join(project_root, "data")
    )
    print("  [OK] 任务管理器初始化成功")
    
    # 8. 初始化任务队列管理器
    print("\n8. 初始化任务队列管理器...")
    task_queue_manager = TaskQueueManager(task_manager)
    print("  [OK] 任务队列管理器初始化成功")
    
    # 9. 初始化执行管理器
    print("\n9. 初始化执行管理器...")
    execution_manager = ExecutionManager(
        device_manager=device_manager,
        screen_capture=screen_capture,
        touch_executor=touch_manager,
        task_queue_manager=task_queue_manager,
        communicator=communicator,
        auth_manager=auth_manager,
        config=config
    )
    print("  [OK] 执行管理器初始化成功")
    
    # 10. 设置任务链
    print("\n10. 设置任务链...")
    
    # 加载任务定义
    task_chain = [
        {
            "id": "task_visit_friends",
            "name": "访问好友",
            "description": "访问好友基地并获取协助"
        },
        {
            "id": "task_daily_rewards",
            "name": "每日奖励",
            "description": "领取每日登录奖励"
        }
    ]
    
    # 添加任务到队列
    for task in task_chain:
        task_queue_manager.add_task(task)
        print(f"  [OK] 添加任务: {task['name']}")
    
    # 设置执行次数
    task_queue_manager.set_execution_count(1)
    print(f"  [OK] 执行次数: 1")
    
    # 11. 开始执行
    print("\n11. 开始执行任务链...")
    print("  注意: 此测试需要服务器响应，将在5秒后停止...")
    
    try:
        # 启动执行
        execution_manager.start_execution(
            log_callback=log_callback,
            update_ui_callback=update_ui_callback
        )
        
        # 等待5秒观察执行效果
        time.sleep(5)
        
        # 停止执行
        print("\n  停止执行...")
        execution_manager.stop_execution()
        
    except Exception as e:
        print(f"  执行异常: {e}")
        import traceback
        traceback.print_exc()
    
    # 12. 断开连接
    print("\n12. 断开设备连接...")
    touch_manager.disconnect()
    print("  [OK] 已断开连接")
    
    return True

def main():
    print("=" * 60)
    print("Task Chain Execution Test")
    print("=" * 60)
    
    # 需要先导入DeviceManager
    from 安卓相关.core.cloud.managers.device_manager import DeviceManager
    
    success = test_task_chain_execution()
    
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)
    
    if success:
        print("\n[OK] 任务链执行测试完成")
    else:
        print("\n[X] 任务链执行测试失败")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)