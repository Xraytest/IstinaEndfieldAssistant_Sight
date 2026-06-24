#!/usr/bin/env python3
"""系统扫描所有导航栏图标位置 (像素差异法)"""
import sys, os, time, cv2, numpy as np, subprocess, json

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

PROJECT_ROOT = r'C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight'
SRC_DIR = os.path.join(PROJECT_ROOT, 'src')

from core.capability.device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig, MAAFW_AVAILABLE

ADB_PATH = os.path.join(PROJECT_ROOT, "3rd-part", "adb", "adb.exe")
DEVICE = "localhost:16512"

# 待扫描图标 (MaaFw 坐标，基于 ADB 坐标/1.5 估算)
ICONS_TO_SCAN = [
    {"name": "quest_icon", "x": 570, "y_range": (25, 65), "step": 5},   # 855/1.5=570
    {"name": "event_icon", "x": 619, "y_range": (25, 65), "step": 5},  # 928/1.5=619
    {"name": "menu_icon", "x": 928, "y_range": (25, 75), "step": 5},   # 1392/1.5=928
    {"name": "city_map", "x": 100, "y_range": (80, 180), "step": 10},  # 150/1.5=100
    {"name": "industry_panel", "x": 200, "y_range": (40, 120), "step": 15},  # 300/1.5=200
]

def go_to_world():
    """回到主世界"""
    print("[前置] 回到主世界...")
    for _ in range(6):
        subprocess.run([ADB_PATH, "-s", DEVICE, "shell", "input", "keyevent", "4"], capture_output=True)
        time.sleep(0.3)
    time.sleep(2)

def scan_icon(icon_info):
    """扫描单个图标"""
    name = icon_info["name"]
    x = icon_info["x"]
    y_start, y_end = icon_info["y_range"]
    step = icon_info["step"]
    
    print(f"\n{'='*60}")
    print(f"扫描：{name} (x={x}, y={y_start}-{y_end}, step={step})")
    print("="*60)
    
    # 基准截图
    img_base = executor.screencap()
    if img_base is None:
        print(f"[ERROR] 基准截图失败")
        return None
    
    results = []
    y_positions = list(range(y_start, y_end + 1, step))
    
    for y in y_positions:
        # 点击
        executor.click(x, y)
        time.sleep(2.5)
        
        # 截图
        img = executor.screencap()
        if img is None:
            print(f"y={y:3d}: 截图失败")
            continue
        
        # 像素差异分析
        diff = cv2.absdiff(img_base, img)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
        
        center_changed = cv2.countNonZero(thresh[80:650, 100:1180])
        nav_changed = cv2.countNonZero(thresh[35:75, 640:1000])
        total_changed = cv2.countNonZero(thresh)
        total_pixels = thresh.shape[0] * thresh.shape[1]
        change_rate = total_changed / total_pixels * 100
        
        results.append({
            'y': y,
            'center': center_changed,
            'nav': nav_changed,
            'rate': change_rate
        })
        
        status = "✅" if center_changed > 100000 else ("⚠️" if center_changed > 10000 else "❌")
        print(f"{status} y={y:3d}: center={center_changed:8d} px ({change_rate:5.1f}%)")
        
        # 关闭面板
        subprocess.run([ADB_PATH, "-s", DEVICE, "shell", "input", "keyevent", "4"], capture_output=True)
        time.sleep(1.5)
    
    if results:
        best = max(results, key=lambda r: r['center'])
        adb_y = int(best['y'] * 1.5)
        print(f"\n[最佳] y={best['y']} (MaaFw) → y={adb_y} (ADB)")
        print(f"[结果] {name}: [{x * 1.5}, {adb_y}]")
        return {name: [int(x * 1.5), adb_y], f"_{name}_note": f"扫描确认 center={best['center']}px"}
    return None

def main():
    if not MAAFW_AVAILABLE:
        print("[ERROR] MaaFramework 不可用")
        return 1
    
    # 连接设备
    config = MaaFwTouchConfig(
        adb_path=ADB_PATH,
        address=DEVICE,
        screencap_methods=MaaFwTouchConfig.SCREENCAP_ADB_SHELL,
        input_methods=MaaFwTouchConfig.INPUT_ADB_SHELL,
    )
    global executor
    executor = MaaFwTouchExecutor(config)
    if not executor.connect():
        print("[ERROR] 连接失败")
        return 1
    print(f"[OK] 已连接，分辨率：{executor.get_resolution()}")
    
    # 回到主世界
    go_to_world()
    
    # 扫描所有图标
    results = {}
    for icon in ICONS_TO_SCAN:
        result = scan_icon(icon)
        if result:
            results.update(result)
        time.sleep(1)
    
    # 输出结果
    print(f"\n{'='*60}")
    print("扫描完成！")
    print(f"{'='*60}")
    for k, v in results.items():
        print(f"{k}: {v}")
    
    executor.disconnect()
    return 0

if __name__ == "__main__":
    sys.exit(main())
