#!/usr/bin/env python3
"""
标准流引擎页面分析器补丁

将旧的金色元素计数方法替换为新的多特征页面分析器
"""

import re
from pathlib import Path

SCRIPT = Path(__file__).parent / "standard_flow_engine.py"

# 1. 替换 _count_gold_elements 和 _classify_page_by_gold 为新的分析器

OLD_COUNT_FUNC = '''    def _count_gold_elements(cv_img):
        """计算金色元素数量（页面类型判断依据）"""
        if cv_img is None:
            return 0
        # 旋转到横屏并 resize
        img_rot = cv2.rotate(cv_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
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

    def _classify_page_by_gold(gold_count):
        """基于金色元素数量判断页面类型"""
        if gold_count >= 22:
            return "quest_panel"
        elif gold_count >= 18:
            return "world"
        elif gold_count >= 15:
            return "world_low_gold"
        elif gold_count >= 12:
            return "exit_dialog"
        elif gold_count >= 8:
            return "menu"
        else:
            return "other"'''

NEW_ANALYZER_INIT = '''    # 初始化高精度页面分析器（替换旧的金色元素计数）
    _page_analyzer = HighPrecisionPageAnalyzer()
    _vlm_client = VLMClient({"vlm_mode": "local"})

    def _classify_page(cv_img):
        """使用多特征分析器判断页面类型"""
        if cv_img is None:
            return {"page_type": "unknown", "confidence": 0.0, "features": {}}
        return _page_analyzer.analyze(cv_img)

    def _classify_with_vlm(cv_img, expected_page="world", step_desc=""):
        """OpenCV 优先，不确定时 VLM 介入决策"""
        result = _classify_page(cv_img)
        if VLMClient.should_invoke_vlm(result, expected_page):
            context = {
                "expected_page": expected_page,
                "step_desc": step_desc,
                "last_action": "按返回键/点击中央"
            }
            vlm_result = _vlm_client.decide_action(cv_img, result, context)
            print(f"  [VLM] 决策：{vlm_result.get('suggested_action', '?')} → {vlm_result.get('reason', '')[:80]}")
            result["page_type"] = vlm_result.get("page_type", result["page_type"])
            result["confidence"] = max(result["confidence"], vlm_result.get("confidence", 0))
            result["vlm_action"] = vlm_result
        return result'''

# 读取文件
content = SCRIPT.read_text(encoding='utf-8')

# 替换
if OLD_COUNT_FUNC in content:
    content = content.replace(OLD_COUNT_FUNC, NEW_ANALYZER_INIT)
    print("[OK] 替换了页面分析函数")
else:
    print("[WARN] 未找到旧的页面分析函数，可能格式有差异")

# 2. 替换使用 _classify_page_by_gold 的地方

# 替换 _close_exit_dialog 中的使用
OLD_CLOSE_DIALOG = '''                    golden_count = _count_gold_elements(cv_img)
                    gold_page = _classify_page_by_gold(golden_count)
                    if gold_page != "exit_dialog":
                        print(f"[前置] 成功关闭退出对话框，当前={gold_page} (金色={golden_count})")
                        return True'''

NEW_CLOSE_DIALOG = '''                    page_result = _classify_page(cv_img)
                    page_type = page_result["page_type"]
                    confidence = page_result["confidence"]
                    if page_type != "exit_dialog":
                        print(f"[前置] 成功关闭退出对话框，当前={page_type} (置信度 {confidence:.2f})")
                        return True'''

if OLD_CLOSE_DIALOG in content:
    content = content.replace(OLD_CLOSE_DIALOG, NEW_CLOSE_DIALOG)
    print("[OK] 替换了_close_exit_dialog 中的页面分类")
else:
    print("[WARN] 未找到_close_exit_dialog 中的旧代码")

