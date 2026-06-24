"""
StarRailCopilot 迁移功能演示脚本
展示设备检测、智能推荐、截图和触控功能
"""
import sys
from pathlib import Path

# 确保 src 在路径中
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.capability.device.adb_manager import ADBDeviceManager
from core.capability.input.screenshot import ScreenCapture
from core.capability.device.touch import TouchManager
from core.foundation.logger import get_logger, LogCategory

# 初始化日志
get_logger()


def demo_device_detection():
    """演示设备检测功能"""
    print("\n" + "="*60)
    print("1. 设备检测演示")
    print("="*60)

    try:
        # 使用真实的 ADBDeviceManager（需要真实设备连接）
        from core.capability.device.adb_manager import ADBDeviceManager
        from core.capability.device.device_detector import DeviceDetector

        # 创建 ADB 管理器（使用项目中的 ADB 路径）
        adb_path = str(Path(__file__).parent.parent / "3rd-part" / "adb" / "adb.exe")
        adb_manager = ADBDeviceManager(adb_path=adb_path, timeout=5)

        # 创建设备检测器
        detector = DeviceDetector(adb_manager)

        print("\n设备检测器已初始化，支持以下设备类型:")
        from core.capability.device.device_detector import DeviceType
        for dtype in DeviceType:
            rec = detector.RECOMMENDATIONS.get(dtype, {})
            print(f"  {dtype.value}: 截图={rec.get('screenshot', 'N/A')}, 触控={rec.get('control', 'N/A')}")

        # 尝试获取已连接设备列表
        devices = adb_manager.get_devices()
        if devices:
            print(f"\n已发现 {len(devices)} 个设备:")
            for dev in devices[:3]:  # 只显示前3个
                print(f"  {dev.serial} ({dev.status})")
        else:
            print("\n未发现已连接的设备（请确保 ADB 已启动且设备已连接）")

    except ImportError as e:
        print(f"模块导入失败: {e}")
    except Exception as e:
        print(f"设备检测异常: {e}")


def demo_screen_capture():
    """演示截图功能"""
    print("\n" + "="*60)
    print("2. 截图系统演示")
    print("="*60)

    class MockADBManager:
        def __init__(self):
            self.adb_path = "adb"
            self.timeout = 10

        def shell_command(self, serial, cmd, timeout=None):
            if "wm size" in cmd:
                return (0, "Physical size: 1920x1080")
            return (0, "")

        def get_device_resolution(self, serial):
            return (1920, 1080)

    adb_manager = MockADBManager()

    # 配置截图器（auto 模式）
    config = {
        "screen": {
            "method": "auto",
            "min_interval": 0.1
        }
    }

    screen_capture = ScreenCapture(adb_manager, config)

    # 模拟设备信息缓存
    screen_capture._device_cache["127.0.0.1:16384"] = {
        "type": "mumu",
        "recommended_screenshot": "nemu_ipc",
        "recommended_control": "MaaTouch"
    }

    print("\n截图器配置:")
    print(f"  模式: {config['screen']['method']}")
    print(f"  最小间隔: {config['screen']['min_interval']}秒")

    print("\n设备信息缓存:")
    print(f"  MuMu 推荐截图方法: nemu_ipc")
    print(f"  MuMu 推荐触控方法: MaaTouch")

    print("\n注意: 实际截图需要连接真实设备")


def demo_touch_manager():
    """演示触控管理器"""
    print("\n" + "="*60)
    print("3. 触控系统演示")
    print("="*60)

    touch_manager = TouchManager()

    print("\n触控方式降级链:")
    print("  MaaTouch → minitouch → scrcpy → ADB")
    print("  nemu_ipc → scrcpy → MaaTouch → ADB")
    print("  ADB (仅自身)")

    print("\n触控执行器状态:")
    print(f"  已创建执行器数量: {len(touch_manager._executors)}")
    print(f"  支持的方法: {list(touch_manager._executors.keys())}")


def demo_config_manager():
    """演示配置管理器"""
    print("\n" + "="*60)
    print("4. 配置管理演示")
    print("="*60)

    from core.foundation.config_manager import ConfigManager

    config = ConfigManager()
    config.set("screen.method", "auto")
    config.set("screen.min_interval", 0.1)
    config.set("touch.method", "auto")

    print("\n当前配置:")
    print(f"  screen.method: {config.get('screen.method')}")
    print(f"  screen.min_interval: {config.get('screen.min_interval')}")
    print(f"  touch.method: {config.get('touch.method')}")

    print("\n配置监听器演示:")
    def on_screen_change(key, new_val, old_val):
        print(f"  配置变更: {key} = {new_val} (旧值: {old_val})")

    config.add_listener("screen.method", on_screen_change)
    config.set("screen.method", "scrcpy")
    config.remove_listener("screen.method", on_screen_change)


def main():
    """主函数"""
    print("\n" + "="*60)
    print("StarRailCopilot 迁移功能演示")
    print("IstinaEndfieldAssistant_Sight")
    print("="*60)

    try:
        demo_device_detection()
        demo_screen_capture()
        demo_touch_manager()
        demo_config_manager()

        print("\n" + "="*60)
        print("演示完成！")
        print("="*60)
        print("\n关键特性:")
        print("✅ 7种截图方式框架")
        print("✅ 6种触控方式框架")
        print("✅ 智能设备检测与推荐")
        print("✅ 自动降级机制")
        print("✅ 配置驱动")
        print("✅ 向后兼容")
        print("\n请查看完整报告:")
        print("  docs/STARRAIL_COPILOT_MIGRATION_REPORT.md")
        print("  docs/MIGRATION_COMPLETION_REPORT.md")

    except Exception as e:
        print(f"\n❌ 演示失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()