import sys
sys.path.insert(0, 'src')

from core.capability.device.adb_manager import ADBDeviceManager
from core.capability.input.screenshot.scrcpy_core import ScrcpyCore
import logging

logging.basicConfig(level=logging.DEBUG)

adb = ADBDeviceManager(adb_path='3rd-part/adb/adb.exe')
core = ScrcpyCore(adb, '192.168.1.12:16512')
try:
    print("Starting scrcpy...")
    core.start()
    import time
    time.sleep(10)
    print('Server still running after 10s')
    core.stop()
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
