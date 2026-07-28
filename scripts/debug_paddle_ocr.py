"""用 PaddleOCR 识别当前屏幕所有文字（调试用）。"""
from __future__ import annotations

import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    img_path = r"C:\Users\cheng\AppData\Local\Temp\iea_now3.png"
    # 先截图
    r = subprocess.run(
        ["3rd-part/adb/adb.exe", "-s", "127.0.0.1:16416", "exec-out", "screencap", "-p"],
        capture_output=True,
    )
    Path(img_path).write_bytes(r.stdout)
    print(f"截图大小: {len(r.stdout)} bytes")

    from paddleocr import PaddleOCR

    ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    result = ocr.ocr(img_path, cls=True)
    print("=== PaddleOCR 识别结果 ===")
    if not result:
        print("无结果")
        return 0
    for idx, page in enumerate(result):
        if not page:
            continue
        print(f"--- Page {idx} ---")
        for line in page:
            box = line[0]
            text = line[1][0]
            conf = line[1][1]
            if conf < 0.5:
                continue
            # box 是 4 个点
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            x_min, y_min = min(xs), min(ys)
            x_max, y_max = max(xs), max(ys)
            print(f"  text={text!r} conf={conf:.2f} box=({x_min:.0f},{y_min:.0f})-({x_max:.0f},{y_max:.0f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
