"""
StarRailCopilot 迁移完整性验证脚本
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

def check_imports():
    """检查所有核心模块导入"""
    print("\n" + "="*60)
    print("1. 模块导入检查")
    print("="*60)

    modules = {
        '设备检测': 'core.capability.device.device_detector',
        'ADB管理器': 'core.capability.device.adb_manager',
        '触控管理器': 'core.capability.device.touch.touch_manager',
        '截图器': 'core.capability.input.screenshot.screen_capture',
        '配置管理': 'core.foundation.config_manager',
        '日志系统': 'core.foundation.logger',
        '错误处理': 'core.capability.device.stuck_detector',
    }

    results = {}
    for name, mod in modules.items():
        try:
            __import__(mod)
            results[name] = (True, None)
            print(f"  ✅ {name}: {mod}")
        except Exception as e:
            results[name] = (False, str(e))
            print(f"  ❌ {name}: {mod}")
            print(f"     错误: {e}")

    return results

def check_classes():
    """检查关键类是否可用"""
    print("\n" + "="*60)
    print("2. 关键类检查")
    print("="*60)

    classes = {
        'DeviceDetector': 'core.capability.device.device_detector',
        'DeviceInfo': 'core.capability.device.device_detector',
        'DeviceType': 'core.capability.device.device_detector',
        'ADBDeviceManager': 'core.capability.device.adb_manager',
        'TouchManager': 'core.capability.device.touch.touch_manager',
        'ScreenCapture': 'core.capability.input.screenshot.screen_capture',
        'ConfigManager': 'core.foundation.config_manager',
        'StuckDetector': 'core.capability.device.stuck_detector',
        'ErrorHandler': 'core.capability.device.stuck_detector',
    }

    results = {}
    for cls_name, mod_name in classes.items():
        try:
            mod = __import__(mod_name, fromlist=[cls_name])
            cls = getattr(mod, cls_name)
            results[cls_name] = (True, None)
            print(f"  ✅ {cls_name}")
        except Exception as e:
            results[cls_name] = (False, str(e))
            print(f"  ❌ {cls_name}: {e}")

    return results

def check_methods():
    """检查关键方法是否存在"""
    print("\n" + "="*60)
    print("3. 关键方法检查")
    print("="*60)

    from core.capability.device.adb_manager import ADBDeviceManager
    from core.capability.device.device_detector import DeviceDetector
    from core.capability.device.touch.touch_manager import TouchManager
    from core.capability.input.screenshot.screen_capture import ScreenCapture

    checks = {
        'ADBDeviceManager': [
            'get_device_info',
            'get_device_type',
            'get_recommended_config',
            'get_devices',
            'shell_command',
        ],
        'DeviceDetector': [
            'detect_device_type',
            'get_device_info',
            'get_recommended_config',
        ],
        'TouchManager': [
            'connect_android',
            'disconnect',
            'safe_press',
            'safe_swipe',
            'safe_long_press',
            'run_pipeline_task',
        ],
        'ScreenCapture': [
            'capture_screen',
            'start_scrcpy',
            'stop_scrcpy',
        ],
    }

    results = {}
    for cls_name, methods in checks.items():
        try:
            if cls_name == 'ADBDeviceManager':
                cls = ADBDeviceManager
            elif cls_name == 'DeviceDetector':
                cls = DeviceDetector
            elif cls_name == 'TouchManager':
                cls = TouchManager
            elif cls_name == 'ScreenCapture':
                cls = ScreenCapture

            missing = []
            for method in methods:
                if not hasattr(cls, method):
                    missing.append(method)

            if missing:
                results[cls_name] = (False, missing)
                print(f"  ❌ {cls_name}: 缺少方法 {missing}")
            else:
                results[cls_name] = (True, None)
                print(f"  ✅ {cls_name}: {', '.join(methods)}")
        except Exception as e:
            results[cls_name] = (False, str(e))
            print(f"  ❌ {cls_name}: {e}")

    return results

def check_config():
    """检查配置文件"""
    print("\n" + "="*60)
    print("4. 配置文件检查")
    print("="*60)

    config_path = Path('config/client_config.example.json')
    if not config_path.exists():
        print("  ❌ client_config.example.json 不存在")
        return False

    import json
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        required_sections = ['screen', 'touch']
        missing = [s for s in required_sections if s not in config]

        if missing:
            print(f"  ❌ 缺少配置段: {missing}")
            return False
        else:
            print("  ✅ 配置文件结构完整")
            print(f"     - screen.method: {config['screen'].get('method')}")
            print(f"     - touch.method: {config['touch'].get('method')}")
            print(f"     - screen.methods: {list(config['screen'].get('methods', {}).keys())}")
            print(f"     - touch.methods: {list(config['touch'].get('methods', {}).keys())}")
            return True
    except Exception as e:
        print(f"  ❌ 配置文件解析失败: {e}")
        return False

def check_tests():
    """检查测试文件"""
    print("\n" + "="*60)
    print("5. 测试文件检查")
    print("="*60)

    test_files = [
        'tests/test_device_detector.py',
        'tests/test_integration.py',
    ]

    results = {}
    for test_file in test_files:
        path = Path(test_file)
        if path.exists():
            # 检查文件内容，统计测试方法数量
            try:
                content = path.read_text(encoding='utf-8')
                test_count = content.count('def test_')
                results[test_file] = (True, test_count)
                print(f"  ✅ {test_file} ({test_count} 个测试)")
            except Exception as e:
                results[test_file] = (False, str(e))
                print(f"  ❌ {test_file}: {e}")
        else:
            results[test_file] = (False, "文件不存在")
            print(f"  ❌ {test_file}: 不存在")

    return results

def main():
    print("\n" + "="*60)
    print("StarRailCopilot 迁移完整性验证")
    print("="*60)

    results = {
        'imports': check_imports(),
        'classes': check_classes(),
        'methods': check_methods(),
        'config': check_config(),
        'tests': check_tests(),
    }

    # 总结
    print("\n" + "="*60)
    print("验证总结")
    print("="*60)

    total_checks = 0
    passed_checks = 0

    for category, checks in results.items():
        if isinstance(checks, dict):
            for name, (success, _) in checks.items():
                total_checks += 1
                if success:
                    passed_checks += 1
        else:
            total_checks += 1
            if checks:
                passed_checks += 1

    print(f"\n通过: {passed_checks}/{total_checks}")

    if passed_checks == total_checks:
        print("\n🎉 所有检查通过！迁移完整且可用。")
        return 0
    else:
        print(f"\n⚠️  有 {total_checks - passed_checks} 项检查未通过，请检查上述错误。")
        return 1

if __name__ == "__main__":
    sys.exit(main())