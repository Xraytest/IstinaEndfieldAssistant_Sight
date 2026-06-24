# -*- coding: utf-8 -*-
"""
使用help和dir探索MaaFramework实际API
注意：MaaFramework通过pip install MaaFw安装，导入名为 maa（不是 MaaFramework）
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

print("=== 探索maa模块（MaaFramework的正确导入） ===")

# 正确的导入方式：pip install MaaFw，导入名是 maa
try:
    import maa
    print(f"maa模块已导入")
    print(f"模块位置: {maa.__file__ if hasattr(maa, '__file__') else 'N/A'}")
    print(f"模块版本: {maa.__version__ if hasattr(maa, '__version__') else 'N/A'}")
    print(f"\nmaa模块内容 (dir):")
    for name in dir(maa):
        if not name.startswith('_'):
            print(f"  - {name}")
except ImportError as e:
    print(f"导入maa失败: {e}")
    print("请确保已安装: pip install MaaFw")
    sys.exit(1)

print("\n=== 探索maa.controller.AdbController ===")
try:
    from maa.controller import AdbController
    print(f"AdbController类已导入")
    print(f"\nAdbController类签名:")
    print(f"  类型: {type(AdbController)}")
    print(f"\nAdbController.__init__签名:")
    if hasattr(AdbController, '__init__'):
        help(AdbController.__init__)
    print(f"\nAdbController公共成员:")
    for name in dir(AdbController):
        if not name.startswith('_'):
            print(f"  - {name}")
except ImportError as e:
    print(f"导入AdbController失败: {e}")

print("\n=== 探索maa.toolkit.Toolkit ===")
try:
    from maa.toolkit import Toolkit
    print(f"Toolkit类已导入")
    print(f"\nToolkit成员:")
    for name in dir(Toolkit):
        if not name.startswith('_'):
            print(f"  - {name}")
    print(f"\nToolkit.find_adb_devices帮助:")
    if hasattr(Toolkit, 'find_adb_devices'):
        help(Toolkit.find_adb_devices)
except ImportError as e:
    print(f"导入Toolkit失败: {e}")

print("\n=== 探索maa.define枚举 ===")
try:
    from maa.define import MaaAdbScreencapMethodEnum, MaaAdbInputMethodEnum
    print(f"MaaAdbScreencapMethodEnum已导入")
    print(f"\nMaaAdbScreencapMethodEnum枚举值:")
    for name, value in MaaAdbScreencapMethodEnum.__members__.items():
        print(f"  - {name}: {value}")
    print(f"\nMaaAdbInputMethodEnum枚举值:")
    for name, value in MaaAdbInputMethodEnum.__members__.items():
        print(f"  - {name}: {value}")
except ImportError as e:
    print(f"导入枚举失败: {e}")

print("\n=== 探索maa.Library ===")
try:
    from maa import Library
    print(f"Library已导入")
    print(f"\nLibrary公共成员:")
    for name in dir(Library):
        if not name.startswith('_'):
            print(f"  - {name}")
except ImportError as e:
    print(f"导入Library失败: {e}")

print("\n=== 测试Toolkit.find_adb_devices ===")
try:
    from maa.toolkit import Toolkit
    devices = Toolkit.find_adb_devices()
    print(f"发现 {len(devices)} 个ADB设备")
    for i, dev in enumerate(devices):
        print(f"\n设备 {i}:")
        print(f"  类型: {type(dev)}")
        print(f"  成员: {[n for n in dir(dev) if not n.startswith('_')]}")
        for attr in ['adb_path', 'address', 'screencap_methods', 'input_methods', 'config']:
            if hasattr(dev, attr):
                val = getattr(dev, attr)
                print(f"  {attr}: {val}")
except Exception as e:
    print(f"Toolkit.find_adb_devices失败: {e}")
    import traceback
    traceback.print_exc()

print("\n=== 测试AdbController连接 ===")
try:
    from maa.controller import AdbController
    from maa.define import MaaAdbScreencapMethodEnum, MaaAdbInputMethodEnum
    
    adb_path = os.path.join(istina_root, "3rd-part", "ADB", "adb.exe")
    if not os.path.exists(adb_path):
        adb_path = "adb"
    
    target_address = "127.0.0.1:16512"
    
    print(f"尝试创建AdbController:")
    print(f"  adb_path: {adb_path}")
    print(f"  address: {target_address}")
    
    # 使用默认方法
    controller = AdbController(
        adb_path=adb_path,
        address=target_address,
        screencap_methods=MaaAdbScreencapMethodEnum.Default,
        input_methods=MaaAdbInputMethodEnum.Default,
        config={}
    )
    print(f"AdbController创建成功")
    print(f"\nAdbController公共成员:")
    for name in dir(controller):
        if not name.startswith('_'):
            print(f"  - {name}")
    
    print(f"\n尝试连接设备...")
    # 查看post_connection方法
    if hasattr(controller, 'post_connection'):
        help(controller.post_connection)
        job = controller.post_connection()
        print(f"post_connection返回: {job}")
        print(f"等待连接完成...")
        job.wait()
        print(f"连接状态: done={job.done}, succeeded={job.succeeded}, failed={job.failed}")
        
        if job.succeeded:
            print(f"连接成功!")
            # 检查cached_image
            if hasattr(controller, 'cached_image'):
                img = controller.cached_image
                print(f"cached_image: {type(img)}, shape={img.shape if img is not None else 'None'}")
        else:
            print(f"连接失败")
    
except Exception as e:
    print(f"AdbController测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n=== 测试完成 ===")