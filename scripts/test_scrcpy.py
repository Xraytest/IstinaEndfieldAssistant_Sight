#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
scrcpy 鍔熻兘娴嬭瘯鑴氭湰
鐢ㄤ簬楠岃瘉 ScreenCapture 鐨?scrcpy 闆嗘垚鏄惁姝ｅ父宸ヤ綔
"""
import sys
from pathlib import Path

# 娣诲姞 src 鍒拌矾寰?project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from core.capability.device.adb_manager import ADBDeviceManager
from core.capability.input.screenshot import ScreenCapture, ScrcpyCore, ScrcpyError
from core.foundation.logger import init_logger, get_logger

def test_scrcpy_import():
    """娴嬭瘯妯″潡瀵煎叆"""
    print("鉁?妯″潡瀵煎叆鎴愬姛")
    return True

def test_scrcpy_core_initialization():
    """娴嬭瘯 ScrcpyCore 鍒濆鍖栵紙涓嶅惎鍔級"""
    # 鍒涘缓妯℃嫙鐨?ADB 绠＄悊鍣?    class MockADBManager:
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
                # 杩斿洖妯℃嫙鐨勬祦瀵硅薄
                class MockStream:
                    def read(self, n):
                        return b'[server] INFO: Device: test\n'
                    def close(self):
                        pass
                return MockStream(), None
            return 0, "OK"

        def create_connection(self, serial, network_type, name):
            print(f"  [Mock] create_connection: {name}")
            # 杩斿洖妯℃嫙 socket
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
        print("鉁?ScrcpyCore 鍒濆鍖栨垚鍔?)
        print(f"  JAR 璺緞: {core.jar_path}")
        return True
    except Exception as e:
        print(f"鉁?ScrcpyCore 鍒濆鍖栧け璐? {e}")
        return False

def test_screen_capture_initialization():
    """娴嬭瘯 ScreenCapture 鍒濆鍖?""
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
        print("鉁?ScreenCapture 鍒濆鍖栨垚鍔?)
        print(f"  scrcpy 鍚敤: {sc._scrcpy_enabled}")
        return True
    except Exception as e:
        print(f"鉁?ScreenCapture 鍒濆鍖栧け璐? {e}")
        return False

def main():
    print("=" * 50)
    print("scrcpy 鍔熻兘娴嬭瘯")
    print("=" * 50)

    tests = [
        test_scrcpy_import,
        test_scrcpy_core_initialization,
        test_screen_capture_initialization,
    ]

    passed = 0
    failed = 0

    for test in tests:
        print(f"\n杩愯娴嬭瘯: {test.__name__}")
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"鉁?娴嬭瘯寮傚父: {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"缁撴灉: {passed} 閫氳繃, {failed} 澶辫触")
    print("=" * 50)

    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

