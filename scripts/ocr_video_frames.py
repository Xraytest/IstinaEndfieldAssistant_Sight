"""视频抽帧 + OCR：用于核对任务「标记完成」时画面是否真的处于预期状态。

输入：cache/recordings/queue_run_*.mp4
输出：
  - cache/recordings/<sample_dir>/t{SSS}s.png  （抽帧图片）
  - cache/recordings/<sample_dir>/ocr_report.json  （每帧 OCR 文本 + 命中关键词）

OCR 引擎优先级：easyocr（轻量、纯 onnxruntime）> paddleocr（备选）。
默认每 2 秒抽一帧；可指定 --interval-s 调整。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, List, Tuple

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

# 大世界主城特征关键词（与 src/core/service/runtime.py:_IN_WORLD_OCR_KEYWORDS 对齐）
# 注意：「寻访」已于 2026-07-22 移除（签到弹窗"踞渊北眺寻访凭证"会误匹配）
IN_WORLD_KEYWORDS = [
    "地区建设", "干员", "采购中心", "行动手册",
    "通行证", "好友", "装备加工", "编队", "百科", "档案库", "探索",
]
# 登录/加载中特征关键词
LOADING_KEYWORDS = [
    "点击", "任意", "位置", "继续", "Continue", "Tap", "anywhere",
    "LOAD", "ING", "loading", "Now", "現在",
    "UID", "登录", "登入", "Login",
    "重新挑战", "检查网络", "Check", "Network",
]
# 已知采集/任务完成弹窗关键词
COMPLETION_KEYWORDS = [
    "获得", "采集成功", "收取成功", "已采集", "奖励",
    "完成", "已领取", "已获得",
]


def _sanitize(text: str) -> str:
    """去除 OCR 文本中的空白与控制字符，便于关键词匹配。"""
    return re.sub(r"\s+", "", text)


def _match_keywords(text: str, keywords: List[str]) -> List[str]:
    sanitized = _sanitize(text)
    return [kw for kw in keywords if kw in sanitized]


def _init_easyocr():
    import easyocr
    # ch_sim+en，GPU 优先，无 GPU 回退 CPU
    try:
        reader = easyocr.Reader(["ch_sim", "en"], gpu=True)
        # 探测一次以确保模型加载成功
        reader.readtext(np.zeros((720, 1280, 3), dtype=np.uint8))
        return reader, "easyocr(gpu)"
    except Exception as e:
        print(f"[ocr_video_frames] easyocr GPU 初始化失败，回退 CPU: {e}", file=sys.stderr)
        reader = easyocr.Reader(["ch_sim", "en"], gpu=False)
        return reader, "easyocr(cpu)"


def _init_paddleocr():
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    return ocr, "paddleocr"


def _ocr_frame_easyocr(reader, frame_bgr: np.ndarray) -> str:
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    results = reader.readtext(frame_rgb, detail=0, paragraph=True)
    return "\n".join(results)


def _ocr_frame_paddleocr(ocr, frame_bgr: np.ndarray) -> str:
    result = ocr.ocr(frame_bgr, cls=True)
    texts: List[str] = []
    if result and result[0]:
        for line in result[0]:
            if line and len(line) >= 2:
                txt = line[1][0] if isinstance(line[1], (list, tuple)) else str(line[1])
                texts.append(txt)
    return "\n".join(texts)


def extract_and_ocr(
    video_path: Path,
    out_dir: Path,
    interval_s: float = 2.0,
    engine: str = "auto",
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration_s = total_frames / fps if fps > 0 else 0.0
    print(f"[ocr_video_frames] video={video_path.name} fps={fps:.2f} "
          f"frames={total_frames} duration={duration_s:.1f}s interval={interval_s}s")

    # 初始化 OCR 引擎
    ocr_obj, ocr_name = (None, None)
    if engine in ("auto", "easyocr"):
        try:
            ocr_obj, ocr_name = _init_easyocr()
        except Exception as e:
            print(f"[ocr_video_frames] easyocr 初始化失败: {e}", file=sys.stderr)
            if engine == "easyocr":
                raise
    if ocr_obj is None and engine in ("auto", "paddleocr"):
        ocr_obj, ocr_name = _init_paddleocr()
    if ocr_obj is None:
        raise RuntimeError("无可用 OCR 引擎（easyocr/paddleocr 均不可用）")
    print(f"[ocr_video_frames] OCR 引擎: {ocr_name}")

    # 选择 OCR 函数
    if "easyocr" in ocr_name:
        ocr_fn = lambda f: _ocr_frame_easyocr(ocr_obj, f)
    else:
        ocr_fn = lambda f: _ocr_frame_paddleocr(ocr_obj, f)

    # 抽帧 + OCR
    step_frames = max(1, int(round(interval_s * fps)))
    samples: List[dict] = []
    frame_idx = 0
    t_extract_start = time.time()
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % step_frames == 0:
            ts_s = frame_idx / fps if fps > 0 else 0.0
            ts_tag = f"t{int(round(ts_s)):03d}s"
            img_path = out_dir / f"{ts_tag}.png"
            cv2.imwrite(str(img_path), frame)
            try:
                text = _ocr_frame_paddleocr(ocr_obj, frame) if "paddleocr" in ocr_name else _ocr_frame_easyocr(ocr_obj, frame)
            except Exception as e:
                text = f"<OCR ERROR: {e}>"
            in_world_hits = _match_keywords(text, IN_WORLD_KEYWORDS)
            loading_hits = _match_keywords(text, LOADING_KEYWORDS)
            completion_hits = _match_keywords(text, COMPLETION_KEYWORDS)
            samples.append({
                "t_s": round(ts_s, 2),
                "frame_idx": frame_idx,
                "img_path": str(img_path.relative_to(ROOT)),
                "ocr_text": text,
                "ocr_preview": text[:200],
                "in_world_hits": in_world_hits,
                "loading_hits": loading_hits,
                "completion_hits": completion_hits,
                "state_guess": _guess_state(in_world_hits, loading_hits, completion_hits, text),
            })
        frame_idx += 1
    cap.release()
    elapsed = time.time() - t_extract_start

    report = {
        "video_path": str(video_path.relative_to(ROOT)) if video_path.is_relative_to(ROOT) else str(video_path),
        "fps": fps,
        "total_frames": total_frames,
        "duration_s": round(duration_s, 2),
        "interval_s": interval_s,
        "ocr_engine": ocr_name,
        "sample_count": len(samples),
        "ocr_elapsed_s": round(elapsed, 2),
        "in_world_keywords": IN_WORLD_KEYWORDS,
        "loading_keywords": LOADING_KEYWORDS,
        "completion_keywords": COMPLETION_KEYWORDS,
        "samples": samples,
    }
    report_path = out_dir / "ocr_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ocr_video_frames] 报告已写入: {report_path}")
    print(f"[ocr_video_frames] 抽帧 {len(samples)} 张，OCR 耗时 {elapsed:.1f}s")

    # 打印简要时间线
    print("\n=== 时间线简要 ===")
    for s in samples:
        marker = ""
        if s["state_guess"] == "in_world":
            marker = " [IN-WORLD]"
        elif s["state_guess"] == "loading":
            marker = " [LOADING]"
        elif s["state_guess"] == "login":
            marker = " [LOGIN]"
        elif s["state_guess"] == "completion":
            marker = " [COMPLETION]"
        print(f"  t={s['t_s']:6.1f}s  state={s['state_guess']:12s}{marker}  "
              f"hits=in:{s['in_world_hits']} load:{s['loading_hits']} done:{s['completion_hits']}  "
              f"txt={s['ocr_preview'][:60]!r}")
    return report


def _guess_state(in_world_hits, loading_hits, completion_hits, text: str) -> str:
    """根据 OCR 命中关键词猜测画面状态。"""
    if in_world_hits and not loading_hits:
        return "in_world"
    if loading_hits:
        # 进一步区分登录 vs 加载
        for kw in ("点击", "任意", "位置", "继续", "Continue", "Tap", "anywhere", "UID", "登录", "Login"):
            if kw in _sanitize(text):
                return "login"
        return "loading"
    if completion_hits:
        return "completion"
    if not text.strip():
        return "black"
    return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", help="视频文件路径（mp4）")
    parser.add_argument("--out-dir", default=None,
                        help="输出目录（默认 cache/recordings/<video_stem>_samples）")
    parser.add_argument("--interval-s", type=float, default=2.0,
                        help="抽帧间隔（秒，默认 2.0）")
    parser.add_argument("--engine", choices=["auto", "easyocr", "paddleocr"], default="auto")
    args = parser.parse_args()

    video_path = Path(args.video).resolve()
    if not video_path.is_file():
        print(f"视频文件不存在: {video_path}", file=sys.stderr)
        return 1
    if args.out_dir:
        out_dir = Path(args.out_dir).resolve()
    else:
        out_dir = video_path.parent / f"{video_path.stem}_samples"

    extract_and_ocr(video_path, out_dir, interval_s=args.interval_s, engine=args.engine)
    return 0


if __name__ == "__main__":
    sys.exit(main())
