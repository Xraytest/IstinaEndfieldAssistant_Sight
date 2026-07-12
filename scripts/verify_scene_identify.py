#!/usr/bin/env python3
"""Verify scene identify works with a local screenshot file.

Usage: python scripts/verify_scene_identify.py <image_path>
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.foundation.paths import ensure_src_path  # noqa: E402

ensure_src_path(__file__)

from core.service.runtime import IstinaRuntime  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: verify_scene_identify.py <image_path>", file=sys.stderr)
        return 2
    image_path = Path(sys.argv[1])
    if not image_path.is_file():
        print(f"image not found: {image_path}", file=sys.stderr)
        return 2

    image_bytes = image_path.read_bytes()
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    print(f"image: {image_path} size={len(image_bytes)} bytes", file=sys.stderr)

    runtime = IstinaRuntime()
    result = runtime.execute("scene.identify", {"image": image_b64})
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
