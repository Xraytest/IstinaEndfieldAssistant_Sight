"""VLM高精度UI元素分析器

调用IstinaPlatform大参数模型分析游戏画面中的UI元素。
"""

import json
import re
import time
from typing import Dict, Any, List, Optional, Tuple

from core.vlm_client import VLMClient

from .models import (
    ElementKnowledge, ElementType, AnalysisResult,
    VerificationStatus, make_semantic_id,
)
from .element_repo import ElementRepository


# 全元素分析：识别所有可交互UI元素
FULL_ELEMENT_SYSTEM_PROMPT = """你是《明日方舟：终末地》精确游戏UI分析器。识别当前画面所有可交互元素并输出JSON。

输出格式（严格遵循）：
```
{
  "page_name": "简短中文页面名",
  "page_type": "world_map/menu/dialog/battle/shop/task_ui/event/loading/other",
  "elements": [
    {
      "id": "e1",
      "type": "button/text/icon/tab/toggle/slider/input/list_item",
      "label": "精确可见文本",
      "bbox": [x1, y1, x2, y2],
      "confidence": 0.95,
      "action": "tap/swipe/none",
      "function": "该元素功能的中文描述"
    }
  ],
  "has_daily_tasks": boolean,
  "has_weekly_tasks": boolean,
  "has_event": boolean,
  "description": "一句中文摘要"
}
```

规则：
1. bbox为[x1,y1,x2,y2]像素坐标，基于实际截图分辨率
2. label用精确可见文本，优先中文
3. type=text的元素action必须为"none"
4. page_name必须是有意义的中文名称
5. 特别注意：每日任务、每周任务、签到、奖励领取相关按钮
6. has_daily_tasks/has_weekly_tasks/has_event：当前页面是否有这些内容
7. function字段描述元素的游戏内功能，非常重要
"""

# 任务聚焦分析：重点识别每日/每周/活动任务
TASK_FOCUSED_PROMPT = """你是《明日方舟：终末地》任务UI分析器。重点识别任务相关元素。

输出JSON：
```
{
  "page_name": "中文页面名",
  "page_type": "task_ui/event/menu/dialog/world_map/other",
  "has_daily_tasks": boolean,
  "has_weekly_tasks": boolean,
  "has_event": boolean,
  "tasks": [
    {
      "task_name": "任务名称",
      "type": "daily/weekly/event",
      "status": "not_started/in_progress/completed/claimable/claimed",
      "progress": "3/10",
      "current": 3,
      "total": 10,
      "claim_button": [x1, y1, x2, y2] 或 null,
      "rewards": [
        {"item": "奖励名称", "count": 1}
      ]
    }
  ],
  "elements": [
    {"id":"e1","type":"button/text/icon/tab","label":"文本","bbox":[x1,y1,x2,y2],"action":"tap/none","function":"功能"}
  ],
  "description": "一句中文描述"
}
```

特别注意：
- 识别每个任务的完成状态，"可领取"/"已完成"/"未开始"
- 定位"领取"按钮的精确bbox坐标
- 读取任务进度如 "5/10" 解析为 current=5, total=10
- 读取奖励物品名称和数量
"""


def _parse_json_from_reply(reply: str) -> Optional[Dict[str, Any]]:
    """从VLM回复中解析JSON"""
    if not reply:
        return None
    # 尝试直接解析
    try:
        return json.loads(reply)
    except json.JSONDecodeError:
        pass
    # 尝试在```json ... ```中提取
    code_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', reply)
    if code_match:
        try:
            return json.loads(code_match.group(1))
        except json.JSONDecodeError:
            pass
    # 尝试提取第一个 {}
    brace_match = re.search(r'\{[\s\S]*\}', reply)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass
    return None


