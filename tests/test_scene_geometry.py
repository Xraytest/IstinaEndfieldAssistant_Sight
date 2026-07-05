from __future__ import annotations

from pathlib import Path


import cv2


def test_local_scene_geometry_analysis_from_debug_screenshot() -> None:
    from core.service.runtime import IstinaRuntime

    image_path = Path("cache/screenshot/debug/after_quest.png")
    assert image_path.is_file()

    screen = cv2.imread(str(image_path))
    assert screen is not None

    runtime = IstinaRuntime()
    result = runtime.scene().analyze_scene_3d(screen)

    assert result is not None
    assert result.ground.get("ground_line_y") is not None
    assert result.ground.get("confidence", 0.0) >= 0.2
    assert isinstance(result.entities, list)
    assert len(result.entities) > 0
    assert result.annotations is not None
    assert any(a.label == "scene_ground" and a.shape_type == "polygon" for a in result.annotations.annotations)

    first = result.entities[0]
    assert first["estimated_distance_m"] > 0
    assert "horizontal_angle_deg" in first
    assert "vertical_angle_deg" in first
    assert -90.0 <= first["horizontal_angle_deg"] <= 90.0
    assert first["bbox_px"][1] >= 0
    assert first["bbox_px"][3] >= result.ground["ground_line_y"] * 0.85


def test_scene_analysis_uses_local_geometry_only() -> None:
    from core.service.runtime import IstinaRuntime

    image_path = Path("cache/screenshot/debug/after_quest.png")
    screen = cv2.imread(str(image_path))
    assert screen is not None

    runtime = IstinaRuntime()
    result = runtime.scene().analyze_scene_3d(screen)

    assert result is not None
    assert result.ground.get("ground_line_y") is not None
    assert result.ground.get("confidence", 0.0) >= 0.2
    assert len(result.entities) > 0
