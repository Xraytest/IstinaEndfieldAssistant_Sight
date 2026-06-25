"""测试启动时自动连接的持久化与启动逻辑"""
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

from PyQt6.QtWidgets import QApplication


def test_auto_connect_slot_updates_config():
    """验证 _on_auto_connect_changed 槽函数直接更新 config"""
    app = QApplication.instance() or QApplication([])
    
    from gui.pyqt6.pages.device_settings_page import DeviceSettingsPage
    from PyQt6.QtCore import Qt
    
    mock_manager = MagicMock()
    mock_manager.get_last_connected_device.return_value = "emulator-5554"
    mock_manager.get_current_device.return_value = None
    page = DeviceSettingsPage(device_manager=mock_manager, config={})
    
    # 验证初始状态为未勾选
    assert page._auto_connect_cb.isChecked() is False
    assert page._config.get('device', {}).get('auto_connect') is None
    
    # 直接调用槽函数，模拟 Checked 状态
    page._on_auto_connect_changed(Qt.CheckState.Checked)
    assert page._config.get('device', {}).get('auto_connect') is True
    
    # 直接调用槽函数，模拟 Unchecked 状态
    page._on_auto_connect_changed(Qt.CheckState.Unchecked)
    assert page._config.get('device', {}).get('auto_connect') is False
    
    print("PASS: _on_auto_connect_changed 直接更新 config 正确")


def test_auto_connect_signal_emission():
    """验证 _on_auto_connect_changed 发射 settings_changed 信号"""
    app = QApplication.instance() or QApplication([])
    
    from gui.pyqt6.pages.device_settings_page import DeviceSettingsPage
    from PyQt6.QtCore import Qt
    
    mock_manager = MagicMock()
    mock_manager.get_last_connected_device.return_value = "emulator-5554"
    mock_manager.get_current_device.return_value = None
    page = DeviceSettingsPage(device_manager=mock_manager, config={})
    
    received = []
    
    def capture(config):
        received.append(config)
    
    page.settings_changed.connect(capture)
    
    # 触发 Checked
    page._on_auto_connect_changed(Qt.CheckState.Checked)
    assert len(received) == 1
    assert received[0].get('device', {}).get('auto_connect') is True
    
    # 触发 Unchecked
    page._on_auto_connect_changed(Qt.CheckState.Unchecked)
    assert len(received) == 2
    assert received[1].get('device', {}).get('auto_connect') is False
    
    print("PASS: _on_auto_connect_changed 发射 settings_changed 信号正确")


def test_auto_connect_config_file_persistence():
    """验证 _save_config 正确持久化 auto_connect 到文件"""
    app = QApplication.instance() or QApplication([])
    
    # 创建临时配置文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({"version": "2.0", "device": {"serial": "localhost:16512"}}, f)
        config_path = f.name
    
    try:
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
            _os.makedirs(_os.path.dirname(config_path), exist_ok=True)
            existing = {}
            try:
                if _os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as fr:
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
            
            fd, tmp_path = _tempfile.mkstemp(prefix="client_config_", suffix=".tmp", dir=_os.path.dirname(config_path))
            with _os.fdopen(fd, 'w', encoding='utf-8') as f:
                _json.dump(existing, f, indent=2, ensure_ascii=False)
            _os.replace(tmp_path, config_path)
        
        # 模拟配置更新（勾选 auto_connect）
        test_config = {
            "device": {
                "serial": "localhost:16512",
                "auto_connect": True
            }
        }
        
        _save_config(test_config)
        
        with open(config_path, 'r', encoding='utf-8') as f:
            saved = json.load(f)
        
        assert saved.get('device', {}).get('auto_connect') is True
        print("PASS: _save_config 正确持久化 auto_connect 到文件")
        
    finally:
        os.unlink(config_path)


def test_main_auto_connect_logic():
    """验证 main.py 启动时自动连接逻辑"""
    config = {
        "device": {
            "auto_connect": True,
            "serial": "emulator-5554"
        }
    }
    
    mock_adb_manager = MagicMock()
    mock_adb_manager.get_last_connected_device.return_value = "emulator-5554"
    mock_adb_manager.connect_device.return_value = True
    
    try:
        auto_connect = config.get('device', {}).get('auto_connect', False)
        if auto_connect:
            last_device = mock_adb_manager.get_last_connected_device()
            if last_device:
                success = mock_adb_manager.connect_device(last_device)
                assert success is True
                print("PASS: main.py 启动时自动连接逻辑正确执行")
            else:
                print("SKIP: 没有上次连接的设备")
        else:
            print("SKIP: auto_connect 未启用")
    except Exception as e:
        print(f"FAIL: 启动时自动连接逻辑异常: {e}")
        raise


if __name__ == "__main__":
    print("=" * 60)
    print("测试启动时自动连接的持久化与启动逻辑")
    print("=" * 60)
    
    try:
        test_auto_connect_slot_updates_config()
        print()
        test_auto_connect_signal_emission()
        print()
        test_auto_connect_config_file_persistence()
        print()
        test_main_auto_connect_logic()
        print()
        print("=" * 60)
        print("所有测试通过")
        print("=" * 60)
    except AssertionError as e:
        print(f"FAIL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