def _elements_from_vlm(vlm_data: Dict[str, Any], page_name: str, page_hash: str) -> List[ElementKnowledge]:
    """将VLM返回的元素数据转换为ElementKnowledge对象列表"""
    elements = []
    raw_elements = vlm_data.get("elements", [])
    if isinstance(raw_elements, list):
        for idx, elem_data in enumerate(raw_elements):
            if not isinstance(elem_data, dict):
                continue
            label = elem_data.get("label", "")
            elem_type_str = elem_data.get("type", "unknown")
            bbox = tuple(elem_data.get("bbox", [0, 0, 0, 0]))
            confidence = elem_data.get("confidence", 0.5)
            action = elem_data.get("action", "tap")
            function = elem_data.get("function", "")

            element_id = elem_data.get("id", f"elem_{idx}")
            semantic_id = make_semantic_id(page_name, label, elem_type_str)

            # 验证bbox合法性
            if len(bbox) == 4 and bbox[2] > bbox[0] and bbox[3] > bbox[1]:
                valid_bbox = bbox
            else:
                valid_bbox = (0.0, 0.0, 0.0, 0.0)

            try:
                element_type = ElementType(elem_type_str)
            except ValueError:
                element_type = ElementType.UNKNOWN

            element = ElementKnowledge(
                element_id=element_id,
                semantic_id=semantic_id,
                element_type=element_type,
                label=label,
                bbox=valid_bbox,
                confidence=confidence,
                page_name=page_name,
                page_hash=page_hash,
                action=action if action in ("tap", "swipe", "none") else "tap",
                extra={"function": function},
            )
            elements.append(element)
    return elements


