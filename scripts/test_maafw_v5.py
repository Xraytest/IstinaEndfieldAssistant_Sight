import sys, os, time, json, numpy as np
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path; ensure_path()
from core.foundation.logger import init_logger, get_logger, LogCategory
init_logger()

adb_path = os.path.join(project_root, "3rd-part", "adb", "adb.exe")
address = "127.0.0.1:5563"

import maa
from maa.controller import AdbController
from maa.job import Job, JobWithResult
from maa.define import MaaAdbScreencapMethodEnum, MaaAdbInputMethodEnum

print(f"Creating AdbController(adb={adb_path}, address={address})")
controller = AdbController(
    adb_path=adb_path,
    address=address,
    screencap_methods=MaaAdbScreencapMethodEnum.Default,
    input_methods=MaaAdbInputMethodEnum.Default,
)

print(f"Controller handle: {controller._handle}")
print(f"Posting connection...")
job = controller.post_connection()
print(f"  Job: {job}")
job.wait()
print(f"  Connected: {controller.connected}")

if controller.connected:
    print(f"  UUID: {controller.uuid}")
    print(f"  Resolution: {controller.resolution}")
    
    print(f"\nTesting click...")
    job = controller.post_click(500, 500)
    job.wait()
    print(f"  Click OK")
    
    print(f"\nTesting screencap...")
    job = controller.post_screencap()
    img = job.wait().result()
    print(f"  Screenshot shape: {img.shape if hasattr(img, 'shape') else 'unknown'}")
    
    print(f"\nMaaFw 5.10 WORKING!")
else:
    print("Connection failed")