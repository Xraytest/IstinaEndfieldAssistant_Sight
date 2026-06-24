#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佸紩鎿庣姸鎬佹満鎵╁睍 - 鏀寔寰幆鍜屾潯浠惰烦杞?
鍩轰簬 MaaEnd 鐨勮璁℃ā寮忥紝涓烘爣鍑嗘祦寮曟搸娣诲姞锛?1. loop 鍔ㄤ綔绫诲瀷锛堝惊鐜墽琛岋級
2. check 鍔ㄤ綔绫诲瀷锛堟潯浠舵鏌ワ級
3. find_and_click 鍔ㄤ綔绫诲瀷锛圡aaFw OCR 鏌ユ壘骞剁偣鍑伙級
4. 鏉′欢璺宠浆锛坥n_found/on_not_found锛?"""

import sys
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()


class FlowStateMachine:
    """鏍囧噯娴佺姸鎬佹満鎵╁睍"""

    def __init__(self, ocr_manager=None, device_manager=None):
        self.ocr_manager = ocr_manager
        self.device_manager = device_manager
        self.logger = __import__("logging").getLogger(__name__)

    def execute_step(self, step: Dict, context: Dict) -> str:
        """
        鎵ц鍗曚釜姝ラ锛屾敮鎸佺姸鎬佹満鎵╁睍

        Args:
            step: 姝ラ閰嶇疆
            context: 鎵ц涓婁笅鏂?
        Returns:
            "CONTINUE" - 缁х画鎵ц
            "BREAK" - 璺冲嚭寰幆
            "JUMP:<step_id>" - 璺宠浆鍒版寚瀹氭楠?            "DONE" - 瀹屾垚
        """
        action = step.get("action", "")
        step_id = step.get("id", "")

        self.logger.debug(f"鎵ц姝ラ锛歿step_id} (action={action})")

        if action == "loop":
            return self._execute_loop(step, context)
        elif action == "check":
            return self._execute_check(step, context)
        elif action == "find_and_click":
            return self._execute_find_and_click(step, context)
        elif action == "navigate":
            return self._execute_navigate(step, context)
        else:
            # 鍘熸湁鍔ㄤ綔绫诲瀷锛屼氦缁欐爣鍑嗘祦寮曟搸澶勭悊
            return "CONTINUE"

    def _execute_loop(self, step: Dict, context: Dict) -> str:
        """鎵ц寰幆姝ラ"""
        max_iterations = step.get("max_iterations", 10)
        loop_steps = step.get("steps", [])

        self.logger.info(f"寮€濮嬪惊鐜紝鏈€澶?{max_iterations} 娆?)

        for iteration in range(max_iterations):
            self.logger.debug(f"寰幆杩唬 {iteration + 1}/{max_iterations}")

            for sub_step in loop_steps:
                result = self.execute_step(sub_step, context)

                if result == "BREAK":
                    self.logger.info("寰幆琚?BREAK 涓柇")
                    return "DONE"
                elif result.startswith("JUMP:"):
                    self.logger.info(f"寰幆琚?JUMP 涓柇锛歿result}")
                    return result

            # 妫€鏌ュ惊鐜户缁潯浠?            if step.get("break_on", ""):
                if context.get(step["break_on"], False):
                    self.logger.info(f"寰幆缁撴潫鏉′欢婊¤冻锛歿step['break_on']}")
                    return "DONE"

        self.logger.info("寰幆杈惧埌鏈€澶ц凯浠ｆ鏁?)
        return "DONE"

    def _execute_check(self, step: Dict, context: Dict) -> str:
        """鎵ц鏉′欢妫€鏌ユ楠?""
        method = step.get("method", "")
        step_id = step.get("id", "")

        if method == "ocr":
            # OCR 鏂囨湰妫€鏌?- 浣跨敤 MaaFw OCR
            expected = step.get("expected", [])
            roi = step.get("roi")

            if self.ocr_manager:
                # 浣跨敤 MaaFw OCR 璇嗗埆
                screenshot = context.get("current_screenshot", None)
                if screenshot is None:
                    from core.capability.adb_utils import adb_screencap
                    screenshot = adb_screencap()

                # 閫氳繃 OCRManager 璋冪敤 MaaFw OCR
                results = self.ocr_manager.run_ocr(roi=roi, expected=expected)

                # 鏌ユ壘鍖归厤鐨勬枃鏈?                result = None
                for r in results:
                    if any(exp in r.get("text", "") for exp in expected):
                        result = r
                        break

                if result:
                    context["check_result"] = result
                    if step.get("on_found") == "break_loop":
                        return "BREAK"
                    elif step.get("on_found", "").startswith("jump:"):
                        return f"JUMP:{step['on_found'][5:]}"
                elif step.get("on_not_found") == "break_loop":
                    return "BREAK"

        elif method == "template_match":
            # 妯℃澘鍖归厤妫€鏌ワ紙寰呭疄鐜帮級
            template = step.get("template", "")
            # TODO: 闆嗘垚妯℃澘鍖归厤

        elif method == "page_type":
            # 椤甸潰绫诲瀷妫€鏌?            expected_type = step.get("expected_type", "")
            actual_type = context.get("current_page_type", "")

            if actual_type == expected_type:
                if step.get("on_found") == "break_loop":
                    return "BREAK"

        return "CONTINUE"

    def _execute_find_and_click(self, step: Dict, context: Dict) -> str:
        """鎵ц鏌ユ壘骞剁偣鍑绘楠?""
        method = step.get("method", "")

        if method == "ocr":
            expected = step.get("expected", [])
            roi = step.get("roi")

            if self.ocr_manager:
                # OCR 鏌ユ壘鏂囨湰 - 浣跨敤 MaaFw OCR
                screenshot = context.get("current_screenshot", None)
                if screenshot is None:
                    from core.capability.adb_utils import adb_screencap
                    screenshot = adb_screencap()

                # 閫氳繃 OCRManager 璋冪敤 MaaFw OCR
                results = self.ocr_manager.run_ocr(roi=roi, expected=expected)

                # 鏌ユ壘鍖归厤鐨勬枃鏈?                result = None
                for r in results:
                    if any(exp in r.get("text", "") for exp in expected):
                        result = r
                        break

                if result:
                    # 鐐瑰嚮鎵惧埌鐨勪綅缃?                    cx, cy = result.get("cx", 0), result.get("cy", 0)
                    self.logger.info(f"鎵惧埌鏂囨湰 '{result['text']}' 浜?({cx}, {cy})锛岀偣鍑?)

                    # 鎵ц鐐瑰嚮
                    if self.device_manager:
                        self.device_manager.tap(cx, cy)
                    else:
                        # 鍥為€€鍒?ADB
                        import subprocess
                        adb_path = PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"
                        subprocess.run([str(adb_path), "shell", "input", "tap", str(cx), str(cy)])

                    time.sleep(1)
                    return "FOUND"
                else:
                    if step.get("on_not_found") == "break_loop":
                        return "BREAK"
                    return "NOT_FOUND"

        return "NOT_FOUND"

    def _execute_navigate(self, step: Dict, context: Dict) -> str:
        """鎵ц瀵艰埅姝ラ"""
        target = step.get("target", "")

        if target == "world_map":
            # 瀵艰埅鍒颁笘鐣屽湴鍥撅紙宸叉湁瀹炵幇锛?            pass

        return "CONTINUE"


# 鈹€鈹€ 娴嬭瘯 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def main():
    """娴嬭瘯鐘舵€佹満"""
    print("=" * 60)
    print("鏍囧噯娴佺姸鎬佹満娴嬭瘯锛圡aaFw OCR锛?)
    print("=" * 60)

    # 鍒涘缓鐘舵€佹満锛堜娇鐢?MaaFw OCR锛?    from core.capability.ocr.ocr_manager import OCRManager
    ocr_manager = OCRManager()
    state_machine = FlowStateMachine(ocr_manager=ocr_manager)

    # 娴嬭瘯寰幆姝ラ锛堢畝鍗曠瓑寰呭惊鐜級
    loop_step = {
        "id": "test_loop",
        "action": "loop",
        "max_iterations": 3,
        "steps": [
            {"id": "wait", "action": "wait", "duration": 0.5}
        ]
    }

    context = {}
    result = state_machine.execute_step(loop_step, context)
    print(f"寰幆鎵ц缁撴灉锛歿result}")

    # 娴嬭瘯 check 姝ラ锛堟棤 OCR锛?    check_step = {
        "id": "test_check",
        "action": "check",
        "method": "page_type",
        "expected_type": "world_map"
    }
    context["current_page_type"] = "world_map"
    result = state_machine.execute_step(check_step, context)
    print(f"Check 鎵ц缁撴灉锛歿result}")

    print("\n[OK] 鐘舵€佹満娴嬭瘯瀹屾垚")
    print("\n娉ㄦ剰锛歁aaFw OCR 闇€閫氳繃 set_maafw_executor() 璁剧疆鎵ц鍣?)


if __name__ == "__main__":
    main()

