"""
集成测试 - 验证迁移后的设备控制与截图功能
"""
import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.capability.device.adb_manager import ADBDeviceManager
from core.capability.device.device_detector import DeviceDetector
from core.capability.input.screenshot import ScreenCapture
from core.capability.device.touch import TouchManager


class MockADBDeviceManager(ADBDeviceManager):
    """模拟 ADB 设备管理器"""

    def __init__(self):
        # 不调用父类 __init__，直接设置必要属性
        self.adb_path = "adb"
        self.timeout = 10
        self.logger = MagicMock()
        self._adb_client = None

    def shell_command(self, serial: str, cmd: str, timeout: int = None):
        """模拟 shell 命令"""
        if "wm size" in cmd:
            return (0, "Physical size: 1920x1080")
        elif "input tap" in cmd:
            return (0, "")
        elif "input swipe" in cmd:
            return (0, "")
        return (0, "")

    def get_device_resolution(self, serial: str):
        return (1920, 1080)

    def get_device_model(self, serial: str):
        return "TestDevice"

    def create_connection(self, serial: str, network_type: int, name: str):
        """模拟 socket 连接"""
        import socket
        return socket.socket()


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_device_detection_flow(self):
        """测试设备检测流程"""
        adb_manager = MockADBDeviceManager()
        detector = DeviceDetector(adb_manager)

        # 测试 MuMu 设备
        device_info = detector.get_device_info("127.0.0.1:16384")
        self.assertIsNotNone(device_info)
        self.assertEqual(device_info.device_type.value, "mumu")
        self.assertEqual(device_info.recommended_screenshot, "nemu_ipc")
        self.assertEqual(device_info.recommended_control, "MaaTouch")

        # 测试普通模拟器
        device_info = detector.get_device_info("127.0.0.1:5555")
        self.assertIsNotNone(device_info)
        self.assertEqual(device_info.device_type.value, "emulator")
        self.assertEqual(device_info.recommended_screenshot, "auto")
        self.assertEqual(device_info.recommended_control, "auto")

    def test_screen_capture_initialization(self):
        """测试 ScreenCapture 初始化"""
        adb_manager = MockADBDeviceManager()
        config = {
            "screen": {
                "method": "auto",
                "min_interval": 0.1
            }
        }
        sc = ScreenCapture(adb_manager, config)

        # 验证初始化状态
        self.assertEqual(sc.adb_manager, adb_manager)
        self.assertEqual(sc.config, config)
        self.assertEqual(sc.min_interval, 0.1)
        # _device_detector 是延迟初始化的，访问一次后创建
        detector = sc._get_device_detector()
        self.assertIsNotNone(detector)
        self.assertIsNotNone(sc._stuck_detector)
        self.assertIsNotNone(sc._error_handler)

    def test_screen_capture_device_info_caching(self):
        """测试设备信息缓存"""
        adb_manager = MockADBDeviceManager()
        sc = ScreenCapture(adb_manager, {})

        # 首次获取设备信息
        info1 = sc._get_device_info("127.0.0.1:16384")
        self.assertIsNotNone(info1)
        self.assertEqual(info1["type"], "mumu")

        # 第二次应从缓存获取
        info2 = sc._get_device_info("127.0.0.1:16384")
        self.assertIsNotNone(info2)
        self.assertEqual(info1, info2)

    def test_touch_manager_initialization(self):
        """测试 TouchManager 初始化"""
        tm = TouchManager()
        self.assertFalse(tm.connected)
        self.assertEqual(len(tm._executors), 6)  # 6种触控方式

    def test_touch_manager_method_order(self):
        """测试触控方式尝试顺序"""
        tm = TouchManager()

        # MaaTouch 的降级链
        order = tm._determine_method_order("MaaTouch")
        self.assertEqual(order[0], "MaaTouch")
        self.assertIn("minitouch", order)
        self.assertIn("scrcpy", order)
        self.assertIn("ADB", order)

        # ADB 只有自己
        order = tm._determine_method_order("ADB")
        self.assertEqual(order, ["ADB"])

    def test_config_manager_basic(self):
        """测试配置管理器基本功能"""
        from core.foundation.config_manager import ConfigManager

        cm = ConfigManager()
        cm.set("test.key", "value")
        self.assertEqual(cm.get("test.key"), "value")
        self.assertEqual(cm.get("test.nonexistent", "default"), "default")

        # 测试嵌套
        cm.set("screen.method", "scrcpy")
        self.assertEqual(cm.get("screen.method"), "scrcpy")


if __name__ == '__main__':
    unittest.main()