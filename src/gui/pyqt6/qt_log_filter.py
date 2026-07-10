"""将 Qt 自身的日志输出（如 qt.qpa.fonts / qt.text.font.db 的字体警告）重定向到独立日志文件。

Qt 的字体警告通过 qCWarning 直接打印到 stderr，绕过了项目的 Python 日志系统，
因此会混入控制台与「标准推理页」的执行日志流。这里用 qInstallMessageHandler 接管：

- 良性的字体/调试类警告（QtWarning/Info/Debug）只写入 logs/qt.log，不进 stderr、不进 main.log；
- 真正的 QtCritical/QtFatal 错误仍会打印到 stderr，保证严重问题不被淹没。

这样字体噪声既不污染控制台，也不与执行日志混杂，仅保留在日志文件中。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PyQt6.QtCore import QMessageLogContext, QtMsgType, qInstallMessageHandler

_INSTALLED = False


def _qt_message_handler(
    msg_type: QtMsgType,
    context: QMessageLogContext,
    message: str,
) -> None:
    logger = logging.getLogger("qt")

    if msg_type in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
        # 严重错误仍保留到控制台，避免真实故障被静默吞掉
        category = context.category if context is not None else ""
        prefix = f"[{category}] " if category else ""
        sys.stderr.write(f"Qt {msg_type.name}: {prefix}{message}\n")
        sys.stderr.flush()
        logger.error("%s%s", prefix, message)
        return

    # 良性警告/信息/调试：仅写入 qt.log
    if msg_type in (QtMsgType.QtWarningMsg, QtMsgType.QtInfoMsg):
        level = logging.INFO
    else:  # QtDebugMsg
        level = logging.DEBUG

    category = context.category if context is not None else ""
    logger.log(level, "[%s] %s", category, message)


def install_qt_message_filter() -> None:
    """安装 Qt 消息过滤器，将 Qt 日志重定向到 logs/qt.log。

    必须在 QApplication() / 任何控件构造之前调用，以捕获最早的字体探测噪声。
    幂等：重复调用不会重复安装。
    """
    global _INSTALLED
    if _INSTALLED:
        return

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    log_dir = project_root / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # 无法建目录时不阻塞启动，Qt 日志退回默认 stderr 行为
        _INSTALLED = True
        return

    qt_logger = logging.getLogger("qt")
    if not qt_logger.handlers:
        qt_logger.setLevel(logging.DEBUG)
        # 不向 root 传播，避免进入控制台 handler 与 main.log
        qt_logger.propagate = False
        try:
            handler = logging.FileHandler(log_dir / "qt.log", encoding="utf-8")
            handler.setFormatter(
                logging.Formatter(
                    "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            qt_logger.addHandler(handler)
        except OSError:
            # 文件不可写则放弃接管，退回默认行为
            _INSTALLED = True
            return

    qInstallMessageHandler(_qt_message_handler)
    _INSTALLED = True
