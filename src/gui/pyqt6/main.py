"""
IstinaEndfieldAssistant Client GUI - PyQt6 Version
"""
import sys
import os
import json
from utils.paths import ensure_src_path

# Force stdio to be unbuffered for immediate output
sys.stdout.reconfigure(line_buffering=True)

ensure_src_path(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

print("[导入] 正在导入依赖模块...")

# Import business logic modules
from core.logger import init_logger, get_logger, LogCategory, LogLevel
from device.adb_manager import ADBDeviceManager
from screenshot.screen_capture import ScreenCapture
from device.touch import TouchManager, TouchDeviceType
from core.communication.communicator import ClientCommunicator
from core.cloud.managers.auth_manager import AuthManager
from core.cloud.managers.device_manager import DeviceManager

print("[导入] 所有依赖模块导入成功")

# 打印项目根目录用于调试
print(f"[启动] 项目根目录：{project_root}")


def load_config(config_file: str) -> dict:
    """Load configuration file from project root only."""
    # 统一使用项目根目录作为配置文件唯一位置
    config_path = os.path.join(project_root, config_file)
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[警告] 配置文件读取失败：{config_path}, 错误：{e}")
            print("[提示] 将使用默认配置")
    # 配置文件不存在或读取失败时返回默认配置
    # 默认配置包含所有必需字段，确保配置完整性
    return {
            "server": {"host": "127.0.0.1", "port": 9999},
            "adb": {"path": "IstinaEndfieldAssistant/3rd-party/adb/adb.exe", "timeout": 10},
            "git": {"path": "IstinaEndfieldAssistant/3rd-party/git/bin/git.exe"},
            "screen": {"use_original_resolution": True},
            "touch": {
                "maa_style": {
                    "enabled": True,
                    "press_duration_ms": 50,
                    "press_jitter_px": 2,
                    "swipe_delay_min_ms": 100,
                    "swipe_delay_max_ms": 300,
                    "use_normalized_coords": True
                },
                "fail_on_error": True
            },
            "communication": {"password": "default_password"},
            "client": {
                "client_name": "IEA_Client",
                "registered": False
            },
            "inference": {
                "mode": "auto",
                "local_inference_enabled": False,
                "local": {"enabled": False, "model_name": "", "gpu_layers": -1}
            },
            "first_run": {
                "local_inference_prompt_shown": False,
                "user_choice": "cloud"
            },
            "security": {
                "enable_safe_press": True,
                "enable_jitter": True
            },
            "system": {
                "minimize_to_tray": False
            },
            "rendering": {
                "hardware_acceleration": True,
                "vsync": True,
                "animation_enabled": True
            }
        }


def main():
    """Main function - Start PyQt6 GUI application"""
    
    print("=" * 70)
    print("伊丝蒂娜·终末地助手 - 启动中")
    print("=" * 70)
    
    # 初始化日志系统
    print("[主进程] 初始化日志系统...")
    init_logger()
    logger = get_logger()
    
    logger.info(LogCategory.MAIN, "IstinaEndfieldAssistant 客户端已启动（代理模式）")
    
    # 加载配置
    print("[主进程] 加载配置...")
    config = load_config("config/client_config.json")
    logger.debug(LogCategory.MAIN, "配置文件加载成功")
    print(f"[主进程] 配置加载成功")
    
    try:
        # 初始化核心功能模块

        # ADB 路径 - 使用 normpath 处理混合路径分隔符
        adb_path = os.path.normpath(os.path.join(project_root, config['adb']['path']))

        if not os.path.exists(adb_path):
            logger.error(LogCategory.MAIN, f"ADB 可执行文件不存在: {adb_path}")
            print(f"[错误] ADB 可执行文件不存在: {adb_path}")
            return 1
        
        print("[主进程] 初始化核心模块（ADB、截屏、触控管理器）...")
        logger.debug(LogCategory.MAIN, "初始化 ADB 设备管理器", adb_path=adb_path)
        adb_manager = ADBDeviceManager(
            adb_path=adb_path,
            timeout=config['adb']['timeout']
        )
        
        logger.debug(LogCategory.MAIN, "初始化截屏模块")
        screen_capture = ScreenCapture(adb_manager=adb_manager)
        
        logger.debug(LogCategory.MAIN, "初始化触控管理器")
        touch_executor = TouchManager()

        logger.debug(LogCategory.MAIN, "关联截屏模块和 MAA 触控管理器")
        screen_capture.set_touch_manager(touch_executor)

        logger.debug(LogCategory.MAIN, "初始化通信模块")
        communicator = ClientCommunicator(
            host=config['server']['host'],
            port=config['server']['port'],
            password=config.get('communication', {}).get('password', 'default_password'),
            timeout=300
        )

        # 初始化推理管理器（端侧优先）
        logger.debug(LogCategory.MAIN, "初始化推理管理器")
        from core.local_inference.inference_manager import InferenceManager
        inference_manager = InferenceManager(
            config=config,
            communicator=communicator,
            models_dir=os.path.join(project_root, "models")
        )
        logger.info(LogCategory.MAIN, "推理管理器初始化完成",
                   local_available=inference_manager.is_local_available())

        # 初始化业务逻辑组件
        logger.debug(LogCategory.MAIN, "初始化认证管理模块")
        auth_manager = AuthManager(communicator, config)
        
        logger.debug(LogCategory.MAIN, "初始化设备管理模块")
        device_manager = DeviceManager(adb_manager, config)
        
        last_device = device_manager.get_last_connected_device()
        if last_device:
            logger.info(LogCategory.MAIN, f"尝试自动连接上次设备：{last_device}")
            device_manager.connect_device(last_device)
        
        logger.info(LogCategory.MAIN, "所有组件初始化成功")
        print("[主进程] 核心模块全部初始化成功")
        
    except Exception as e:
        logger.exception(LogCategory.MAIN, "管理器初始化失败", exc_info=True)
        print(f"[错误] 管理器初始化失败: {e}")
        return 1
    
    # 启动 PyQt6 应用
    from gui.pyqt6.app_main import run_application
    
    print(f"\n[主进程] 启动 PyQt6 应用程序...")
    
    try:
        from core.cloud.agent_executor import AgentExecutor
        
        logger.debug(LogCategory.MAIN, "初始化代理执行器")
        agent_executor = AgentExecutor(
            communicator=communicator,
            screen_capture=screen_capture,
            touch_executor=touch_executor,
            config=config,
            inference_manager=inference_manager
        )

        print(f"[主进程] 调用 run_application() - 窗口即将显示...")
        exit_code = run_application(
            auth_manager=auth_manager,
            device_manager=device_manager,
            agent_executor=agent_executor,
            communicator=communicator,
            screen_capture=screen_capture,
            touch_executor=touch_executor,
            config=config,
            inference_manager=inference_manager
        )
        
        logger.info(LogCategory.MAIN, f"应用程序退出，退出码: {exit_code}")
        print(f"[主进程] 应用程序退出，退出码: {exit_code}")
        return exit_code
        
    except Exception as e:
        logger.exception(LogCategory.MAIN, "应用程序启动失败", exc_info=True)
        print(f"[错误] 应用程序启动失败: {e}")
        return 1


if __name__ == "__main__":
    import json
    sys.exit(main())