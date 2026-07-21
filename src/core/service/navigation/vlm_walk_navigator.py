"""VlmWalkNavigator - VLM-driven walk controller for open-world navigation.

Replaces MaaEnd's blind-walk (ZONE + hard-coded waypoints) with an LLM/VLM
loop: screenshot -> VLM decides action -> execute -> screenshot again, until
target is reached or the loop times out.

Action space exposed to the VLM:
  - forward(<seconds>)  — move forward for <seconds> (1-5)
  - left(<seconds>)     — strafe left
  - right(<seconds>)    — strafe right
  - backward(<seconds>) — move back
  - turn_left          — rotate camera ~45° left
  - turn_right         — rotate camera ~45° right
  - interact           — press interact key (F)
  - stop               — stop movement, wait
  - arrived            — signal that target is reached

Dependencies:
  - LlmClient (OpenAI-compatible, image support)
  - MapPosition / MinimapLocator for location verification
  - MaaEndRuntime for zone switching / teleport
  - ADB / touch / keyboard for input
"""

from __future__ import annotations

import base64
import json
import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from core.capability.llm import LlmClient
from core.foundation.logger import get_logger

from .map_data_loader import MapDataLoader
from .minimap_locator import MapPosition, MinimapLocator


@dataclass
class VlmWalkConfig:
    """Configuration for VLM walking behaviour."""
    max_steps: int = 40               # max VLM decision steps
    target_radius: float = 12.0       # distance tolerance to consider "arrived"
    step_timeout_s: float = 30.0      # max real time per step
    vlm_temperature: float = 0.2
    vlm_max_tokens: int = 128
    # 单次 VLM 推理首 token 超时（秒）= 2min = 120s。
    # 流式传输模式下，socket timeout 仅保护首 token 等待；首 token 到达后
    # 后续流式输出不限每块超时。此值也传递给线程 join timeout 作为首 token
    # 等待的上限。
    # 实测：云端 qwen3.5-35b 正常响应 1-5s/步，慢时 30-77s。
    # 原 1800s（30min）过保守，transient 失败时单步可挂 30min×3retry=90min。
    # 改为 120s 后：单步最长 120s×1=120s（timeout 不重试），3 次连续 timeout
    # 中止 walk（max_consecutive_vlm_timeouts=3），总 worst case 6min/route。
    vlm_call_timeout_s: float = 120.0
    # VLM 输入图像缩放比例（0-1）。缩小图像可显著加速云端 API 响应。
    # 0.5 = 640x360（原图 1280x720 的一半），实测可减少 30-50% 响应时间。
    image_scale: float = 0.5
    stuck_threshold: int = 4          # consecutive no-movement steps before fallback
    fallback_to_navmesh: bool = True
    turn_key_duration_ms: int = 200   # ms for a camera turn tap
    move_key_duration_s: float = 1.5  # default duration for a movement key press
    # FAST-FAIL-ON-TIMEOUT: 连续 N 次 VLM 超时直接中止当前 walk 循环，
    # 避免云端 API 不稳定时浪费 60*90s = 90min 等待。
    # 实测：API 高峰期 60 步内有 3-5 次 90s 超时，浪费 4.5-7.5min/轮。
    # 设为 0 关闭此机制。
    max_consecutive_vlm_timeouts: int = 3


_DEFAULT_SYSTEM_PROMPT = """\
You are controlling a character in a 3D open-world game.
You receive a screenshot of the game screen and the following context:

Current Info:
- Current Position: (map_id, level_id, tile, confidence)
- Target Position: (x, y)
- Last Action: <what you did last step>
- Step Count: <current step>

You must respond with a JSON object containing exactly one action.
Available actions:
{"action": "forward", "duration": 1.5}  — walk forward (1-5 seconds)
{"action": "left", "duration": 1.5}     — strafe left
{"action": "right", "duration": 1.5}    — strafe right
{"action": "backward", "duration": 1.5} — walk back
{"action": "turn_left"}                  — rotate camera ~45° left
{"action": "turn_right"}                — rotate camera ~45° right
{"action": "interact"}                  — press interact key (F)
{"action": "stop"}                       — stop and observe
{"action": "arrived"}                    — I have reached the target

Rules:
- Look at the screenshot. Orient toward the target.
- Use short movements (1-2s) and look at the minimap to see progress.
- If you see obstacles/a cliff/danger, adjust course.
- Only use "arrived" if clearly at the destination.
- Output ONLY the JSON, no extra text.

Example output:
{"action": "forward", "duration": 1.5}\
"""

