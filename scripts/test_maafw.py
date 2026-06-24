import sys, os, json
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path; ensure_path()

# Add MaaFramework path
maa_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "MaaFramework")
if os.path.isdir(maa_path):
    sys.path.insert(0, maa_path)

from core.foundation.logger import init_logger, get_logger, LogCategory
init_logger()

adb_path = os.path.join(project_root, "3rd-part", "adb", "adb.exe")
address = "127.0.0.1:5563"

print(f"Testing MaaFw connection to {address} with adb={adb_path}")
print(f"  ADB exists: {os.path.isfile(adb_path)}")
print(f"  MaaFw importable: ", end="")

try:
    from maafw import Tasker, Resource, Controller, AdbController, Win32Controller
    from maafw.controller import AdbController
    print("YES")
    
    import MaaFw
    print(f"  MaaFw version: {MaaFw.__version__ if hasattr(MaaFw, '__version__') else 'unknown'}")
except ImportError as e:
    print(f"NO - {e}")
    # Try the package name approach
    try:
        import MaaFw
        print(f"YES (as MaaFw)")
    except ImportError as e2:
        print(f"NO - {e2}")
        sys.exit(1)

print("\nAttempting direct MaaFw controller connection...")
try:
    controller = AdbController(adb_path=adb_path, address=address, screencap_methods=2, input_methods=2)
    print(f"  Controller created: {controller}")
    
    result = controller.post_connection()
    print(f"  Connection result: {result}")
    
    if result and result.succeeded():
        print("  MaaFw CONNECTED SUCCESSFULLY!")
        
        # Get resolution
        resolution = controller.get_resolution()
        print(f"  Resolution: {resolution}")
        
        # Test click
        job = controller.post_click(500, 500)
        job.wait()
        print(f"  Click result: succeeded={job.succeeded()}")
    else:
        print(f"  Connection failed")
except Exception as e:
    print(f"  Error: {e}")
    import traceback
    traceback.print_exc()