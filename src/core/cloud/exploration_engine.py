"""
探索引擎 [已废弃]

此模块功能已被 exploration_engine_optimized.py 替代。
新代码请使用 OptimizedExplorationEngine。
"""

import warnings
warnings.warn(
    "exploration_engine.py 已废弃，请使用 exploration_engine_optimized.py",
    DeprecationWarning, stacklevel=2
)

import base64
import json
import os
import re
import signal
import subprocess
import time
import threading
from typing import Optional, Dict, Any, List, Callable, Tuple
from dataclasses import dataclass
from enum import Enum

from core.vlm_client import VLMClient

from .page_tree import (
    PageTree, PageNode, PageEdge, UIElement, ElementType, PageState,
    hash_screenshot, hash_element,
)


EXPLORATION_SYSTEM_PROMPT = """你是《明日方舟：终末地》精确游戏UI分析器。识别所有可交互元素并输出JSON。

输出格式：
{
  "page_name": "简短中文页面名，如「战斗准备」「制造设施」「每日任务」「商店」「角色编队」",
  "page_type": "menu/dialog/battle/world_map/shop/inventory/gacha/settings/loading/other",
  "elements": [
    {
      "id": "elem_1",
      "type": "button/text/icon/tab/toggle/slider/input/list_item",
      "label": "精确可见文本或功能描述，如「签到」「领取」「开始战斗」「制造」「收取」",
      "bbox": [x1, y1, x2, y2],
      "confidence": 0.95,
      "action": "tap/swipe/none"
    }
  ],
  "back_button": "返回按钮elem_id或null",
  "scrollable": true/false,
  "description": "一句中文摘要"
}

规则：
1. bbox为[x1,y1,x2,y2]像素坐标，基于实际截图分辨率
2. label用精确可见文本，优先中文
3. 不可点击的文本标签action为"none"
4. page_name必须是有意义的中文名称
5. 特别注意：每日任务、每周任务、签到、奖励领取相关按钮"""

ELEMENT_VERIFY_PROMPT = """验证当前画面上的这些UI元素。对每个元素确认：
1. 该元素在给定坐标处存在
2. 标签文本正确
3. 它是可点击的

输出JSON：
{
  "verified_elements": [
    {
      "id": "elem_N",
      "verified": true/false,
      "label": "修正后的标签（如果错误）",
      "bbox": [x1, y1, x2, y2],
      "confidence": 0.95
    }
  ]
}"""


class ExplorationState(Enum):
    IDLE = "idle"
    ANALYZING = "analyzing"
    VERIFYING = "verifying"
    NAVIGATING = "navigating"
    BACKTRACKING = "backtracking"
    SAVING = "saving"
    ERROR = "error"


@dataclass
class ExplorationConfig:
    device_serial: str = ""
    server_host: str = "127.0.0.1"
    server_port: int = 9999
    model_tag: str = "exploration_deep"
    verification_passes: int = 2
    tap_wait_time: float = 2.0
    backtrack_command: str = "back"
    max_depth: int = 20
    max_pages: int = 200
    output_file: str = "cache/game_map.md"
    output_json: str = "cache/page_tree.json"
    save_interval: int = 5
    session_id: str = ""
    user_id: str = "explorer"


