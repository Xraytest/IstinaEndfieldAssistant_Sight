#!/usr/bin/env python3
"""调试 tap 坐标对比：扫描脚本 vs 标准流引擎"""
import subprocess, time, cv2, numpy as np, sys, os
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

ADB_PATH = f"{PROJECT_ROOT}\\3rd-party\\adb\\adb.exe"
DEVICE = "localhost:16512"

# 测试坐标：扫描脚本验证有效的坐标
TEST_X, TEST_Y = 860, 80

def adb_screencap():
    """截图"""
    r = subprocess.run([ADB_PATH, "-s", DEVICE, "exec-out", "screencap", "-p"],
                       capture_output=True, timeout=10)
    if r.returncode == 0 and len(r.stdout) > 1000:
        return cv2.imdecode(np.frombuffer(r.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
    return None

def count_gold_elements(img):
    """计算金色元素数量（页面特征）"""
    if img is None:
        return 0
    # 旋转到横屏
    img_rot = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    img_resized = cv2.resize(img_rot, (1280, 720))
    
    hsv = cv2.cvtColor(img_resized, cv2.COLOR_BGR2HSV)
    lower_gold = np.array([25, 100, 100])
    upper_gold = np.array([35, 255, 255])
    mask = cv2.inRange(hsv, lower_gold, upper_gold)
    
    kernel = np.ones((3,3),np.uint8)
    dilated_mask = cv2.dilate(mask, kernel, iterations=2)
    eroded_mask = cv2.erode(dilated_mask, kernel, iterations=1)
    
    contours, _ = cv2.findContours(eroded_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_contours = [c for c in contours if cv2.contourArea(c) > 50]
    return len(valid_contours)

def adb_back():
    """按返回键"""
    subprocess.run([ADB_PATH, "-s", DEVICE, "shell", "input", "keyevent", "4"], 
                   capture_output=True, timeout=5)

def test_scan_script_tap():
    """测试扫描脚本方式的 tap"""
    print("\n[测试 1] 扫描脚本方式：subprocess.run([... 'input', 'tap', '860', '80'])")
    result = subprocess.run(
        [ADB_PATH, "-s", DEVICE, "shell", "input", "tap", "860", "80"],
        capture_output=True, timeout=5
    )
    return result.returncode == 0

def test_adb_utils_tap():
    """测试 adb_utils 方式的 tap"""
    print("\n[测试 2] adb_utils 方式：ADB().tap(860, 80)")
    from core.adb_utils import ADB
    adb = ADB()
    return adb.tap(860, 80)

def test_adb_utils_tap_direct():
    """测试 adb_utils 底层函数的 tap"""
    print("\n[测试 3] adb_utils 底层：adb_tap(860, 80)")
    from core.adb_utils import adb_tap
    return adb_tap(860, 80)

def main():
    # 回到世界
    print("[前置] 回到世界...")
    for i in range(8):
        adb_back()
        time.sleep(0.3)
    time.sleep(2)
    
    # 基准截图
    img_base = adb_screencap()
    if img_base is None:
        print("[ERROR] 基准截图失败")
        sys.exit(1)
    
    gold_base = count_gold_elements(img_base)
    print(f"[基准] 分辨率：{img_base.shape[1]}x{img_base.shape[0]}")
    print(f"[基准] 金色元素：{gold_base}")
    
    if gold_base < 15:
        print("[警告] 金色元素数量较少，可能不在世界页面")
    elif gold_base > 20:
        print("[提示] 金色元素数量较多，可能在任务面板页面")
    else:
        print("[提示] 金色元素数量正常，应在世界页面")
    
    # 测试三种 tap 方式
    tests = [
        ("扫描脚本方式", test_scan_script_tap),
        ("ADB().tap()", test_adb_utils_tap),
        ("adb_tap()", test_adb_utils_tap_direct),
    ]
    
    for name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"[测试] {name}")
        print(f"{'='*60}")
        
        # 确保回到世界
        print("[准备] 回到世界...")
        for _ in range(5):
            adb_back()
            time.sleep(0.3)
        time.sleep(1)
        
        img_before = adb_screencap()
        gold_before = count_gold_elements(img_before)
        print(f"[点击前] 金色元素：{gold_before}")
        
        # 执行 tap
        success = test_func()
        print(f"[点击] input tap 860 80 {'成功' if success else '失败'}")
        
        # 等待并截图
        time.sleep(3)
        img_after = adb_screencap()
        gold_after = count_gold_elements(img_after)
        print(f"[点击后] 金色元素：{gold_after}")
        
        # 判断结果
        if gold_after > gold_before + 5:
            print(f"[结果] ✅ 面板已打开 (金色 +{gold_after - gold_before})")
        elif gold_after < gold_before - 5:
            print(f"[结果] ❌ 金色消失 (金色 -{gold_before - gold_after})")
        else:
            print(f"[结果] ⚠️  无明显变化 (金色 {gold_after - gold_before:+d})")
        
        # 返回
        print("[恢复] 按返回键...")
        for _ in range(3):
            adb_back()
            time.sleep(0.3)
        time.sleep(1)

if __name__ == "__main__":
    main()
