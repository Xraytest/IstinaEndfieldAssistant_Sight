# -*- coding: utf-8 -*-
"""
使用Toolkit发现的正确设备信息连接MaaFramework
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

print("=== 使用Toolkit发现的正确设备信息连接 ===")

from maa.toolkit import Toolkit
from maa.controller import AdbController

# 使用Toolkit发现设备
print("使用Toolkit.find_adb_devices发现设备...")
devices = Toolkit.find_adb_devices()
print(f"发现 {len(devices)} 个设备")

# 找到目标设备 127.0.0.1:16512
target_address = "127.0.0.1:16512"
target_device = None
for dev in devices:
    print(f"\n设备信息:")
    print(f"  name: {dev.name}")
    print(f"  adb_path: {dev.adb_path}")
    print(f"  address: {dev.address}")
    print(f"  screencap_methods: {dev.screencap_methods}")
    print(f"  input_methods: {dev.input_methods}")
    print(f"  config: {dev.config}")
    if dev.address == target_address:
        target_device = dev

if target_device is None:
    print(f"未找到目标设备 {target_address}")
    sys.exit(1)

print(f"\n找到目标设备: {target_address}")
print("使用设备信息创建AdbController...")

# 使用发现的设备信息创建控制器
controller = AdbController(
    adb_path=target_device.adb_path,
    address=target_device.address,
    screencap_methods=target_device.screencap_methods,
    input_methods=target_device.input_methods,
    config=target_device.config
)
print(f"AdbController创建成功")

# 连接设备
print(f"\n连接设备...")
job = controller.post_connection()
print(f"等待连接完成...")
job.wait()
print(f"连接状态: done={job.done}, succeeded={job.succeeded}, failed={job.failed}")

if job.succeeded:
    print(f"连接成功!")
    
    # 检查连接状态
    print(f"\n检查控制器状态:")
    print(f"  connected: {controller.connected}")
    print(f"  uuid: {controller.uuid}")
    print(f"  info: {controller.info}")
    
    # 尝试截图
    print(f"\n尝试截图 (post_screencap)...")
    screencap_job = controller.post_screencap()
    screencap_job.wait()
    print(f"截图状态: done={screencap_job.done}, succeeded={screencap_job.succeeded}, failed={screencap_job.failed}")
    
    if screencap_job.succeeded:
        print(f"截图成功!")
        # 现在检查cached_image
        try:
            img = controller.cached_image
            if img is not None:
                print(f"cached_image: type={type(img)}, shape={img.shape}")
            else:
                print(f"cached_image: None")
        except Exception as e:
            print(f"获取cached_image失败: {e}")
    else:
        print(f"截图失败")
else:
    print(f"连接失败")

print("\n=== 测试完成 ===")