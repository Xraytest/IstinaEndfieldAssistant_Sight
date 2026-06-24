#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
scrcpy 闆嗘垚楠岃瘉鑴氭湰
妫€鏌ユ墍鏈夌粍浠舵槸鍚︽纭畨瑁呭拰閰嶇疆
"""
import sys
from pathlib import Path

# 娣诲姞 src 鍒拌矾寰?project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

def check_dependencies():
    """妫€鏌?Python 渚濊禆"""
    print("1. 妫€鏌?Python 渚濊禆...")
    missing = []

    try:
        import av
        print(f"   鉁?av (PyAV) 宸插畨瑁? 鐗堟湰: {av.__version__}")
    except ImportError:
        missing.append("av")
        print("   鉁?av (PyAV) 鏈畨瑁?)

    try:
        import adbutils
        print(f"   鉁?adbutils 宸插畨瑁? 鐗堟湰: {adbutils.__version__}")
    except ImportError:
        missing.append("adbutils")
        print("   鉁?adbutils 鏈畨瑁?)

    try:
        from PIL import Image
        print(f"   鉁?Pillow 宸插畨瑁?)
    except ImportError:
        missing.append("Pillow")
        print("   鉁?Pillow 鏈畨瑁?)

    try:
        import numpy as np
        print(f"   鉁?numpy 宸插畨瑁? 鐗堟湰: {np.__version__}")
    except ImportError:
        missing.append("numpy")
        print("   鉁?numpy 鏈畨瑁?)

    if missing:
        print(f"\n   缂哄皯渚濊禆: {', '.join(missing)}")
        print("   璇疯繍琛? venv\\Scripts\\python.exe -m pip install " + " ".join(missing))
        return False
    return True

def check_resources():
    """妫€鏌ヨ祫婧愭枃浠?""
    print("\n2. 妫€鏌ヨ祫婧愭枃浠?..")

    jar_path = project_root / "3rd-part" / "scrcpy" / "scrcpy-server.jar"
    if jar_path.exists():
        size_mb = jar_path.stat().st_size / (1024*1024)
        print(f"   鉁?scrcpy-server.jar 瀛樺湪 ({size_mb:.1f} MB)")
        return True
    else:
        print(f"   鉁?scrcpy-server.jar 涓嶅瓨鍦? {jar_path}")
        print("   璇蜂粠 StarRailCopilot 澶嶅埗: bin/scrcpy/scrcpy-server-v1.25.jar")
        return False

def check_modules():
    """妫€鏌ユā鍧楀鍏?""
    print("\n3. 妫€鏌ユā鍧楀鍏?..")

    try:
        from core.capability.input.screenshot import ScreenCapture, ScrcpyCore
        print("   鉁?ScreenCapture 瀵煎叆鎴愬姛")
        print("   鉁?ScrcpyCore 瀵煎叆鎴愬姛")

        # 妫€鏌ュ紓甯哥被
        from core.capability.input.screenshot import (
            ScrcpyError,
            ScrcpyServerError,
            ScrcpyConnectionError,
            ScrcpyDecodeError
        )
        print("   鉁?寮傚父绫诲鍏ユ垚鍔?)
        return True
    except ImportError as e:
        print(f"   鉁?妯″潡瀵煎叆澶辫触: {e}")
        return False

def check_adb_manager():
    """妫€鏌?ADB 绠＄悊鍣ㄩ泦鎴?""
    print("\n4. 妫€鏌?ADB 绠＄悊鍣?..")

    try:
        from core.capability.device.adb_manager import ADBDeviceManager
        print("   鉁?ADBDeviceManager 瀵煎叆鎴愬姛")

        # 妫€鏌?adbutils 闆嗘垚
        adb = ADBDeviceManager("adb", timeout=10)
        if hasattr(adb, 'adb') and callable(getattr(adb, 'create_connection', None)):
            print("   鉁?adbutils 闆嗘垚姝ｅ父")
            return True
        else:
            print("   鈿?adbutils 闆嗘垚鍙兘涓嶅畬鏁?)
            return True  # 浠嶇劧绠楅€氳繃
    except Exception as e:
        print(f"   鉁?ADB 绠＄悊鍣ㄦ鏌ュけ璐? {e}")
        return False

def check_config():
    """妫€鏌ラ厤缃枃浠?""
    print("\n5. 妫€鏌ラ厤缃枃浠?..")

    config_path = project_root / "config" / "client_config.example.json"
    if not config_path.exists():
        print(f"   鉁?閰嶇疆鏂囦欢涓嶅瓨鍦? {config_path}")
        return False

    import json
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        screen_config = config.get('screen', {})
        method = screen_config.get('method', '')
        scrcpy_config = screen_config.get('scrcpy', {})

        print(f"   鉁?閰嶇疆鏂囦欢瀛樺湪")
        print(f"   - screen.method: {method or '鏈缃?}")
        print(f"   - screen.scrcpy: {scrcpy_config or '鏈缃?}")

        if method == 'scrcpy':
            print("   鉁?榛樿鏂规硶涓?scrcpy")
        else:
            print("   鈿?榛樿鏂规硶涓嶆槸 scrcpy锛堝缓璁缃负 'scrcpy'锛?)

        return True
    except Exception as e:
        print(f"   鉁?閰嶇疆鏂囦欢瑙ｆ瀽澶辫触: {e}")
        return False

def main():
    print("=" * 60)
    print("scrcpy 闆嗘垚楠岃瘉")
    print("=" * 60)

    checks = [
        check_dependencies,
        check_resources,
        check_modules,
        check_adb_manager,
        check_config,
    ]

    results = []
    for check in checks:
        try:
            results.append(check())
        except Exception as e:
            print(f"   鉁?妫€鏌ュ紓甯? {e}")
            results.append(False)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"缁撴灉: {passed}/{total} 椤规鏌ラ€氳繃")

    if passed == total:
        print("鉁?鎵€鏈夋鏌ラ€氳繃锛乻crcpy 闆嗘垚灏辩华銆?)
        print("\n浣跨敤璇存槑锛?)
        print("1. 纭繚 ADB 鏈嶅姟鍣ㄨ繍琛? 3rd-part\\adb\\adb.exe start-server")
        print("2. 杩炴帴璁惧: 3rd-part\\adb\\adb.exe devices")
        print("3. 杩愯娴嬭瘯: venv\\Scripts\\python.exe scripts\\test_scrcpy.py")
        print("4. 鍦ㄤ唬鐮佷腑浣跨敤:")
        print("   from core.capability.input.screenshot import ScreenCapture")
        print("   sc = ScreenCapture(adb_manager, config)")
        print("   img = sc.capture_screen(device_serial)")
    else:
        print("鉂?閮ㄥ垎妫€鏌ユ湭閫氳繃锛岃淇涓婅堪闂銆?)

    print("=" * 60)
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

