#!/usr/bin/env python3
"""
scrcpy 功能测试脚本
用于验证 ScreenCapture 的 scrcpy 集成是否正常工作
"""
import sys
from pathlib import Path

# 添加 src 到路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from core.capability.device.adb_manager import ADBDeviceManager
from core.capability.input.screenshot import ScreenCapture, ScrcpyCore, ScrcpyError
from core.foundation.logger import init_logger, get_logger

def test_scrcpy_import():
    """测试模块导入"""
    print("✓ 模块导入成功")
    return True

def test_scrcpy_core_initialization():
    """测试 ScrcpyCore 初始化（不启动）"""
    # 创建模拟的 ADB 管理器
    class MockADBManager:
        def __init__(self):
            self.adb_path = "adb"
            self.timeout = 10
            self._adb_client = None

        def push_file(self, serial, local, remote):
            print(f"  [Mock] push_file: {local} -> {remote}")
            return True

        def shell_command(self, serial, cmd, timeout=None, stream=False):
            print(f"  [Mock] shell_command: {cmd}")
            if stream:
                # 返回模拟的流对象
                class MockStream:
                    def read(self, n):
                        return b'[server] INFO: Device: test\n'
                    def close(self):
                        pass
                return MockStream(), None
            return 0, "OK"

        def create_connection(self, serial, network_type, name):
            print(f"  [Mock] create_connection: {name}")
            # 返回模拟 socket
            import socket
            return socket.socket()

    mock_adb = MockADBManager()
    config = {
        'screen': {
            'scrcpy': {
                'frame_rate': 10,
                'max_resolution': 1280,
                'bitrate': 20000000
            }
        }
    }

    try:
        core = ScrcpyCore(mock_adb, "127.0.0.1:5555", config.get('screen', {}).get('scrcpy', {}))
        print("✓ ScrcpyCore 初始化成功")
        print(f"  JAR 路径: {core.jar_path}")
        return True
    except Exception as e:
        print(f"✗ ScrcpyCore 初始化失败: {e}")
        return False

def test_screen_capture_initialization():
    """测试 ScreenCapture 初始化"""
    class MockADBManager:
        def __init__(self):
            self.adb_path = "adb"
            self.timeout = 10

    mock_adb = MockADBManager()
    config = {
        'screen': {
            'method': 'scrcpy',
            'scrcpy': {
                'frame_rate': 10,
                'max_resolution': 1280,
                'bitrate': 20000000
            }
        }
    }

    try:
        sc = ScreenCapture(mock_adb, config)
        print("✓ ScreenCapture 初始化成功")
        print(f"  scrcpy 启用: {sc._scrcpy_enabled}")
        return True
    except Exception as e:
        print(f"✗ ScreenCapture 初始化失败: {e}")
        return False

def main():
    print("=" * 50)
    print("scrcpy 功能测试")
    print("=" * 50)

    tests = [
        test_scrcpy_import,
        test_scrcpy_core_initialization,
        test_screen_capture_initialization,
    ]

    passed = 0
    failed = 0

    for test in tests:
        print(f"\n运行测试: {test.__name__}")
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ 测试异常: {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"结果: {passed} 通过, {failed} 失败")
    print("=" * 50)

    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
