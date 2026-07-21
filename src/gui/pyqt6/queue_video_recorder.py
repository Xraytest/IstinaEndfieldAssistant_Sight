"""QueueVideoRecorder - 录制队列执行期间的设备帧为 MP4 视频。

设计要点：
  - 独立 ScrcpyFrameReader 实例（与 PreviewWorker 解耦，互不影响）
  - 后台线程轮询 mmap 新帧，写入 cv2.VideoWriter
  - 视频编码：mp4v（OpenCV 默认，兼容性最好，无 ffmpeg 依赖）
  - 帧率：目标 15fps，实际帧率取决于 scrcpy 推流频率（避免重复帧填充黑屏）
  - 输出路径：cache/recordings/queue_run_YYYYMMDD_HHMMSS.mp4

线程安全：
  - start() 在主线程调用，启动后台录制线程
  - stop() 在主线程调用，设置停止标志并 join 线程
  - 录制线程独占 ScrcpyFrameReader，无并发读取冲突
"""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Optional

import cv2
import numpy as np

from core.foundation.logger import get_logger
from core.foundation.paths import get_cache_subdir
from gui.pyqt6.scrcpy_frame_reader import ScrcpyFrameReader


class QueueVideoRecorder:
    """录制队列执行期间的设备帧为 MP4 视频。

    使用独立的 ScrcpyFrameReader 实例读取 mmap，不干扰预览。每个队列执行
    生成一个独立视频文件，文件名含时间戳。
    """

    TARGET_FPS = 15
    # 帧轮询间隔：scrcpy 默认 30fps，我们 16ms 轮询一次以避免漏帧
    POLL_INTERVAL_S = 0.033

    def __init__(self, serial: str) -> None:
        self._serial = serial
        self._logger = get_logger(__name__)
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._reader: Optional[ScrcpyFrameReader] = None
        self._writer: Optional[cv2.VideoWriter] = None
        self._output_path: Optional[str] = None
        self._lock = threading.Lock()
        self._frame_count = 0
        self._start_ts: float = 0.0

    @property
    def output_path(self) -> Optional[str]:
        return self._output_path

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def start(self) -> bool:
        """启动录制。若 ScrcpyFrameReader 启动失败则返回 False（不阻塞队列执行）。"""
        if self._thread is not None:
            return True  # already running
        # 准备输出目录和文件名
        recordings_dir = get_cache_subdir("recordings")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._output_path = str(recordings_dir / f"queue_run_{ts}.mp4")

        # 先启动 reader，从 header 推断宽高用于 VideoWriter 初始化
        self._reader = ScrcpyFrameReader(self._serial)
        if not self._reader.start():
            self._logger.warning("QueueVideoRecorder: ScrcpyFrameReader 启动失败，跳过录制")
            self._reader = None
            return False

        self._stop_flag.clear()
        self._frame_count = 0
        self._start_ts = time.time()
        self._thread = threading.Thread(target=self._run, name="QueueVideoRecorder", daemon=True)
        self._thread.start()
        self._logger.info("QueueVideoRecorder: 录制开始", path=self._output_path, serial=self._serial)
        return True

    def stop(self) -> Optional[str]:
        """停止录制并 finalize 视频文件。返回输出文件路径（或 None 失败时）。"""
        if self._thread is None:
            return None
        self._stop_flag.set()
        self._thread.join(timeout=5.0)
        self._thread = None
        with self._lock:
            if self._writer is not None:
                try:
                    self._writer.release()
                except Exception:
                    pass
                self._writer = None
            if self._reader is not None:
                try:
                    self._reader.stop()
                except Exception:
                    pass
                self._reader = None
        duration = time.time() - self._start_ts if self._start_ts else 0.0
        self._logger.info(
            "QueueVideoRecorder: 录制结束",
            path=self._output_path,
            frames=self._frame_count,
            duration_s=round(duration, 2),
        )
        return self._output_path

    def _run(self) -> None:
        """录制线程主循环：轮询 mmap 新帧写入 VideoWriter。"""
        # VideoWriter 延迟初始化：首帧到达后才知宽高
        writer_initialized = False
        last_poll = time.time()
        while not self._stop_flag.is_set():
            try:
                frame = self._reader.read_frame_bgr() if self._reader else None
            except Exception as exc:
                self._logger.warning("QueueVideoRecorder: 读取帧异常", error=str(exc))
                frame = None

            if frame is not None:
                if not writer_initialized:
                    h, w = frame.shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    with self._lock:
                        self._writer = cv2.VideoWriter(
                            self._output_path, fourcc, self.TARGET_FPS, (w, h)
                        )
                    writer_initialized = True
                    self._logger.info(
                        "QueueVideoRecorder: VideoWriter 初始化",
                        width=w, height=h, fps=self.TARGET_FPS,
                    )
                if self._writer is not None:
                    try:
                        self._writer.write(frame)
                        self._frame_count += 1
                    except Exception as exc:
                        self._logger.warning("QueueVideoRecorder: 写入帧异常", error=str(exc))
            else:
                # 检测 daemon 重启（CLI 崩溃后新 mmap）
                if self._reader and self._reader.is_stale(max_age=10.0):
                    if self._reader.refresh():
                        self._logger.info("QueueVideoRecorder: 检测到 daemon 重启，已切换到新 mmap")
                    else:
                        # refresh 失败：等待外部 stop 或 daemon 恢复
                        pass

            # 控制轮询频率，避免 100% CPU
            elapsed = time.time() - last_poll
            sleep_s = self.POLL_INTERVAL_S - elapsed
            if sleep_s > 0:
                time.sleep(sleep_s)
            last_poll = time.time()
