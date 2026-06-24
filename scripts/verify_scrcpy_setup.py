#!/usr/bin/env python3
"""
scrcpy 集成验证脚本
检查所有组件是否正确安装和配置
"""
import sys
from pathlib import Path

# 添加 src 到路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

def check_dependencies():
    """检查 Python 依赖"""
    print("1. 检查 Python 依赖...")
    missing = []

    try:
        import av
        print(f"   ✓ av (PyAV) 已安装, 版本: {av.__version__}")
    except ImportError:
        missing.append("av")
        print("   ✗ av (PyAV) 未安装")

    try:
        import adbutils
        print(f"   ✓ adbutils 已安装, 版本: {adbutils.__version__}")
    except ImportError:
        missing.append("adbutils")
        print("   ✗ adbutils 未安装")

    try:
        from PIL import Image
        print(f"   ✓ Pillow 已安装")
    except ImportError:
        missing.append("Pillow")
        print("   ✗ Pillow 未安装")

    try:
        import numpy as np
        print(f"   ✓ numpy 已安装, 版本: {np.__version__}")
    except ImportError:
        missing.append("numpy")
        print("   ✗ numpy 未安装")

    if missing:
        print(f"\n   缺少依赖: {', '.join(missing)}")
        print("   请运行: venv\\Scripts\\python.exe -m pip install " + " ".join(missing))
        return False
    return True

def check_resources():
    """检查资源文件"""
    print("\n2. 检查资源文件...")

    jar_path = project_root / "3rd-part" / "scrcpy" / "scrcpy-server.jar"
    if jar_path.exists():
        size_mb = jar_path.stat().st_size / (1024*1024)
        print(f"   ✓ scrcpy-server.jar 存在 ({size_mb:.1f} MB)")
        return True
    else:
        print(f"   ✗ scrcpy-server.jar 不存在: {jar_path}")
        print("   请从 StarRailCopilot 复制: bin/scrcpy/scrcpy-server-v1.25.jar")
        return False

def check_modules():
    """检查模块导入"""
    print("\n3. 检查模块导入...")

    try:
        from core.capability.input.screenshot import ScreenCapture, ScrcpyCore
        print("   ✓ ScreenCapture 导入成功")
        print("   ✓ ScrcpyCore 导入成功")

        # 检查异常类
        from core.capability.input.screenshot import (
            ScrcpyError,
            ScrcpyServerError,
            ScrcpyConnectionError,
            ScrcpyDecodeError
        )
        print("   ✓ 异常类导入成功")
        return True
    except ImportError as e:
        print(f"   ✗ 模块导入失败: {e}")
        return False

def check_adb_manager():
    """检查 ADB 管理器集成"""
    print("\n4. 检查 ADB 管理器...")

    try:
        from core.capability.device.adb_manager import ADBDeviceManager
        print("   ✓ ADBDeviceManager 导入成功")

        # 检查 adbutils 集成
        adb = ADBDeviceManager("adb", timeout=10)
        if hasattr(adb, 'adb') and callable(getattr(adb, 'create_connection', None)):
            print("   ✓ adbutils 集成正常")
            return True
        else:
            print("   ⚠ adbutils 集成可能不完整")
            return True  # 仍然算通过
    except Exception as e:
        print(f"   ✗ ADB 管理器检查失败: {e}")
        return False

def check_config():
    """检查配置文件"""
    print("\n5. 检查配置文件...")

    config_path = project_root / "config" / "client_config.example.json"
    if not config_path.exists():
        print(f"   ✗ 配置文件不存在: {config_path}")
        return False

    import json
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        screen_config = config.get('screen', {})
        method = screen_config.get('method', '')
        scrcpy_config = screen_config.get('scrcpy', {})

        print(f"   ✓ 配置文件存在")
        print(f"   - screen.method: {method or '未设置'}")
        print(f"   - screen.scrcpy: {scrcpy_config or '未设置'}")

        if method == 'scrcpy':
            print("   ✓ 默认方法为 scrcpy")
        else:
            print("   ⚠ 默认方法不是 scrcpy（建议设置为 'scrcpy'）")

        return True
    except Exception as e:
        print(f"   ✗ 配置文件解析失败: {e}")
        return False

def main():
    print("=" * 60)
    print("scrcpy 集成验证")
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
            print(f"   ✗ 检查异常: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"结果: {passed}/{total} 项检查通过")

    if passed == total:
        print("✅ 所有检查通过！scrcpy 集成就绪。")
        print("\n使用说明：")
        print("1. 确保 ADB 服务器运行: 3rd-part\\adb\\adb.exe start-server")
        print("2. 连接设备: 3rd-part\\adb\\adb.exe devices")
        print("3. 运行测试: venv\\Scripts\\python.exe scripts\\test_scrcpy.py")
        print("4. 在代码中使用:")
        print("   from core.capability.input.screenshot import ScreenCapture")
        print("   sc = ScreenCapture(adb_manager, config)")
        print("   img = sc.capture_screen(device_serial)")
    else:
        print("❌ 部分检查未通过，请修复上述问题。")

    print("=" * 60)
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
