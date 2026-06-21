#!/usr/bin/env python3
"""扫描导航栏任务图标精确位置 (像素差异法)"""
import sys, os, time, cv2, numpy as np, subprocess

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

from device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig, MAAFW_AVAILABLE

ADB_PATH = os.path.join(str(PROJECT_ROOT), "3rd-party", "adb", "adb.exe")
DEVICE = "localhost:16512"

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
    executor = MaaFwTouchExecutor(config)
    if not executor.connect():
        print("[ERROR] 连接失败")
        return 1
    print(f"[OK] 已连接，分辨率：{executor.get_resolution()}")
    
    # 回到主世界
    print("[前置] 回到主世界...")
    for _ in range(6):
        subprocess.run([ADB_PATH, "-s", DEVICE, "shell", "input", "keyevent", "4"], capture_output=True)
        time.sleep(0.3)
    time.sleep(2)
    
    # 基准截图
    print("[基准] 获取基准截图...")
    img_base = executor.screencap()
    if img_base is None:
        print("[ERROR] 基准截图失败")
        executor.disconnect()
        return 1
    
    # 已知 quest_icon 大致位置 (MaaFw 1280x720 空间)
    # flows_config.json 中是 [855, 33] ADB 坐标 → MaaFw 坐标约 [570, 22]
    # 但实际游戏导航栏在顶部，y 应该在 30-70 之间
    x_base = 570  # 855 / 1.5
    y_positions = [25, 28, 30, 32, 33, 35, 38, 40, 45, 50, 55, 60]
    
    print(f"\n[扫描] 扫描任务图标位置 (x={x_base}, y={y_positions})")
    print("=" * 60)
    
    results = []
    for y in y_positions:
        # 点击
        executor.click(x_base, y)
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
        
        # 中央面板区域 (y:80-650, x:100-1180)
        center_changed = cv2.countNonZero(thresh[80:650, 100:1180])
        # 导航栏区域 (y:35-75, x:640-1000)
        nav_changed = cv2.countNonZero(thresh[35:75, 640:1000])
        # 全局变化率
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
        
        # 关闭面板 (点击返回键)
        subprocess.run([ADB_PATH, "-s", DEVICE, "shell", "input", "keyevent", "4"], capture_output=True)
        time.sleep(1.5)
    
    print("\n" + "=" * 60)
    if results:
        best = max(results, key=lambda r: r['center'])
        print(f"[最佳] y={best['y']} (center={best['center']} px, rate={best['rate']:.1f}%)")
        
        # 转换为 ADB 坐标
        adb_y = int(best['y'] * 1.5)
        print(f"[ADB] 坐标：[855, {adb_y}]")
        
        if best['center'] > 100000:
            print("[结论] ✅ 任务图标位置已确认")
        else:
            print("[结论] ❌ 未找到有效位置，可能需要调整 x 坐标")
    
    executor.disconnect()
    return 0

if __name__ == "__main__":
    sys.exit(main())
