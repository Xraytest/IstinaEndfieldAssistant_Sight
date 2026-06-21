#!/usr/bin/env python3
"""
高精度标准流验证脚本

问题诊断：
1. 退出对话框"取消"按钮坐标 (600, 750) 是否准确？
2. 页面类型判断逻辑是否正确？
3. 标准流实际执行是否成功？

方法：
1. 通过像素差异分析精确定位"取消"按钮
2. 采集实际页面样本验证金色元素阈值
3. 运行标准流并详细记录每一步的状态
"""

import subprocess, time, cv2, numpy as np, os, json, sys
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

PROJECT = Path(__file__).resolve().parent.parent
ADB = str(PROJECT / '3rd-party' / 'adb' / 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = PROJECT / 'cache' / 'high_precision_verify'
CACHE.mkdir(exist_ok=True)


def tap(x, y):
    """ADB tap"""
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True, timeout=10)

def back():
    """ADB back"""
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], capture_output=True, timeout=5)

def screencap():
    """截图到内存"""
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'],
                       capture_output=True, timeout=15)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def save_img(img, path):
    """保存图片"""
    if img is not None:
        cv2.imwrite(str(path), img)
        return True
    return False

def screen_diff(img1, img2):
    """计算两张图片的差异"""
    if img1 is None or img2 is None:
        return 0, 0
    d = cv2.absdiff(img1, img2)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t), g.mean()


