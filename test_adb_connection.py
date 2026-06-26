#!/usr/bin/env python3
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from core.capability.device.adb_manager import ADBDeviceManager
adb = ADBDeviceManager(
    adb_path=os.path.join(project_root, "3rd-part", "adb", "adb.exe"),
    timeout=30
)
print('ADB client:', adb.adb)
client = adb.adb
device = client.device('192.168.1.12:16512')
print('Device:', device)
try:
    sock = device.create_connection(1, 'scrcpy')
    print('Connection created:', sock)
    sock.close()
except Exception as e:
    print('Connection failed:', type(e).__name__, e)