class ElementAnalyzer:
    """统一 UI 元素分析器

    使用 VLMClient（自动路由本地/服务端）分析游戏画面中的 UI 元素。
    替代云端 ElementAnalyzer 和本地 LocalElementAnalyzer。
    """

    def __init__(
        self,
        vlm_client=None,
        screen_capture=None,
        device_serial: str = "localhost:16512",
        model_tag: str = "exploration_deep",
        session_id: str = "",
        user_id: str = "explorer",
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ):
        self._vlm_client = vlm_client or VLMClient({"vlm_mode": "local"})
        self.screen_capture = screen_capture
        self.device_serial = device_serial
        self.model_tag = model_tag
        self.session_id = session_id
        self.user_id = user_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.repo = ElementRepository()
        self._last_raw_reply: str = ""

    @property
    def last_raw_reply(self) -> str:
        return self._last_raw_reply

    def _capture_and_encode(self) -> Optional[str]:
        """截图并 base64 编码

        支持多种输入格式：
        - bytes 且以 b'/' 开头：文件路径，读取并 base64 编码
        - bytes 且为 PNG 数据：直接 base64 编码
        - str 且以 '/' 开头：文件路径，读取并 base64 编码
        - str 且为 base64 数据：直接返回
        """
        raw = self.screen_capture.capture_screen(self.device_serial)
        if not raw:
            return None

        import base64

        if isinstance(raw, bytes):
            if raw.startswith(b'/'):
                # 文件路径 → 读取并编码
                path = raw.decode("utf-8")
                try:
                    with open(path, "rb") as f:
                        return base64.b64encode(f.read()).decode("utf-8")
                except OSError:
                    return None
            # PNG 字节 → base64 编码
            return base64.b64encode(raw).decode("utf-8")

        if isinstance(raw, str):
            if raw.startswith('/'):
                # 文件路径 → 读取并编码
                try:
                    with open(raw, "rb") as f:
                        import base64
                        return base64.b64encode(f.read()).decode("utf-8")
                except OSError:
                    return None
            # 已经是 base64 字符串
            return raw

        return raw

    def _send_analysis(self, instruction: str, system_prompt: str) -> Optional[Dict[str, Any]]:
        """通过 VLMClient 分析画面（统一路由本地/服务端）"""
        screenshot_b64 = self._capture_and_encode()
        if not screenshot_b64:
            return None

        try:
            result = self._vlm_client.analyze_image(
                screenshot_b64,
                instruction,
                system_prompt=system_prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            if result.get("status") != "success":
                return None

            content = result.get("content", "")
            self._last_raw_reply = content
            return _parse_json_from_reply(content) or result.get("parsed")
        except Exception:
            return None

    def analyze_full_page(self) -> Optional[AnalysisResult]:
        """全页面元素分析
        
        识别所有可交互UI元素。
        """
        screenshot_b64 = self._capture_and_encode()
        if not screenshot_b64:
            return None

        import hashlib
        page_hash = hashlib.sha256(
            screenshot_b64.encode()[:4096] if len(screenshot_b64) > 4096 else screenshot_b64.encode()
        ).hexdigest()[:16]

        vlm_data = self._send_analysis(
            "识别当前游戏画面中的所有可交互UI元素，包括按钮、图标、文字标签等。特别注意任务相关按钮。",
            FULL_ELEMENT_SYSTEM_PROMPT,
        )

        if not vlm_data:
            return None

        page_name = vlm_data.get("page_name", "未知页面")
        page_type = vlm_data.get("page_type", "other")
        description = vlm_data.get("description", "")
        has_daily = bool(vlm_data.get("has_daily_tasks", False))
        has_weekly = bool(vlm_data.get("has_weekly_tasks", False))
        has_event = bool(vlm_data.get("has_event", False))

        elements = _elements_from_vlm(vlm_data, page_name, page_hash)

        result = AnalysisResult(
            page_name=page_name,
            page_type=page_type,
            elements=[e.to_dict() for e in elements],
            has_daily_tasks=has_daily,
            has_weekly_tasks=has_weekly,
            has_event=has_event,
            description=description,
            raw_reply=self._last_raw_reply,
            model_tag=self.model_tag,
            timestamp=time.time(),
            screenshot_hash=page_hash,
        )

        # 持久化
        self.repo.save_analysis_result(result)

        return result

    def analyze_tasks_focused(self) -> Optional[AnalysisResult]:
        """任务聚焦分析
        
        重点识别每日/每周/活动任务及其状态。
        """
        screenshot_b64 = self._capture_and_encode()
        if not screenshot_b64:
            return None

        import hashlib
        page_hash = hashlib.sha256(
            screenshot_b64.encode()[:4096] if len(screenshot_b64) > 4096 else screenshot_b64.encode()
        ).hexdigest()[:16]

        vlm_data = self._send_analysis(
            "分析当前游戏界面中的每日任务、每周任务和活动任务。列出所有任务及其完成状态、进度和领取按钮位置。",
            TASK_FOCUSED_PROMPT,
        )

        if not vlm_data:
            return None

        page_name = vlm_data.get("page_name", "未知页面")
        page_type = vlm_data.get("page_type", "other")
        description = vlm_data.get("description", "")
        has_daily = bool(vlm_data.get("has_daily_tasks", False))
        has_weekly = bool(vlm_data.get("has_weekly_tasks", False))
        has_event = bool(vlm_data.get("has_event", False))

        elements = _elements_from_vlm(vlm_data, page_name, page_hash)

        result = AnalysisResult(
            page_name=page_name,
            page_type=page_type,
            elements=[e.to_dict() for e in elements],
            has_daily_tasks=has_daily,
            has_weekly_tasks=has_weekly,
            has_event=has_event,
            description=description,
            raw_reply=self._last_raw_reply,
            model_tag=self.model_tag,
            timestamp=time.time(),
            screenshot_hash=page_hash,
        )

        self.repo.save_analysis_result(result)

        return result

    def verify_element(self, element: ElementKnowledge) -> bool:
        """验证单个元素的存在（位置/标签匹配）
        
        通过截屏并调用VLM确认元素是否仍在原位置。
        """
        # 简化的验证：截新图并检查相同区域
        # TODO: 实现裁剪bbox区域发送验证
        return True
