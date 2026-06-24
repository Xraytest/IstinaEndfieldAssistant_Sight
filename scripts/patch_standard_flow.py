#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佸紩鎿庨〉闈㈠垎鏋愬櫒琛ヤ竵

灏嗘棫鐨勯噾鑹插厓绱犺鏁版柟娉曟浛鎹负鏂扮殑澶氱壒寰侀〉闈㈠垎鏋愬櫒
"""

import re
from pathlib import Path

SCRIPT = Path(__file__).parent / "standard_flow_engine.py"

# 1. 鏇挎崲 _count_gold_elements 鍜?_classify_page_by_gold 涓烘柊鐨勫垎鏋愬櫒

OLD_COUNT_FUNC = '''    def _count_gold_elements(cv_img):
        """璁＄畻閲戣壊鍏冪礌鏁伴噺锛堥〉闈㈢被鍨嬪垽鏂緷鎹級"""
        if cv_img is None:
            return 0
        # 鏃嬭浆鍒版í灞忓苟 resize
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
        """鍩轰簬閲戣壊鍏冪礌鏁伴噺鍒ゆ柇椤甸潰绫诲瀷"""
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

NEW_ANALYZER_INIT = '''    # 鍒濆鍖栭珮绮惧害椤甸潰鍒嗘瀽鍣紙鏇挎崲鏃х殑閲戣壊鍏冪礌璁℃暟锛?    _page_analyzer = HighPrecisionPageAnalyzer()
    _vlm_client = GUIClient({"vlm_mode": "local"})

    def _classify_page(cv_img):
        """浣跨敤澶氱壒寰佸垎鏋愬櫒鍒ゆ柇椤甸潰绫诲瀷"""
        if cv_img is None:
            return {"page_type": "unknown", "confidence": 0.0, "features": {}}
        return _page_analyzer.analyze(cv_img)

    def _classify_with_vlm(cv_img, expected_page="world", step_desc=""):
        """OpenCV 浼樺厛锛屼笉纭畾鏃?VLM 浠嬪叆鍐崇瓥"""
        result = _classify_page(cv_img)
        if GUIClient.should_invoke_vlm(result, expected_page):
            context = {
                "expected_page": expected_page,
                "step_desc": step_desc,
                "last_action": "鎸夎繑鍥為敭/鐐瑰嚮涓ぎ"
            }
            vlm_result = _vlm_client.decide_action(cv_img, result, context)
            print(f"  [VLM] 鍐崇瓥锛歿vlm_result.get('suggested_action', '?')} 鈫?{vlm_result.get('reason', '')[:80]}")
            result["page_type"] = vlm_result.get("page_type", result["page_type"])
            result["confidence"] = max(result["confidence"], vlm_result.get("confidence", 0))
            result["vlm_action"] = vlm_result
        return result'''

# 璇诲彇鏂囦欢
content = SCRIPT.read_text(encoding='utf-8')

# 鏇挎崲
if OLD_COUNT_FUNC in content:
    content = content.replace(OLD_COUNT_FUNC, NEW_ANALYZER_INIT)
    print("[OK] 鏇挎崲浜嗛〉闈㈠垎鏋愬嚱鏁?)
else:
    print("[WARN] 鏈壘鍒版棫鐨勯〉闈㈠垎鏋愬嚱鏁帮紝鍙兘鏍煎紡鏈夊樊寮?)

# 2. 鏇挎崲浣跨敤 _classify_page_by_gold 鐨勫湴鏂?
# 鏇挎崲 _close_exit_dialog 涓殑浣跨敤
OLD_CLOSE_DIALOG = '''                    golden_count = _count_gold_elements(cv_img)
                    gold_page = _classify_page_by_gold(golden_count)
                    if gold_page != "exit_dialog":
                        print(f"[鍓嶇疆] 鎴愬姛鍏抽棴閫€鍑哄璇濇锛屽綋鍓?{gold_page} (閲戣壊={golden_count})")
                        return True'''

NEW_CLOSE_DIALOG = '''                    page_result = _classify_page(cv_img)
                    page_type = page_result["page_type"]
                    confidence = page_result["confidence"]
                    if page_type != "exit_dialog":
                        print(f"[鍓嶇疆] 鎴愬姛鍏抽棴閫€鍑哄璇濇锛屽綋鍓?{page_type} (缃俊搴?{confidence:.2f})")
                        return True'''

if OLD_CLOSE_DIALOG in content:
    content = content.replace(OLD_CLOSE_DIALOG, NEW_CLOSE_DIALOG)
    print("[OK] 鏇挎崲浜哶close_exit_dialog 涓殑椤甸潰鍒嗙被")
else:
    print("[WARN] 鏈壘鍒癬close_exit_dialog 涓殑鏃т唬鐮?)

# 鏇挎崲涓诲惊鐜腑鐨勪娇鐢?OLD_MAIN_LOOP = '''                analysis = _analyzer.analyze(cv_img)
                page = analysis["page_type"]
                golden_count = len(analysis.get("golden_elements", []))
                # 浼樺厛浣跨敤閲戣壊鍏冪礌鍒ゆ柇锛堟洿鍙潬锛?                gold_page = _classify_page_by_gold(golden_count)
                ocr_text = analysis.get("ocr_text", "")[:80]
                print(f"  [鍓嶇疆 {preamble_attempt+1}/8] 椤甸潰={page}({gold_page}) 閲戣壊={golden_count} OCR={ocr_text}")

                # 鎴愬姛鏉′欢锛歸orld 椤甸潰涓旈噾鑹插厓绱?15-21 涓?                if page in ("world", "world_map") and 15 <= golden_count <= 21:
                    print("[鍓嶇疆] 鉁?宸茶繘鍏ユ父鎴忎笘鐣?)
                    nav_success = True
                    break
                elif page in ("world", "world_map") and 12 <= golden_count <= 16:
                    # world 椤甸潰浣嗘湁閫€鍑哄璇濇閬尅锛岀偣鍑诲彇娑堟寜閽?                    print(f"[鍓嶇疆] world 椤甸潰浣嗘湁閫€鍑哄璇濇 (閲戣壊={golden_count})锛屽皾璇曞叧闂?..")'''

NEW_MAIN_LOOP = '''                # 浣跨敤鏂扮殑楂樼簿搴﹂〉闈㈠垎鏋愬櫒
                page_result = _classify_page(cv_img)
                page_type = page_result["page_type"]
                confidence = page_result["confidence"]
                features = page_result["features"]
                
                # 鍚屾椂淇濈暀鏃х殑 VLM 鍒嗘瀽锛堢敤浜?OCR 鏂囨湰锛?                analysis = _analyzer.analyze(cv_img)
                ocr_text = analysis.get("ocr_text", "")[:80]
                
                print(f"  [鍓嶇疆 {preamble_attempt+1}/8] 椤甸潰={page_type} (缃俊搴?{confidence:.2f})")
                print(f"    鐗瑰緛锛歭eft_bar={features.get('left_bar_brightness', 0):.1f} green={features.get('green_pixels_top_right', 0):.0f} OCR={ocr_text}")

                # 鎴愬姛鏉′欢锛歸orld 椤甸潰涓旂疆淇″害 > 0.5
                if page_type == "world" and confidence > 0.5:
                    print("[鍓嶇疆] 鉁?宸茶繘鍏ユ父鎴忎笘鐣?)
                    nav_success = True
                    break
                elif page_type == "quest_panel":
                    # 鍦ㄤ换鍔￠潰鏉匡紝鎸夎繑鍥?                    print("[鍓嶇疆] 鍦ㄤ换鍔￠潰鏉匡紝鎸夎繑鍥?..")
                    subprocess.run([adb_path, "-s", "localhost:16512", "shell", "input", "keyevent", "4"],
                                  capture_output=True, timeout=5)
                    time.sleep(3)
                    continue
                elif page_type == "exit_dialog":'''

if OLD_MAIN_LOOP in content:
    content = content.replace(OLD_MAIN_LOOP, NEW_MAIN_LOOP)
    print("[OK] 鏇挎崲浜嗕富寰幆涓殑椤甸潰鍒嗙被")
else:
    print("[WARN] 鏈壘鍒颁富寰幆涓殑鏃т唬鐮?)

# 鏇挎崲 gold_page == "exit_dialog" 鐨勫垽鏂?OLD_EXIT_DIALOG_CHECK = '''                elif gold_page == "exit_dialog":
                    # 閫€鍑哄璇濇锛岀偣鍑诲彇娑堟寜閽?                    print("[鍓嶇疆] 妫€娴嬪埌閫€鍑哄璇濇锛屽皾璇曞叧闂?..")
                    if not _close_exit_dialog():
                        print("[鍓嶇疆] 閫€鍑哄璇濇鏃犳硶鍏抽棴锛屽皾璇曟寜杩斿洖...")
                        subprocess.run([adb_path, "-s", "localhost:16512", "shell", "input", "keyevent", "4"],
                                      capture_output=True, timeout=5)
                        time.sleep(2)
                elif gold_page == "menu":
                    # 鑿滃崟椤甸潰锛屾寜杩斿洖
                    print("[鍓嶇疆] 鑿滃崟椤甸潰锛屾寜杩斿洖...")
                    subprocess.run([adb_path, "-s", "localhost:16512", "shell", "input", "keyevent", "4"],
                                  capture_output=True, timeout=5)
                    time.sleep(1)'''

NEW_EXIT_DIALOG_CHECK = '''                    # 閫€鍑哄璇濇锛岀偣鍑诲彇娑堟寜閽?                    print("[鍓嶇疆] 妫€娴嬪埌閫€鍑哄璇濇锛屽皾璇曞叧闂?..")
                    if not _close_exit_dialog():
                        print("[鍓嶇疆] 閫€鍑哄璇濇鏃犳硶鍏抽棴锛屽皾璇曟寜杩斿洖...")
                        subprocess.run([adb_path, "-s", "localhost:16512", "shell", "input", "keyevent", "4"],
                                      capture_output=True, timeout=5)
                        time.sleep(2)
                    continue
                elif page_type == "unknown":'''

if OLD_EXIT_DIALOG_CHECK in content:
    content = content.replace(OLD_EXIT_DIALOG_CHECK, NEW_EXIT_DIALOG_CHECK)
    print("[OK] 鏇挎崲浜?exit_dialog 鍒ゆ柇")
else:
    print("[WARN] 鏈壘鍒?exit_dialog 鍒ゆ柇鐨勬棫浠ｇ爜")

# 鍐欏洖鏂囦欢
SCRIPT.write_text(content, encoding='utf-8')

print("\n[瀹屾垚] 琛ヤ竵宸插簲鐢?)

