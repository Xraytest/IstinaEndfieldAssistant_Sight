#!/usr/bin/env python3
"""Test scrcpy on real device"""
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

print("Step 1: Importing modules...")
from core.capability.device.adb_manager import ADBDeviceManager
from core.capability.input.screenshot.screen_capture import ScreenCapture
print("Step 2: Creating ADBDeviceManager...")

adb = ADBDeviceManager(
    adb_path=os.path.join(project_root, "3rd-part", "adb", "adb.exe"),
    timeout=30
)
print("Step 3: Getting devices...")
devices = adb.get_devices()
print(f"Devices: {devices}")
print(f"Current device: {adb.get_current_device()}")
print(f"Last connected device: {adb.get_last_connected_device()}")

print("Step 4: Creating ScreenCapture with strict scrcpy...")
config = {
    'screen': {
        'method': 'scrcpy',
        'strict': True,
        'scrcpy': {
            'frame_rate': 10,
            'max_resolution': 1280,
            'bitrate': 20000000,
            'auto_restart': True
        }
    }
}
sc = ScreenCapture(adb_manager=adb, config=config)
print("Step 5: Capturing screen with scrcpy...")

# Use the actual device address from adb devices
device_addr = "192.168.1.12:16512"
img = sc.capture_screen(device_addr)
print(f"Image type: {type(img)}")
print(f"Image length: {len(img) if img else 0}")
if img and len(img) > 100:
    print("SUCCESS: scrcpy captured real image from device!")
else:
    print("FAILED: scrcpy did not capture image")
