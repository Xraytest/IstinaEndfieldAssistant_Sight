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

        PERSIST-01: is_stale 现仅用于触发 refresh() 检测 daemon 重启（CLI 崩溃后
        新 mmap），不再用于显示"已断开"。daemon 的 _recv_exact 已移除 max_stalls
        限制，server 存活时持续等待不重建会话，连接不会因编码器停滞而断开。
        max_age=10s 足以覆盖 CLI 崩溃后 auto-reconnect（1.5s）+ 新 daemon 启动
        + scrcpy 首帧（~5-8s）的周期。
        """
        if self._last_new_frame_gui_ts <= 0:
            return True
        return (time.time() - self._last_new_frame_gui_ts) > max_age

    def refresh(self) -> bool:
        """重新读取 info 文件，如果 daemon 已重启（新 mmap 路径）则切换到新 mmap。

        CLI 崩溃后 CLIBridge 自动重启 CLI 进程，新 daemon 写入同一个 info 文件
        （按 serial 命名），但 mmap 路径不同。本方法检测到路径变化后关闭旧 mmap
        并打开新 mmap，使 reader 无缝跟随 daemon 重启。

        Returns:
            True  — 检测到新 mmap 并成功切换
            False — info 文件不存在、打开失败、或路径未变化（daemon 未重启）
        """
        try:
            info = json.loads(Path(self._info_path).read_text(encoding="utf-8"))
            new_path = info.get("frame_mmap_path", "")
            new_size = int(info.get("frame_mmap_size", 0))
        except Exception:
            return False
        if not new_path or new_size <= 0:
            return False
        if new_path == self._frame_mmap_path and new_size == self._mmap_size:
            return False
        old_mm = self._mm
        old_fd = self._fd
        self._frame_mmap_path = new_path
        self._mmap_size = new_size
        self._last_frame_count = -1
        self._last_new_frame_gui_ts = 0.0
        try:
            flags = os.O_RDONLY
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            self._fd = os.open(self._frame_mmap_path, flags)
            self._mm = mmap.mmap(self._fd, self._mmap_size, access=mmap.ACCESS_READ)
            if old_mm is not None:
                try:
                    old_mm.close()
                except Exception:
                    pass
            if old_fd is not None:
                try:
                    os.close(old_fd)
                except Exception:
                    pass
            return True
        except Exception:
            self.stop()
            return False

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
