"""检查屏幕特定区域以判断当前场景。"""
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

    # 关键区域 OCR 探测
    probes = [
        # 云游戏开始页 "开始游戏" 按钮 (1000, 590, 200, 60)
        ("云开始游戏按钮", [1000, 590, 200, 60], ["开始游戏", "開始遊戲", "Start", "Start Game"]),
        # 云开始页左上 "终末地" logo (0, 0, 300, 100)
        ("云终末地logo", [0, 0, 300, 100], ["终末地", "終末地", "ENDFIELD", "Endfield"]),
        # 自动登出弹窗中心 (300, 250, 700, 200)
        ("自动登出弹窗", [300, 250, 700, 200], ["长时间", "自动", "登出", "确认", "取消"]),
        # 主世界 UID 区域 (172, 0, 183, 119)
        ("主世界UID区", [172, 0, 183, 119], ["UID", "uid"]),
        # 加载文字 (500, 600, 300, 80)
        ("加载文字", [500, 600, 300, 80], ["加载", "載入", "Loading", "loading", "正在"]),
        # 点击继续 (400, 500, 500, 100)
        ("点击继续", [400, 500, 500, 100], ["点击", "點擊", "Continue", "Tap", "任意位置"]),
    ]
    for name, roi, expected in probes:
        try:
            ocr_param = JOCR(
                expected=expected,
                roi=roi,
                threshold=0.3,
                only_rec=False,  # 用 expected 过滤
            )
            ocr_job = tasker.post_recognition(JRecognitionType.OCR, ocr_param, img)
            detail = ocr_job.wait().get()
            hit_texts = []
            if detail:
                for node in detail.nodes:
                    if node.recognition and node.recognition.hit:
                        all_results = node.recognition.all_results
                        if all_results:
                            for r in all_results:
                                text = getattr(r, "text", "") or ""
                                score = getattr(r, "score", 0) or 0
                                if text:
                                    hit_texts.append(f"{text!r}(score={score:.2f})")
            status = "HIT" if hit_texts else "miss"
            print(f"  [{name}] {status} {hit_texts if hit_texts else ''}")
        except Exception as e:
            print(f"  [{name}] 异常: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
