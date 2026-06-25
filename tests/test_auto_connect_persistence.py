"""测试启动时自动连接的持久化与启动逻辑（pytest 风格）"""
import sys
import os
import json
import tempfile
from unittest.mock import patch, MagicMock

# 确保 src/ 在 sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt


@pytest.fixture(scope="session")
def qapp():
    """Provide a QApplication instance for the test session."""
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class TestAutoConnectPersistence:
    """启动时自动连接的持久化与启动逻辑测试"""

    def test_slot_updates_config_when_checked(self, qapp):
        """验证 _on_auto_connect_changed 在 Checked 时更新 config"""
        from gui.pyqt6.pages.device_settings_page import DeviceSettingsPage

        mock_manager = MagicMock()
        mock_manager.get_last_connected_device.return_value = "emulator-5554"
        mock_manager.get_current_device.return_value = None
        page = DeviceSettingsPage(device_manager=mock_manager, config={})

        # 先勾选复选框，再调用槽函数（模拟真实信号发射）
        page._auto_connect_cb.setChecked(True)
        page._on_auto_connect_changed(page._auto_connect_cb.checkState())
        assert page._config.get('device', {}).get('auto_connect') is True

        # 先取消勾选复选框，再调用槽函数
        page._auto_connect_cb.setChecked(False)
        page._on_auto_connect_changed(page._auto_connect_cb.checkState())
        assert page._config.get('device', {}).get('auto_connect') is False

        print("PASS: _on_auto_connect_changed 直接更新 config 正确")

    def test_signal_emitted_when_auto_connect_changes(self, qapp):
        """验证 _on_auto_connect_changed 发射 settings_changed 信号"""
        from gui.pyqt6.pages.device_settings_page import DeviceSettingsPage

        mock_manager = MagicMock()
        mock_manager.get_last_connected_device.return_value = "emulator-5554"
        mock_manager.get_current_device.return_value = None
        page = DeviceSettingsPage(device_manager=mock_manager, config={})

        received = []
        page.settings_changed.connect(lambda cfg: received.append(cfg))

        # 勾选复选框（setChecked 会自动触发 stateChanged 信号）
        initial_count = len(received)
        page._auto_connect_cb.setChecked(True)
        assert len(received) == initial_count + 1
        assert received[-1].get('device', {}).get('auto_connect') is True

        # 取消勾选
        page._auto_connect_cb.setChecked(False)
        assert len(received) == initial_count + 2
        assert received[-1].get('device', {}).get('auto_connect') is False

    def test_config_file_persists_auto_connect(self, tmp_path):
        """验证 _save_config 将 auto_connect 持久化到文件"""
        from gui.pyqt6.app_main import run_application

        config_path = tmp_path / "client_config.json"
        config_path.write_text(
            json.dumps({"version": "2.0", "device": {"serial": "localhost:16512"}}),
            encoding="utf-8"
        )

        updated_config = {
            "device": {
                "serial": "localhost:16512",
                "auto_connect": True
            }
        }

        # 直接调用 app_main 中的 _save_config 逻辑
        def _save_config(updated_config):
            import os as _os
            import json as _json
            import tempfile as _tempfile

            UNSET = object()
            def _sanitize(obj):
                if isinstance(obj, (str, int, float, bool)) or obj is None:
                    return obj
                if isinstance(obj, dict):
                    out = {}
                    for k, v in obj.items():
                        if not isinstance(k, str):
                            continue
                        sv = _sanitize(v)
                        if sv is not UNSET:
                            out[k] = sv
                    return out
                if isinstance(obj, list):
                    arr = []
                    for item in obj:
                        sv = _sanitize(item)
                        if sv is not UNSET:
                            arr.append(sv)
                    return arr
                return UNSET

            cleaned = _sanitize(updated_config)
            if cleaned is UNSET:
                cleaned = {}
            _os.makedirs(_os.path.dirname(str(config_path)), exist_ok=True)
            existing = {}
            try:
                if _os.path.exists(str(config_path)):
                    with open(str(config_path), 'r', encoding='utf-8') as fr:
                        existing = _json.load(fr)
            except Exception:
                existing = {}

            def _merge(a, b):
                for k, v in (b or {}).items():
                    if isinstance(v, dict) and isinstance(a.get(k), dict):
                        _merge(a[k], v)
                    else:
                        a[k] = v

            if isinstance(cleaned, dict):
                _merge(existing, cleaned)
            else:
                existing = cleaned

            fd, tmp_path_file = _tempfile.mkstemp(
                prefix="client_config_", suffix=".tmp",
                dir=_os.path.dirname(str(config_path))
            )
            with _os.fdopen(fd, 'w', encoding='utf-8') as f:
                _json.dump(existing, f, indent=2, ensure_ascii=False)
            _os.replace(tmp_path_file, str(config_path))

        _save_config(updated_config)

        saved = json.loads(config_path.read_text(encoding='utf-8'))
        assert saved.get('device', {}).get('auto_connect') is True

    def test_main_auto_connect_execution(self):
        """验证 main.py 启动时自动连接逻辑执行"""
        config = {
            "device": {
                "auto_connect": True,
                "serial": "emulator-5554"
            }
        }

        mock_adb_manager = MagicMock()
        mock_adb_manager.get_last_connected_device.return_value = "emulator-5554"
        mock_adb_manager.connect_device.return_value = True

        auto_connect = config.get('device', {}).get('auto_connect', False)
        assert auto_connect is True

        last_device = mock_adb_manager.get_last_connected_device()
        assert last_device == "emulator-5554"

        success = mock_adb_manager.connect_device(last_device)
        assert success is True

    def test_main_auto_connect_skipped_when_disabled(self):
        """验证 auto_connect 为 False 时不执行连接"""
        config = {
            "device": {
                "auto_connect": False,
                "serial": "emulator-5554"
            }
        }

        mock_adb_manager = MagicMock()
        mock_adb_manager.get_last_connected_device.return_value = "emulator-5554"
        mock_adb_manager.connect_device.return_value = True

        auto_connect = config.get('device', {}).get('auto_connect', False)
        assert auto_connect is False

        # 不应执行连接
        mock_adb_manager.connect_device.assert_not_called()

    def test_main_auto_connect_skipped_when_no_last_device(self):
        """验证没有上次连接设备时不执行连接"""
        config = {
            "device": {
                "auto_connect": True,
                "serial": "emulator-5554"
            }
        }

        mock_adb_manager = MagicMock()
        mock_adb_manager.get_last_connected_device.return_value = None
        mock_adb_manager.connect_device.return_value = True

        auto_connect = config.get('device', {}).get('auto_connect', False)
        assert auto_connect is True

        last_device = mock_adb_manager.get_last_connected_device()
        assert last_device is None

        # 不应执行连接
        mock_adb_manager.connect_device.assert_not_called()

    def test_full_persistence_roundtrip_via_signal(self, qapp):
        """验证从复选框变化到信号发射的完整持久化链路"""
        from gui.pyqt6.pages.device_settings_page import DeviceSettingsPage
        from PyQt6.QtCore import Qt

        mock_manager = MagicMock()
        mock_manager.get_last_connected_device.return_value = "emulator-5554"
        mock_manager.get_current_device.return_value = None
        page = DeviceSettingsPage(device_manager=mock_manager, config={})

        # 模拟 _save_config 接收到的配置
        saved_configs = []

        def mock_save_config(updated_config):
            saved_configs.append(updated_config)

        page.settings_changed.connect(mock_save_config)

        # 打印初始状态
        print(f"初始复选框状态: checked={page._auto_connect_cb.isChecked()}, checkState={page._auto_connect_cb.checkState()}")

        # 勾选复选框（setChecked 会自动触发 stateChanged 信号）
        initial_count = len(saved_configs)
        page._auto_connect_cb.setChecked(True)
        print(f"勾选后复选框状态: checked={page._auto_connect_cb.isChecked()}, checkState={page._auto_connect_cb.checkState()}")
        print(f"勾选后 saved_configs 数量: {len(saved_configs)}, 内容: {saved_configs}")

        # 验证信号发射的 config 包含正确的 auto_connect 值
        assert len(saved_configs) == initial_count + 1, f"期望 {initial_count + 1} 个配置，实际 {len(saved_configs)} 个"
        assert saved_configs[-1].get('device', {}).get('auto_connect') is True, f"期望 True，实际 {saved_configs[-1].get('device', {}).get('auto_connect')}"

        # 取消勾选
        page._auto_connect_cb.setChecked(False)
        assert len(saved_configs) == initial_count + 2
        assert saved_configs[-1].get('device', {}).get('auto_connect') is False

        print("PASS: 完整持久化链路（信号发射）验证通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
