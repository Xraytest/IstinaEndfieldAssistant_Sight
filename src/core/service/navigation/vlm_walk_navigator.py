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
    # 单次 VLM 推理超时（秒）。超过即跳过该步并继续循环，避免单步卡死拖累
    # 整条导航——这正是"避免用户直接观感影响"的关键：界面/预览不会因某一步
    # 推理停滞而长时间无响应。
    vlm_call_timeout_s: float = 30.0
    stuck_threshold: int = 4          # consecutive no-movement steps before fallback
    fallback_to_navmesh: bool = True
    turn_key_duration_ms: int = 200   # ms for a camera turn tap
    move_key_duration_s: float = 1.5  # default duration for a movement key press


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
- Output ONLY the JSON, no extra text.\
"""

# 任务追踪标识驱动导航的系统提示。
# 与坐标驱动不同：VLM 通过识别屏幕上的任务追踪标识（箭头/路径/小地图标记/
# 目标光柱）自主决定方向，不需要精确目标坐标。这正是用户需求的"依据任务
# 追踪标识（VLM识别方向并控制前进）到达指定地点"。
_TRACKING_SYSTEM_PROMPT = """\
You are controlling a character in a 3D open-world game.
You receive a screenshot of the game screen.

Your goal: follow the on-screen quest tracking marker to reach the destination.

Quest tracking markers may appear as:
- A glowing path/trail on the ground leading to the destination
- An arrow/chevron icon pointing toward the destination
- A minimap marker (yellow/blue icon) showing destination direction
- A floating beam/pillar of light in the distance marking the target
- A highlighted area or entrance (dungeon portal, collection node)

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
{"action": "arrived"}                    — I have reached the destination (dungeon entrance, collection point, battle trigger, etc.)

Rules:
- Look at the screenshot. Find the quest tracking marker.
- Orient toward the marker and move forward.
- Use short movements (1-2s) and re-check the marker each step.
- If the marker leads through a narrow path, adjust course carefully.
- If you see the destination (dungeon portal, collection node, battle trigger), use "arrived".
- If you see obstacles/a cliff/danger, adjust course.
- If you cannot see the marker, turn to search for it.
- Output ONLY the JSON, no extra text.\
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

    def __init__(
        self,
        llm_client: LlmClient,
        screenshot_fn: Callable[[], Optional[bytes]],
        input_fn: Callable[[str, Optional[float]], None],
        locator: MinimapLocator,
        data_loader: MapDataLoader,
        config: Optional[VlmWalkConfig] = None,
        system_prompt: Optional[str] = None,
    ):
        self._llm = llm_client
        self._screenshot_fn = screenshot_fn
        self._input_fn = input_fn
        self._locator = locator
        self._data = data_loader
        self._config = config or VlmWalkConfig()
        self._system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        self._logger = get_logger(__name__)
        self._last_positions: deque[Tuple[float, float]] = deque(maxlen=self._config.stuck_threshold)

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
                    prompt=f"Look at the screenshot and decide the next action.\n\n{context}",
                    system=self._system_prompt,
                    temperature=self._config.vlm_temperature,
                    max_tokens=self._config.vlm_max_tokens,
                    image=img_b64,
                    timeout=self._config.vlm_call_timeout_s,
                )
                reply = handle.result_or(
                    default="",
                    timeout=self._config.vlm_call_timeout_s,
                )
            except Exception as exc:
                self._logger.error("VLM call failed at step %d: %s", step_idx, exc)
                history.append({"step": step_idx, "action": "vlm_error", "detail": str(exc)})
                continue

            if not reply:
                self._logger.warning("VLM step %d returned empty/timed out, skipping", step_idx)
                history.append({"step": step_idx, "action": "vlm_timeout"})
                continue

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

        loop_deadline = time.monotonic() + (self._config.step_timeout_s * max(steps, 1))

        frame = self._grab_frame()
        if frame is None:
            return {"status": "error", "message": "no screenshot available"}

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
                    ),
                    system=_TRACKING_SYSTEM_PROMPT,
                    temperature=self._config.vlm_temperature,
                    max_tokens=self._config.vlm_max_tokens,
                    image=img_b64,
                    timeout=self._config.vlm_call_timeout_s,
                )
                reply = handle.result_or(
                    default="",
                    timeout=self._config.vlm_call_timeout_s,
                )
            except Exception as exc:
                self._logger.error("VLM tracking call failed at step %d: %s", step_idx, exc)
                history.append({"step": step_idx, "action": "vlm_error", "detail": str(exc)})
                continue

            if not reply:
                self._logger.warning("VLM tracking step %d returned empty/timed out, skipping", step_idx)
                history.append({"step": step_idx, "action": "vlm_timeout"})
                continue

            action = self._parse_action(reply)
            if action is None:
                self._logger.warning("unparseable VLM tracking reply at step %d: %s", step_idx, reply[:200])
                history.append({"step": step_idx, "action": "parse_error", "raw": reply[:120]})
                continue

            if action["action"] == "arrived":
                history.append({"step": step_idx, "action": "arrived"})
                self._logger.info("VLM tracking arrived at step %d", step_idx)
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
        keycode = _ACTION_KEYCODE_MAP.get(act)
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
        try:
            data = self._screenshot_fn()
            if data is None:
                return None
            arr = np.frombuffer(data, dtype=np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception as exc:
            self._logger.warning("grab_frame failed: %s", exc)
            return None

    def _frame_to_base64(self, frame: np.ndarray) -> str:
        _, buf = cv2.imencode(".png", frame)
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
        """Parse JSON action from VLM reply."""
        cleaned = reply.strip()
        if cleaned.startswith("```") and cleaned.endswith("```"):
            cleaned = cleaned.strip("`").strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        try:
            obj = json.loads(cleaned)
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict) or "action" not in obj:
            return None
        return obj

    @property
    def config(self) -> VlmWalkConfig:
        return self._config

    @config.setter
    def config(self, cfg: VlmWalkConfig) -> None:
        self._config = cfg
