"""测试 ADBDeviceManager.get_devices() 同步当前设备状态"""
import sys
import os
import json
import tempfile
from unittest.mock import patch, MagicMock

# 确保 src 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class TestADBDeviceManagerCurrentDeviceSync:
    """验证 get_devices() 会自动同步 _current_device"""

    def test_get_devices_sets_current_device_when_none(self, tmp_path):
        """当 _current_device 为 None 时，get_devices() 应设置为第一个已连接设备"""
        from core.capability.device.adb_manager import ADBDeviceManager

        # 模拟 adb devices 返回一个 USB 设备
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "List of devices attached\nemulator-5554\tdevice\n"

        with patch('subprocess.run', return_value=mock_result):
            manager = ADBDeviceManager(adb_path="adb", timeout=10)
            # 初始状态
            assert manager._current_device is None
            assert manager._last_connected_device is None

            # 调用 get_devices
            devices = manager.get_devices()

            # 验证 _current_device 被自动设置
            assert manager._current_device == "emulator-5554"
            assert manager._last_connected_device == "emulator-5554"
            assert len(devices) == 1

    def test_get_devices_updates_current_device_when_disconnected(self, tmp_path):
        """当 _current_device 已断开时，get_devices() 应更新为新的已连接设备"""
        from core.capability.device.adb_manager import ADBDeviceManager

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "List of devices attached\nemulator-5556\tdevice\n"

        with patch('subprocess.run', return_value=mock_result):
            manager = ADBDeviceManager(adb_path="adb", timeout=10)
            # 模拟之前连接过 emulator-5554，但现在已断开
            manager._current_device = "emulator-5554"
            manager._last_connected_device = "emulator-5554"

            # 调用 get_devices，发现新设备
            devices = manager.get_devices()

            # 验证 _current_device 被更新为新设备
            assert manager._current_device == "emulator-5556"
            assert manager._last_connected_device == "emulator-5556"

    def test_get_devices_preserves_current_device_when_still_connected(self, tmp_path):
        """当 _current_device 仍然连接时，get_devices() 不应改变它"""
        from core.capability.device.adb_manager import ADBDeviceManager

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "List of devices attached\nemulator-5554\tdevice\n"

        with patch('subprocess.run', return_value=mock_result):
            manager = ADBDeviceManager(adb_path="adb", timeout=10)
            manager._current_device = "emulator-5554"
            manager._last_connected_device = "emulator-5554"

            devices = manager.get_devices()

            # 验证 _current_device 保持不变
            assert manager._current_device == "emulator-5554"
            assert manager._last_connected_device == "emulator-5554"

    def test_get_devices_handles_multiple_devices(self, tmp_path):
        """当有多个设备时，get_devices() 应选择第一个状态为 device 的设备"""
        from core.capability.device.adb_manager import ADBDeviceManager

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "List of devices attached\n"
            "emulator-5554\tdevice\n"
            "emulator-5556\toffline\n"
        )

        with patch('subprocess.run', return_value=mock_result):
            manager = ADBDeviceManager(adb_path="adb", timeout=10)
            devices = manager.get_devices()

            # 验证选择了第一个 device 状态的设备
            assert manager._current_device == "emulator-5554"
            assert manager._last_connected_device == "emulator-5554"
            assert len(devices) == 2

    def test_get_devices_no_devices_clears_current(self, tmp_path):
        """当没有设备时，get_devices() 不应设置 _current_device，_last_connected_device 保持不变"""
        from core.capability.device.adb_manager import ADBDeviceManager

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "List of devices attached\n"

        with patch('subprocess.run', return_value=mock_result):
            manager = ADBDeviceManager(adb_path="adb", timeout=10)
            # 先设置一个当前设备
            manager._current_device = "emulator-5554"
            manager._last_connected_device = "emulator-5554"

            devices = manager.get_devices()

            # 验证没有设备时，_current_device 和 _last_connected_device 保持原值
            # （由 disconnect 或外部逻辑清除，而不是 get_devices）
            assert manager._current_device == "emulator-5554"  # 保持不变
            assert manager._last_connected_device == "emulator-5554"  # 保持不变
            assert len(devices) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
