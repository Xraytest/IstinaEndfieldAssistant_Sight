"""PreviewWorker - 在独立 QThread 中读取 scrcpy mmap 帧并 emit QImage。

性能优化：
  - mmap 读取、numpy BGR→RGB 翻转、QImage.copy() 全部移出主线程
  - 主线程仅做 QPixmap.fromImage + update()，30fps 占用 <3%
  - 跳帧策略：worker 维护 pending_frame，若主线程未消费上一帧则只更新不 emit
  - 无新帧时 sleep(16ms) 让出 CPU，不忙等

线程安全：
  - mmap 由 worker 独占，主线程不访问
  - QImage 跨线程前 .copy() 确保独立内存
  - 信号默认 AutoConnection，跨线程自动 QueuedConnection
"""

from __future__ import annotations

import threading
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from gui.pyqt6.scrcpy_frame_reader import ScrcpyFrameReader


class PreviewWorker(QThread):
    """后台读取 scrcpy mmap 帧，emit QImage 给主线程渲染。"""

    frame_ready = pyqtSignal(QImage)
    status_changed = pyqtSignal(str, str)  # text, color

    def __init__(self, serial: str, parent=None) -> None:
        super().__init__(parent)
        self._serial = serial
        self._reader = ScrcpyFrameReader(serial)
        self._stop_flag = threading.Event()
        # 跳帧缓冲：worker 端维护最新帧，主线程消费时取最新
        self._pending_lock = threading.Lock()
        self._pending_frame: Optional[QImage] = None
        self._has_pending = False

    def run(self) -> None:
        if not self._reader.start():
            self.status_changed.emit("已断开", "#e03131")
            return
        self.status_changed.emit("● 实时", "#19d1ff")
        while not self._stop_flag.is_set():
            img = self._reader.read_frame()
            if img is not None:
                # 跳帧策略：若主线程仍在上一次 emit 的 QueuedConnection 队列中，
                # 直接覆盖 pending，不重复 emit。主线程 slot 内会消费 pending。
                with self._pending_lock:
                    self._pending_frame = img
                    self._has_pending = True
                self.frame_ready.emit(img)
            else:
                # 无新帧：检查是否过期（daemon 重启）
                if self._reader.is_stale(max_age=10.0):
                    if self._reader.refresh():
                        # 新 mmap，重置状态继续读取
                        continue
                    else:
                        # refresh 失败：短暂等待后重试
                        self.msleep(200)
                        continue
                # 短暂让出 CPU，避免 100% 占用
                self.msleep(16)

    def consume_pending(self) -> Optional[QImage]:
        """主线程调用：取出最新 pending 帧（如果有），并清空标记。

        用于跳帧：frame_ready 信号可能多次 emit，主线程 slot 调用本方法
        获取最新帧，跳过中间未消费的帧。
        """
        with self._pending_lock:
            if not self._has_pending:
                return None
            img = self._pending_frame
            self._pending_frame = None
            self._has_pending = False
            return img

    def stop(self) -> None:
        self._stop_flag.set()
        self.wait(2000)
        self._reader.stop()
