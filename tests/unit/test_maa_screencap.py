#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test MaaFramework with different screencap methods"""

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

def main():
    print("=" * 60)
    print("MaaFramework Screencap Methods Test")
    print("=" * 60)
    
    device_address = "127.0.0.1:16512"
    adb_path = "3rd-part/ADB/adb.exe"
    
    # Test different screencap methods
    # 0 = Default (auto)
    # 1 = RawByNetcat
    # 2 = EncodeToFileAndPull
    # 3 = MinicapDirect
    # 4 = MinicapStream
    # 5 = RawWithGzip
    # 6 = EncodeToADB
    
    methods = [
        (0, "Default (auto)"),
        (1, "RawByNetcat"),
        (2, "EncodeToFileAndPull"),
        (5, "RawWithGzip"),
        (6, "EncodeToADB"),
    ]
    
    for method_code, method_name in methods:
        print(f"\n[Test] screencap_methods={method_code} ({method_name})")
        
        touch_manager = TouchManager()
        result = touch_manager.connect_android(
            adb_path=adb_path,
            address=device_address,
            screencap_methods=method_code
        )
        
        if result:
            print(f"[PASS] Connected with {method_name}")
            print(f"[INFO] resolution: {touch_manager.resolution}")
            
            # Try screencap
            try:
                screen = touch_manager.screencap()
                if screen:
                    print(f"[PASS] Screencap successful")
                else:
                    print(f"[WARN] Screencap returned None")
            except Exception as e:
                print(f"[FAIL] Screencap error: {str(e)[:80]}")
            
            touch_manager.disconnect()
            print("[INFO] Disconnected")
            break  # Found working method
        else:
            print(f"[FAIL] Connection failed with {method_name}")
    
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)

if __name__ == '__main__':
    main()