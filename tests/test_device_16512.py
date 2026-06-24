#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test connection to device 127.0.0.1:16512"""

import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
os.chdir(project_root)

android_dir = os.path.join(project_root, "安卓相关")
entry_dir = os.path.join(project_root, "入口")
if android_dir not in sys.path:
    sys.path.insert(0, android_dir)
if entry_dir not in sys.path:
    sys.path.insert(0, entry_dir)

from 控制.touch.touch_manager import TouchManager
from 控制.adb_manager import ADBDeviceManager
from 图像传递.screen_capture import ScreenCapture

def main():
    print("=" * 60)
    print("Device Connection Test - 127.0.0.1:16512")
    print("=" * 60)
    
    device_address = "127.0.0.1:16512"
    
    # Test TouchManager connection
    print("\n[Step 1] TouchManager Connection")
    touch_manager = TouchManager()
    print('[PASS] TouchManager created')
    
    print('[INFO] Connecting to', device_address)
    result = touch_manager.connect_android(
        adb_path='3rd-part/ADB/adb.exe',
        address=device_address
    )
    
    if result:
        print('[PASS] Device connected successfully!')
        print('[INFO] connected:', touch_manager.connected)
        print('[INFO] device_type:', touch_manager.device_type)
        print('[INFO] resolution:', touch_manager.resolution)
        
        # Test screen capture through TouchManager
        print("\n[Step 2] Screen Capture via TouchManager")
        try:
            screen = touch_manager.screencap()
            if screen:
                print('[PASS] Screen captured via TouchManager')
            else:
                print('[WARN] Screencap returned None')
        except Exception as e:
            print('[INFO] Screencap error:', str(e)[:100])
        
        # Disconnect
        print("\n[Step 3] Disconnect")
        touch_manager.disconnect()
        print('[PASS] Disconnected')
    else:
        print('[FAIL] Connection failed')
    
    # Test ScreenCapture module
    print("\n[Step 4] ScreenCapture Module Test")
    adb_manager = ADBDeviceManager("3rd-part/ADB/adb.exe", timeout=10)
    screen_capture = ScreenCapture(adb_manager)
    
    try:
        screen_data = screen_capture.capture_screen(device_address)
        if screen_data:
            print('[PASS] Screen captured, size:', len(screen_data), 'bytes')
        else:
            print('[WARN] Capture returned None')
    except Exception as e:
        print('[INFO] Capture error:', str(e)[:100])
    
    # Get device info
    print("\n[Step 5] Device Info")
    try:
        info = screen_capture.get_device_info(device_address)
        print('[INFO] Device info:', info)
    except Exception as e:
        print('[INFO] Device info error:', str(e)[:100])
    
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)

if __name__ == '__main__':
    main()