# 任务追踪标识驱动导航的系统提示。
# 与坐标驱动不同：VLM 通过识别屏幕上的任务追踪标识（箭头/路径/小地图标记/
# 目标光柱）自主决定方向，不需要精确目标坐标。这正是用户需求的"依据任务
# 追踪标识（VLM识别方向并控制前进）到达指定地点"。
_TRACKING_SYSTEM_PROMPT = """\
You are controlling a character in a 3D open-world game on a mobile device.
You receive a screenshot of the game screen (1280x720 landscape).

Your goal: follow the on-screen quest tracking marker to reach the destination.

CRITICAL — COLORED QUEST FOCUS MARKERS:
The 3D viewport has COLORED focus/target markers corresponding to task importance:
- 紧急 (URGENT) tasks: RED/ORANGE markers — bright colored dots, diamonds, or crosshairs
- 重要 (IMPORTANT) tasks: YELLOW markers
- 次要 (NORMAL) tasks: BLUE/CYAN markers — dimmer colored dots or arrows
These markers float in the 3D world at the destination point. They may appear:
- As a colored dot/diamond hovering in the air at medium distance
- As a colored marker at the EDGE of your screen pointing toward the target
- As a colored pillar/beam of light rising from the ground at the destination
- As a colored crosshair or target reticle

IF you see a colored marker matching the description ABOVE → it IS your target.
Walk toward it. If it's at the edge of your screen, turn to center it, then walk forward.
The color tells you the task category, and its presence means you are tracking the right quest.

KEY NAVIGATION RULE (CRITICAL - read carefully):
The minimap is in the TOP-LEFT corner of the screen. The quest tracking arrow
on the minimap shows which direction to go RELATIVE TO WHERE THE CAMERA IS FACING.

- If the arrow points UP on the minimap → walk FORWARD (target is ahead)
- If the arrow points UP-LEFT or LEFT → turn camera LEFT until arrow points UP, then walk forward
- If the arrow points UP-RIGHT or RIGHT → turn camera RIGHT until arrow points UP, then walk forward
- If the arrow points DOWN → turn around (turn left or right twice) until arrow points UP
- ALWAYS check the minimap arrow direction BEFORE choosing your action
- The goal is to make the minimap arrow point UP, then walk FORWARD

DISTANCE INDICATOR:
- The quest tracking panel (top of screen, near the minimap) often shows a distance
  like "434 m" or "90 m" to the destination.
- If you see a distance > 100 m → you are FAR away, walk forward for LONGER
  (2-3 seconds per step) to cover more ground. Minimize turning.
- If you see a distance 30-100 m → you are getting close, use normal 1.5s steps.
- If you see a distance < 30 m → SLOW DOWN, look for the NPC and interact button.
- If NO distance is visible → you are FAR away (the panel hides distance when
  you are very far). Walk forward for LONGER (2-3 seconds). Do NOT report arrived.

ARRIVED CRITERIA (VERY STRICT - read carefully):
You may ONLY respond with "arrived" if AT LEAST ONE of these is true:
1. There is an on-screen INTERACT BUTTON visible (a circular button with text
   like "交谈"/"拾取"/"互动"/"F" on the right side of the screen, typically
   around x=1000-1200, y=300-500). This button ONLY appears when the character
   is within touching distance of an interactable.
2. An NPC is visible at VERY CLOSE range (the NPC is large, fills significant
   portion of the screen, you can virtually touch them — not a distant figure).

DO NOT report "arrived" if:
- You only see a distant NPC (small figure far away)
- You only see a landmark, crystal, building, or structure
- You only see a quest marker/arrow on the minimap
- You only see a glowing path/beam in the distance
- You have not walked forward at least 5 times in this navigation session
- No distance indicator AND no interact button visible

When in doubt, DO NOT report arrived. Continue navigating instead.

You must respond with a JSON object containing exactly one action.
Available actions:
{"action": "forward", "duration": 2.5}  — walk forward (use 2.5-3.0s when far away, 1.5s when close)
{"action": "left", "duration": 1.5}     — strafe left
{"action": "right", "duration": 1.5}    — strafe right
{"action": "backward", "duration": 1.5} — walk back
{"action": "turn_left"}                  — rotate camera ~45° left
{"action": "turn_right"}                — rotate camera ~45° right
{"action": "interact"}                  — press interact key (F)
{"action": "stop"}                       — stop and observe
{"action": "arrived"}                    — I have reached the destination (STRICT — see criteria above)

Rules:
- FIRST look for colored focus markers in the 3D viewport — they ARE your destination.
- If you see a colored marker at screen edge, turn toward it.
- If you see a colored marker ahead, walk toward it.
- If NO colored marker is visible, check the minimap arrow for direction.
- Use short movements (1-2s) and re-check visually each step.
- If you see obstacles/a cliff/danger, adjust course.
- If you cannot see any marker or arrow, turn to search for it.
- Output ONLY the JSON, no extra text.

Example — colored BLUE or CYAN marker visible ahead (次要 task focus):
{"action": "forward", "duration": 2.5}

Example — colored marker visible to the LEFT edge of screen:
{"action": "turn_left"}

Example — minimap arrow points UP (target ahead):
{"action": "forward", "duration": 1.5}

Example — minimap arrow points LEFT (target to the left):
{"action": "turn_left"}

Example — you see an interact button "交谈" on screen at close range:
{"action": "arrived"}

CRITICAL: Look for colored 3D viewport markers FIRST. Turn toward them and walk.
CRITICAL: Do NOT report arrived unless you see an interact button OR an NPC at touching distance!
"""

# 采集任务专用系统提示：把路线坐标(waypoints)与采集物名称(collect_items)
# 作为上下文提供给 VLM，由 VLM 综合截图+小地图+路线信息+标志物名称自主
# 决定导航动作。关键：VLM 不死板按坐标走，而是用坐标作参考，主要靠视角
# 平视环绕 360 度找资源点指引标识（光柱/箭头/采集物名称飘字）进行赶路。
# 这是用户要求的"在地图内追踪资源点后视角平视环绕360度找到指引标识进行
# 赶路而不是依赖固定行动"。
_COLLECT_SYSTEM_PROMPT = """\
You are controlling a character in a 3D open-world game to collect resources.

Your task: navigate to collection points and collect the specified resources.

IMPORTANT NAVIGATION STRATEGY (do NOT blindly follow coordinates):
- The Waypoints are REFERENCE ONLY — they show the general direction and area.
- Your PRIMARY navigation method is VISUAL: look around the screen for resource
  point indicators (quest markers, glowing beams, floating arrows, resource node
  labels, minimap directional markers).
- At each step: TURN THE CAMERA to look around (horizontally, level/pitch view)
  in a full 360° sweep if needed, searching for visual indicators of resource
  points. Do NOT just walk forward based on coordinates alone.
- When you see a resource point indicator (glowing beam, arrow, marker, or the
  collect item's name floating above a node), walk toward it.
- Use the minimap to confirm the rough direction, then use the main screen view
  to actually navigate by following the visual indicator.
- The final waypoints are near collection points — when close, SLOW DOWN and
  look around carefully (turn left/right repeatedly) to find the resource node.

COLLECTION PROCESS:
- At a collection point, look for a resource node on screen. The node often
  shows a text label matching one of the Collect Items names
  (e.g. "映火荞花", "萤壳虫", "灼壳虫").
- When you see a collectible resource node on screen, use "interact" to press F.
- After interacting, if you see floating "获得" text or a collection
  confirmation, use "arrived" to signal success.
- If the first interact does not collect (no "获得" text), turn to find another
  resource node and try again.

CONTEXT YOU RECEIVE:
- Current Position: your coordinates on the minimap (rough reference)
- Map: the minimap identifier
- Waypoints: ordered list of (x, y) reference coordinates
- Next Target: the next reference waypoint (general direction only)
- Collect Items: names of resources to look for and collect (landmarks)
- Last Action: what you did last step
- Step Count: current step / total steps

Available actions (output ONLY a single JSON object):
{"action": "forward", "duration": 1.5}  — walk forward (1-5 seconds)
{"action": "left", "duration": 1.5}     — strafe left
{"action": "right", "duration": 1.5}    — strafe right
{"action": "backward", "duration": 1.5} — walk back
{"action": "turn_left"}                  — rotate camera ~45° left (use this to look around)
{"action": "turn_right"}                — rotate camera ~45° right (use this to look around)
{"action": "interact"}                  — press F to collect/interact
{"action": "stop"}                       — stop and observe
{"action": "arrived"}                    — collection done

Rules:
- Prefer VISUAL navigation over coordinate following.
- When unsure of direction, use turn_left/turn_right to look around 360°.
- Use short movements (1-2s) and re-check the view each step.
- Output ONLY the JSON, no extra text.

Example — at start, look around to find the indicator:
{"action": "turn_right"}

Example — saw a glowing beam/arrow toward the target:
{"action": "forward", "duration": 1.5}

Example — at collection point, see resource node with item name:
{"action": "interact"}

Example — collection confirmed (saw "获得" text):
{"action": "arrived"}\
"""


