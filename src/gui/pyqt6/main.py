"""
IstinaEndfieldAssistant Client GUI - PyQt6 Version
"""
import sys
import os
import json

# 先将 src/ 加入 sys.path，确保内部模块可导入
_src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from core.foundation.paths import ensure_src_path

# Force stdio to be unbuffered for immediate output
sys.stdout.reconfigure(line_buffering=True)

ensure_src_path(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

print("[导入] 正在导入依赖模块...")

# Import business logic modules
from core.foundation.logger import init_logger, get_logger, LogCategory, LogLevel
from core.capability.device.adb_manager import ADBDeviceManager
from core.capability.input.screenshot import ScreenCapture
from core.capability.device.touch import TouchManager, TouchDeviceType

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
            "adb": {"path": "3rd-part/adb/adb.exe", "timeout": 10},
            "git": {"path": "3rd-part/git/bin/git.exe"},
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

        # ADB 路径 - 使用 core.foundation.paths 统一管理
        from core.foundation.paths import get_adb_path
        adb_path = get_adb_path()

        if not os.path.exists(adb_path):
            logger.error(LogCategory.MAIN, f"ADB 可执行文件不存在: {adb_path}")
            print(f"[错误] ADB 可执行文件不存在: {adb_path}")
            return 1

        print("[主进程] 初始化核心模块（ADB、截屏、触控管理器）...")
        logger.debug(LogCategory.MAIN, "初始化 ADB 设备管理器", adb_path=adb_path)
        adb_manager = ADBDeviceManager(
            adb_path=adb_path,
            timeout=int(config.get('adb', {}).get('timeout', 30))
        )

        # 启动时扫描设备，确保 _last_connected_device 被正确设置
        try:
            adb_manager.get_devices()
        except Exception as e:
            logger.warning(LogCategory.MAIN, "启动时扫描设备失败", error=str(e))

        logger.debug(LogCategory.MAIN, "初始化截屏模块")
        screen_capture = ScreenCapture(adb_manager=adb_manager)
        
        logger.debug(LogCategory.MAIN, "初始化触控管理器")
        touch_executor = TouchManager()

        logger.debug(LogCategory.MAIN, "关联截屏模块和 MAA 触控管理器")
        screen_capture.set_touch_manager(touch_executor)

        # 初始化推理管理器（纯本地模式，无通信模块）
        logger.debug(LogCategory.MAIN, "初始化推理管理器")
        from core.capability.local_inference.inference_manager import InferenceManager
        from core.foundation.paths import get_project_root
        inference_manager = InferenceManager(
            config=config,
            models_dir=os.path.join(get_project_root(), "models")
        )
        logger.info(LogCategory.MAIN, "推理管理器初始化完成",
                   local_available=inference_manager.is_local_available())

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
        # 通过 GUI Client 工厂函数创建 AgentExecutor
        logger.debug(LogCategory.MAIN, "通过 GUI Client 工厂函数初始化代理执行器")
        from core.service.gui_client import create_agent_executor
        
        # 获取当前设备序列号，确保截图时指定正确设备
        device_serial = ""
        try:
            if adb_manager.get_current_device():
                device_serial = adb_manager.get_current_device()
            elif adb_manager.get_last_connected_device():
                device_serial = adb_manager.get_last_connected_device()
        except Exception:
            pass
        
        agent_executor = create_agent_executor(
            inference_manager=inference_manager,
            screen_capture=screen_capture,
            touch_executor=touch_executor,
            config=config,
            device_serial=device_serial,
        )

        # 创建 GUIClient（GUI 层唯一推理入口，纯本地模式）
        from core.service.gui_client import GUIClient
        gui_client = GUIClient(
            config=config,
            inference_manager=inference_manager,
        )

        print(f"[主进程] 调用 run_application() - 窗口即将显示...")
        exit_code = run_application(
            agent_executor=agent_executor,
            gui_client=gui_client,
            screen_capture=screen_capture,
            touch_executor=touch_executor,
            config=config,
            inference_manager=inference_manager,
            adb_manager=adb_manager
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