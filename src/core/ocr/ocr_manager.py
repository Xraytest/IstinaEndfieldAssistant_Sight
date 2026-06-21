#!/usr/bin/env python3
"""
OCR 管理器 - 基于 MaaFw 内置 OCR 的屏幕决策系统

使用 MaaFramework 内建 OCR 引擎，替代 VLM 图像输入。
延迟从 ~20s 降低到 ~1s（95%+ 性能提升）
"""

import os
import sys
import json
import logging
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path

from utils.paths import get_project_root, get_src_dir, ensure_src_path
ensure_src_path(__file__)

from core.ocr.screen_decider import ScreenDecider, ScreenState


class OCRManager:
    """
    OCR 管理器 - 基于 MaaFw 内置 OCR 的屏幕决策系统

    仅使用 MaaFramework 内建 OCR 引擎，无需额外依赖。
    """

    def __init__(self, device_manager=None, config_path: str = None):
        """
        初始化 OCR 管理器

        Args:
            device_manager: 设备管理器（可选）
            config_path: 配置文件路径（可选）
        """
        self.logger = logging.getLogger(__name__)
        self.device_manager = device_manager
        self.decider = ScreenDecider()

        # 加载配置
        self.config = self._load_config(config_path)

        # MaaFw OCR 相关
        self._maafw_executor = None
        self._controller_id = None

        self.logger.info("OCR 管理器初始化完成（MaaFw 内置 OCR）")

    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """加载 OCR 配置"""
        if config_path and os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)

        # 默认配置路径
        default_path = project_root / "config" / "ocr_config.json"

        if default_path.exists():
            with open(default_path, "r", encoding="utf-8") as f:
                return json.load(f)

        # 返回默认配置
        return {
            "screen_resolution": {"width": 1280, "height": 720},
            "top_bar": {"y_range": [10, 80]},
            "overlay": {"roi": {"x_start": 950, "x_end": 1280, "y_start": 60, "y_end": 700}},
            "claim_keywords": ["领取", "收取", "一键领取", "完成", "提交", "领奖"],
        }

    def set_maafw_executor(self, executor, controller_id: str):
        """
        设置 MaaFw 执行器

        Args:
            executor: MaaFwTouchExecutor 实例
            controller_id: 控制器 ID
        """
        self._maafw_executor = executor
        self._controller_id = controller_id
        self.logger.info(f"MaaFw 执行器已设置，controller_id: {controller_id}")

    def run_ocr(self, roi: List[int] = None, expected: List[str] = None) -> List[Dict]:
        """
        通过 MaaFw 执行 OCR 识别

        Args:
            roi: 识别区域 [x, y, w, h]，None 表示全屏
            expected: 期望匹配的文本列表（可选）

        Returns:
            OCR 结果列表：[{"text": str, "box": [x,y,w,h], "score": float}, ...]
        """
        if self._maafw_executor is None:
            self.logger.error("MaaFw 执行器未设置")
            return []

        try:
            # 调用 MaaFw OCR
            # 注意：实际调用需要通过 MaaFwTouchExecutor 的 ocr 方法
            ocr_results = self._maafw_executor.ocr(
                controller_id=self._controller_id,
                roi=roi,
                expected=expected
            )

            # 归一化结果格式
            return self._normalize_ocr_results(ocr_results)

        except Exception as e:
            self.logger.error(f"MaaFw OCR 识别异常：{e}", exc_info=True)
            return []

    def _normalize_ocr_results(self, results: Any) -> List[Dict]:
        """
        归一化 OCR 结果为标准格式

        Args:
            results: MaaFw OCR 原始结果

        Returns:
            标准化 OCR 结果列表
        """
        if not results:
            return []

        normalized = []
        for item in results:
            # MaaFw OCR 结果格式：{"text": str, "box": [x,y,w,h], "score": float}
            text = item.get("text", "").strip()
            box = item.get("box", [0, 0, 0, 0])
            score = item.get("score", 0.0)

            if not text or score < 0.3:
                continue

            x, y, w, h = box
            cx = x + w // 2
            cy = y + h // 2

            normalized.append({
                "text": text,
                "box": [int(x), int(y), int(w), int(h)],
                "cx": cx,
                "cy": cy,
                "score": float(score)
            })

        return normalized

    def capture_and_recognize(self, device_serial: str = None,
                              roi: List[int] = None, expected: List[str] = None) -> ScreenState:
        """
        OCR + 决策一站式流程

        Args:
            device_serial: 设备序列号（可选，MaaFw 模式下不使用）
            roi: 识别区域 [x, y, w, h]
            expected: 期望匹配的文本列表

        Returns:
            ScreenState: 屏幕状态检测结果
        """
        try:
            # 1. OCR 识别（通过 MaaFw）
            ocr_results = self.run_ocr(roi=roi, expected=expected)
            if not ocr_results:
                return ScreenState(page_type="unknown", description="OCR 无结果")

            # 2. 决策模块分析
            state = self.decider.detect_screen_state(ocr_results)

            self.logger.info(f"OCR 决策完成：{state.page_type} - {state.description}")
            return state

        except Exception as e:
            self.logger.error(f"OCR 决策异常：{e}", exc_info=True)
            return ScreenState(page_type="error", description=f"OCR 异常：{str(e)}")

    def build_llm_prompt(self, state: ScreenState, instruction: str,
                         history: List[Dict] = None) -> str:
        """
        构建纯文本 LLM 提示词

        Args:
            state: 屏幕状态检测结果
            instruction: 任务指令
            history: 历史上下文（可选）

        Returns:
            完整的 LLM 提示词
        """
        lines = [
            "你是一个明日方舟终末地游戏助手。根据以下屏幕信息执行任务。",
            "",
            "【屏幕状态】",
            state.to_llm_prompt(),
            "",
            "【任务指令】",
            instruction,
        ]

        if history and len(history) > 0:
            lines.append("")
            lines.append("【历史上下文】")
            for h in history[-3:]:  # 最近 3 步
                role = "操作" if h.get("role") == "user" else "结果"
                content = h.get("content", "")[:100]
                lines.append(f"- {role}: {content}")

        lines.append("")
        lines.append("请返回 JSON 格式的操作建议：")
        lines.append('{')
        lines.append('  "action": "click|swipe|back|wait|navigate",')
        lines.append('  "target": {"x": 123, "y": 456},  // 可选')
        lines.append('  "reason": "操作原因说明"')
        lines.append('}')

        return "\n".join(lines)

    def get_known_coords(self, name: str) -> Optional[Tuple[int, int]]:
        """
        获取已知功能坐标

        Args:
            name: 坐标名称（tasks_button, event_button, claim_all 等）

        Returns:
            (x, y) 坐标元组，或 None
        """
        from core.game_coords import KNOWN_COORDS
        return KNOWN_COORDS.get(name)


# ── 独立测试 ──────────────────────────────────────────────────────

def main():
    """独立测试"""
    print("=" * 60)
    print("OCR 管理器 - 测试（MaaFw 内置 OCR）")
    print("=" * 60)

    manager = OCRManager()

    # 测试已知坐标
    coords = manager.get_known_coords("tasks_button")
    print(f"任务按钮坐标：{coords}")

    # 测试提示词构建
    mock_state = ScreenState(
        page_type="world_map_with_overlay",
        overlay_detected=True,
        overlay_texts=["每日任务", "领取"],
        claim_buttons=[(1035, 323, "一键领取")]
    )

    prompt = manager.build_llm_prompt(mock_state, "检查并领取每日任务奖励")
    print(f"\nLLM 提示词预览:\n{prompt[:500]}...")


if __name__ == "__main__":
    main()
