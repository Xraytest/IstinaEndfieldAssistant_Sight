from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np

from .matcher import TemplateMatcher
from .pipeline_node import NodeAction, PipelineGraph, PipelineNode, RecognitionType
from .template_registry import TemplateRegistry

logger = logging.getLogger(__name__)

MAAFW_AVAILABLE = False
try:
    from maa.pipeline import JOCR, JRecognitionType
    from maa.pipeline import JTemplateMatch as MJTemplateMatch
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
        clear_state: bool = True,
    ) -> Dict[str, Any]:
        # N2: 仅在全新执行时清空命中计数；重试场景由 run_pipeline 控制，
        # 避免清空已累计的 max_hit 计数导致重试失效。
        if clear_state:
            self._hit_counts.clear()
        current = graph.get_node_or_entry(entry)
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
            match_result = self._evaluate(screen, current, graph)
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
        max_retries: int = 3,
        retry_backoff_s: float = 0.1,
    ) -> Dict[str, Any]:
        # N2: 全新执行入口清空命中计数；后续重试传入 clear_state=False 不再清空。
        self._hit_counts.clear()
        result = self.run(screen, graph, entry, max_steps, clear_state=False)
        retries = 0
        while result["status"] != "matched" and result["steps"] < max_steps and retries < max_retries:
            time.sleep(retry_backoff_s)
            retries += 1
            result = self.run(screen, graph, entry, max_steps, clear_state=False)
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
        self, screen: np.ndarray, node: PipelineNode, graph: Optional[PipelineGraph] = None
    ) -> Optional[List[Dict]]:
        if node.recognition == RecognitionType.DirectHit:
            return [{"confidence": 1.0, "method": "DirectHit"}]
        if node.recognition == RecognitionType.TemplateMatch:
            return self._match_template(screen, node)
        if node.recognition == RecognitionType.OCR:
            return self._match_ocr(screen, node)
        if node.recognition == RecognitionType.And:
            return self._evaluate_and(screen, node, graph)
        if node.recognition == RecognitionType.Or:
            return self._evaluate_or(screen, node, graph)
        # G: 未实现的识别类型（ColorMatch/Custom 等）按非命中处理并记录告警。
        logger.warning(
            "未实现的识别类型 %s（节点 %s），按非命中处理",
            node.recognition.value if hasattr(node.recognition, "value") else node.recognition,
            node.name,
        )
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
        # OCR/TEMPLATE-HARD-TIMEOUT: job.get() 在 MaaFramework 内部有未完成
        # pipeline 任务时会因并发限制阻塞。改用线程 + join(timeout) 包装，
        # 超时返回空列表（视为未匹配）。
        import threading as _threading
        box: dict = {"detail": None, "error": None}
        TEMPLATE_TIMEOUT_S = 10.0

        def _do_match() -> None:
            try:
                job = self._maa_tasker.post_recognition(
                    JRecognitionType.TemplateMatch,
                    param,
                    screen,
                )
                job.wait()
                box["detail"] = job.get()
            except BaseException as exc:
                box["error"] = exc

        t = _threading.Thread(target=_do_match, daemon=True, name="maafw-tmpl-match")
        t.start()
        t.join(timeout=TEMPLATE_TIMEOUT_S)
        if t.is_alive():
            logger.warning(f"maafw template match 超时 {TEMPLATE_TIMEOUT_S}s，放弃（MaaFramework 可能忙）")
            return []
        if box["error"] is not None:
            logger.debug(f"maafw template match 异常: {box['error']}")
            return []
        detail = box["detail"]
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
                # OCR-HARD-TIMEOUT: job.get() 在 MaaFramework 内部有未完成
                # pipeline 任务时会因并发限制阻塞。改用线程 + join(timeout) 包装，
                # 超时返回空列表（视为未匹配）。
                import threading as _threading
                box: dict = {"detail": None, "error": None}
                OCR_TIMEOUT_S = 10.0

                def _do_ocr() -> None:
                    try:
                        job = self._maa_tasker.post_recognition(
                            JRecognitionType.OCR,
                            param,
                            screen,
                        )
                        job.wait()
                        box["detail"] = job.get()
                    except BaseException as exc:
                        box["error"] = exc

                t = _threading.Thread(target=_do_ocr, daemon=True, name="maafw-runner-ocr")
                t.start()
                t.join(timeout=OCR_TIMEOUT_S)
                if t.is_alive():
                    logger.warning(f"maafw runner OCR 超时 {OCR_TIMEOUT_S}s，放弃（MaaFramework 可能忙）")
                    return []
                if box["error"] is not None:
                    logger.debug(f"maafw runner OCR 异常: {box['error']}")
                    return []
                detail = box["detail"]
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

    def _evaluate_and(
        self, screen: np.ndarray, node: PipelineNode, graph: Optional[PipelineGraph]
    ) -> Optional[List[Dict]]:
        sub_names = node.all_of or []
        all_results = []
        for sub_name in sub_names:
            sub_node = graph.get_node(sub_name) if graph is not None else None
            if sub_node is None:
                logger.warning(f"Missing sub-node '{sub_name}' for AND evaluation, treating as non-match")
                return None
            result = self._evaluate(screen, sub_node, graph)
            if not result:
                return None
            all_results.extend(result)
        return all_results

    def _evaluate_or(
        self, screen: np.ndarray, node: PipelineNode, graph: Optional[PipelineGraph]
    ) -> Optional[List[Dict]]:
        sub_names = node.any_of or []
        for sub_name in sub_names:
            sub_node = graph.get_node(sub_name) if graph is not None else None
            if sub_node is None:
                logger.warning(f"Missing sub-node '{sub_name}' for OR evaluation, treating as non-match")
                continue
            result = self._evaluate(screen, sub_node, graph)
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
        # B4: 没有有效的下一节点时结束流程，而不是返回带方括号的死令牌（如 "[...]"）。
        return None

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
        # H-03: 实现「等待画面稳定」的最小可用版本。runner 此时只持有当前帧，
        # 无法跨帧比较 SSIM，故将 freeze_spec 解释为「等待时长（毫秒）」让画面沉降，
        # 避免节点在动画/转场未完成时立即识别。
        duration_ms = 0
        if isinstance(freeze_spec, int):
            duration_ms = freeze_spec
        elif isinstance(freeze_spec, dict):
            duration_ms = int(freeze_spec.get("duration", freeze_spec.get("timeout", 0)) or 0)
        if duration_ms > 0:
            time.sleep(duration_ms / 1000.0)
