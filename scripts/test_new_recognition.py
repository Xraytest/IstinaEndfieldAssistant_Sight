#!/usr/bin/env python3
"""
新识别方法测试脚本

问题：金色元素计数无法区分世界页面和任务面板（都是 26-27 个）
解决：使用 MaaEnd 式多源融合识别

测试内容：
1. 模板匹配识别页面特征图标
2. OCR 识别页面标题文本
3. 颜色匹配识别特定区域
"""

import cv2
import numpy as np
import subprocess
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
ADB_EXE = PROJECT / '3rd-party' / 'adb' / 'adb.exe'
SERIAL = 'localhost:16512'


def adb_cmd(args):
    """执行 ADB 命令"""
    return subprocess.run(
        [str(ADB_EXE), '-s', SERIAL] + args,
        capture_output=True, timeout=15
    )


def screencap():
    """截图"""
    r = adb_cmd(['exec-out', 'screencap', '-p'])
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)


def tap(x, y):
    """点击"""
    adb_cmd(['shell', 'input', 'tap', str(int(x)), str(int(y))])


def keyevent(key):
    """按键"""
    adb_cmd(['shell', 'input', 'keyevent', str(key)])


def template_match(img, template_path, roi=None, threshold=0.8):
    """
    模板匹配
    
    Args:
        img: 源图像
        template_path: 模板路径
        roi: [x, y, w, h] 搜索区域
        threshold: 匹配阈值
        
    Returns:
        (是否匹配，位置，置信度)
    """
    template = cv2.imread(str(template_path))
    if template is None:
        return False, None, 0
    
    if roi:
        x, y, w, h = roi
        search_img = img[y:y+h, x:x+w]
    else:
        search_img = img
        x, y = 0, 0
    
    result = cv2.matchTemplate(search_img, template, cv2.TM_CCOEFF_NORMED)
    max_val = np.max(result)
    max_loc = np.unravel_index(np.argmax(result), result.shape)
    
    if max_val >= threshold:
        location = (x + max_loc[1], y + max_loc[0])
        return True, location, float(max_val)
    
    return False, None, float(max_val)


def detect_region_color(img, roi, lower_hsv, upper_hsv):
    """
    检测区域颜色
    
    Args:
        img: 源图像
        roi: [x, y, w, h]
        lower_hsv: HSV 下限 [h, s, v]
        upper_hsv: HSV 上限 [h, s, v]
        
    Returns:
        匹配像素数
    """
    x, y, w, h = roi
    crop = img[y:y+h, x:x+w]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(lower_hsv), np.array(upper_hsv))
    return int(np.count_nonzero(mask))