def detect_golden_elements(img):
    """检测金色元素（与 ScreenAnalyzer 一致）"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    ranges = [
        ("亮金", np.array([15, 80, 150]), np.array([35, 255, 255])),
        ("暗金", np.array([15, 50, 80]), np.array([35, 255, 200])),
        ("暖金", np.array([10, 60, 100]), np.array([40, 255, 255])),
    ]
    all_elems = []
    for name, lower, upper in ranges:
        mask = cv2.inRange(hsv, lower, upper)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 30:
                x, y, bw, bh = cv2.boundingRect(cnt)
                all_elems.append({
                    "cx": x + bw // 2, "cy": y + bh // 2,
                    "w": bw, "h": bh, "area": area, "range": name
                })
    unique = []
    for elem in sorted(all_elems, key=lambda e: e["area"], reverse=True):
        if not any(abs(elem["cx"] - u["cx"]) < 20 and abs(elem["cy"] - u["cy"]) < 20 for u in unique):
            unique.append(elem)
    return unique


def classify_page_by_gold(gold_count, img_mean):
    """基于金色元素数量和画面亮度判断页面类型"""
    # 退出对话框：12-16 个金色元素 + 较暗背景
    if 12 <= gold_count <= 16 and img_mean < 100:
        return "exit_dialog"
    # 任务面板：≥22 个金色元素
    if gold_count >= 22:
        return "quest_panel"
    # 世界页面：18-21 个金色元素
    if 18 <= gold_count <= 21:
        return "world"
    # 菜单：8-11 个金色元素
    if 8 <= gold_count <= 11:
        return "menu"
    # 世界（低金色）：15-17 个
    if 15 <= gold_count <= 17:
        return "world_low_gold"
    return "other"


def find_exit_dialog_cancel_button(img):
    """
    通过像素差异分析精确定位退出对话框"取消"按钮
    
    方法：
    1. 检测退出对话框区域（通常在画面中央）
    2. 在对话框底部寻找两个按钮
    3. 左侧为"取消"，右侧为"确认"
    """
    print("\n[分析] 检测退出对话框按钮位置...")
    
    if img is None:
        return None
    
    h, w = img.shape[:2]  # 1080x1920 竖屏
    
    # 退出对话框通常在中央区域
    # 按钮在对话框底部，大约在 (600-800, 700-900) 范围
    
    # 检测底部区域的金色/亮色元素（按钮）
    bottom_region = img[600:900, 400:1200]  # 底部中央区域
    
    golden = detect_golden_elements(bottom_region)
    
    # 筛选按钮大小的元素（宽度 80-200，高度 40-80）
    buttons = []
    for g in golden:
        adjusted_cx = g["cx"] + 400  # 调整到原图坐标
        adjusted_cy = g["cy"] + 600
        if 80 <= g["w"] <= 200 and 40 <= g["h"] <= 80:
            buttons.append({
                "cx": adjusted_cx, "cy": adjusted_cy,
                "w": g["w"], "h": g["h"], "area": g["area"]
            })
    
    # 按 x 坐标排序，左侧为"取消"
    buttons.sort(key=lambda b: b["cx"])
    
    if len(buttons) >= 2:
        cancel_btn = buttons[0]
        confirm_btn = buttons[1]
        print(f"  [发现] 取消按钮：({cancel_btn['cx']}, {cancel_btn['cy']}) {cancel_btn['w']}x{cancel_btn['h']}")
        print(f"  [发现] 确认按钮：({confirm_btn['cx']}, {confirm_btn['cy']}) {confirm_btn['w']}x{confirm_btn['h']}")
        return cancel_btn
    elif len(buttons) == 1:
        print(f"  [警告] 只找到 1 个按钮：({buttons[0]['cx']}, {buttons[0]['cy']})")
        return buttons[0]
    else:
        print(f"  [警告] 未找到按钮，使用默认坐标 (600, 750)")
        return {"cx": 600, "cy": 750, "w": 100, "h": 60}


def verify_cancel_button_coords():
    """
    验证退出对话框"取消"按钮坐标
    
    步骤：
    1. 触发退出对话框
    2. 截图分析按钮位置
    3. 测试多个候选坐标
    4. 通过画面变化确认哪个坐标有效
    """
    print("\n" + "="*70)
    print("验证退出对话框'取消'按钮坐标")
    print("="*70)
    
    # 步骤 1: 确保在世界页面
    print("\n[步骤 1] 确保在世界页面...")
    for _ in range(5):
        back()
        time.sleep(0.5)
    
    time.sleep(1)
    world_img = screencap()
    if world_img is None:
        print("  [失败] 无法截图")
        return False
    
    world_gold = len(detect_golden_elements(world_img))
    world_page = classify_page_by_gold(world_gold, world_img.mean())
    print(f"  [当前] 页面={world_page} 金色={world_gold} 亮度={world_img.mean():.1f}")
    
    # 步骤 2: 触发退出对话框（按返回键）
    print("\n[步骤 2] 触发退出对话框...")
    back()
    time.sleep(2)
    
    dialog_img = screencap()
    if dialog_img is None:
        print("  [失败] 无法截图")
        return False
    
    dialog_gold = len(detect_golden_elements(dialog_img))
    dialog_page = classify_page_by_gold(dialog_gold, dialog_img.mean())
    print(f"  [当前] 页面={dialog_page} 金色={dialog_gold} 亮度={dialog_img.mean():.1f}")
    
    if dialog_page != "exit_dialog":
        print(f"  [警告] 未检测到退出对话框，当前页面={dialog_page}")
        # 继续测试，但标记为异常
    else:
        print(f"  [成功] 检测到退出对话框")
    
    save_img(dialog_img, CACHE / 'exit_dialog.png')
    
    # 步骤 3: 分析按钮位置
    print("\n[步骤 3] 分析按钮位置...")
    cancel_btn = find_exit_dialog_cancel_button(dialog_img)
    
    # 步骤 4: 测试候选坐标
    print("\n[步骤 4] 测试候选坐标...")
    
    # 候选坐标：分析得到的 + 默认 (600, 750) + 附近区域
    candidates = [
        (cancel_btn["cx"], cancel_btn["cy"], "分析得到"),
        (600, 750, "默认坐标"),
        (540, 720, "附近 1"),
        (660, 780, "附近 2"),
    ]
    
    best_coord = None
    best_diff = 0
    
    for cx, cy, desc in candidates:
        # 重新触发退出对话框
        back()
        time.sleep(2)
        
        before = screencap()
        if before is None:
            continue
        
        # 点击候选坐标
        print(f"  [测试] {desc}: ({cx}, {cy})", end=" ")
        tap(cx, cy)
        time.sleep(2)
        
        after = screencap()
        if after is None:
            print("截图失败")
            continue
        
        # 计算画面变化
        diff, mean_diff = screen_diff(before, after)
        
        # 检查是否回到世界页面
        after_gold = len(detect_golden_elements(after))
        after_page = classify_page_by_gold(after_gold, after.mean())
        
        print(f"diff={diff:,} mean={mean_diff:.1f} 页面={after_page}")
        
        # 如果画面变化大且回到世界页面，说明坐标有效
        if diff > best_diff and after_page in ("world", "world_low_gold"):
            best_diff = diff
            best_coord = (cx, cy, desc)
            print(f"    [有效] 成功关闭对话框，回到{after_page}")
    
    if best_coord:
        print(f"\n[结论] 最佳坐标：{best_coord[0]}, {best_coord[1]} ({best_coord[2]})")
        return best_coord
    else:
        print(f"\n[结论] 未找到有效坐标，建议使用默认 (600, 750)")
        return (600, 750, "默认")


def verify_page_classification():
    """
    验证页面类型判断逻辑
    
    采集各页面的实际样本，验证金色元素阈值是否准确
    """
    print("\n" + "="*70)
    print("验证页面类型判断逻辑")
    print("="*70)
    
    samples = {}
    
    # 采集世界页面样本
    print("\n[采集] 世界页面样本...")
    for i in range(5):
        for _ in range(3):
            back()
            time.sleep(0.5)
        time.sleep(1)
        
        img = screencap()
        if img is None:
            continue
        
        gold = len(detect_golden_elements(img))
        mean = img.mean()
        page = classify_page_by_gold(gold, mean)
        
        print(f"  [样本 {i+1}] 金色={gold} 亮度={mean:.1f} 判断={page}")
        
        if "world" not in samples:
            samples["world"] = []
        samples["world"].append({"gold": gold, "mean": mean, "page": page})
        
        save_img(img, CACHE / f'world_sample_{i+1}.png')
        time.sleep(0.5)
    
    # 采集任务面板样本
    print("\n[采集] 任务面板样本...")
    tap(860, 80)  # 任务图标
    time.sleep(2)
    
    for i in range(3):
        img = screencap()
        if img is None:
            continue
        
        gold = len(detect_golden_elements(img))
        mean = img.mean()
        page = classify_page_by_gold(gold, mean)
        
        print(f"  [样本 {i+1}] 金色={gold} 亮度={mean:.1f} 判断={page}")
        
        if "quest_panel" not in samples:
            samples["quest_panel"] = []
        samples["quest_panel"].append({"gold": gold, "mean": mean, "page": page})
        
        save_img(img, CACHE / f'quest_panel_sample_{i+1}.png')
        time.sleep(0.5)
    
    # 按返回退出任务面板
    for _ in range(3):
        back()
        time.sleep(0.5)
    
    # 统计结果
    print("\n[统计] 页面类型判断准确性...")
    for page_type, page_samples in samples.items():
        if not page_samples:
            continue
        
        golds = [s["gold"] for s in page_samples]
        means = [s["mean"] for s in page_samples]
        correct = sum(1 for s in page_samples if page_type in s["page"])
        
        print(f"\n  {page_type}:")
        print(f"    金色元素：min={min(golds)} max={max(golds)} avg={sum(golds)/len(golds):.1f}")
        print(f"    画面亮度：min={min(means):.1f} max={max(means):.1f} avg={sum(means)/len(means):.1f}")
        print(f"    判断准确：{correct}/{len(page_samples)}")
    
    # 保存统计结果
    result = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "samples": {}
    }
    for page_type, page_samples in samples.items():
        if page_samples:
            golds = [s["gold"] for s in page_samples]
            means = [s["mean"] for s in page_samples]
            result["samples"][page_type] = {
                "gold_range": [min(golds), max(golds)],
                "gold_avg": sum(golds) / len(golds),
                "mean_range": [min(means), max(means)],
                "mean_avg": sum(means) / len(means),
                "count": len(page_samples)
            }
    
    with open(CACHE / 'page_classification_stats.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n[保存] 统计结果：{CACHE / 'page_classification_stats.json'}")
    
    return result


def run_standard_flow_test(flow_name="daily_quest"):
    """
    运行标准流测试
    
    详细记录每一步的状态，验证是否能正确执行
    """
    print("\n" + "="*70)
    print(f"运行标准流测试：{flow_name}")
    print("="*70)
    
    # 导入标准流引擎
    try:
        from scripts.standard_flow_engine import StandardFlowExecutor, load_config
    except Exception as e:
        print(f"[失败] 导入标准流引擎失败：{e}")
        return False
    
    # 加载配置
    config = load_config()
    
    # 检查流程是否存在
    if not config.is_flow_exists(flow_name):
        print(f"[失败] 流程不存在：{flow_name}")
        return False
    
    # 创建执行器
    executor = StandardFlowExecutor(config)
    
    # 执行流程
    print(f"\n[执行] 开始执行 {flow_name}...")
    success = executor.execute_flow(flow_name)
    
    print(f"\n[结果] {'成功' if success else '有失败步骤'}")
    
    return success


def main():
    print("\n" + "="*70)
    print("高精度标准流验证")
    print("="*70)
    
    results = {}
    
    # 1. 验证退出对话框坐标
    cancel_coord = verify_cancel_button_coords()
    results["cancel_button"] = cancel_coord
    
    # 2. 验证页面类型判断
    page_stats = verify_page_classification()
    results["page_classification"] = page_stats
    
    # 3. 运行标准流测试
    # flow_success = run_standard_flow_test("daily_quest")
    # results["flow_test"] = flow_success
    
    # 保存结果
    with open(CACHE / 'verification_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # 总结
    print("\n" + "="*70)
    print("验证总结")
    print("="*70)
    
    print(f"\n1. 退出对话框'取消'按钮坐标：{cancel_coord[0]}, {cancel_coord[1]} ({cancel_coord[2]})")
    
    if page_stats and "samples" in page_stats:
        for page_type, stats in page_stats["samples"].items():
            print(f"2. {page_type} 页面:")
            print(f"   金色元素范围：[{stats['gold_range'][0]}, {stats['gold_range'][1]}]")
            print(f"   平均金色元素：{stats['gold_avg']:.1f}")
    
    print(f"\n详细结果已保存：{CACHE / 'verification_results.json'}")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[错误] 验证失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
