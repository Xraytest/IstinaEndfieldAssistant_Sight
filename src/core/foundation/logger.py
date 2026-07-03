"""日志系统模块

提供项目统一的日志初始化和管理功能。
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional


class LogCategory:
    """日志分类枚举

    用于区分不同模块的日志输出，便于过滤和分析。
    """
    MAIN = "MAIN"
    ADB = "ADB"
    COMMUNICATION = "COMMUNICATION"
    EXECUTION = "EXECUTION"
    AUTHENTICATION = "AUTHENTICATION"
    GUI = "GUI"
    EXCEPTION = "EXCEPTION"
    PERFORMANCE = "PERFORMANCE"


# 全局日志初始化状态标记
_logger_initialized: bool = False


def init_logger(
    log_dir: Optional[Path] = None,
    log_level: int = logging.INFO,
    console_level: int = logging.WARNING,
) -> None:
    """初始化项目日志系统

    创建日志目录和文件处理器，设置全局日志级别。
    必须在任何 get_logger() 或日志调用之前调用。

    Args:
        log_dir: 日志文件存放目录，默认为项目根目录下的 logs/
        log_level: 文件日志级别，默认为 INFO
        console_level: 控制台日志级别，默认为 WARNING
    """
    global _logger_initialized

    if _logger_initialized:
        return

    # 自包含路径：logger.py 位于 src/core/foundation/
    project_root = Path(__file__).resolve().parent.parent.parent.parent

    if log_dir is None:
        log_dir = project_root / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)

    # 创建日志文件路径
    log_file = log_dir / "main.log"

    # 配置根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除已有处理器，避免重复添加
    root_logger.handlers.clear()

    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(funcName)s:%(lineno)d] [%(threadName)s] [-] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_formatter = logging.Formatter("[%(levelname)s] [%(name)s] %(message)s")
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    _logger_initialized = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """获取日志记录器

    如果尚未调用 init_logger()，会自动调用一次默认初始化。

    Args:
        name: logger 名称，通常使用 __name__

    Returns:
        logging.Logger 实例
    """
    global _logger_initialized

    if not _logger_initialized:
        init_logger()

    return logging.getLogger(name)


__all__ = ["LogCategory", "init_logger", "get_logger"]