class VlmWalkNavigator:
    """VLM-driven walking controller for the open world."""

    _llm: LlmClient
    _screenshot_fn: Callable[[], Optional[bytes]]
    _input_fn: Callable[[str, Optional[float]], None]
    _locator: MinimapLocator
    _data: MapDataLoader
    _config: VlmWalkConfig
    _system_prompt: str
    # OCR 验证函数：接收 PNG bytes，返回 OCR 标签列表（list[str]）。
    # 用于 arrived 状态的服务端硬验证——VLM 经常误报 arrived（如 qwen3.5-35b
    # 在 forward 60 次后即使没看到交互按钮也会报 arrived），必须用 OCR 检查
    # 屏幕上是否真有交互关键词（交谈/拾取/互动/F）。
    _ocr_fn: Optional[Callable[[bytes], List[str]]]

    # 交互关键词：屏幕上出现这些文字说明角色确实在 NPC/采集物面前。
    # "F" 是手机端的交互按钮文字（与 PC 端 F 键对应）。
    _INTERACT_KEYWORDS: tuple = ("交谈", "拾取", "互动", "F")

    def __init__(
        self,
        llm_client: LlmClient,
        screenshot_fn: Callable[[], Optional[bytes]],
        input_fn: Callable[[str, Optional[float]], None],
        locator: MinimapLocator,
        data_loader: MapDataLoader,
        config: Optional[VlmWalkConfig] = None,
        system_prompt: Optional[str] = None,
        ocr_fn: Optional[Callable[[bytes], List[str]]] = None,
    ):
        self._llm = llm_client
        self._screenshot_fn = screenshot_fn
        self._input_fn = input_fn
        self._locator = locator
        self._data = data_loader
        self._config = config or VlmWalkConfig()
        self._system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        self._ocr_fn = ocr_fn
        self._logger = get_logger(__name__)
        self._last_positions: deque[Tuple[float, float]] = deque(maxlen=self._config.stuck_threshold)

    def _verify_arrived_by_ocr(self, frame_bytes: bytes) -> bool:
        """OCR 验证屏幕上是否有交互关键词。

        Args:
            frame_bytes: PNG/JPG 原始字节（来自 screenshot_fn）。

        Returns:
            True 如果检测到交互关键词（角色确实在 NPC/采集物面前）；
            False 如果未检测到（VLM 误报 arrived）。
            OCR 不可用或异常时返回 True（不阻塞流程，向后兼容）。
        """
        if self._ocr_fn is None:
            return True  # 未提供 OCR 函数，跳过验证
        if not frame_bytes:
            return True
        try:
            labels = self._ocr_fn(frame_bytes)
        except Exception as exc:
            self._logger.warning(
                "OCR arrival verification failed: %s (accepting arrived)", exc,
            )
            return True
        if not labels:
            return False
        # 检查是否包含任一交互关键词。
        # 中文关键词（交谈/拾取/互动）用 substring 匹配（OCR 可能带额外字符）；
        # "F" 必须精确匹配整个 label（避免匹配 "Factory"/"SceneManager/..." 等）。
        for label in labels:
            label_str = str(label).strip()
            for kw in ("交谈", "拾取", "互动"):
                if kw in label_str:
                    return True
            # "F" 精确匹配（手机端交互按钮文字就是单字母 F）
            if label_str == "F":
                return True
        return False

    def _grab_frame_bytes(self) -> Optional[bytes]:
        """获取截图原始字节（带 15s 超时保护），用于 OCR 验证。"""
        import threading as _threading

        result_box: Dict[str, Any] = {"data": None, "error": None}

        def _do_shot() -> None:
            try:
                result_box["data"] = self._screenshot_fn()
            except Exception as exc:  # noqa: BLE001
                result_box["error"] = exc

        t = _threading.Thread(target=_do_shot, daemon=True, name="grab-frame-bytes")
        t.start()
        t.join(timeout=15.0)
        if t.is_alive():
            self._logger.warning("grab_frame_bytes 超时 15s")
            return None
        if result_box["error"] is not None:
            self._logger.warning("grab_frame_bytes failed: %s", result_box["error"])
            return None
        return result_box["data"]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def walk_to(
        self,
        map_name: str,
        target_x: float,
        target_y: float,
        level_id: Optional[str] = None,
        max_steps: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Walk from current position to target using VLM control.

        Args:
            map_name: e.g. "map01", "map02"
            target_x, target_y: target map coordinates
            level_id: target level (optional, auto-detect if omitted)
            max_steps: override max VLM steps

        Returns:
            result dict with status, steps taken, final distance, actions
        """
        steps = max_steps or self._config.max_steps
        self._last_positions.clear()
        history: List[Dict[str, Any]] = []
        # FAST-FAIL-ON-TIMEOUT: 连续 vlm_timeout 计数器
        consecutive_timeouts = 0
        max_consecutive = self._config.max_consecutive_vlm_timeouts

        # Watchdog: abort the whole loop if cumulative real time overshoots.
        loop_deadline = time.monotonic() + (self._config.step_timeout_s * max(steps, 1))

        # Wait for a fresh frame before starting
        frame = self._grab_frame()
        if frame is None:
            return {"status": "error", "message": "no screenshot available"}

        current_pos = self._locator.locate(frame)

        for step_idx in range(steps):
            # Per-step watchdog: bail out if a single step runs too long.
            step_start = time.monotonic()
            if step_start > loop_deadline:
                self._logger.warning("walk_to exceeded total budget, aborting at step %d", step_idx)
                break

            # Grab latest screenshot and locate
            frame = self._grab_frame()
            if frame is None:
                history.append({"step": step_idx, "action": "error", "detail": "screenshot_failed"})
                break

            current_pos = self._locator.locate(frame)
            if current_pos is None:
                self._logger.warning("cannot locate position at step %d", step_idx)
                # Still send frame — VLM may orient without minimap
                current_context = MapPosition(
                    map_id=map_name, level_id=level_id or "unknown",
                    tile_class="unknown", grid_cell=None,
                    center_x=0, center_y=0,
                    confidence=0.0, raw_class_id=-1,
                )
            else:
                current_context = current_pos

            # Compute distance to target
            dx = target_x - current_context.center_x
            dy = target_y - current_context.center_y
            dist = (dx * dx + dy * dy) ** 0.5

            # Check if arrived
            if dist <= self._config.target_radius:
                self._logger.info("arrived: dist=%.1f <= %.1f", dist, self._config.target_radius)
                history.append({"step": step_idx, "action": "arrived", "distance": round(dist, 1)})
                break

            # Check for stuck condition (position not changing)
            if self._is_stuck(current_context.center_x, current_context.center_y, dist):
                self._logger.warning("stuck detected at step %d, initiating fallback", step_idx)
                if self._config.fallback_to_navmesh:
                    history.append({"step": step_idx, "action": "stuck_fallback_navmesh"})
                    # Return early — caller should retry via navmesh
                    break
                history.append({"step": step_idx, "action": "stuck_continue"})

            # Encode frame to base64 for VLM
            img_b64 = self._frame_to_base64(frame)

            # Build context block
            last_action = history[-1]["action"] if history else "none"
            context = (
                f"Current Position: ({current_context.map_id}, {current_context.level_id}, "
                f"{current_context.tile_class}, conf={current_context.confidence:.2f})\n"
                f"Target Position: ({target_x:.1f}, {target_y:.1f})  distance={dist:.1f}\n"
                f"Last Action: {last_action}\n"
                f"Step Count: {step_idx + 1}"
            )

            # Query VLM — 使用异步调用 + 步级超时，单步推理卡死不会拖垮整条
            # 导航循环，也不会阻塞调用方线程（GUI 预览/任务线程继续运转）。
            self._logger.info(
                "VLM step %d/%d: dist=%.1f pos=(%.1f,%.1f) target=(%.1f,%.1f)",
                step_idx + 1, steps, dist,
                current_context.center_x, current_context.center_y,
                target_x, target_y,
            )
            try:
                handle = self._llm.chat_async(
                    prompt=f"Look at the screenshot and decide the next action.\n\n{context}\n\nRespond with ONLY the JSON action, nothing else.",
                    system=self._system_prompt,
                    temperature=self._config.vlm_temperature,
                    max_tokens=self._config.vlm_max_tokens,
                    image=img_b64,
                    image_mime_type="image/jpeg",
                    timeout=self._config.vlm_call_timeout_s,
                    # Qwen3 thinking 模式默认开启，会返回自然语言推理而非 JSON。
                    # 通过 chat_template_kwargs.enable_thinking=False 在请求粒度关闭
                    # thinking，让模型直接输出 JSON 动作。这是 VLM 步进循环可解析
                    # 的关键依赖——/no_think 指令对小模型不可靠。
                    chat_template_kwargs={"enable_thinking": False},
                )
                reply = handle.result_or(
                    default="",
                    timeout=self._config.vlm_call_timeout_s,
                )
            except Exception as exc:
                self._logger.error("VLM call failed at step %d: %s", step_idx, exc)
                history.append({"step": step_idx, "action": "vlm_error", "detail": str(exc)})
                consecutive_timeouts += 1
                if max_consecutive > 0 and consecutive_timeouts >= max_consecutive:
                    self._logger.warning(
                        "VLM walk 连续 %d 次超时/错误，中止 walk_to（API 不稳定）",
                        consecutive_timeouts,
                    )
                    history.append({"step": step_idx, "action": "abort_consecutive_timeouts",
                                    "count": consecutive_timeouts})
                    break
                continue

            if not reply:
                self._logger.warning("VLM step %d returned empty/timed out, skipping", step_idx)
                history.append({"step": step_idx, "action": "vlm_timeout"})
                consecutive_timeouts += 1
                if max_consecutive > 0 and consecutive_timeouts >= max_consecutive:
                    self._logger.warning(
                        "VLM walk 连续 %d 次超时，中止 walk_to（API 不稳定）",
                        consecutive_timeouts,
                    )
                    history.append({"step": step_idx, "action": "abort_consecutive_timeouts",
                                    "count": consecutive_timeouts})
                    break
                continue

            # 收到有效回复，重置计数器
            consecutive_timeouts = 0

            # Parse VLM response
            action = self._parse_action(reply)
            if action is None:
                self._logger.warning("unparseable VLM reply at step %d: %s", step_idx, reply[:200])
                history.append({"step": step_idx, "action": "parse_error", "raw": reply[:120]})
                continue

            if action["action"] == "arrived":
                history.append({"step": step_idx, "action": "arrived", "distance": round(dist, 1)})
                break

            # Execute the action
            self._execute_action(action)
            history.append({**action, "step": step_idx})

            # Brief settle delay for the game to update minimap
            time.sleep(0.3)

            # Step-timing warning (soft watchdog — informs rather than aborts).
            step_elapsed = time.monotonic() - step_start
            if step_elapsed > self._config.step_timeout_s:
                self._logger.warning(
                    "step %d took %.1fs (> step_timeout_s %.1fs)",
                    step_idx, step_elapsed, self._config.step_timeout_s,
                )

        final_pos = self._grab_frame()
        final_dist = float('inf')
        if final_pos is not None:
            p = self._locator.locate(final_pos)
            if p:
                dx = target_x - p.center_x
                dy = target_y - p.center_y
                final_dist = (dx * dx + dy * dy) ** 0.5

        arrived = final_dist <= self._config.target_radius * 1.5
        return {
            "status": "success" if arrived else "partial",
            "action": "vlm_walk",
            "steps_taken": len([h for h in history if "step" in h]),
            "total_decisions": step_idx + 1,
            "final_distance": round(final_dist, 1),
            "target_x": target_x,
            "target_y": target_y,
            "history": history[-15:],  # last 15 actions for review
        }

    def walk_to_tracking(
        self,
        max_steps: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Walk toward the destination by following on-screen quest tracking markers.

        Unlike ``walk_to``, this does NOT require a target coordinate — the VLM
        reads the in-game quest tracking indicator (arrows / path trail / minimap
        marker / destination beam) and decides movement direction autonomously.
        This is the key difference from MaaEnd's coordinate-driven blind-walk:
        the VLM "识别方向并控制前进" based on visual tracking markers.

        Args:
            max_steps: override max VLM decision steps

        Returns:
            result dict with status, steps taken, actions history
        """
        steps = max_steps or self._config.max_steps
        self._last_positions.clear()
        history: List[Dict[str, Any]] = []
        step_idx = -1
        # FAST-FAIL-ON-TIMEOUT: 连续 vlm_timeout 计数器
        consecutive_timeouts = 0
        max_consecutive = self._config.max_consecutive_vlm_timeouts

        loop_deadline = time.monotonic() + (self._config.step_timeout_s * max(steps, 1))

        frame = self._grab_frame()
        if frame is None:
            return {"status": "error", "message": "no screenshot available"}

        # 360° 预扫描阶段：每 60° 旋转一次，帮助 VLM 找到场景中的彩色标记。
        # VLM 经常因初始视角看不到追踪标记而出 no_action → rewalk 循环。
        # 通过预旋转让 VLM 观察不同角度，提高发现焦点标记的概率。
        self._logger.info("VLM tracking 360° pre-scan: rotating camera to find colored markers")
        for scan_i in range(6):
            # 旋转约 60°（_input_fn=_vlm_keyevent 期望 KEYCODE_* 名，而非 action 名）
            self._input_fn("KEYCODE_Q", None)
            time.sleep(0.3)
            self._input_fn("KEYCODE_Q", None)
            time.sleep(0.2)
            scan_frame = self._grab_frame()
            if scan_frame is None:
                continue
            # 用 VLM 快速检查是否看到标记——只做 1 步判断
            scan_b64 = self._frame_to_base64(scan_frame)
            scan_handle = self._llm.chat_async(
                prompt=(
                    "Look at this screenshot carefully. Do you see a colored "
                    "focus/quest marker (colored dot, diamond, crosshair, beam) "
                    "in the 3D viewport? If YES, respond with the direction "
                    "(center/left/right/up/down). If NO, respond with 'none'.\n"
                    "Respond with ONLY one word."
                ),
                system="",
                image=scan_b64,
                image_mime_type="image/jpeg",
                max_tokens=10,
                temperature=0.1,
                timeout=10.0,
            )
            scan_reply = scan_handle.result_or(default="none", timeout=12.0)
            self._logger.info("VLM tracking 360° pre-scan step %d: %s", scan_i, scan_reply.strip() if scan_reply else "none")
            history.append({"step": f"scan_{scan_i}", "action": "scan", "reply": (scan_reply or "none").strip()})
        self._logger.info("VLM tracking 360° pre-scan done")

        for step_idx in range(steps):
            step_start = time.monotonic()
            if step_start > loop_deadline:
                self._logger.warning("walk_to_tracking exceeded total budget, aborting at step %d", step_idx)
                break

            frame = self._grab_frame()
            if frame is None:
                history.append({"step": step_idx, "action": "error", "detail": "screenshot_failed"})
                break

            # 辅助定位（可选）：用于 stuck 检测，不依赖精确坐标
            current_pos = self._locator.locate(frame)
            pos_info = ""
            if current_pos:
                cx, cy = current_pos.center_x, current_pos.center_y
                pos_info = (
                    f"Current Position: ({cx:.1f}, {cy:.1f}) on {current_pos.map_id}\n"
                )
                if self._is_stuck(cx, cy):
                    self._logger.warning("stuck detected (tracking) at step %d", step_idx)
                    pos_info += (
                        "WARNING: You appear to be stuck. Try turning to find "
                        "the quest marker.\n"
                    )
            else:
                # locator 不可用时清空历史避免误判 stuck
                self._last_positions.clear()

            img_b64 = self._frame_to_base64(frame)
            last_action = history[-1]["action"] if history else "none"
            context = (
                f"{pos_info}"
                f"Last Action: {last_action}\n"
                f"Step Count: {step_idx + 1}/{steps}\n"
                f"Follow the quest tracking marker to reach the destination."
            )

            self._logger.info("VLM tracking step %d/%d", step_idx + 1, steps)
            try:
                handle = self._llm.chat_async(
                    prompt=(
                        "Look at the screenshot. Find the quest tracking marker "
                        "and decide the next action.\n\n" + context
                        + "\n\nRespond with ONLY the JSON action, nothing else."
                    ),
                    system=_TRACKING_SYSTEM_PROMPT,
                    temperature=self._config.vlm_temperature,
                    max_tokens=self._config.vlm_max_tokens,
                    image=img_b64,
                    image_mime_type="image/jpeg",
                    timeout=self._config.vlm_call_timeout_s,
                    # Qwen3 thinking 模式默认开启，会返回自然语言推理而非 JSON。
                    # 通过 chat_template_kwargs.enable_thinking=False 在请求粒度关闭
                    # thinking，让模型直接输出 JSON 动作。这是 VLM 步进循环可解析
                    # 的关键依赖——/no_think 指令对小模型不可靠。
                    chat_template_kwargs={"enable_thinking": False},
                )
                reply = handle.result_or(
                    default="",
                    timeout=self._config.vlm_call_timeout_s,
                )
            except Exception as exc:
                self._logger.error("VLM tracking call failed at step %d: %s", step_idx, exc)
                history.append({"step": step_idx, "action": "vlm_error", "detail": str(exc)})
                consecutive_timeouts += 1
                if max_consecutive > 0 and consecutive_timeouts >= max_consecutive:
                    self._logger.warning(
                        "VLM tracking 连续 %d 次超时/错误，中止 walk_to_tracking（API 不稳定）",
                        consecutive_timeouts,
                    )
                    history.append({"step": step_idx, "action": "abort_consecutive_timeouts",
                                    "count": consecutive_timeouts})
                    break
                continue

            if not reply:
                self._logger.warning("VLM tracking step %d returned empty/timed out, skipping", step_idx)
                history.append({"step": step_idx, "action": "vlm_timeout"})
                consecutive_timeouts += 1
                if max_consecutive > 0 and consecutive_timeouts >= max_consecutive:
                    self._logger.warning(
                        "VLM tracking 连续 %d 次超时，中止 walk_to_tracking（API 不稳定）",
                        consecutive_timeouts,
                    )
                    history.append({"step": step_idx, "action": "abort_consecutive_timeouts",
                                    "count": consecutive_timeouts})
                    break
                continue

            # 收到有效回复，重置计数器
            consecutive_timeouts = 0

            action = self._parse_action(reply)
            if action is None:
                self._logger.warning("unparseable VLM tracking reply at step %d: %s", step_idx, reply[:200])
                history.append({"step": step_idx, "action": "parse_error", "raw": reply[:120]})
                continue

            if action["action"] == "arrived":
                # 服务端硬性约束：必须至少前进过 5 次才接受 arrived。
                # 这是为了防止 VLM 在没有真正到达 NPC 面前就误判 arrived。
                # 之前测试发现 VLM 经常在 step 1-7 就报 arrived，但角色实际
                # 还在远离 NPC 的位置，导致后续 press_f 无效。
                forward_count = sum(
                    1 for h in history if h.get("action") == "forward"
                )
                if forward_count < 5:
                    self._logger.warning(
                        "VLM tracking arrived at step %d but only %d forward steps "
                        "(need >= 5), rejecting arrived and forcing forward",
                        step_idx, forward_count,
                    )
                    # 强制改为 forward，让 VLM 继续靠近目标
                    action = {"action": "forward", "duration": 1.5}
                else:
                    # OCR 硬验证：VLM（尤其 qwen3.5-35b free）经常在 forward
                    # 60 次后即使没看到交互按钮也报 arrived。必须用 OCR 检查
                    # 屏幕上是否真有交互关键词（交谈/拾取/互动/F），否则拒绝
                    # arrived 强制继续行走。最多拒绝 3 次，超过则接受 arrived
                    # （可能 OCR 漏检或交互按钮用其他文字）。
                    arrived_reject_count = sum(
                        1 for h in history
                        if h.get("action") == "arrived_rejected_by_ocr"
                    )
                    if self._ocr_fn is not None and arrived_reject_count < 3:
                        # 取当前帧进行 OCR 验证（用 bytes 而非 ndarray）
                        verify_bytes = self._grab_frame_bytes()
                        if verify_bytes is not None:
                            verified = self._verify_arrived_by_ocr(verify_bytes)
                            if not verified:
                                self._logger.warning(
                                    "VLM tracking arrived at step %d (forward=%d) "
                                    "REJECTED by OCR (no interact keywords). "
                                    "Forcing forward.",
                                    step_idx, forward_count,
                                )
                                history.append({
                                    "step": step_idx,
                                    "action": "arrived_rejected_by_ocr",
                                    "forward_count": forward_count,
                                })
                                # 强制改为 forward，让 VLM 继续靠近目标
                                action = {"action": "forward", "duration": 1.5}
                            else:
                                self._logger.info(
                                    "VLM tracking arrived at step %d (forward=%d) "
                                    "VERIFIED by OCR (interact keywords found)",
                                    step_idx, forward_count,
                                )
                                history.append({"step": step_idx, "action": "arrived"})
                                break
                        else:
                            # 截图失败，无法验证，接受 arrived（向后兼容）
                            history.append({"step": step_idx, "action": "arrived"})
                            self._logger.info(
                                "VLM tracking arrived at step %d (forward_count=%d, "
                                "OCR verify skipped: no frame bytes)",
                                step_idx, forward_count,
                            )
                            break
                    else:
                        # OCR 不可用或已拒绝 3 次，接受 arrived
                        history.append({"step": step_idx, "action": "arrived"})
                        if arrived_reject_count >= 3:
                            self._logger.info(
                                "VLM tracking arrived at step %d (forward=%d) "
                                "accepted after %d OCR rejections (limit reached)",
                                step_idx, forward_count, arrived_reject_count,
                            )
                        else:
                            self._logger.info(
                                "VLM tracking arrived at step %d (forward_count=%d, "
                                "OCR not available)",
                                step_idx, forward_count,
                            )
                        break

            self._execute_action(action)
            history.append({**action, "step": step_idx})
            time.sleep(0.3)

            step_elapsed = time.monotonic() - step_start
            if step_elapsed > self._config.step_timeout_s:
                self._logger.warning(
                    "tracking step %d took %.1fs (> step_timeout_s %.1fs)",
                    step_idx, step_elapsed, self._config.step_timeout_s,
                )

        arrived = any(h.get("action") == "arrived" for h in history)
        return {
            "status": "success" if arrived else "partial",
            "action": "vlm_walk_tracking",
            "steps_taken": len([h for h in history if "step" in h]),
            "total_decisions": max(0, step_idx + 1),
            "history": history[-15:],
        }

    def walk_to_collect(
        self,
        waypoints: List[Tuple[float, float]],
        collect_items: List[str],
        map_name: str = "",
        max_steps: Optional[int] = None,
    ) -> Dict[str, Any]:
        """VLM 携带路线+标志物自主导航到采集点并采集指定资源。

        关键策略（用户要求）：
        - pipeline 只负责传送到传送点，地图内导航完全由 VLM 自主完成
        - VLM 不死板按坐标走，waypoints 仅作"大致方向参考"
        - 主要靠视角平视环绕 360 度找资源点指引标识（光柱/箭头/采集物名称飘字）
          进行赶路，找到后朝指引走
        - 到达采集物附近时识别屏幕上的采集物名称按 F 采集

        Args:
            waypoints: 路线坐标点列表（参考用，来自 MapTrackerMove 节点 path 字段）
            collect_items: 该路线对应的采集物名称列表（如 ["映火荞花"]），
                           作为 VLM 识别屏幕上采集物的"标志物"提示。
            map_name: 小地图 ID（如 ``map01_lv001``），用于 VLM 上下文。
            max_steps: 最大 VLM 决策步数。None 则使用 config.max_steps。

        Returns:
            result dict with status, steps taken, history
        """
        if not waypoints:
            return {"status": "error", "message": "no waypoints provided"}

        steps = max_steps or self._config.max_steps
        self._last_positions.clear()
        history: List[Dict[str, Any]] = []
        step_idx = -1
        # FAST-FAIL-ON-TIMEOUT: 连续 vlm_timeout 计数器
        consecutive_timeouts = 0
        max_consecutive = self._config.max_consecutive_vlm_timeouts

        # 起点坐标（第一个 waypoint）和终点坐标（最后一个 waypoint）作参考
        start_x, start_y = waypoints[0]
        end_x, end_y = waypoints[-1]

        loop_deadline = time.monotonic() + (self._config.step_timeout_s * max(steps, 1))

        # 把所有 waypoints + collect_items 预格式化为字符串
        wp_str = ", ".join(f"({x:.1f},{y:.1f})" for x, y in waypoints)
        items_str = "/".join(collect_items) if collect_items else "(unknown)"

        frame = self._grab_frame()
        if frame is None:
            return {"status": "error", "message": "no screenshot available"}

        for step_idx in range(steps):
            step_start = time.monotonic()
            if step_start > loop_deadline:
                self._logger.warning(
                    "walk_to_collect exceeded total budget, aborting at step %d",
                    step_idx,
                )
                break

            frame = self._grab_frame()
            if frame is None:
                history.append({"step": step_idx, "action": "error", "detail": "screenshot_failed"})
                break

            # 辅助定位：仅提供"当前位置+终点方向+距离"作为参考，
            # 不强制推进 waypoint 索引，VLM 自主决定如何导航
            current_pos = self._locator.locate(frame)
            pos_info = ""
            dist_to_end = float("inf")
            if current_pos:
                cx, cy = current_pos.center_x, current_pos.center_y
                dx = end_x - cx
                dy = end_y - cy
                dist_to_end = (dx * dx + dy * dy) ** 0.5
                # 起点距离（用于判断是否刚刚传送过来）
                dist_to_start = ((start_x - cx) ** 2 + (start_y - cy) ** 2) ** 0.5
                pos_info = (
                    f"Current Position: ({cx:.1f}, {cy:.1f}) on {current_pos.map_id}\n"
                    f"Start (teleport): ({start_x:.1f}, {start_y:.1f})  distance={dist_to_start:.1f}\n"
                    f"Final Target (collection area): ({end_x:.1f}, {end_y:.1f})  distance={dist_to_end:.1f}\n"
                )
                # stuck 检测
                if self._is_stuck(cx, cy, dist_to_end):
                    self._logger.warning("stuck detected at step %d", step_idx)
                    pos_info += (
                        "WARNING: You appear to be stuck. Turn around to find another path, "
                        "or look for a resource point indicator nearby.\n"
                    )
            else:
                # locator 不可用时清空历史避免误判 stuck
                self._last_positions.clear()
                pos_info = (
                    f"Current Position: unknown (minimap not locatable)\n"
                    f"Final Target (collection area): ({end_x:.1f}, {end_y:.1f})\n"
                )

            img_b64 = self._frame_to_base64(frame)
            last_action = history[-1]["action"] if history else "none"
            context = (
                f"{pos_info}"
                f"Map: {map_name}\n"
                f"Reference Waypoints (general path, NOT strict): {wp_str}\n"
                f"Collect Items (look for these on screen): {items_str}\n"
                f"Last Action: {last_action}\n"
                f"Step Count: {step_idx + 1}/{steps}\n"
                f"NAVIGATE BY VISUAL INDICATORS: turn the camera to look around 360° "
                f"for resource point indicators (glowing beams, arrows, markers, item name labels). "
                f"When you see an indicator, walk toward it. At the collection point, press F to collect. "
                f"Output ONLY the JSON action."
            )

            self._logger.info(
                "VLM collect step %d/%d: dist_to_end=%.1f items=%s last=%s",
                step_idx + 1, steps, dist_to_end, items_str, last_action,
            )
            try:
                handle = self._llm.chat_async(
                    prompt=(
                        "Look at the screenshot. Decide the next action to navigate "
                        "to the collection point and collect the resource.\n\n" + context
                    ),
                    system=_COLLECT_SYSTEM_PROMPT,
                    temperature=self._config.vlm_temperature,
                    max_tokens=self._config.vlm_max_tokens,
                    image=img_b64,
                    image_mime_type="image/jpeg",
                    timeout=self._config.vlm_call_timeout_s,
                    chat_template_kwargs={"enable_thinking": False},
                )
                reply = handle.result_or(
                    default="",
                    timeout=self._config.vlm_call_timeout_s,
                )
            except Exception as exc:
                self._logger.error("VLM collect call failed at step %d: %s", step_idx, exc)
                history.append({"step": step_idx, "action": "vlm_error", "detail": str(exc)})
                consecutive_timeouts += 1
                if max_consecutive > 0 and consecutive_timeouts >= max_consecutive:
                    self._logger.warning(
                        "VLM collect 连续 %d 次超时/错误，中止 walk_to_collect（API 不稳定）",
                        consecutive_timeouts,
                    )
                    history.append({"step": step_idx, "action": "abort_consecutive_timeouts",
                                    "count": consecutive_timeouts})
                    break
                continue

            if not reply:
                self._logger.warning("VLM collect step %d returned empty/timed out, skipping", step_idx)
                history.append({"step": step_idx, "action": "vlm_timeout"})
                consecutive_timeouts += 1
                if max_consecutive > 0 and consecutive_timeouts >= max_consecutive:
                    self._logger.warning(
                        "VLM collect 连续 %d 次超时，中止 walk_to_collect（API 不稳定）",
                        consecutive_timeouts,
                    )
                    history.append({"step": step_idx, "action": "abort_consecutive_timeouts",
                                    "count": consecutive_timeouts})
                    break
                continue

            # 收到有效回复，重置计数器
            consecutive_timeouts = 0

            action = self._parse_action(reply)
            if action is None:
                self._logger.warning("unparseable VLM collect reply at step %d: %s", step_idx, reply[:200])
                history.append({"step": step_idx, "action": "parse_error", "raw": reply[:120]})
                continue

            if action["action"] == "arrived":
                history.append({"step": step_idx, "action": "arrived"})
                self._logger.info("VLM collect arrived at step %d", step_idx)
                break

            self._execute_action(action)
            history.append({**action, "step": step_idx})
            time.sleep(0.3)

            step_elapsed = time.monotonic() - step_start
            if step_elapsed > self._config.step_timeout_s:
                self._logger.warning(
                    "collect step %d took %.1fs (> step_timeout_s %.1fs)",
                    step_idx, step_elapsed, self._config.step_timeout_s,
                )

        arrived = any(h.get("action") == "arrived" for h in history)
        return {
            "status": "success" if arrived else "partial",
            "action": "vlm_walk_collect",
            "steps_taken": len([h for h in history if "step" in h]),
            "total_decisions": max(0, step_idx + 1),
            "final_distance_to_target": round(dist_to_end, 1) if dist_to_end != float("inf") else None,
            "history": history[-15:],
        }

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

    # Semantic VLM action -> Android keycode name.
    # The AndroidRuntime daemon only accepts digit keycodes or known KEYCODE_*
    # constant names (see android_runtime._KNOWN_KEYEVENT_NAMES); raw letters
    # like "w" were previously rejected silently, breaking the whole walk loop.
    _ACTION_KEYCODE_MAP: Dict[str, str] = {
        "forward": "KEYCODE_W",
        "backward": "KEYCODE_S",
        "left": "KEYCODE_A",
        "right": "KEYCODE_D",
        "turn_left": "KEYCODE_Q",
        "turn_right": "KEYCODE_E",
        "interact": "KEYCODE_F",
    }

    def _execute_action(self, action: Dict[str, Any]) -> None:
        act = action["action"]
        keycode = self._ACTION_KEYCODE_MAP.get(act)
        if keycode is None:
            # "stop"/"arrived" (and any unknown action) => just settle
            if act == "stop":
                time.sleep(0.5)
            return

        # Clamp duration: the VLM may emit tens of seconds which would block the
        # loop; cap to a sane range. None => short tap (no hold).
        duration = action.get("duration")
        if duration is not None:
            try:
                duration = max(0.5, min(float(duration), 5.0))
            except (TypeError, ValueError):
                self._logger.warning("invalid duration %r for action %s, using tap", duration, act)
                duration = None

        self._input_fn(keycode, duration)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _grab_frame(self) -> Optional[np.ndarray]:
        # GRAB-FRAME-HARD-TIMEOUT: 截图调用必须有时限保护。
        # 即使底层 screenshot_fn 自身无超时（如 maaend.screenshot 旧版的 job.wait()），
        # 也通过线程+Event.wait() 强制 15s 上限，避免 VLM 循环因截图卡死而整个进程假死。
        import threading as _threading

        result_box: Dict[str, Any] = {"data": None, "error": None}

        def _do_shot() -> None:
            try:
                result_box["data"] = self._screenshot_fn()
            except Exception as exc:  # noqa: BLE001
                result_box["error"] = exc

        t = _threading.Thread(target=_do_shot, daemon=True, name="grab-frame")
        t.start()
        t.join(timeout=15.0)
        if t.is_alive():
            self._logger.warning("grab_frame 超时 15s，放弃本次截图")
            return None
        if result_box["error"] is not None:
            self._logger.warning("grab_frame failed: %s", result_box["error"])
            return None
        data = result_box["data"]
        if data is None:
            return None
        arr = np.frombuffer(data, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    def _frame_to_base64(self, frame: np.ndarray) -> str:
        # 缩小图像以加速云端 VLM API 响应（云端 qwen3.5-35b 图像请求
        # 耗时与图像大小正相关，640x360 实测比 1280x720 快 30-50%）。
        scale = float(getattr(self._config, "image_scale", 1.0))
        if scale < 1.0:
            h, w = frame.shape[:2]
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        # JPEG 编码比 PNG 小很多（~100KB vs ~1MB），进一步减少传输时间。
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return base64.b64encode(buf).decode("ascii")

    def _is_stuck(self, cx: float, cy: float, target_dist: float = 0.0) -> bool:
        self._last_positions.append((cx, cy))
        if len(self._last_positions) < self._config.stuck_threshold:
            return False
        # Check if all recent positions are within a tiny bounding box
        xs = [p[0] for p in self._last_positions]
        ys = [p[1] for p in self._last_positions]
        spread = (max(xs) - min(xs)) + (max(ys) - min(ys))
        # Relative threshold: scale with distance-to-target so coarse minimap
        # scales (far targets) are not falsely flagged as stuck.
        threshold = max(2.0, target_dist * 0.05)
        return spread < threshold

    def _parse_action(self, reply: str) -> Optional[Dict[str, Any]]:
        """Parse JSON action from VLM reply.

        Handles Qwen3 thinking mode (<think>...</think> blocks), markdown
        code fences, and natural language responses by extracting the first
        JSON object or falling back to keyword matching.
        """
        cleaned = reply.strip()

        # 1. Strip Qwen3 thinking blocks (</think> blocks), markdown
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()

        # 2. Strip markdown code fences
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first line (```json or ```) and last line (```)
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        # 3. Try direct JSON parse
        try:
            obj = json.loads(cleaned)
            if isinstance(obj, dict) and "action" in obj:
                return obj
        except json.JSONDecodeError:
            pass

        # 4. Extract first JSON object from text (find first { and last })
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_str = cleaned[first_brace:last_brace + 1]
            try:
                obj = json.loads(json_str)
                if isinstance(obj, dict) and "action" in obj:
                    return obj
            except json.JSONDecodeError:
                pass

        # 5. Keyword-based fallback: scan for action keywords in the reply.
        # 同时识别动作词（forward/turn left）和场景描述词（on the left/quest
        # marker ahead），覆盖小模型在 thinking 模式被关闭失败时返回自然语言
        # 描述的情况。顺序很重要：arrived/danger/interact 优先于方向词，避免
        # "I should turn left to reach the marker" 误判为 arrived。
        reply_lower = reply.lower()

        # 5a. 优先级最高：到达 / 交互 / 危险
        if any(kw in reply_lower for kw in (
            "arrived", "reached the", "at the destination", "at the target",
            "destination reached", "i am at", "i'm at", "have reached",
            "reached destination", "dungeon portal", "collection node",
        )):
            return {"action": "arrived"}
        if any(kw in reply_lower for kw in (
            "press f", "interact", "press the f", "press key f", "f key",
            "press f to", "use f to",
        )):
            return {"action": "interact"}
        if any(kw in reply_lower for kw in (
            "obstacle", "cliff", "danger", "wall ahead", "blocked",
            "cannot pass", "can't pass", "dead end", "dead-end",
        )):
            return {"action": "stop"}

        # 5b. 方向动作词（动作短语优先于单字匹配）
        direction_map = [
            (("turn left", "rotate left", "turn to the left", "rotate to the left",
              "camera left"), "turn_left"),
            (("turn right", "rotate right", "turn to the right", "rotate to the right",
              "camera right"), "turn_right"),
            (("move forward", "walk forward", "go forward", "move ahead",
              "walk ahead", "go ahead", "forward", "straight ahead",
              "ahead of", "in front"), "forward"),
            (("strafe left", "move left", "walk left", "go left"), "left"),
            (("strafe right", "move right", "walk right", "go right"), "right"),
            (("backward", "go back", "walk back", "move back", "back up"), "backward"),
        ]
        for keywords, action_name in direction_map:
            for kw in keywords:
                if kw in reply_lower:
                    result: Dict[str, Any] = {"action": action_name}
                    if action_name in ("forward", "left", "right", "backward"):
                        result["duration"] = 1.5
                    return result

        # 5c. 场景描述（VLM 描述了追踪标识相对位置但未明确动作词）
        # 例: "The quest marker is on the left of the screen"
        if any(kw in reply_lower for kw in (
            "on the left", "to the left", "on my left", "on your left",
            "left side of", "left of the screen", "left of screen",
            "marker is left", "marker is to the left",
        )):
            return {"action": "turn_left"}
        if any(kw in reply_lower for kw in (
            "on the right", "to the right", "on my right", "on your right",
            "right side of", "right of the screen", "right of screen",
            "marker is right", "marker is to the right",
        )):
            return {"action": "turn_right"}
        if any(kw in reply_lower for kw in (
            "quest marker", "tracking marker", "marker ahead",
            "marker is ahead", "marker in front", "marker visible",
            "follow the path", "follow the trail", "path ahead",
            "marker is visible",
        )):
            return {"action": "forward", "duration": 1.5}

        # 5d. 兜底：找不到具体方向时优先 forward（VLM 决策不应无所作为）
        if any(kw in reply_lower for kw in ("move", "walk", "go")):
            return {"action": "forward", "duration": 1.5}

        return None

    @property
    def config(self) -> VlmWalkConfig:
        return self._config

    @config.setter
    def config(self, cfg: VlmWalkConfig) -> None:
        self._config = cfg
