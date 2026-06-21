#!/usr/bin/env python3
"""
标准流前置检查：验证页面状态并导航到世界
用法：python scripts/check_and_navigate.py
"""
import subprocess, time, cv2, numpy as np, sys
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\xray\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant')
ADB_PATH = f"{PROJECT_ROOT}\\3rd-party\\adb\\adb.exe"
DEVICE = "localhost:16512"

def adb_cmd(args):
    r = subprocess.run([ADB_PATH, "-s", DEVICE] + args, capture_output=True, timeout=10)
    return r

def adb_tap(x, y):
    adb_cmd(["shell", "input", "tap", str(int(x)), str(int(y))])

def adb_back():
    adb_cmd(["shell", "input", "keyevent", "4"])

def adb_screencap():
    r = adb_cmd(["exec-out", "screencap", "-p"])
    if r.returncode == 0 and len(r.stdout) > 1000:
        return cv2.imdecode(np.frombuffer(r.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
    return None

def count_gold(img):
    if img is None:
        return 0
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
    return len([c for c in contours if cv2.contourArea(c) > 50])

def get_brightness(img):
    if img is None:
        return 0
    img_rot = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    img_resized = cv2.resize(img_rot, (1280, 720))
    return np.mean(cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY))

def classify_page(gold, brightness):
    """基于金色元素和亮度判断页面类型"""
    if brightness < 30:
        return "black_screen"
    elif gold >= 22:
        return "quest_panel"
    elif gold >= 18:
        return "world"
    elif gold >= 15:
        return "world_low_gold"  # 世界页面但金色较少
    elif gold >= 12:
        return "exit_dialog"
    elif gold >= 8:
        return "menu"
    elif brightness > 150:
        return "loading"
    else:
        return "other"

def navigate_to_world(max_attempts=3):
    """尝试导航到世界页面"""
    for attempt in range(max_attempts):
        print(f"\n[尝试 {attempt+1}/{max_attempts}] 检查当前页面...")
        
        img = adb_screencap()
        if img is None:
            print("[ERROR] 截图失败")
            continue
        
        gold = count_gold(img)
        brightness = get_brightness(img)
        page_type = classify_page(gold, brightness)
        
        print(f"  金色元素：{gold}, 亮度：{brightness:.1f}, 类型：{page_type}")
        
        if page_type == "world" or page_type == "world_low_gold":
            print(f"\n[成功] 已确认在世界页面")
            return True
        
        elif page_type == "black_screen":
            print("[操作] 黑屏，点击中央")
            adb_tap(540, 960)
            time.sleep(3)
        
        elif page_type == "exit_dialog":
            print("[操作] 退出对话框，点击取消")
            adb_tap(600, 750)
            time.sleep(2)
        
        elif page_type == "quest_panel":
            print("[操作] 任务面板，按返回")
            adb_back()
            time.sleep(2)
        
        elif page_type == "menu":
            print("[操作] 菜单页面，按返回")
            adb_back()
            time.sleep(1)
        
        elif page_type == "loading":
            print("[操作] 加载中，等待 15 秒")
            time.sleep(15)
        
        else:
            print("[操作] 未知页面，按返回并点击中央")
            adb_back()
            time.sleep(0.5)
            adb_tap(540, 960)
            time.sleep(3)
    
    print(f"\n[失败] {max_attempts} 次尝试后仍未进入世界页面")
    return False

def main():
    print("="*60)
    print("标准流前置检查：导航到世界页面")
    print("="*60)
    
    # 先按几次返回确保不在深层菜单
    print("\n[前置] 按返回键退出深层菜单...")
    for i in range(5):
        adb_back()
        time.sleep(0.3)
    time.sleep(1)
    
    # 导航到世界
    success = navigate_to_world(max_attempts=5)
    
    if success:
        # 保存世界页面截图
        img = adb_screencap()
        if img is not None:
            img_rot = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            cv2.imwrite(str(PROJECT_ROOT / "data" / "analysis" / "world_page_reference.png"), img_rot)
            print(f"\n[保存] 世界页面参考截图已保存")
        
        print(f"\n{'='*60}")
        print("[就绪] 可以运行标准流：python scripts/standard_flow_engine.py --flow daily_quest")
        print(f"{'='*60}")
        return 0
    else:
        print(f"\n{'='*60}")
        print("[提示] 请手动进入游戏世界页面后重新运行")
        print(f"{'='*60}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
