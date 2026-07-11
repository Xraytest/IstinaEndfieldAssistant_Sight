"""PyQt 全页面离屏渲染模块

渲染完整的 MaaEndControlPage，在 offscreen 平台下截图取证。
- 不启动任何 CLI 子进程（桥接器已 stub）
- 不连接任何设备
- 使用缓存数据填充列表

用法:
  python -m ToolBox.pyqt_renderer <output.png> [--width W] [--height H]
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

from gui.pyqt6.pages.maaend_control_page import MaaEndControlPage


class StubBridge(QObject):
    """CLIBridge 的无头替代品：不启动任何子进程，立即返回空结果。"""

    commandFinished = pyqtSignal(str, dict)
    commandError = pyqtSignal(str, str)
    processCrashed = pyqtSignal(int)
    logMessage = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> None:
        # 立即返回空成功结果，不启动任何进程
        QTimer.singleShot(0, lambda: self.commandFinished.emit(command, {"status": "success"}))

    def set_interactive(self, interactive: bool) -> None:
        pass


def _load_cached_metadata() -> dict:
    """尝试加载已缓存的 metadata，供渲染使用。"""
    cache_paths = [
        _PROJECT_ROOT / "cache" / "maaend_metadata_cache.json",
        _PROJECT_ROOT / "config" / "maaend_metadata_cache.json",
    ]
    for p in cache_paths:
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def render_page(output: str, width: int = 1280, height: int = 800) -> None:
    """渲染完整的 MaaEndControlPage 到 PNG。"""
    app = QApplication.instance() or QApplication(sys.argv)

    # 创建 stub bridge（不启动任何 CLI 进程）
    bridge = StubBridge()

    # 创建页面
    page = MaaEndControlPage(bridge=bridge)
    page.resize(width, height)

    # 注入缓存数据，避免空列表
    cached = _load_cached_metadata()
    if cached:
        page._tasks_cache = cached.get("tasks", {})
        page._presets_cache = cached.get("presets", {})
        page._task_option_defs = cached.get("task_option_defs", {})

    # 阻止 _delayed_init 中的真实 CLI 调用
    page._auto_connect_attempted = True  # 跳过自动连接
    page._connected = False

    page.show()

    # 处理事件让布局完成
    for _ in range(10):
        QApplication.processEvents()
        time.sleep(0.05)

    # 手动触发一次刷新（用缓存数据）
    page.refresh()
    for _ in range(10):
        QApplication.processEvents()
        time.sleep(0.05)

    # 打印关键按钮尺寸
    stop_btn = page._stop_btn
    exec_btn = page._retry_btn
    print(f"\n[Stop]     geometry={stop_btn.geometry().width()}x{stop_btn.geometry().height()}, "
          f"minH={stop_btn.minimumHeight()}, maxH={stop_btn.maximumHeight()}, h={stop_btn.height()}")
    print(f"[Execute]  geometry={exec_btn.geometry().width()}x{exec_btn.geometry().height()}, "
          f"minH={exec_btn.minimumHeight()}, maxH={exec_btn.maximumHeight()}, h={exec_btn.height()}")
    diff = stop_btn.height() - exec_btn.height()
    print(f">>> 高度差 = {diff}px {'✓' if diff == 0 else '⚠ 不等高'}")

    # 截图
    img = QImage(page.size(), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.white)
    painter = QPainter(img)
    page.render(painter)
    painter.end()

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_path))
    print(f"\n📸 截图已保存 -> {out_path}")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Render full MaaEndControlPage (headless)")
    parser.add_argument("output", nargs="?", default="render_page.png", help="Output PNG path")
    parser.add_argument("--width", type=int, default=1280, help="Page width")
    parser.add_argument("--height", type=int, default=800, help="Page height")
    args = parser.parse_args()

    render_page(args.output, args.width, args.height)


if __name__ == "__main__":
    main()
