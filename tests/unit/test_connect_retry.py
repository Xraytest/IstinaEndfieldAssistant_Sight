# -*- coding: utf-8 -*-
"""
重试连接测试 - 模拟器重启后重新测试MaaFramework连接
"""
import sys
import os

# 设置路径
istina_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
安卓相关_dir = os.path.join(istina_root, "安卓相关")
入口_dir = os.path.join(istina_root, "入口")

if 安卓相关_dir not in sys.path:
    sys.path.insert(0, 安卓相关_dir)
if 入口_dir not in sys.path:
    sys.path.insert(0, 入口_dir)

print(f"Python路径已设置:")
print(f"  - 安卓相关: {安卓相关_dir}")
print(f"  - 入口: {入口_dir}")

# 测试ADB连接
print("\n=== 测试ADB连接 ===")
from 控制.adb_manager import ADBDeviceManager

adb_path = os.path.join(istina_root, "3rd-part", "ADB", "adb.exe")
if not os.path.exists(adb_path):
    adb_path = "adb"  # 使用系统PATH中的adb

print(f"ADB路径: {adb_path}")
adb_manager = ADBDeviceManager(adb_path)

# 启动ADB服务器
print("启动ADB服务器...")
adb_manager.start_server()

# 列出设备
print("扫描设备...")
devices = adb_manager.get_devices()
print(f"发现 {len(devices)} 个设备:")
for dev in devices:
    print(f"  - {dev.serial} ({dev.status}) address={dev.address}")

# 连接目标设备
target_device = "127.0.0.1:16512"
print(f"\n尝试连接 {target_device}...")
connect_result = adb_manager.connect_device(target_device)
print(f"连接结果: {connect_result}")

# 重新列出设备
devices = adb_manager.get_devices()
print(f"连接后设备列表:")
for dev in devices:
    print(f"  - {dev.serial} ({dev.status}) address={dev.address}")

# 测试ADB截图
print(f"\n=== 测试ADB截图 ===")
from 图像传递.screen_capture import ScreenCapture

screen_capture = ScreenCapture(adb_manager)
screenshot = screen_capture.capture_screen(target_device)
if screenshot:
    print(f"截图成功: {len(screenshot)} 字节")
else:
    print("截图失败")

# 测试MaaFramework连接
print(f"\n=== 测试MaaFramework TouchManager连接 ===")
from 控制.touch.touch_manager import TouchManager

touch_manager = TouchManager()

# 读取配置
import json
config_path = os.path.join(istina_root, "config", "maa_option.json")
with open(config_path, 'r', encoding='utf-8') as f:
    maa_config = json.load(f)

print(f"MaaFramework配置: {maa_config}")

# 尝试连接 - 使用screencap_methods=0 (默认)
print(f"\n尝试连接 {target_device} (screencap_methods=0)...")
result = touch_manager.connect_android(
    adb_path=adb_path,
    address=target_device,
    screencap_methods=0,
    input_methods=0,
    config=maa_config.get("maa_style", {})
)
print(f"连接结果: {result}")
print(f"连接状态: {touch_manager.connected}")

if touch_manager.connected:
    # 获取分辨率
    try:
        resolution = touch_manager.get_resolution()
        print(f"分辨率: {resolution}")
    except Exception as e:
        print(f"获取分辨率失败: {e}")
    
    # 尝试截图
    try:
        image = touch_manager.screencap()
        if image is not None:
            print(f"MaaFramework截图成功: {type(image)}")
        else:
            print("MaaFramework截图返回None")
    except Exception as e:
        print(f"MaaFramework截图失败: {e}")
else:
    print("连接失败，尝试其他screencap方法...")
    
    # 尝试不同的screencap方法
    for method in [1, 2, 5, 6]:
        print(f"\n尝试 screencap_methods={method}...")
        tm = TouchManager()
        result = tm.connect_android(
            adb_path=adb_path,
            address=target_device,
            screencap_methods=method,
            input_methods=0,
            config=maa_config.get("maa_style", {})
        )
        print(f"  连接结果: {result}, 状态: {tm.connected}")
        if tm.connected:
            try:
                resolution = tm.get_resolution()
                print(f"  分辨率: {resolution}")
                image = tm.screencap()
                if image is not None:
                    print(f"  截图成功!")
                    break
            except Exception as e:
                print(f"  操作失败: {e}")

print("\n=== 测试完成 ===")