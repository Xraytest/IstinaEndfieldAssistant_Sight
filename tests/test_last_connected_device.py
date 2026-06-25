"""测试上次连接设备逻辑：验证 get_devices 是否优先记录可用设备"""
import sys
import os

# 确保 src/ 在 sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from unittest.mock import patch, MagicMock
from core.capability.device.adb_manager import ADBDeviceManager, AdbDeviceInfo


def test_last_connected_device_should_prefer_device_status():
    """当存在多个设备时，_last_connected_device 应优先记录状态为 device 的设备"""
    manager = ADBDeviceManager(adb_path="adb", timeout=5)

    # 模拟 adb devices 输出：第一个是可用设备，第二个是未授权设备
    mock_result = MagicMock()
    mock_result.stdout = "List of devices attached\nemulator-5554\tdevice\nemulator-5556\tunauthorized\n"
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result):
        devices = manager.get_devices()

    print(f"扫描到的设备: {[d.serial for d in devices]}")
    print(f"_last_connected_device: {manager.get_last_connected_device()}")

    # 断言：应该记录 emulator-5554（device 状态），而不是 emulator-5556（unauthorized）
    assert manager.get_last_connected_device() == "emulator-5554", \
        f"期望 'emulator-5554'，实际 '{manager.get_last_connected_device()}'"
    print("PASS: 优先记录 device 状态的设备")


def test_last_connected_device_fallback_to_last_when_no_device():
    """当没有设备状态为 device 时，回退记录最后一个设备"""
    manager = ADBDeviceManager(adb_path="adb", timeout=5)

    # 模拟 adb devices 输出：所有设备都不可用
    mock_result = MagicMock()
    mock_result.stdout = "List of devices attached\nemulator-5556\tunauthorized\n"
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result):
        devices = manager.get_devices()

    print(f"扫描到的设备: {[d.serial for d in devices]}")
    print(f"_last_connected_device: {manager.get_last_connected_device()}")

    # 断言：没有 device 状态的设备，回退记录最后一个
    assert manager.get_last_connected_device() == "emulator-5556", \
        f"期望 'emulator-5556'，实际 '{manager.get_last_connected_device()}'"
    print("PASS: 无可用设备时回退记录最后一个")


def test_last_connected_device_updated_on_connect():
    """connect_device 成功时应更新 _last_connected_device"""
    manager = ADBDeviceManager(adb_path="adb", timeout=5)

    mock_result = MagicMock()
    mock_result.stdout = "connected to 127.0.0.1:5555\n"
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result):
        success = manager.connect_device("127.0.0.1:5555")

    print(f"连接结果: {success}")
    print(f"_last_connected_device: {manager.get_last_connected_device()}")

    assert success is True
    assert manager.get_last_connected_device() == "127.0.0.1:5555"
    print("PASS: connect_device 更新 _last_connected_device")


if __name__ == "__main__":
    print("=" * 60)
    print("测试上次连接设备逻辑")
    print("=" * 60)

    try:
        test_last_connected_device_should_prefer_device_status()
        print()
        test_last_connected_device_fallback_to_last_when_no_device()
        print()
        test_last_connected_device_updated_on_connect()
        print()
        print("=" * 60)
        print("所有测试通过")
        print("=" * 60)
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
