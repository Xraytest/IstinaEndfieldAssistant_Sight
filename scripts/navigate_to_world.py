#!/usr/bin/env python3
"""分析当前页面并导航到世界"""
import subprocess, time, cv2, numpy as np, sys
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

PROJECT_ROOT = Path(r'C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight')

ADB_PATH = f"{PROJECT_ROOT}\\3rd-part\\adb\\adb.exe"
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
    """获取画面平均亮度"""
    if img is None:
        return 0
    img_rot = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    img_resized = cv2.resize(img_rot, (1280, 720))
    return np.mean(cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY))

def check_text_ocr(img, keywords):
    """简单 OCR 检查关键词（使用模板匹配代替）"""
    # 这里简化处理，仅返回 None 表示需要 VLM 分析
    return None

# 截图分析
print("[分析] 获取当前画面...")
img = adb_screencap()
if img is None:
    print("[ERROR] 截图失败")
    sys.exit(1)

gold = count_gold(img)
brightness = get_brightness(img)

print(f"\n[画面信息]")
print(f"  分辨率：{img.shape[1]}x{img.shape[0]} (竖屏)")
print(f"  金色元素：{gold}")
print(f"  平均亮度：{brightness:.1f}")

# 页面判断
if brightness < 30:
    page_type = "black_screen (黑屏)"
elif gold >= 20:
    page_type = "quest_panel (任务面板)"
elif gold >= 18:
    page_type = "world (世界)"
elif gold >= 12:
    page_type = "exit_dialog (退出对话框)"
elif gold >= 8:
    page_type = "menu/menu_dialog (菜单/对话框)"
else:
    page_type = "loading/other (加载/其他)"

print(f"\n[页面类型]: {page_type}")

# 导航到世界
print(f"\n[导航] 尝试导航到世界页面...")

if "black_screen" in page_type:
    print("[操作] 黑屏，点击中央唤醒")
    adb_tap(540, 960)
    time.sleep(3)
    
elif "exit_dialog" in page_type or "menu_dialog" in page_type:
    print("[操作] 检测到对话框，点击取消按钮")
    # 取消按钮通常在底部
    adb_tap(600, 750)
    time.sleep(2)
    
    # 如果还有对话框，按返回
    img2 = adb_screencap()
    gold2 = count_gold(img2)
    if gold2 >= 12:
        print("[操作] 仍有对话框，按返回键")
        adb_back()
        time.sleep(2)

elif "quest_panel" in page_type:
    print("[操作] 已在任务面板，按返回到世界")
    adb_back()
    time.sleep(2)

elif "loading" in page_type:
    print("[操作] 加载中，等待 30 秒")
    time.sleep(30)

else:
    # 未知页面，尝试通用导航
    print("[操作] 未知页面，尝试按返回键导航")
    for i in range(5):
        adb_back()
        time.sleep(0.5)
    
    # 检查是否需要点击中央
    img2 = adb_screencap()
    gold2 = count_gold(img2)
    brightness2 = get_brightness(img2)
    
    if brightness2 < 50 or gold2 < 10:
        print("[操作] 点击中央进入")
        adb_tap(540, 960)
        time.sleep(5)

# 验证结果
print(f"\n[验证] 检查导航结果...")
img_final = adb_screencap()
gold_final = count_gold(img_final)
brightness_final = get_brightness(img_final)

print(f"  金色元素：{gold_final}")
print(f"  平均亮度：{brightness_final:.1f}")

if gold_final >= 18 and gold_final <= 22:
    print(f"\n[结果] ✅ 成功进入世界页面")
elif gold_final >= 20:
    print(f"\n[结果] ⚠️  可能在任务面板页面")
elif gold_final >= 12:
    print(f"\n[结果] ⚠️  可能有退出对话框")
else:
    print(f"\n[结果] ❌ 未进入世界页面，请手动操作")

# 保存截图供分析
img_final_rot = cv2.rotate(img_final, cv2.ROTATE_90_COUNTERCLOCKWISE)
cv2.imwrite(str(PROJECT_ROOT / "data" / "analysis" / "current_page.png"), img_final_rot)
print(f"\n[保存] 截图已保存到 data/analysis/current_page.png")
