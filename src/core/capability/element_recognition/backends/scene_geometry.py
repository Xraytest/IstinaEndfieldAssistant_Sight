from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

from core.capability.element_recognition.annotation import Annotation, AnnotationSet
from core.capability.element_recognition.element_info import SceneAnalysis3D


@dataclass
class _Candidate:
    bbox: Tuple[int, int, int, int]
    center: Tuple[float, float]
    area: float
    score: float
    confidence: float
    metadata: Dict[str, Any]


class SceneGeometryAnalyzer:
    """Pure local scene geometry analyzer."""

    def __init__(
        self,
        horizontal_fov_deg: float = 70.0,
        vertical_fov_deg: float = 43.0,
        max_entities: int = 8,
    ) -> None:
        self._horizontal_fov_deg = horizontal_fov_deg
        self._vertical_fov_deg = vertical_fov_deg
        self._max_entities = max_entities

    def analyze(self, screen: np.ndarray, prompt: str = "") -> SceneAnalysis3D:
        if screen is None or screen.size == 0:
            return SceneAnalysis3D(
                ground={},
                entities=[],
                camera={
                    "horizontal_fov_deg": self._horizontal_fov_deg,
                    "vertical_fov_deg": self._vertical_fov_deg,
                },
                summary={"status": "empty"},
                metadata={"analysis_mode": "local_geometry"},
            )

        h_img, w_img = screen.shape[:2]
        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY).astype(np.float32)
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV).astype(np.float32)
        lab = cv2.cvtColor(screen, cv2.COLOR_BGR2LAB).astype(np.float32)

        edge_map = self._compute_edge_map(gray)
        texture_map = self._compute_local_texture(gray)
        chroma_map = self._compute_chroma_map(lab)
        saliency_map = self._compute_saliency_map(edge_map, texture_map, hsv, chroma_map)

        ground = self._estimate_ground(gray, hsv, edge_map, texture_map, h_img)
        candidates = self._extract_candidates(
            saliency_map=saliency_map,
            edge_map=edge_map,
            texture_map=texture_map,
            ground_y=ground.get("ground_line_y"),
            h_img=h_img,
            w_img=w_img,
        )

        rendered = screen.copy()
        annotations: List[Annotation] = []
        entities: List[Dict[str, Any]] = []
        self._draw_ground(rendered, ground)
        annotations.append(
            Annotation(
                label="scene_ground",
                shape_type="polygon",
                points=self._ground_polygon_points(w_img, h_img, ground.get("ground_line_y")),
                confidence=float(ground.get("confidence", 0.0)),
                metadata=ground,
            )
        )

        for index, candidate in enumerate(candidates[: self._max_entities]):
            entity = self._build_entity(
                index=index,
                candidate=candidate,
                h_img=h_img,
                w_img=w_img,
                ground_y=ground.get("ground_line_y"),
            )
            entities.append(entity)
            annotations.append(
                Annotation(
                    label=entity["label"],
                    shape_type="rectangle",
                    points=[
                        (int(entity["bbox_px"][0]), int(entity["bbox_px"][1])),
                        (int(entity["bbox_px"][2]), int(entity["bbox_px"][3])),
                    ],
                    confidence=float(entity["confidence"]),
                    metadata=entity["metadata"],
                )
            )
            self._draw_entity(rendered, entity)

        summary = self._build_summary(ground, entities)
        raw_text = self._compose_text(ground, entities, prompt)

        return SceneAnalysis3D(
            annotations=AnnotationSet(
                annotations=annotations,
                raw_text=raw_text,
                raw_tool_calls=[],
            ),
            rendered_image=rendered,
            raw_text=raw_text,
            raw_tool_calls=[],
            usage={},
            ground=ground,
            entities=entities,
            camera={
                "horizontal_fov_deg": self._horizontal_fov_deg,
                "vertical_fov_deg": self._vertical_fov_deg,
                "image_size": [w_img, h_img],
            },
            summary=summary,
            metadata={
                "analysis_mode": "local_geometry",
                "prompt_used": bool(prompt),
                "candidate_count": len(candidates),
            },
        )

    def _compute_edge_map(self, gray: np.ndarray) -> np.ndarray:
        blurred = cv2.GaussianBlur(gray, (0, 0), 2.0)
        edge = cv2.Canny(blurred.astype(np.uint8), 60, 160).astype(np.float32) / 255.0
        return cv2.GaussianBlur(edge, (0, 0), 3.0)

    def _compute_local_texture(self, gray: np.ndarray) -> np.ndarray:
        mean = cv2.GaussianBlur(gray, (0, 0), 15.0)
        mean_sq = cv2.GaussianBlur(gray * gray, (0, 0), 15.0)
        std = np.sqrt(np.maximum(mean_sq - mean * mean, 0.0))
        return std / (std.max() + 1e-6)

    def _compute_chroma_map(self, lab: np.ndarray) -> np.ndarray:
        a = lab[:, :, 1]
        b = lab[:, :, 2]
        mean_a = cv2.GaussianBlur(a, (0, 0), 11.0)
        mean_b = cv2.GaussianBlur(b, (0, 0), 11.0)
        chroma = np.sqrt((a - mean_a) ** 2 + (b - mean_b) ** 2)
        return chroma / (chroma.max() + 1e-6)

    def _compute_saliency_map(
        self,
        edge_map: np.ndarray,
        texture_map: np.ndarray,
        hsv: np.ndarray,
        chroma_map: np.ndarray,
    ) -> np.ndarray:
        sat = hsv[:, :, 1].astype(np.float32) / 255.0
        value = hsv[:, :, 2].astype(np.float32) / 255.0
        saliency = (
            0.34 * edge_map
            + 0.30 * texture_map
            + 0.18 * chroma_map
            + 0.10 * sat
            + 0.08 * (1.0 - value)
        )
        saliency = cv2.GaussianBlur(saliency, (0, 0), 2.0)
        saliency = cv2.normalize(saliency, None, 0.0, 1.0, cv2.NORM_MINMAX)
        return saliency.astype(np.float32)

    def _estimate_ground(
        self,
        gray: np.ndarray,
        hsv: np.ndarray,
        edge_map: np.ndarray,
        texture_map: np.ndarray,
        h_img: int,
    ) -> Dict[str, Any]:
        row_texture = 0.45 * edge_map.mean(axis=1) + 0.35 * texture_map.mean(axis=1) + 0.20 * (
            hsv[:, :, 1].astype(np.float32) / 255.0
        ).mean(axis=1)
        row_texture = cv2.GaussianBlur(row_texture.reshape(-1, 1), (1, 31), 0).reshape(-1)
        row_brightness = cv2.GaussianBlur((gray / 255.0).mean(axis=1).reshape(-1, 1), (1, 31), 0).reshape(-1)
        row_saturation = cv2.GaussianBlur(
            (hsv[:, :, 1].astype(np.float32) / 255.0).mean(axis=1).reshape(-1, 1), (1, 31), 0
        ).reshape(-1)

        start = max(8, int(h_img * 0.18))
        end = max(start + 16, int(h_img * 0.88))
        window = max(24, h_img // 12)

        best_y = int(h_img * 0.6)
        best_score = -1.0
        scores: List[float] = []
        for y in range(start, min(end, h_img - window)):
            upper = slice(max(0, y - window), y)
            lower = slice(y, min(h_img, y + window))
            texture_delta = abs(float(row_texture[lower].mean()) - float(row_texture[upper].mean()))
            brightness_delta = abs(float(row_brightness[lower].mean()) - float(row_brightness[upper].mean()))
            saturation_delta = abs(float(row_saturation[lower].mean()) - float(row_saturation[upper].mean()))
            lower_bias = 0.7 + 0.3 * (y / max(h_img - 1, 1))
            score = (0.55 * texture_delta + 0.25 * brightness_delta + 0.20 * saturation_delta) * lower_bias
            scores.append(score)
            if score > best_score:
                best_score = score
                best_y = y

        if scores:
            score_arr = np.asarray(scores, dtype=np.float32)
            score_norm = float((best_score - float(score_arr.mean())) / (float(score_arr.std()) + 1e-6))
        else:
            score_norm = 0.0

        confidence = float(np.clip(0.42 + score_norm / 7.0, 0.0, 0.95))
        lower_band = gray[min(h_img - 1, best_y + 1) :, :]
        upper_band = gray[: max(best_y, 1), :]

        return {
            "ground_line_y": int(best_y),
            "ground_region_ratio": round(float((h_img - best_y) / max(h_img, 1)), 3),
            "confidence": round(confidence, 3),
            "score": round(float(best_score), 4),
            "surface_guess": self._guess_surface_type(hsv, best_y, h_img),
            "dominant_lower_band": self._mean_band_info(hsv[min(h_img - 1, best_y + 1) :, :, :], lower_band),
            "brightness_above": round(float(upper_band.mean()) if upper_band.size else 0.0, 1),
            "brightness_below": round(float(lower_band.mean()) if lower_band.size else 0.0, 1),
        }

    def _guess_surface_type(self, hsv: np.ndarray, ground_y: int, h_img: int) -> str:
        lower = hsv[min(h_img - 1, ground_y + 1) :, :, :]
        if lower.size == 0:
            return "unknown"
        sat = float(lower[:, :, 1].mean()) / 255.0
        value = float(lower[:, :, 2].mean()) / 255.0
        hue = float(lower[:, :, 0].mean())
        if sat < 0.18 and value < 0.35:
            return "shadowed_ground"
        if 35 <= hue <= 95 and sat > 0.18:
            return "vegetation_or_grass"
        if value > 0.7 and sat < 0.18:
            return "bright_floor_or_road"
        return "mixed_surface"

    def _mean_band_info(self, hsv: np.ndarray, gray: np.ndarray) -> Dict[str, Any]:
        if hsv.size == 0 or gray.size == 0:
            return {}
        mean_hsv = np.mean(hsv.reshape(-1, 3), axis=0)
        return {
            "mean_h": round(float(mean_hsv[0]), 1),
            "mean_s": round(float(mean_hsv[1]), 1),
            "mean_v": round(float(mean_hsv[2]), 1),
            "mean_gray": round(float(gray.mean()), 1),
        }

    def _extract_candidates(
        self,
        saliency_map: np.ndarray,
        edge_map: np.ndarray,
        texture_map: np.ndarray,
        ground_y: Any,
        h_img: int,
        w_img: int,
    ) -> List[_Candidate]:
        saliency = saliency_map.copy()
        saliency[: int(h_img * 0.12), :] *= 0.45
        saliency[: int(h_img * 0.20), :] *= 0.55
        saliency[:, : max(1, int(w_img * 0.04))] *= 0.70
        saliency[:, max(0, w_img - int(w_img * 0.04)) :] *= 0.70

        threshold = float(max(np.percentile(saliency, 89), saliency.mean() + saliency.std() * 0.8))
        mask = (saliency >= threshold).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))

        num_labels, _, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        candidates: List[_Candidate] = []
        total_area = float(h_img * w_img)

        for idx in range(1, num_labels):
            x, y, bw, bh, area = stats[idx]
            if area < 350:
                continue
            if bw < 14 or bh < 14:
                continue
            if area / total_area > 0.35:
                continue

            bottom = y + bh
            center_y = y + bh * 0.5
            top_band = max(1, int(h_img * 0.20))
            ui_like = False
            if bottom < top_band:
                ui_like = True
            if y < int(h_img * 0.14) and bw > int(w_img * 0.18) and bh < int(h_img * 0.10):
                ui_like = True
            if y < int(h_img * 0.18) and bw > int(w_img * 0.45):
                ui_like = True
            if ground_y is not None and bottom < int(float(ground_y) * 0.88):
                ui_like = True
            if ui_like:
                continue

            bbox_area = float(max(bw * bh, 1))
            compactness = float(area / bbox_area)
            saliency_mean = float(saliency[y : y + bh, x : x + bw].mean())
            edge_mean = float(edge_map[y : y + bh, x : x + bw].mean())
            texture_mean = float(texture_map[y : y + bh, x : x + bw].mean())
            cx, cy = float(centroids[idx][0]), float(centroids[idx][1])

            if ground_y is not None:
                ground_gap = abs((y + bh) - float(ground_y))
                ground_alignment = 1.0 - min(1.0, ground_gap / max(h_img * 0.18, 1.0))
            else:
                ground_alignment = cy / max(h_img, 1)
            center_bias = 1.0 - min(1.0, abs(cx - (w_img * 0.5)) / max(w_img * 0.5, 1.0))
            vertical_bias = 1.0 - min(1.0, center_y / max(h_img * 0.35, 1.0))

            score = (
                0.40 * saliency_mean
                + 0.20 * compactness
                + 0.18 * edge_mean
                + 0.12 * texture_mean
                + 0.10 * ground_alignment
            )
            score *= 1.0 - 0.35 * max(0.0, vertical_bias)
            confidence = float(np.clip(0.32 + score + 0.10 * center_bias, 0.05, 0.98))

            candidates.append(
                _Candidate(
                    bbox=(int(x), int(y), int(x + bw), int(y + bh)),
                    center=(cx, cy),
                    area=float(area),
                    score=float(score),
                    confidence=confidence,
                    metadata={
                        "saliency_mean": round(saliency_mean, 4),
                        "edge_mean": round(edge_mean, 4),
                        "texture_mean": round(texture_mean, 4),
                        "compactness": round(compactness, 4),
                    "ground_alignment": round(float(ground_alignment), 4),
                    "center_bias": round(float(center_bias), 4),
                    "vertical_bias": round(float(vertical_bias), 4),
                },
            )
            )

        candidates.sort(key=lambda item: (item.confidence, item.score, item.area), reverse=True)
        return candidates

    def _build_entity(
        self,
        index: int,
        candidate: _Candidate,
        h_img: int,
        w_img: int,
        ground_y: Any,
    ) -> Dict[str, Any]:
        x1, y1, x2, y2 = candidate.bbox
        cx, cy = candidate.center
        bbox_w = max(x2 - x1, 1)
        bbox_h = max(y2 - y1, 1)
        bbox_area = bbox_w * bbox_h
        area_ratio = candidate.area / float(max(h_img * w_img, 1))

        horizontal_angle = ((cx - (w_img * 0.5)) / max(w_img * 0.5, 1.0)) * (self._horizontal_fov_deg / 2.0)
        vertical_angle = ((h_img * 0.5 - cy) / max(h_img * 0.5, 1.0)) * (self._vertical_fov_deg / 2.0)

        if ground_y is None:
            ground_factor = 0.5
        else:
            usable = max(h_img - float(ground_y), h_img * 0.25)
            ground_factor = float(np.clip((h_img - y2) / usable, 0.0, 1.0))

        size_factor = float(np.clip(0.22 - (bbox_h / max(h_img, 1)), 0.0, 0.22) / 0.22)
        relative_distance = float(np.clip(0.62 * size_factor + 0.38 * ground_factor, 0.0, 1.0))
        estimated_distance_m = round(3.0 + relative_distance * 52.0, 1)
        if estimated_distance_m < 8:
            distance_band = "near"
        elif estimated_distance_m < 24:
            distance_band = "mid"
        else:
            distance_band = "far"

        label = f"entity_{index + 1}"
        metadata = {
            **candidate.metadata,
            "area": int(candidate.area),
            "area_ratio": round(float(area_ratio), 5),
            "bbox_area": int(bbox_area),
            "bbox_px": [x1, y1, x2, y2],
            "contact_point_px": [int(cx), int(y2)],
            "distance_band": distance_band,
        }

        return {
            "label": label,
            "bbox_px": [x1, y1, x2, y2],
            "bbox": [round(x1 / w_img, 4), round(y1 / h_img, 4), round(x2 / w_img, 4), round(y2 / h_img, 4)],
            "center": [round(cx / w_img, 4), round(cy / h_img, 4)],
            "confidence": round(candidate.confidence, 3),
            "estimated_distance_m": estimated_distance_m,
            "estimated_distance_range_m": [round(max(1.0, estimated_distance_m - 6.0), 1), round(estimated_distance_m + 8.0, 1)],
            "distance_band": distance_band,
            "horizontal_angle_deg": round(float(horizontal_angle), 2),
            "vertical_angle_deg": round(float(vertical_angle), 2),
            "view_angle_deg": round(float(horizontal_angle), 2),
            "relative_distance": round(relative_distance, 3),
            "ground_contact_px": [int(cx), int(y2)],
            "metadata": metadata,
        }

    def _build_summary(self, ground: Dict[str, Any], entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        if entities:
            nearest = min(entities, key=lambda item: item["estimated_distance_m"])
            farthest = max(entities, key=lambda item: item["estimated_distance_m"])
        else:
            nearest = None
            farthest = None
        return {
            "ground_found": bool(ground),
            "entity_count": len(entities),
            "nearest_distance_m": nearest["estimated_distance_m"] if nearest else None,
            "farthest_distance_m": farthest["estimated_distance_m"] if farthest else None,
            "ground_confidence": ground.get("confidence", 0.0),
        }

    def _compose_text(self, ground: Dict[str, Any], entities: List[Dict[str, Any]], prompt: str) -> str:
        parts = [
            "local geometry scene analysis",
            f"ground_line_y={ground.get('ground_line_y', 'n/a')}",
            f"surface={ground.get('surface_guess', 'unknown')}",
            f"entities={len(entities)}",
        ]
        if prompt:
            parts.append(f"prompt={prompt[:80]}")
        if entities:
            top = entities[0]
            parts.append(
                f"nearest={top['label']} dist={top['estimated_distance_m']}m angle={top['horizontal_angle_deg']}deg"
            )
        return " | ".join(parts)

    def _draw_ground(self, img: np.ndarray, ground: Dict[str, Any]) -> None:
        h_img, w_img = img.shape[:2]
        y = int(ground.get("ground_line_y", h_img // 2))
        y = max(0, min(h_img - 1, y))
        polygon = np.array(
            [self._ground_polygon_points(w_img, h_img, y)],
            dtype=np.int32,
        )
        overlay = img.copy()
        cv2.fillPoly(overlay, polygon, (20, 80, 140))
        cv2.addWeighted(overlay, 0.10, img, 0.90, 0, img)
        cv2.polylines(img, polygon, isClosed=True, color=(255, 200, 80), thickness=2)
        cv2.putText(
            img,
            f"ground poly y={y} conf={ground.get('confidence', 0.0):.2f} {ground.get('surface_guess', 'unknown')}",
            (18, max(28, y - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 200, 80),
            2,
            cv2.LINE_AA,
        )

    def _ground_polygon_points(
        self,
        w_img: int,
        h_img: int,
        ground_y: Any,
    ) -> List[Tuple[int, int]]:
        y = int(ground_y if ground_y is not None else h_img // 2)
        y = max(0, min(h_img - 1, y))
        top_left = (0, y)
        top_right = (w_img - 1, y)
        bottom_right = (w_img - 1, h_img - 1)
        bottom_left = (0, h_img - 1)
        return [top_left, top_right, bottom_right, bottom_left]

    def _draw_entity(self, img: np.ndarray, entity: Dict[str, Any]) -> None:
        x1, y1, x2, y2 = [int(v) for v in entity["bbox_px"]]
        color = (
            (50, 220, 255)
            if entity["distance_band"] == "near"
            else (80, 200, 120)
            if entity["distance_band"] == "mid"
            else (170, 140, 255)
        )
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        label = f"{entity['label']} {entity['estimated_distance_m']}m {entity['horizontal_angle_deg']:+.1f}deg"
        text_y = max(20, y1 - 8)
        cv2.putText(img, label, (x1, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)
        cx, cy = [int(v) for v in entity["ground_contact_px"]]
        cv2.circle(img, (cx, cy), 4, color, -1)
        cv2.line(img, (int((x1 + x2) / 2), int((y1 + y2) / 2)), (cx, cy), color, 1)
