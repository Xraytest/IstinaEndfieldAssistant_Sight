#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
OCR 绠＄悊鍣?- 鍩轰簬 MaaFw 鍐呯疆 OCR 鐨勫睆骞曞喅绛栫郴缁?

浣跨敤 MaaFramework 鍐呭缓 OCR 寮曟搸锛屾浛浠?VLM 鍥惧儚杈撳叆銆?
寤惰繜浠?~20s 闄嶄綆鍒?~1s锛?5%+ 鎬ц兘鎻愬崌锛?
"""

import os
import sys
import json
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path

from core.foundation.paths import get_project_root, get_src_dir, ensure_src_path
ensure_src_path(__file__)

from core.foundation.logger import get_logger, LogCategory
from core.capability.ocr.screen_decider import ScreenDecider, ScreenState


class OCRManager:
    """
    OCR 绠＄悊鍣?- 鍩轰簬 MaaFw 鍐呯疆 OCR 鐨勫睆骞曞喅绛栫郴缁?

    浠呬娇鐢?MaaFramework 鍐呭缓 OCR 寮曟搸锛屾棤闇€棰濆渚濊禆銆?
    """

    def __init__(self, device_manager=None, config_path: str = None, touch_executor=None):
        """
        鍒濆鍖?OCR 绠＄悊鍣?

        Args:
            device_manager: 璁惧绠＄悊鍣紙鍙€夛級
            config_path: 閰嶇疆鏂囦欢璺緞锛堝彲閫夛級
            touch_executor: MaaFwTouchExecutor 瀹炰緥锛堝彲閫夛級
        """
        self.logger = get_logger()
        self.device_manager = device_manager
        self.decider = ScreenDecider()

        # 鍔犺浇閰嶇疆
        self.config = self._load_config(config_path)

        # MaaFw OCR 鐩稿叧
        self._maafw_executor = touch_executor
        self._controller_id = None

        # 濡傛灉浼犲叆浜?touch_executor锛岃嚜鍔ㄨ缃?
        if touch_executor is not None:
            self.set_maafw_executor(touch_executor, "default")

        self.logger.info(LogCategory.INFERENCE, "OCR 管理器初始化完成（MaaFw 提供 OCR）")

    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """鍔犺浇 OCR 閰嶇疆"""
        if config_path and os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)

        # 榛樿閰嶇疆璺緞
        default_path = Path(get_project_root(__file__)) / "config" / "ocr_config.json"

        if default_path.exists():
            with open(default_path, "r", encoding="utf-8") as f:
                return json.load(f)

        # 杩斿洖榛樿閰嶇疆
        return {
            "screen_resolution": {"width": 1280, "height": 720},
            "top_bar": {"y_range": [10, 80]},
            "overlay": {"roi": {"x_start": 950, "x_end": 1280, "y_start": 60, "y_end": 700}},
            "claim_keywords": ["领取", "收取", "一键领取", "完成", "提交", "领奖"],
        }

    def set_maafw_executor(self, executor, controller_id: str):
        """
        璁剧疆 MaaFw 鎵ц鍣?

        Args:
            executor: MaaFwTouchExecutor 瀹炰緥
            controller_id: 鎺у埗鍣?ID
        """
        self._maafw_executor = executor
        self._controller_id = controller_id
        self.logger.info(f"MaaFw 鎵ц鍣ㄥ凡璁剧疆锛宑ontroller_id: {controller_id}")

    def run_ocr(self, roi: List[int] = None, expected: List[str] = None) -> List[Dict]:
        """
        閫氳繃 MaaFw 鎵ц OCR 璇嗗埆

        Args:
            roi: 璇嗗埆鍖哄煙 [x, y, w, h]锛孨one 琛ㄧず鍏ㄥ睆
            expected: 鏈熸湜鍖归厤鐨勬枃鏈垪琛紙鍙€夛級

        Returns:
            OCR 缁撴灉鍒楄〃锛歔{"text": str, "box": [x,y,w,h], "score": float}, ...]
        """
        # 濡傛灉鎵ц鍣ㄦ湭璁剧疆锛屽皾璇曚粠 device_manager 鑾峰彇
        if self._maafw_executor is None:
            if self.device_manager and hasattr(self.device_manager, 'get_touch_executor'):
                self._maafw_executor = self.device_manager.get_touch_executor()
                if self._maafw_executor:
                    self.logger.info("从 device_manager 自动获取 MaaFw 执行器")
                    self.set_maafw_executor(self._maafw_executor, "auto")
            
            if self._maafw_executor is None:
                self.logger.error("MaaFw 鎵ц鍣ㄦ湭璁剧疆")
                return []

        try:
            # 璋冪敤 MaaFw OCR (5.11.1+ API)
            # 鍙傛暟杞崲涓?tuple 鏍煎紡
            roi_tuple = tuple(roi) if roi else None
            
            ocr_results = self._maafw_executor.ocr(
                roi=roi_tuple,
                expected=expected
            )

            # 褰掍竴鍖栫粨鏋滄牸寮?
            return self._normalize_ocr_results(ocr_results)

        except Exception as e:
            self.logger.error(f"MaaFw OCR 识别失败: {e}", exc_info=True)
            return []

    def _normalize_ocr_results(self, results: Any) -> List[Dict]:
        """
        褰掍竴鍖?OCR 缁撴灉涓烘爣鍑嗘牸寮?

        Args:
            results: MaaFw OCR 鍘熷缁撴灉

        Returns:
            鏍囧噯鍖?OCR 缁撴灉鍒楄〃
        """
        if not results:
            return []

        normalized = []
        for item in results:
            # MaaFw OCR 缁撴灉鏍煎紡锛歿"text": str, "box": [x,y,w,h], "score": float}
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

    def capture_and_recognize(self, roi: List[int] = None, expected: List[str] = None) -> ScreenState:
        """
        OCR + 鍐崇瓥涓€绔欏紡娴佺▼

        Args:
            roi: 璇嗗埆鍖哄煙 [x, y, w, h]
            expected: 鏈熸湜鍖归厤鐨勬枃鏈垪琛?

        Returns:
            ScreenState: 灞忓箷鐘舵€佹娴嬬粨鏋?
        """
        try:
            # 1. OCR 璇嗗埆锛堥€氳繃 MaaFw锛?
            ocr_results = self.run_ocr(roi=roi, expected=expected)
            if not ocr_results:
                return ScreenState(page_type="unknown", description="OCR 无结果")

            # 2. 鍐崇瓥妯″潡鍒嗘瀽
            state = self.decider.detect_screen_state(ocr_results)

            self.logger.info(f"OCR 识别完成: {state.page_type} - {state.description}")
            return state

        except Exception as e:
            self.logger.error(f"OCR 处理异常: {e}", exc_info=True)
            return ScreenState(page_type="error", description=f"OCR 异常: {str(e)}")

    def build_llm_prompt(self, state: ScreenState, instruction: str,
                         history: List[Dict] = None) -> str:
        """
        鏋勫缓绾枃鏈?LLM 鎻愮ず璇?

        Args:
            state: 灞忓箷鐘舵€佹娴嬬粨鏋?
            instruction: 浠诲姟鎸囦护
            history: 鍘嗗彶涓婁笅鏂囷紙鍙€夛級

        Returns:
            瀹屾暣鐨?LLM 鎻愮ず璇?
        """
        lines = [
            "你是一个明日方舟终末地游戏助手。根据以下屏幕信息执行操作：",
            "",
            "【屏幕状态】",
            state.to_llm_prompt(),
            "",
            "【操作指令】",
            instruction,
        ]

        if history and len(history) > 0:
            lines.append("")
            lines.append("【历史上下文】")
            for h in history[-3:]:  # 鏈€杩?3 姝?
                role = "操作" if h.get("role") == "user" else "结果"
                content = h.get("content", "")[:100]
                lines.append(f"- {role}: {content}")

        lines.append("")
        lines.append("请返回 JSON 格式的动作建议：")
        lines.append('{')
        lines.append('  "action": "click|swipe|back|wait|navigate",')
        lines.append('  "target": {"x": 123, "y": 456},  // 可选')
        lines.append('  "reason": "操作原因说明"')
        lines.append('}')

        return "\n".join(lines)

    def get_known_coords(self, name: str) -> Optional[Tuple[int, int]]:
        """
        鑾峰彇宸茬煡鍔熻兘鍧愭爣

        Args:
            name: 鍧愭爣鍚嶇О锛坱asks_button, event_button, claim_all 绛夛級

        Returns:
            (x, y) 鍧愭爣鍏冪粍锛屾垨 None
        """
        from core.foundation.game_coords import KNOWN_COORDS
        return KNOWN_COORDS.get(name)


# 鈹€鈹€ 鐙珛娴嬭瘯 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def main():
    """鐙珛娴嬭瘯"""
    print("=" * 60)
    print("OCR 管理器 - 测试（MaaFw 提供 OCR）")
    print("=" * 60)

    manager = OCRManager()

    # 娴嬭瘯宸茬煡鍧愭爣
    coords = manager.get_known_coords("tasks_button")
    print(f"任务按钮坐标: {coords}")

    # 娴嬭瘯鎻愮ず璇嶆瀯寤?
    mock_state = ScreenState(
        page_type="world_map_with_overlay",
        overlay_detected=True,
        overlay_texts=["姣忔棩浠诲姟", "棰嗗彇"],
        claim_buttons=[(1035, 323, "一键领取")]
    )

    prompt = manager.build_llm_prompt(mock_state, "检查并领取每日任务奖励")
    print(f"\nLLM 提示词预览:\n{prompt[:500]}...")


if __name__ == "__main__":
    main()

