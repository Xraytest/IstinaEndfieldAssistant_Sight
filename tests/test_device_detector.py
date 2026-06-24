"""
设备检测器单元测试
"""
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

# 确保 src 在路径中
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.capability.device.device_detector import DeviceDetector, DeviceInfo, DeviceType


class MockADBManager:
    """模拟 ADB 管理器"""

    def __init__(self):
        self.adb_path = "adb"
        self.timeout = 10

    def shell_command(self, serial: str, cmd: str, timeout: int = None):
        """模拟 shell 命令执行"""
        return (0, "")

    def get_device_resolution(self, serial: str):
        """模拟获取分辨率"""
        return (1920, 1080)

    def get_device_model(self, serial: str):
        """模拟获取设备型号"""
        return "TestDevice"


class TestDeviceDetector(unittest.TestCase):
    """设备检测器测试类"""

    def setUp(self):
        """测试前置"""
        self.adb_manager = MockADBManager()
        self.detector = DeviceDetector(self.adb_manager)

    def test_device_type_unknown(self):
        """测试未知设备类型"""
        # 网络设备且端口不在常见模拟器范围，应被识别为 REAL_DEVICE（真机）
        device_type = self.detector.detect_device_type("127.0.0.1:9999")
        self.assertEqual(device_type, DeviceType.REAL_DEVICE)

    def test_device_type_wsa(self):
        """测试 WSA 设备"""
        device_type = self.detector.detect_device_type("wsa-0")
        self.assertEqual(device_type, DeviceType.WSA)

    def test_device_type_mumu_by_port(self):
        """测试通过端口识别 MuMu"""
        device_type = self.detector.detect_device_type("127.0.0.1:16384")
        self.assertEqual(device_type, DeviceType.MUMU)

    def test_device_type_mumu_by_serial(self):
        """测试通过序列号识别 MuMu"""
        device_type = self.detector.detect_device_type("emulator-mumu-5555")
        self.assertEqual(device_type, DeviceType.MUMU)

    def test_device_type_waydroid(self):
        """测试 Waydroid 设备"""
        def mock_getprop(serial, prop):
            if prop == 'ro.product.brand':
                return "waydroid"
            return ""

        with patch.object(self.detector, '_getprop', side_effect=mock_getprop):
            device_type = self.detector.detect_device_type("192.168.1.100:5555")
            self.assertEqual(device_type, DeviceType.WAYDROID)

    def test_device_type_avd(self):
        """测试 AVD 设备"""
        def mock_getprop(serial, prop):
            if prop == 'ro.hardware':
                return "ranchu"
            return ""

        with patch.object(self.detector, '_getprop', side_effect=mock_getprop):
            device_type = self.detector.detect_device_type("emulator-5554")
            self.assertEqual(device_type, DeviceType.AVD)

    def test_get_device_info(self):
        """测试获取完整设备信息"""
        with patch.object(self.detector, '_get_device_resolution', return_value=(1920, 1080)):
            with patch.object(self.detector, '_collect_device_properties', return_value={}):
                device_info = self.detector.get_device_info("127.0.0.1:5555")
                self.assertIsNotNone(device_info)
                # 127.0.0.1:5555 是网络设备，端口 5555 在常见模拟器范围内，会被识别为 EMULATOR
                self.assertEqual(device_info.device_type, DeviceType.EMULATOR)
                self.assertEqual(device_info.original_resolution, (1920, 1080))

    def test_get_recommended_config(self):
        """测试推荐配置"""
        device_info = DeviceInfo(
            serial="test",
            device_type=DeviceType.MUMU,
            original_resolution=(1920, 1080),
            recommended_screenshot="nemu_ipc",
            recommended_control="MaaTouch",
            properties={}
        )

        config = self.detector.get_recommended_config(device_info)
        self.assertEqual(config['screenshot']['method'], 'nemu_ipc')
        self.assertEqual(config['control']['method'], 'MaaTouch')

    def test_extract_port(self):
        """测试端口提取"""
        self.assertEqual(self.detector._extract_port("127.0.0.1:5555"), 5555)
        self.assertIsNone(self.detector._extract_port("emulator-5554"))


if __name__ == '__main__':
    unittest.main()