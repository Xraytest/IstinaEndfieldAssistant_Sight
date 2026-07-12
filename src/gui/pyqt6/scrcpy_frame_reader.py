"""ScrcpyFrameReader - 从 daemon 持久 mmap 零拷贝读取 scrcpy 视频帧。

daemon 侧的 _ScrcpySession._decode_loop 每解码一帧即通过 _on_frame 回调
写入预分配的持久 mmap（32B header + 像素数据）。GUI 进程通过本类直接读
同一 mmap 文件，无需 JSON-RPC、序列化或子进程开销，实现 30fps 流畅预览。
"""

from __future__ import annotations

import json
import mmap
import os
import struct
import time
from pathlib import Path
from typing import Optional

import numpy as np
from PyQt6.QtGui import QImage

from core.foundation.paths import get_cache_subdir

_HEADER_FORMAT = "<4siiiiQI"  # magic(4) + w(4) + h(4) + stride(4) + fmt(4) + ts(8) + count(4) = 32
_HEADER_SIZE = 32
_MAGIC = b"SCF1"


class ScrcpyFrameReader:
    """从 daemon 预分配的持久 mmap 读取 scrcpy 视频帧，零 RPC 零序列化。

    生命周期：
      - start()：读 info 文件获取 mmap 路径和大小，打开 mmap
      - read_frame()：读 header，frame_count 变化时读像素并转 QImage
      - stop()：关闭 mmap
    线程安全：仅限 GUI 主线程调用（QTimer 回调）。
    """

    def __init__(self, serial: str):
        safe = serial.replace(":", "_").replace("/", "_").replace("\\", "_")
        self._info_path = str(get_cache_subdir("ipc") / f"android-{safe}.info")
        self._frame_mmap_path: Optional[str] = None
        self._mm: Optional[mmap.mmap] = None
        self._fd: Optional[int] = None
        self._mmap_size: int = 0
        self._last_frame_count: int = -1
        self._last_frame_ts: float = 0.0
        # GUI 进程时钟：上次成功读到新帧的时刻。is_stale 基于此判断，而非
        # daemon 写入的 ts（int 截断 + 编码器停滞时 ts 不更新，会导致误判）。
        self._last_new_frame_gui_ts: float = 0.0

    def start(self) -> bool:
        """读 info 文件，打开 frame mmap。成功返回 True。"""
        self.stop()
        try:
            info = json.loads(Path(self._info_path).read_text(encoding="utf-8"))
            self._frame_mmap_path = info.get("frame_mmap_path", "")
            self._mmap_size = int(info.get("frame_mmap_size", 0))
        except Exception:
            return False
        if not self._frame_mmap_path or self._mmap_size <= 0:
            return False
        try:
            flags = os.O_RDONLY
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            self._fd = os.open(self._frame_mmap_path, flags)
            self._mm = mmap.mmap(self._fd, self._mmap_size, access=mmap.ACCESS_READ)
            return True
        except Exception:
            self.stop()
            return False

    def read_frame(self) -> Optional[QImage]:
        """读取最新帧。无新帧返回 None（调用方应跳过不更新画面）。"""
        if self._mm is None:
            return None
        try:
            magic = self._mm[0:4]
            if magic != _MAGIC:
                return None
            _, w, h, stride, _fmt, ts, count = struct.unpack_from(_HEADER_FORMAT, self._mm, 0)
        except Exception:
            return None
        if w <= 0 or h <= 0 or stride <= 0:
            return None
        if 32 + h * stride > self._mmap_size:
            return None
        if count == self._last_frame_count:
            return None
        self._last_frame_count = count
        self._last_frame_ts = float(ts)
        self._last_new_frame_gui_ts = time.time()
        pixel_size = h * stride
        try:
            raw = self._mm[32:32 + pixel_size]
            arr = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 3)
            rgb = arr[..., ::-1].copy()
            img = QImage(rgb.data, w, h, stride, QImage.Format.Format_RGB888)
            return img.copy()
        except Exception:
            return None

    def is_stale(self, max_age: float = 10.0) -> bool:
        """超过 max_age 秒未读到新帧视为过期（基于 GUI 时钟，非 daemon 时钟）。

        使用 GUI 时钟而非 daemon 写入的 ts，因为 daemon 的 ts 是 int(time.time())
        秒级截断，且编码器停滞时 ts 不更新，导致 is_stale 误判。
        """
        if self._last_new_frame_gui_ts <= 0:
            return True
        return (time.time() - self._last_new_frame_gui_ts) > max_age

    def stop(self) -> None:
        if self._mm is not None:
            try:
                self._mm.close()
            except Exception:
                pass
            self._mm = None
        if self._fd is not None:
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None
        self._last_frame_count = -1
        self._last_frame_ts = 0.0
        self._last_new_frame_gui_ts = 0.0