class ExplorationEngine:
    def __init__(self, vlm_client=None, screen_capture=None, touch_executor=None,
                 agent_executor=None, config: ExplorationConfig = None):
        self._vlm_client = vlm_client or VLMClient({"vlm_mode": "local"})
        self._screen_capture = screen_capture
        self._touch_executor = touch_executor
        self._agent_executor = agent_executor
        self._config = config or ExplorationConfig()
        self._page_tree = PageTree()
        self._state = ExplorationState.IDLE
        self._running = False
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._explore_queue: List[str] = []
        self._visited_pages: set = set()
        self._stats = {"vlm_calls": 0, "pages_found": 0, "elements_found": 0, "taps": 0, "errors": 0}
        self._callbacks: Dict[str, List[Callable]] = {
            "page_discovered": [],
            "element_found": [],
            "state_changed": [],
            "error": [],
            "save": [],
        }
        self._history: List[Dict[str, Any]] = []

    @property
    def page_tree(self) -> PageTree:
        return self._page_tree

    @property
    def state(self) -> ExplorationState:
        return self._state

    @property
    def running(self) -> bool:
        return self._running

    @property
    def stats(self) -> Dict[str, int]:
        return dict(self._stats)

    def on(self, event: str, callback: Callable) -> None:
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _emit(self, event: str, **kwargs) -> None:
        for cb in self._callbacks.get(event, []):
            cb(**kwargs)

    def _set_state(self, state: ExplorationState) -> None:
        self._state = state
        self._emit("state_changed", state=state)

    def start(self) -> None:
        self._running = True
        self._set_state(ExplorationState.ANALYZING)
        self._explore_loop()

    def stop(self) -> None:
        self._running = False
        self._pause_event.set()

    def pause(self) -> None:
        self._pause_event.clear()

    def resume(self) -> None:
        self._pause_event.set()

    def _capture_screen(self) -> Optional[str]:
        if not self._screen_capture:
            self._emit("error", message="ScreenCapture not initialized")
            return None

        if self._config.device_serial:
            result = self._screen_capture.capture_screen(self._config.device_serial)
        else:
            result = self._screen_capture.capture_screen("emulator-5554")

        if result is None:
            self._emit("error", message="Screenshot capture returned None")
            return None

        if isinstance(result, tuple):
            success, img_bytes = result
            if not success:
                self._emit("error", message="Screenshot capture failed")
                return None
        else:
            img_bytes = result

        if isinstance(img_bytes, bytes):
            return img_bytes.decode("utf-8")
        return img_bytes

    def _execute_tap(self, x: int, y: int) -> bool:
        if self._touch_executor:
            result = self._touch_executor.safe_press(x, y)
            if result:
                self._stats["taps"] += 1
                return True
        return False

    def _execute_back(self) -> bool:
        if self._touch_executor:
            return self._touch_executor.execute_tool_call("pipeline_task", {"entry": "Back"})
        return False

    def _call_vlm(self, screenshot_b64: str, user_prompt: str,
                  system_prompt: str = None, model_tag: str = None) -> Optional[Dict[str, Any]]:
        self._stats["vlm_calls"] += 1

        if self._agent_executor:
            try:
                response = self._agent_executor.send_instruction(user_prompt)
                if response and response.get("status") == "success":
                    reply_text = response.get("reply", "")
                    actions = response.get("actions", [])
                    parsed = self._parse_json_from_text(reply_text)
                    if parsed:
                        parsed["_actions"] = actions
                        return parsed
                    return {"reply": reply_text, "actions": actions}
                return None
            except Exception as e:
                self._emit("error", message=f"AgentExecutor failed: {e}")
                return None

        try:
            result = self._vlm_client.analyze_image(
                screenshot_b64,
                user_prompt,
                system_prompt=system_prompt,
                max_tokens=2048,
                temperature=0.1,
            )
            if result.get("status") == "success":
                content = result.get("content", "")
                parsed = result.get("parsed") or self._parse_json_from_text(content)
                return parsed or {"reply": content}
            return None
        except Exception as e:
            self._emit("error", message=f"VLM call failed: {e}")
            return None

    def _parse_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None

        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        return None

    def _identify_elements(self, screenshot_b64: str) -> Optional[Dict[str, Any]]:
        result = self._call_vlm(screenshot_b64, "识别当前游戏画面中所有可交互的UI元素，包括按钮、图标、文字标签、标签页、滑块、开关等。给出精确的坐标。", EXPLORATION_SYSTEM_PROMPT, "exploration_deep")
        if result is None:
            return None
        if isinstance(result, list):
            return {"elements": result, "page_name": "Unknown", "page_type": "other", "description": "", "back_button": None, "scrollable": False}
        return result

    def _verify_elements(self, screenshot_b64: str, elements: List[Dict]) -> Optional[Dict[str, Any]]:
        elem_list = json.dumps(elements, ensure_ascii=False, indent=2)
        prompt = f"{ELEMENT_VERIFY_PROMPT}\n\nElements to verify:\n{elem_list}"
        return self._call_vlm(screenshot_b64, prompt, model_tag="vision")

    def _explore_loop(self) -> None:
        self._set_state(ExplorationState.ANALYZING)
        root_page = self._analyze_current_page(parent_edge=None)
        if root_page:
            self._page_tree.root = root_page
            self._visited_pages.add(root_page.page_id)
            self._enqueue_elements(root_page)
        self._save_results()

        while self._running and self._page_tree.stats["pages_discovered"] < self._config.max_pages:
            self._pause_event.wait()

            if not self._explore_queue:
                unvisited = self._find_next_unvisited()
                if unvisited:
                    self._explore_queue = unvisited
                else:
                    break

            if not self._explore_queue:
                break

            target_page_id, element_id, element = self._explore_queue.pop(0)
            self._navigate_and_explore(target_page_id, element_id, element)

            if self._page_tree.stats["pages_discovered"] % max(1, self._config.save_interval) == 0:
                self._save_results()

        self._save_results()

    def _analyze_current_page(self, parent_edge: str = None) -> Optional[PageNode]:
        self._set_state(ExplorationState.ANALYZING)
        screenshot_b64 = self._capture_screen()
        if not screenshot_b64:
            self._stats["errors"] += 1
            return None

        page_hash = hash_screenshot(screenshot_b64)
        existing = self._page_tree.get_node_by_hash(page_hash)
        if existing and existing.state == PageState.EXPLORED:
            return existing

        vlm_result = self._identify_elements(screenshot_b64)
        if not vlm_result:
            self._stats["errors"] += 1
            return None

        elements = self._parse_elements_from_vlm(vlm_result)
        page_name = vlm_result.get("page_name", f"Page_{page_hash[:8]}")

        verified_elements = self._multi_pass_verify(screenshot_b64, elements)

        page_id = f"page_{page_hash}"
        node = PageNode(
            page_id=page_id,
            name=page_name,
            screenshot_hash=page_hash,
            elements=verified_elements,
            parent_edge=parent_edge,
            depth=0,
            state=PageState.EXPLORING,
            vlm_response=vlm_result,
        )

        existing_node = self._page_tree.get_node(page_id)
        if existing_node:
            existing_node.elements = verified_elements
            existing_node.state = PageState.EXPLORING
            existing_node.vlm_response = vlm_result
            existing_node.verification_count += 1
        else:
            self._page_tree.add_node(node)
            self._stats["pages_found"] += 1
            self._emit("page_discovered", page=node)

        self._stats["elements_found"] += len(verified_elements)
        return node

    def _parse_elements_from_vlm(self, vlm_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_elements = vlm_result.get("elements", [])
        if not raw_elements:
            reply = vlm_result.get("reply", "")
            if reply:
                parsed = self._parse_json_from_text(reply)
                if isinstance(parsed, list):
                    raw_elements = parsed
                elif isinstance(parsed, dict):
                    raw_elements = parsed.get("elements", [])

        normalized = []
        for elem in raw_elements:
            if not isinstance(elem, dict):
                continue
            ne = dict(elem)
            if "bbox_2d" in ne and "bbox" not in ne:
                ne["bbox"] = ne.pop("bbox_2d")
            if "text_content" in ne and "label" not in ne:
                ne["label"] = ne.pop("text_content")
            if "bbox" not in ne:
                ne["bbox"] = [0, 0, 0, 0]
            if "label" not in ne:
                ne["label"] = ne.get("text_content", "")
            if "id" not in ne:
                ne["id"] = f"elem_{hash_element(json.dumps(ne, sort_keys=True))}"
            if "type" not in ne:
                ne["type"] = "button" if ne.get("action") in ("tap", None) else "unknown"
            if "confidence" not in ne:
                ne["confidence"] = 0.7
            if "action" not in ne:
                ne["action"] = "tap"
            normalized.append(ne)

        return normalized

    def _multi_pass_verify(self, screenshot_b64: str, elements: List[Dict[str, Any]]) -> List[UIElement]:
        verified: List[UIElement] = []
        element_map: Dict[str, Dict] = {}
        for elem in elements:
            eid = elem.get("id", hash_element(json.dumps(elem, sort_keys=True)))
            element_map[eid] = elem

        if not elements:
            return []

        verified_ids: set = set()
        for pass_num in range(self._config.verification_passes):
            if pass_num == 0:
                for eid, elem in element_map.items():
                    if eid in verified_ids:
                        continue
                    verified.append(self._dict_to_element(eid, elem))
                    verified_ids.add(eid)
            else:
                verify_result = self._verify_elements(screenshot_b64, [element_map[eid] for eid in element_map if eid not in verified_ids])
                if verify_result:
                    for ve in verify_result.get("verified_elements", []):
                        vid = ve.get("id", "")
                        if ve.get("verified", True) and vid in element_map:
                            elem = element_map[vid]
                            elem["label"] = ve.get("label", elem.get("label", ""))
                            elem["bbox"] = ve.get("bbox", elem.get("bbox", [0, 0, 0, 0]))
                            elem["confidence"] = ve.get("confidence", elem.get("confidence", 0.5))
                            verified.append(self._dict_to_element(vid, elem))
                            verified_ids.add(vid)

        if not verified:
            for eid, elem in element_map.items():
                verified.append(self._dict_to_element(eid, elem))

        return verified

    def _dict_to_element(self, eid: str, elem: Dict[str, Any]) -> UIElement:
        elem_type_str = elem.get("type", "unknown")
        element_type = ElementType.UNKNOWN
        for et in ElementType:
            if et.value == elem_type_str:
                element_type = et
                break

        bbox = elem.get("bbox", [0, 0, 0, 0])
        if len(bbox) != 4:
            bbox = [0, 0, 0, 0]

        return UIElement(
            element_id=eid,
            element_type=element_type,
            label=elem.get("label", ""),
            bbox=tuple(float(b) for b in bbox),
            confidence=float(elem.get("confidence", 0.5)),
            extra={
                "action": elem.get("action", "tap"),
                "description": elem.get("description", ""),
            },
        )

    def _enqueue_elements(self, node: PageNode) -> None:
        for element in node.unexplored_elements:
            self._explore_queue.append((node.page_id, element.element_id, element))

    def _find_next_unvisited(self) -> List[Tuple[str, str, UIElement]]:
        for page_id in self._visited_pages:
            node = self._page_tree.get_node(page_id)
            if not node:
                continue
            unexplored = [e for e in node.unexplored_elements if e.confidence >= 0.5]
            if unexplored:
                unexplored.sort(key=lambda e: e.confidence, reverse=True)
                return [(page_id, e.element_id, e) for e in unexplored[:5]]
        return []

    def _navigate_and_explore(self, from_page_id: str, element_id: str, element: UIElement) -> None:
        self._set_state(ExplorationState.NAVIGATING)
        bbox = element.bbox
        cx = int((bbox[0] + bbox[2]) / 2)
        cy = int((bbox[1] + bbox[3]) / 2)

        if cx <= 0 or cy <= 0:
            self._emit("error", message=f"Invalid bbox for element {element_id}: {bbox}")
            return

        self._execute_tap(cx, cy)
        time.sleep(self._config.tap_wait_time)

        before_hash = ""
        if from_page_id in self._page_tree.nodes:
            before_hash = self._page_tree.get_node(from_page_id).screenshot_hash

        self._set_state(ExplorationState.ANALYZING)
        new_node = self._analyze_current_page(parent_edge=element_id)
        if not new_node:
            self._execute_back()
            time.sleep(1.0)
            return

        new_hash = new_node.screenshot_hash
        if new_hash == before_hash:
            self._emit("element_found", element=element, page=new_node)
            return

        edge = PageEdge(
            edge_id=f"edge_{from_page_id}_{element_id}_{new_node.page_id}",
            from_page_id=from_page_id,
            to_page_id=new_node.page_id,
            element_id=element_id,
            action_type=element.extra.get("action", "tap"),
            action_params={"x": cx, "y": cy},
        )
        self._page_tree.add_edge(edge)

        if new_node.page_id not in self._visited_pages:
            self._visited_pages.add(new_node.page_id)
            self._enqueue_elements(new_node)

        self._execute_back()
        time.sleep(1.0)

    def _save_results(self) -> None:
        self._set_state(ExplorationState.SAVING)

        output_dir = os.path.dirname(self._config.output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        self._page_tree.save(self._config.output_json)

        md_content = self._render_markdown()
        with open(self._config.output_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        self._emit("save", md_file=self._config.output_file, json_file=self._config.output_json)

    def _render_markdown(self) -> str:
        lines = []
        lines.append("# Arknights Endfield - Game Map")
        lines.append(f"")
        lines.append(f"**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Pages Discovered**: {self._page_tree.stats['pages_discovered']}")
        lines.append(f"**Elements Found**: {self._page_tree.stats['elements_found']}")
        lines.append(f"**Edges Created**: {self._page_tree.stats['edges_created']}")
        lines.append(f"**VLM Calls**: {self._stats['vlm_calls']}")
        lines.append(f"**Taps Executed**: {self._stats['taps']}")
        lines.append(f"")
        lines.append("---")
        lines.append("")
        lines.append("## Page Tree")
        lines.append("")
        lines.append("```")
        self._render_tree_markdown(lines, self._page_tree.root, "", True)
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Page Details")
        lines.append("")

        for page_id in sorted(self._page_tree.nodes.keys()):
            node = self._page_tree.get_node(page_id)
            if not node:
                continue
            lines.append(f"### {node.icon_name} {node.name}")
            lines.append(f"- **ID**: `{node.page_id}`")
            lines.append(f"- **Hash**: `{node.screenshot_hash}`")
            lines.append(f"- **State**: {node.state.value}")
            lines.append(f"- **Depth**: {node.depth}")
            lines.append(f"- **Verifications**: {node.verification_count}")
            lines.append(f"- **Resolution**: {node.resolution[0]}x{node.resolution[1]}")
            lines.append("")
            if node.elements:
                lines.append("| # | Type | Label | BBox [x1,y1,x2,y2] | Conf | Explored |")
                lines.append("|---|------|-------|----------------------|------|----------|")
                for i, elem in enumerate(node.elements, 1):
                    bbox_str = f"[{int(elem.bbox[0])},{int(elem.bbox[1])},{int(elem.bbox[2])},{int(elem.bbox[3])}]"
                    explored = "" if elem.explored else ""
                    lines.append(f"| {i} | {elem.element_type.value} | {elem.label} | {bbox_str} | {elem.confidence:.2f} | {explored} |")
            else:
                lines.append("*(No interactive elements found)*")
            lines.append("")

        return "\n".join(lines)

    def _render_tree_markdown(self, lines: List[str], node: Optional[PageNode],
                               prefix: str, is_last: bool) -> None:
        if not node:
            return
        connector = "  " if is_last else "| "
        line_prefix = prefix + connector
        icon = node.icon_name
        elem_count = len(node.elements)
        lines.append(f"{line_prefix}{icon} {node.name} [{elem_count} elements, depth={node.depth}]")

        edges = self._page_tree.get_edges_from(node.page_id)
        for i, edge in enumerate(edges):
            child = self._page_tree.get_node(edge.to_page_id)
            child_is_last = (i == len(edges) - 1)
            child_prefix = prefix + ("   " if is_last else "|  ")
            elem = next((e for e in node.elements if e.element_id == edge.element_id), None)
            elem_label = elem.label if elem else edge.element_id
            lines.append(f"{child_prefix}|- [{edge.action_type}] {elem_label}")
            self._render_tree_markdown(lines, child, child_prefix, child_is_last)
