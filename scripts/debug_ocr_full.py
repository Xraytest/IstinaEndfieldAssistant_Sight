"""全屏 OCR 扫描（不带 expected 过滤）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from core.foundation.paths import ensure_src_path

ensure_src_path()

from core.foundation.logger import init_logger

init_logger()

from core.service.runtime import IstinaRuntime


def main() -> int:
    runtime = IstinaRuntime()
    if not runtime.connect(serial="127.0.0.1:16416"):
        print("连接失败")
        return 1
    maaend = runtime.maaend()
    tasker = maaend._tasker
    controller = maaend._controller
    if tasker is None or controller is None:
        print("tasker/controller 未就绪")
        return 2
    if not maaend._wait_for_tasker_ready(wait_s=5.0, rebuild_on_stuck=True):
        print("Tasker 未就绪")
        return 3
    job = controller.post_screencap()
    if not maaend._wait_job(job, timeout_s=10.0):
        print("截图失败")
        return 4
    img = controller.cached_image
    if img is None:
        print("cached_image 为空")
        return 5
    print(f"图像尺寸: {img.shape}")

    from maa.pipeline import JOCR, JRecognitionType

    # 不带 expected，only_rec=True 返回所有识别到的文本
    ocr_param = JOCR(
        expected=[],
        roi=[0, 0, img.shape[1], img.shape[0]],
        threshold=0.1,
        only_rec=True,
    )
    ocr_job = tasker.post_recognition(JRecognitionType.OCR, ocr_param, img)
    detail = ocr_job.wait().get()
    if not detail:
        print("OCR 无结果")
        return 6
    print("=== OCR 全屏识别结果（only_rec=True, 无 expected 过滤）===")
    hit_count = 0
    for node in detail.nodes:
        if node.recognition:
            all_results = node.recognition.all_results
            if all_results:
                for r in all_results:
                    box = r.box
                    if hasattr(box, "x"):
                        coords = (box.x, box.y, box.w, box.h)
                    else:
                        coords = tuple(box)
                    text = getattr(r, "text", "") or ""
                    score = getattr(r, "score", 0) or 0
                    if text:
                        print(f"  text={text!r} score={score:.2f} box={coords}")
                        hit_count += 1
    print(f"总计 {hit_count} 个文本块")
    return 0


if __name__ == "__main__":
    sys.exit(main())