def analyze_page_features(img):
    """
    分析页面特征（不使用金色元素计数）
    
    特征：
    1. 左上角区域亮度（菜单页面通常有暗色背景）
    2. 右上角资源图标区域颜色分布
    3. 底部导航栏区域特征
    4. 中央区域文本密度
    """
    h, w = img.shape[:2]
    
    features = {}
    
    # 1. 左上角 200x200 区域平均亮度
    top_left = img[0:200, 0:200]
    features['top_left_brightness'] = top_left.mean()
    
    # 2. 右上角资源区域（通常有绿色/黄色资源图标）
    top_right = img[0:100, w-400:w]
    hsv_tr = cv2.cvtColor(top_right, cv2.COLOR_BGR2HSV)
    
    # 绿色像素（资源图标）
    green_mask = cv2.inRange(hsv_tr, np.array([40, 50, 50]), np.array([80, 255, 200]))
    features['green_pixels_top_right'] = int(np.count_nonzero(green_mask))
    
    # 黄色像素
    yellow_mask = cv2.inRange(hsv_tr, np.array([20, 100, 100]), np.array([35, 255, 255]))
    features['yellow_pixels_top_right'] = int(np.count_nonzero(yellow_mask))
    
    # 3. 底部导航栏区域（1080 高度的 70%-100%）
    bottom_nav = img[int(h*0.7):h, int(w*0.3):int(w*0.7)]
    features['bottom_nav_brightness'] = bottom_nav.mean()
    
    # 4. 中央区域边缘检测（UI 元素密度）
    center = img[int(h*0.2):int(h*0.8), int(w*0.2):int(w*0.8)]
    gray = cv2.cvtColor(center, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    features['center_edge_density'] = int(np.count_nonzero(edges)) / edges.size * 100
    
    # 5. 左侧边栏区域（菜单页面通常有左侧导航）
    left_bar = img[int(h*0.1):int(h*0.9), 0:int(w*0.15)]
    features['left_bar_brightness'] = left_bar.mean()
    
    return features


def classify_page_v2(features):
    """
    V2 页面分类（基于多特征）
    
    根据实际采集数据校准的规则：
    - 任务面板：left_bar_brightness > 120 AND green_pixels < 30
    - 世界页面：green_pixels > 100 OR left_bar_brightness < 80
    - 退出对话框：待进一步分析
    """
    f = features
    
    # 规则 1: 任务面板（左侧亮边栏 + 较少绿色像素）
    if f['left_bar_brightness'] > 120 and f['green_pixels_top_right'] < 30:
        return "quest_panel", 0.9
    
    # 规则 2: 世界页面（较多绿色资源图标 或 左侧边栏暗）
    if f['green_pixels_top_right'] > 100 or f['left_bar_brightness'] < 80:
        return "world", 0.8
    
    # 规则 3: 退出对话框（需要更多特征）
    # 暂时用排除法
    return "unknown", 0.3


def main():
    print("\n" + "="*70)
    print("新识别方法测试")
    print("="*70)
    
    # 采集不同页面样本
    pages = {
        "world": [],
        "quest_panel": [],
        "exit_dialog": [],
    }
    
    # 1. 采集世界页面
    print("\n[1] 采集世界页面样本...")
    for i in range(3):
        # 按返回键确保在世界
        for _ in range(5):
            keyevent(4)
            time.sleep(0.3)
        time.sleep(1)
        
        img = screencap()
        if img is None:
            continue
        
        features = analyze_page_features(img)
        page_type, confidence = classify_page_v2(features)
        
        print(f"  样本 {i+1}: {page_type} (置信度 {confidence:.2f})")
        print(f"    特征：{features}")
        
        pages["world"].append(features)
        
        # 保存样本
        cv2.imwrite(str(PROJECT / f'cache/test_recognition/world_{i+1}.png'), img)
        time.sleep(0.5)
    
    # 2. 采集任务面板
    print("\n[2] 采集任务面板样本...")
    tap(860, 80)  # 任务图标
    time.sleep(2)
    
    for i in range(3):
        img = screencap()
        if img is None:
            continue
        
        features = analyze_page_features(img)
        page_type, confidence = classify_page_v2(features)
        
        print(f"  样本 {i+1}: {page_type} (置信度 {confidence:.2f})")
        print(f"    特征：{features}")
        
        pages["quest_panel"].append(features)
        
        cv2.imwrite(str(PROJECT / f'cache/test_recognition/quest_{i+1}.png'), img)
        time.sleep(0.5)
    
    # 返回世界
    for _ in range(3):
        keyevent(4)
        time.sleep(0.3)
    
    # 3. 采集退出对话框
    print("\n[3] 采集退出对话框样本...")
    keyevent(4)  # 触发退出对话框
    time.sleep(1)
    
    for i in range(3):
        img = screencap()
        if img is None:
            continue
        
        features = analyze_page_features(img)
        page_type, confidence = classify_page_v2(features)
        
        print(f"  样本 {i+1}: {page_type} (置信度 {confidence:.2f})")
        print(f"    特征：{features}")
        
        pages["exit_dialog"].append(features)
        
        cv2.imwrite(str(PROJECT / f'cache/test_recognition/dialog_{i+1}.png'), img)
        
        # 关闭对话框（按返回或点击取消）
        keyevent(4)
        time.sleep(0.5)
    
    # 统计分析
    print("\n" + "="*70)
    print("特征统计")
    print("="*70)
    
    for page_name, samples in pages.items():
        if not samples:
            continue
        
        print(f"\n{page_name}:")
        for feature, values in samples[0].items():
            all_values = [s[feature] for s in samples]
            print(f"  {feature}: min={min(all_values):.1f} max={max(all_values):.1f} avg={sum(all_values)/len(all_values):.1f}")
    
    # 保存特征数据
    import json
    cache_dir = PROJECT / 'cache' / 'test_recognition'
    cache_dir.mkdir(exist_ok=True)
    
    with open(cache_dir / 'features.json', 'w', encoding='utf-8') as f:
        json.dump({
            name: samples 
            for name, samples in pages.items() if samples
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n[保存] 特征数据：{cache_dir / 'features.json'}")
    print(f"[保存] 图像样本：{cache_dir}/")
    
    print("\n[结论] 请根据上述特征统计数据，调整 classify_page_v2 的分类规则")


if __name__ == "__main__":
    main()
