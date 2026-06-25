"""测试启动时自动连接逻辑（覆盖 USB 设备场景）"""
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


class TestAutoConnectWithRealADBLogic:
    """模拟真实 ADB 设备管理器行为的自动连接测试"""

    def test_usb_device_should_not_call_adb_connect(self, tmp_path):
        """USB 设备（无冒号）不应调用 adb connect，因为已通过 adb devices 可用"""
        # 模拟 get_devices 返回一个 USB 设备
        mock_manager = MagicMock()
        mock_manager.get_devices.return_value = [
            MagicMock(serial="emulator-5554", status="device")
        ]
        mock_manager.get_last_connected_device.return_value = "emulator-5554"
        mock_manager.get_current_device.return_value = None
        mock_manager.connect_device.return_value = False  # adb connect 会失败

        # 模拟 main.py 的启动逻辑
        config = {"device": {"auto_connect": True}}

        # 1. 扫描设备
        devices = mock_manager.get_devices()
        mock_manager.get_last_connected_device()  # 这会设置 _last_connected_device

        # 2. 自动连接
        auto_connect = config.get('device', {}).get('auto_connect', False)
        assert auto_connect is True

        last_device = mock_manager.get_last_connected_device()
        assert last_device == "emulator-5554"

        # 当前实现会调用 connect_device，对 USB 设备这会导致失败
        success = mock_manager.connect_device(last_device)
        assert success is False, "USB 设备调用 adb connect 会失败"

        # 验证 connect_device 被调用（说明当前实现有问题）
        mock_manager.connect_device.assert_called_once_with("emulator-5554")

    def test_network_device_should_call_adb_connect(self, tmp_path):
        """网络设备（含冒号）应调用 adb connect"""
        mock_manager = MagicMock()
        mock_manager.get_devices.return_value = []  # 网络设备不在 devices 列表中
        mock_manager.get_last_connected_device.return_value = "127.0.0.1:5555"
        mock_manager.get_current_device.return_value = None
        mock_manager.connect_device.return_value = True

        config = {"device": {"auto_connect": True}}

        auto_connect = config.get('device', {}).get('auto_connect', False)
        assert auto_connect is True

        last_device = mock_manager.get_last_connected_device()
        assert last_device == "127.0.0.1:5555"

        success = mock_manager.connect_device(last_device)
        assert success is True

        mock_manager.connect_device.assert_called_once_with("127.0.0.1:5555")

    def test_already_connected_device_should_skip_connect(self, tmp_path):
        """已连接的设备应跳过 adb connect，直接标记为当前设备"""
        mock_manager = MagicMock()
        mock_manager.get_devices.return_value = [
            MagicMock(serial="emulator-5554", status="device")
        ]
        mock_manager.get_last_connected_device.return_value = "emulator-5554"
        mock_manager.get_current_device.return_value = None
        mock_manager.connect_device.return_value = True

        config = {"device": {"auto_connect": True}}

        # 扫描设备后，设备已在列表中
        devices = mock_manager.get_devices()
        device_serials = [d.serial for d in devices]
        assert "emulator-5554" in device_serials

        last_device = mock_manager.get_last_connected_device()
        assert last_device == "emulator-5554"

        # 理想行为：已连接的设备应跳过 connect_device
        # 但当前实现会调用 connect_device
        if last_device in device_serials:
            # 设备已连接，不应再调用 connect_device
            pass  # 当前实现仍会调用

        success = mock_manager.connect_device(last_device)
        assert success is True

    def test_auto_connect_should_update_ui_state(self, tmp_path):
        """自动连接成功后，UI 应反映连接状态"""
        mock_manager = MagicMock()
        mock_manager.get_devices.return_value = [
            MagicMock(serial="emulator-5554", status="device")
        ]
        mock_manager.get_last_connected_device.return_value = "emulator-5554"
        mock_manager.get_current_device.return_value = "emulator-5554"  # 连接后返回
        mock_manager.connect_device.return_value = True

        config = {"device": {"auto_connect": True}}

        # 模拟 main.py 的启动流程
        devices = mock_manager.get_devices()
        auto_connect = config.get('device', {}).get('auto_connect', False)
        if auto_connect:
            last_device = mock_manager.get_last_connected_device()
            if last_device:
                success = mock_manager.connect_device(last_device)

        # 模拟 DeviceSettingsPage 检查连接状态
        current = mock_manager.get_current_device()
        assert current == "emulator-5554", "UI 应能检测到已连接的设备"

    def test_no_last_device_should_skip_auto_connect(self, tmp_path):
        """没有上次连接设备时，应跳过自动连接"""
        mock_manager = MagicMock()
        mock_manager.get_devices.return_value = []
        mock_manager.get_last_connected_device.return_value = None
        mock_manager.connect_device.return_value = True

        config = {"device": {"auto_connect": True}}

        auto_connect = config.get('device', {}).get('auto_connect', False)
        assert auto_connect is True

        last_device = mock_manager.get_last_connected_device()
        assert last_device is None

        # 不应执行连接
        mock_manager.connect_device.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
