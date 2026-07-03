from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import cv2
import numpy as np

from ..element_info import ElementInfo
from .pipeline_node import PipelineNode, PipelineGraph, RecognitionType, NodeAction
from .template_registry import TemplateRegistry
from .matcher import TemplateMatcher

logger = logging.getLogger(__name__)

MAAFW_AVAILABLE = False
try:
    from maa.pipeline import JRecognitionType, JOCR, JTemplateMatch as MJTemplateMatch
    from maa.tasker import Tasker
    MAAFW_AVAILABLE = True
except ImportError:
    JRecognitionType = None
    JOCR = None
    MJTemplateMatch = None
    Tasker = None


class PipelineRunner:
    def __init__(
        self,
        registry: Optional[TemplateRegistry] = None,
        matcher: Optional[TemplateMatcher] = None,
        maa_tasker: Optional[Any] = None,
    ):
        self._registry = registry or TemplateRegistry()
        self._matcher = matcher or TemplateMatcher(self._registry)
        self._maa_tasker = maa_tasker
        self._hit_counts: Dict[str, int] = {}
        self._last_run: Dict[str, float] = {}

    def set_maa_tasker(self, tasker: Any) -> None:
        self._maa_tasker = tasker

    def run(
        self,
        screen: np.ndarray,
        graph: PipelineGraph,
        entry: str,
        max_steps: int = 100,
    ) -> Dict[str, Any]:
        self._hit_counts.clear()
        current = graph.get_entry(entry)
        if current is None:
            return {"status": "error", "message": f"Entry node '{entry}' not found"}
        step = 0
        executed: List[str] = []
        result = {"status": "idle", "executed": executed, "matches": []}
        while current and step < max_steps:
            step += 1
            if not current.enabled:
                current = self._transition(graph, current, executed)
                continue
            if self._is_rate_limited(current):
                current = self._transition(graph, current, executed)
                continue
            if self._hit_limit_reached(current):
                current = self._transition(graph, current, executed)
                continue
            if current.pre_delay > 0:
                time.sleep(current.pre_delay / 1000.0)
            if current.pre_wait_freezes is not None:
                self._wait_for_freeze(screen, current.pre_wait_freezes)
            match_result = self._evaluate(screen, current)
            executed.append(current.name)
            self._hit_counts[current.name] = self._hit_counts.get(current.name, 0) + 1
            self._last_run[current.name] = time.time()
            if current.post_delay > 0:
                time.sleep(current.post_delay / 1000.0)
            if match_result:
                result["status"] = "matched"
                result["last_match"] = current.name
                result["matches"].append({
                    "node": current.name,
                    "results": match_result,
                })
            else:
                result["status"] = "no_match"
            if current.action == NodeAction.StopTask:
                break
            next_name = self._pick_next(current, graph)
            if next_name is None:
                break
            nxt = graph.get_node(next_name)
            if nxt is not None:
                current = nxt
        result["executed"] = executed
        result["steps"] = step
        result["hit_counts"] = dict(self._hit_counts)
        return result

    def run_pipeline(
        self,
        screen: np.ndarray,
        graph: PipelineGraph,
        entry: str,
        target_node: Optional[str] = None,
        max_steps: int = 200,
    ) -> Dict[str, Any]:
        result = self.run(screen, graph, entry, max_steps)
        while result["status"] != "matched" and result["steps"] < max_steps:
            result = self.run(screen, graph, entry, max_steps)
            if target_node and target_node in result.get("executed", []):
                break
        return result

    def match_node(
        self,
        screen: np.ndarray,
        node: PipelineNode,
    ) -> List[Dict]:
        return self._evaluate(screen, node) or []

    def reset(self) -> None:
        self._hit_counts.clear()
        self._last_run.clear()

    def _evaluate(
        self, screen: np.ndarray, node: PipelineNode
    ) -> Optional[List[Dict]]:
        if node.recognition == RecognitionType.DirectHit:
            return [{"confidence": 1.0, "method": "DirectHit"}]
        if node.recognition == RecognitionType.TemplateMatch:
            return self._match_template(screen, node)
        if node.recognition == RecognitionType.OCR:
            return self._match_ocr(screen, node)
        if node.recognition == RecognitionType.ColorMatch:
            return self._match_color(screen, node)
        if node.recognition == RecognitionType.And:
            return self._evaluate_and(screen, node)
        if node.recognition == RecognitionType.Or:
            return self._evaluate_or(screen, node)
        return None

    def _match_template(
        self, screen: np.ndarray, node: PipelineNode
    ) -> List[Dict]:
        # Route 1: maafw 管道匹配（优先）
        if self._maa_tasker is not None and MAAFW_AVAILABLE:
            try:
                return self._match_template_maafw(screen, node)
            except Exception as e:
                logger.debug(f"maafw template match failed: {e}")

        # Route 2: OpenCV 本地匹配
        return self._match_template_opencv(screen, node)

    def _match_template_maafw(
        self, screen: np.ndarray, node: PipelineNode
    ) -> List[Dict]:
        template_refs = node.template
        if isinstance(template_refs, str):
            template_refs = [template_refs]
        if not template_refs:
            return []

        roi = node.roi or (0, 0, screen.shape[1], screen.shape[0])
        param = MJTemplateMatch(
            template=template_refs,
            roi=tuple(roi),
            threshold=[node.threshold],
        )
        job = self._maa_tasker.post_recognition(
            JRecognitionType.TemplateMatch,
            param,
            screen,
        )
        detail = job.get()
        if not detail or not detail.hit:
            return []

        results = []
        best = detail.best_result
        if best is not None:
            bx, by, bw, bh = best.box
            results.append({
                "x": bx, "y": by, "w": bw, "h": bh,
                "confidence": best.score,
                "center": (bx + bw // 2, by + bh // 2),
                "method": "maafw",
                "template": template_refs[0],
            })

        if detail.filtered_results:
            for item in detail.filtered_results:
                score = getattr(item, "score", 0)
                if score < node.threshold:
                    continue
                ibox = getattr(item, "box", (0, 0, 0, 0))
                results.append({
                    "x": ibox[0], "y": ibox[1], "w": ibox[2], "h": ibox[3],
                    "confidence": score,
                    "center": (ibox[0] + ibox[2] // 2, ibox[1] + ibox[3] // 2),
                    "method": "maafw",
                    "template": template_refs[0],
                })

        return results

    def _match_template_opencv(
        self, screen: np.ndarray, node: PipelineNode
    ) -> List[Dict]:
        template_refs = node.template
        if isinstance(template_refs, str):
            template_refs = [template_refs]
        if not template_refs:
            return []
        roi = node.roi
        results: List[Dict] = []
        for ref in template_refs:
            matches = self._matcher.match(screen, ref, node.threshold, roi)
            if matches:
                for m in matches:
                    m["template"] = ref
                if node.box_index > 0 and len(matches) > node.box_index - 1:
                    results.append(matches[node.box_index - 1])
                    return results
                results.extend(matches)
        if results:
            results.sort(key=lambda r: -r["confidence"])
            return results[:5]
        return results

    def _match_ocr(
        self, screen: np.ndarray, node: PipelineNode
    ) -> List[Dict]:
        if self._maa_tasker is not None and MAAFW_AVAILABLE:
            try:
                h, w = screen.shape[:2]
                roi = node.roi or (0, 0, w, h)
                param = JOCR(
                    expected=node.expected or [],
                    roi=tuple(roi),
                    threshold=node.threshold,
                )
                job = self._maa_tasker.post_recognition(
                    JRecognitionType.OCR,
                    param,
                    screen,
                )
                detail = job.get()
                if detail and detail.hit:
                    results = []
                    best = detail.best_result
                    if best is not None:
                        bx, by, bw, bh = best.box
                        results.append({
                            "x": bx, "y": by, "w": bw, "h": bh,
                            "confidence": best.score,
                            "text": best.text.strip(),
                            "center": (bx + bw // 2, by + bh // 2),
                            "method": "maafw_ocr",
                        })
                    if detail.filtered_results:
                        for item in detail.filtered_results:
                            txt = getattr(item, "text", "").strip()
                            if not txt:
                                continue
                            ibox = getattr(item, "box", (0, 0, 0, 0))
                            score = getattr(item, "score", 0)
                            results.append({
                                "x": ibox[0], "y": ibox[1], "w": ibox[2], "h": ibox[3],
                                "confidence": score,
                                "text": txt,
                                "center": (ibox[0] + ibox[2] // 2, ibox[1] + ibox[3] // 2),
                                "method": "maafw_ocr",
                            })
                    return results
            except Exception as e:
                logger.debug(f"maafw OCR in runner failed: {e}")
        return []

    def _match_color(
        self, screen: np.ndarray, node: PipelineNode
    ) -> List[Dict]:
        lower = getattr(node, "lower", None) or node.metadata.get("lower", [0, 0, 0])
        upper = getattr(node, "upper", None) or node.metadata.get("upper", [180, 255, 255])
        try:
            hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, np.array(lower, dtype=np.uint8), np.array(upper, dtype=np.uint8))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            results = []
            for c in contours:
                area = cv2.contourArea(c)
                if area < (node.metadata.get("min_area", 30)):
                    continue
                x, y, bw, bh = cv2.boundingRect(c)
                results.append({
                    "x": x, "y": y, "w": bw, "h": bh,
                    "confidence": 0.7,
                    "center": (x + bw // 2, y + bh // 2),
                    "method": "color_match",
                })
            return results
        except Exception as e:
            logger.debug(f"Color match failed: {e}")
            return []

    def _evaluate_and(
        self, screen: np.ndarray, node: PipelineNode
    ) -> Optional[List[Dict]]:
        sub_names = node.all_of or []
        all_results = []
        for sub_name in sub_names:
            sub_node = PipelineNode(
                name=sub_name,
                recognition=RecognitionType.DirectHit,
                template=None,
                roi=None,
                threshold=node.threshold,
            )
            result = self._evaluate(screen, sub_node)
            if not result:
                return None
            all_results.extend(result)
        return all_results

    def _evaluate_or(
        self, screen: np.ndarray, node: PipelineNode
    ) -> Optional[List[Dict]]:
        sub_names = node.any_of or []
        for sub_name in sub_names:
            sub_node = PipelineNode(
                name=sub_name,
                recognition=RecognitionType.DirectHit,
                template=None,
                roi=None,
                threshold=node.threshold,
            )
            result = self._evaluate(screen, sub_node)
            if result:
                return result
        return None

    def _pick_next(
        self, node: PipelineNode, graph: PipelineGraph
    ) -> Optional[str]:
        if not node.next:
            return None
        for next_name in node.next:
            if next_name.startswith("["):
                continue
            if graph.get_node(next_name) is not None:
                return next_name
        return node.next[0] if node.next else None

    def _transition(
        self, graph: PipelineGraph, current: PipelineNode, executed: List[str]
    ) -> Optional[PipelineNode]:
        next_name = self._pick_next(current, graph)
        if next_name:
            return graph.get_node(next_name)
        return None

    def _is_rate_limited(self, node: PipelineNode) -> bool:
        if node.rate_limit <= 0:
            return False
        last = self._last_run.get(node.name, 0)
        if last == 0:
            return False
        return (time.time() - last) * 1000 < node.rate_limit

    def _hit_limit_reached(self, node: PipelineNode) -> bool:
        if node.max_hit <= 0:
            return False
        return self._hit_counts.get(node.name, 0) >= node.max_hit

    def _wait_for_freeze(
        self, screen: np.ndarray, freeze_spec: Any
    ) -> None:
        pass