# 替换主循环中的使用
OLD_MAIN_LOOP = '''                analysis = _analyzer.analyze(cv_img)
                page = analysis["page_type"]
                golden_count = len(analysis.get("golden_elements", []))
                # 优先使用金色元素判断（更可靠）
                gold_page = _classify_page_by_gold(golden_count)
                ocr_text = analysis.get("ocr_text", "")[:80]
                print(f"  [前置 {preamble_attempt+1}/8] 页面={page}({gold_page}) 金色={golden_count} OCR={ocr_text}")

                # 成功条件：world 页面且金色元素 15-21 个
                if page in ("world", "world_map") and 15 <= golden_count <= 21:
                    print("[前置] ✅ 已进入游戏世界")
                    nav_success = True
                    break
                elif page in ("world", "world_map") and 12 <= golden_count <= 16:
                    # world 页面但有退出对话框遮挡，点击取消按钮
                    print(f"[前置] world 页面但有退出对话框 (金色={golden_count})，尝试关闭...")'''

NEW_MAIN_LOOP = '''                # 使用新的高精度页面分析器
                page_result = _classify_page(cv_img)
                page_type = page_result["page_type"]
                confidence = page_result["confidence"]
                features = page_result["features"]
                
                # 同时保留旧的 VLM 分析（用于 OCR 文本）
                analysis = _analyzer.analyze(cv_img)
                ocr_text = analysis.get("ocr_text", "")[:80]
                
                print(f"  [前置 {preamble_attempt+1}/8] 页面={page_type} (置信度 {confidence:.2f})")
                print(f"    特征：left_bar={features.get('left_bar_brightness', 0):.1f} green={features.get('green_pixels_top_right', 0):.0f} OCR={ocr_text}")

                # 成功条件：world 页面且置信度 > 0.5
                if page_type == "world" and confidence > 0.5:
                    print("[前置] ✅ 已进入游戏世界")
                    nav_success = True
                    break
                elif page_type == "quest_panel":
                    # 在任务面板，按返回
                    print("[前置] 在任务面板，按返回...")
                    subprocess.run([adb_path, "-s", "localhost:16512", "shell", "input", "keyevent", "4"],
                                  capture_output=True, timeout=5)
                    time.sleep(3)
                    continue
                elif page_type == "exit_dialog":'''

if OLD_MAIN_LOOP in content:
    content = content.replace(OLD_MAIN_LOOP, NEW_MAIN_LOOP)
    print("[OK] 替换了主循环中的页面分类")
else:
    print("[WARN] 未找到主循环中的旧代码")

# 替换 gold_page == "exit_dialog" 的判断
OLD_EXIT_DIALOG_CHECK = '''                elif gold_page == "exit_dialog":
                    # 退出对话框，点击取消按钮
                    print("[前置] 检测到退出对话框，尝试关闭...")
                    if not _close_exit_dialog():
                        print("[前置] 退出对话框无法关闭，尝试按返回...")
                        subprocess.run([adb_path, "-s", "localhost:16512", "shell", "input", "keyevent", "4"],
                                      capture_output=True, timeout=5)
                        time.sleep(2)
                elif gold_page == "menu":
                    # 菜单页面，按返回
                    print("[前置] 菜单页面，按返回...")
                    subprocess.run([adb_path, "-s", "localhost:16512", "shell", "input", "keyevent", "4"],
                                  capture_output=True, timeout=5)
                    time.sleep(1)'''

NEW_EXIT_DIALOG_CHECK = '''                    # 退出对话框，点击取消按钮
                    print("[前置] 检测到退出对话框，尝试关闭...")
                    if not _close_exit_dialog():
                        print("[前置] 退出对话框无法关闭，尝试按返回...")
                        subprocess.run([adb_path, "-s", "localhost:16512", "shell", "input", "keyevent", "4"],
                                      capture_output=True, timeout=5)
                        time.sleep(2)
                    continue
                elif page_type == "unknown":'''

if OLD_EXIT_DIALOG_CHECK in content:
    content = content.replace(OLD_EXIT_DIALOG_CHECK, NEW_EXIT_DIALOG_CHECK)
    print("[OK] 替换了 exit_dialog 判断")
else:
    print("[WARN] 未找到 exit_dialog 判断的旧代码")

# 写回文件
SCRIPT.write_text(content, encoding='utf-8')

print("\n[完成] 补丁已应用")
