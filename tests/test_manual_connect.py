"""测试 DeviceSettingsPage 手动连接逻辑（覆盖 USB 设备场景）"""
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
from PyQt6.QtWidgets import QApplication, QMessageBox


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class TestDeviceSettingsPageManualConnect:
    """DeviceSettingsPage 手动连接测试"""

    def test_usb_device_manual_connect_skips_adb_connect(self, qtbot):
        """手动连接 USB 设备时应跳过 adb connect"""
        from gui.pyqt6.pages.device_settings_page import DeviceSettingsPage

        mock_manager = MagicMock()
        mock_manager.get_devices.return_value = [
            MagicMock(serial="emulator-5554", status="device")
        ]
        mock_manager.get_last_connected_device.return_value = None
        mock_manager.get_current_device.return_value = None
        mock_manager.connect_device.return_value = False  # adb connect 会失败

        page = DeviceSettingsPage(device_manager=mock_manager, config={})
        page._serial_input.setText("emulator-5554")

        # 模拟 QMessageBox 避免弹出对话框
        with patch.object(QMessageBox, 'warning'), \
             patch.object(QMessageBox, 'critical'):
            page._connect_device()

        # 验证 adb connect 未被调用
        mock_manager.connect_device.assert_not_called()
        # 验证 _current_device 被直接设置
        assert mock_manager._current_device == "emulator-5554"
        # 验证 UI 状态更新
        assert page._status_indicator.text() == "\u25cf 已连接 (emulator-5554)"

    def test_network_device_manual_connect_calls_adb_connect(self, qtbot):
        """手动连接网络设备时应调用 adb connect"""
        from gui.pyqt6.pages.device_settings_page import DeviceSettingsPage

        mock_manager = MagicMock()
        mock_manager.get_devices.return_value = []  # 网络设备不在 devices 列表中
        mock_manager.get_last_connected_device.return_value = None
        mock_manager.get_current_device.return_value = None
        mock_manager.connect_device.return_value = True

        page = DeviceSettingsPage(device_manager=mock_manager, config={})
        page._serial_input.setText("127.0.0.1:5555")

        with patch.object(QMessageBox, 'warning'), \
             patch.object(QMessageBox, 'critical'):
            page._connect_device()

        # 验证 adb connect 被调用
        mock_manager.connect_device.assert_called_once_with("127.0.0.1:5555")
        # 验证 UI 状态更新
        assert page._status_indicator.text() == "\u25cf 已连接 (127.0.0.1:5555)"

    def test_manual_connect_shows_warning_on_failure(self, qtbot):
        """手动连接失败时应显示警告对话框"""
        from gui.pyqt6.pages.device_settings_page import DeviceSettingsPage

        mock_manager = MagicMock()
        mock_manager.get_devices.return_value = []
        mock_manager.get_last_connected_device.return_value = None
        mock_manager.get_current_device.return_value = None
        mock_manager.connect_device.return_value = False

        page = DeviceSettingsPage(device_manager=mock_manager, config={})
        page._serial_input.setText("invalid-device")

        with patch.object(QMessageBox, 'warning') as warning_mock, \
             patch.object(QMessageBox, 'critical'):
            page._connect_device()

        warning_mock.assert_called_once()
        # 验证 UI 状态为未连接
        assert page._status_indicator.text() == "\u25cf 未连接"

    def test_manual_connect_requires_serial_input(self, qtbot):
        """未输入序列号时应显示警告"""
        from gui.pyqt6.pages.device_settings_page import DeviceSettingsPage

        mock_manager = MagicMock()
        mock_manager.get_last_connected_device.return_value = None
        mock_manager.get_current_device.return_value = None
        page = DeviceSettingsPage(device_manager=mock_manager, config={})
        page._serial_input.setText("")

        with patch.object(QMessageBox, 'warning') as warning_mock:
            page._connect_device()

        warning_mock.assert_called_once()
        mock_manager.connect_device.assert_not_called()

    def test_manual_connect_emits_device_connected_signal(self, qtbot):
        """手动连接成功时应发射 device_connected 信号"""
        from gui.pyqt6.pages.device_settings_page import DeviceSettingsPage

        mock_manager = MagicMock()
        mock_manager.get_devices.return_value = [
            MagicMock(serial="emulator-5554", status="device")
        ]
        mock_manager.get_last_connected_device.return_value = None
        mock_manager.get_current_device.return_value = None

        page = DeviceSettingsPage(device_manager=mock_manager, config={})
        page._serial_input.setText("emulator-5554")

        received_serials = []
        page.device_connected.connect(lambda serial: received_serials.append(serial))

        with patch.object(QMessageBox, 'warning'), \
             patch.object(QMessageBox, 'critical'):
            page._connect_device()

        assert received_serials == ["emulator-5554"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
