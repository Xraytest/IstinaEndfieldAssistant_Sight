#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鐧诲嚭瀵硅瘽妗嗗鐞嗚剼鏈?- 浣跨敤澶氱鏂规硶纭繚鐐瑰嚮鎴愬姛
"""

import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def click_with_adb(device_serial: str, x: int, y: int):
    """浣跨敤 ADB 鐩存帴鐐瑰嚮"""
    print(f"[ADB] 鐐瑰嚮 ({x}, {y})")
    adb_path = PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"
    result = subprocess.run(
        [str(adb_path), "-s", device_serial, "shell", "input", "tap", str(x), str(y)],
        capture_output=True,
        text=True
    )
    print(f"  缁撴灉锛歿result.returncode}")
    return result.returncode == 0

def click_multiple_times(device_serial: str, x: int, y: int, times: int = 3):
    """澶氭鐐瑰嚮浠ユ彁楂樻垚鍔熺巼"""
    print(f"[鐐瑰嚮] 灏濊瘯 {times} 娆?@ ({x}, {y})")
    for i in range(times):
        print(f"  绗?{i+1}/{times} 娆?)
        click_with_adb(device_serial, x, y)
        import time
        time.sleep(0.5)

def main():
    device_serial = "192.168.1.12:16512"
    
    print("\n" + "="*60)
    print("鐧诲嚭瀵硅瘽妗嗗鐞?- 澶氭鐐瑰嚮纭鎸夐挳")
    print("="*60)
    
    # 鐧诲嚭瀵硅瘽妗嗙‘璁ゆ寜閽綅缃?    # 鐗╃悊鍧愭爣锛?920x1080, 鎸夐挳鍦ㄥ簳閮ㄤ腑澶?    # 閫昏緫鍧愭爣锛?280x720
    # 鎸夐挳澶х害鍦?(640, 580) 宸﹀彸
    
    print("\n灏濊瘯 1: 浣跨敤閫昏緫鍧愭爣 (640, 580)")
    click_multiple_times(device_serial, 640, 580, times=3)
    
    import time
    time.sleep(2)
    
    print("\n灏濊瘯 2: 浣跨敤鐗╃悊鍧愭爣 (960, 850)")
    click_multiple_times(device_serial, 960, 850, times=3)
    
    time.sleep(2)
    
    print("\n灏濊瘯 3: 浣跨敤灞忓箷搴曢儴涓ぎ (640, 650)")
    click_multiple_times(device_serial, 640, 650, times=3)
    
    time.sleep(2)
    
    print("\n" + "="*60)
    print("鐐瑰嚮瀹屾垚锛岃妫€鏌ヨ澶囩姸鎬?)
    print("="*60)
    
    # 鎴浘纭
    print("\n鎴浘纭...")
    result = subprocess.run(
        ["adb", "-s", device_serial, "exec-out", "screencap", "-p"],
        capture_output=True
    )
    if result.returncode == 0:
        output_path = PROJECT_ROOT / "cache" / "logout_check.png"
        with open(output_path, "wb") as f:
            f.write(result.stdout)
        print(f"鎴浘宸蹭繚瀛橈細{output_path}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

