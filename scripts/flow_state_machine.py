#!/usr/bin/env python3
"""
标准流引擎状态机扩展 - 支持循环和条件跳转

基于 MaaEnd 的设计模式，为标准流引擎添加：
1. loop 动作类型（循环执行）
2. check 动作类型（条件检查）
3. find_and_click 动作类型（MaaFw OCR 查找并点击）
4. 条件跳转（on_found/on_not_found）
"""

import sys
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()


class FlowStateMachine:
    """标准流状态机扩展"""

    def __init__(self, ocr_manager=None, device_manager=None):
        self.ocr_manager = ocr_manager
        self.device_manager = device_manager
        self.logger = __import__("logging").getLogger(__name__)

    def execute_step(self, step: Dict, context: Dict) -> str:
        """
        执行单个步骤，支持状态机扩展

        Args:
            step: 步骤配置
            context: 执行上下文

        Returns:
            "CONTINUE" - 继续执行
            "BREAK" - 跳出循环
            "JUMP:<step_id>" - 跳转到指定步骤
            "DONE" - 完成
        """
        action = step.get("action", "")
        step_id = step.get("id", "")

        self.logger.debug(f"执行步骤：{step_id} (action={action})")

        if action == "loop":
            return self._execute_loop(step, context)
        elif action == "check":
            return self._execute_check(step, context)
        elif action == "find_and_click":
            return self._execute_find_and_click(step, context)
        elif action == "navigate":
            return self._execute_navigate(step, context)
        else:
            # 原有动作类型，交给标准流引擎处理
            return "CONTINUE"

    def _execute_loop(self, step: Dict, context: Dict) -> str:
        """执行循环步骤"""
        max_iterations = step.get("max_iterations", 10)
        loop_steps = step.get("steps", [])

        self.logger.info(f"开始循环，最多 {max_iterations} 次")

        for iteration in range(max_iterations):
            self.logger.debug(f"循环迭代 {iteration + 1}/{max_iterations}")

            for sub_step in loop_steps:
                result = self.execute_step(sub_step, context)

                if result == "BREAK":
                    self.logger.info("循环被 BREAK 中断")
                    return "DONE"
                elif result.startswith("JUMP:"):
                    self.logger.info(f"循环被 JUMP 中断：{result}")
                    return result

            # 检查循环继续条件
            if step.get("break_on", ""):
                if context.get(step["break_on"], False):
                    self.logger.info(f"循环结束条件满足：{step['break_on']}")
                    return "DONE"

        self.logger.info("循环达到最大迭代次数")
        return "DONE"

    def _execute_check(self, step: Dict, context: Dict) -> str:
        """执行条件检查步骤"""
        method = step.get("method", "")
        step_id = step.get("id", "")

        if method == "ocr":
            # OCR 文本检查 - 使用 MaaFw OCR
            expected = step.get("expected", [])
            roi = step.get("roi")

            if self.ocr_manager:
                # 使用 MaaFw OCR 识别
                screenshot = context.get("current_screenshot", None)
                if screenshot is None:
                    from core.adb_utils import adb_screencap
                    screenshot = adb_screencap()

                # 通过 OCRManager 调用 MaaFw OCR
                results = self.ocr_manager.run_ocr(roi=roi, expected=expected)

                # 查找匹配的文本
                result = None
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
            # 模板匹配检查（待实现）
            template = step.get("template", "")
            # TODO: 集成模板匹配

        elif method == "page_type":
            # 页面类型检查
            expected_type = step.get("expected_type", "")
            actual_type = context.get("current_page_type", "")

            if actual_type == expected_type:
                if step.get("on_found") == "break_loop":
                    return "BREAK"

        return "CONTINUE"

    def _execute_find_and_click(self, step: Dict, context: Dict) -> str:
        """执行查找并点击步骤"""
        method = step.get("method", "")

        if method == "ocr":
            expected = step.get("expected", [])
            roi = step.get("roi")

            if self.ocr_manager:
                # OCR 查找文本 - 使用 MaaFw OCR
                screenshot = context.get("current_screenshot", None)
                if screenshot is None:
                    from core.adb_utils import adb_screencap
                    screenshot = adb_screencap()

                # 通过 OCRManager 调用 MaaFw OCR
                results = self.ocr_manager.run_ocr(roi=roi, expected=expected)

                # 查找匹配的文本
                result = None
                for r in results:
                    if any(exp in r.get("text", "") for exp in expected):
                        result = r
                        break

                if result:
                    # 点击找到的位置
                    cx, cy = result.get("cx", 0), result.get("cy", 0)
                    self.logger.info(f"找到文本 '{result['text']}' 于 ({cx}, {cy})，点击")

                    # 执行点击
                    if self.device_manager:
                        self.device_manager.tap(cx, cy)
                    else:
                        # 回退到 ADB
                        import subprocess
                        adb_path = PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"
                        subprocess.run([str(adb_path), "shell", "input", "tap", str(cx), str(cy)])

                    time.sleep(1)
                    return "FOUND"
                else:
                    if step.get("on_not_found") == "break_loop":
                        return "BREAK"
                    return "NOT_FOUND"

        return "NOT_FOUND"

    def _execute_navigate(self, step: Dict, context: Dict) -> str:
        """执行导航步骤"""
        target = step.get("target", "")

        if target == "world_map":
            # 导航到世界地图（已有实现）
            pass

        return "CONTINUE"


# ── 测试 ──────────────────────────────────────────────────────────

def main():
    """测试状态机"""
    print("=" * 60)
    print("标准流状态机测试（MaaFw OCR）")
    print("=" * 60)

    # 创建状态机（使用 MaaFw OCR）
    from core.ocr.ocr_manager import OCRManager
    ocr_manager = OCRManager()
    state_machine = FlowStateMachine(ocr_manager=ocr_manager)

    # 测试循环步骤（简单等待循环）
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
    print(f"循环执行结果：{result}")

    # 测试 check 步骤（无 OCR）
    check_step = {
        "id": "test_check",
        "action": "check",
        "method": "page_type",
        "expected_type": "world_map"
    }
    context["current_page_type"] = "world_map"
    result = state_machine.execute_step(check_step, context)
    print(f"Check 执行结果：{result}")

    print("\n[OK] 状态机测试完成")
    print("\n注意：MaaFw OCR 需通过 set_maafw_executor() 设置执行器")


if __name__ == "__main__":
    main()
