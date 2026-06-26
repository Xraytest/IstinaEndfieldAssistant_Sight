#!/usr/bin/env python3
import sys
sys.path.insert(0, 'C:\\Users\\cheng\\Documents\\ArkStudio\\IstinaAI\\IstinaEndfieldAssistant_Sight\\src')
from core.capability.device.adb_manager import ADBDeviceManager
adb = ADBDeviceManager(adb_path='C:\\Users\\cheng\\Documents\\ArkStudio\\IstinaAI\\IstinaEndfieldAssistant_Sight\\3rd-part\\adb\\adb.exe', timeout=30)
client = adb.adb
device = client.device('192.168.1.12:16512')
try:
    from adbutils import Network as AdbNetwork
    sock = device.create_connection(AdbNetwork.LOCAL_ABSTRACT, 'scrcpy')
    print('Connection created:', sock)
    sock.close()
except Exception as e:
    print('Connection failed:', type(e).__name__, e)
