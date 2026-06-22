"""基础层 — 无内部依赖的底层模块

包含：utils（路径工具）、logger（日志系统）、game_data（游戏坐标）
"""

from .utils.paths import (
    get_project_root,
    get_src_dir,
    get_config_dir,
    get_cache_dir,
    get_data_dir,
    get_3rd_party_dir,
    get_client_config_path,
    ensure_src_path,
    ensure_path,
    get_adb_path,
)

from .logger.logger import (
    get_logger,
    init_logger,
    LogLevel,
    LogCategory,
    ClientLogger,
    LogRecord,
    LogFormatter,
    JSONLogFormatter,
    LogHandler,
    ConsoleHandler,
    FileHandler,
    GUIHandler,
    LogRotator,
    PerformanceMonitor,
)

from .game_data.game_coords import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    ADB_WIDTH,
    ADB_HEIGHT,
    TOP_BAR_Y_RANGE,
    OVERLAY_ROI,
    Coords,
    TOP_BAR_BUTTONS,
    OVERLAY_KEYWORDS,
    xy_str,
    lookup_button,
    coords_for_model,
)

__all__ = [
    # utils
    "get_project_root", "get_src_dir", "get_config_dir", "get_cache_dir",
    "get_data_dir", "get_3rd_party_dir", "get_client_config_path",
    "ensure_src_path", "ensure_path", "get_adb_path",
    # logger
    "get_logger", "init_logger", "LogLevel", "LogCategory",
    "ClientLogger", "LogRecord", "LogFormatter", "JSONLogFormatter",
    "LogHandler", "ConsoleHandler", "FileHandler", "GUIHandler",
    "LogRotator", "PerformanceMonitor",
    # game_data
    "SCREEN_WIDTH", "SCREEN_HEIGHT", "ADB_WIDTH", "ADB_HEIGHT",
    "TOP_BAR_Y_RANGE", "OVERLAY_ROI", "Coords", "TOP_BAR_BUTTONS",
    "OVERLAY_KEYWORDS", "xy_str", "lookup_button", "coords_for_model",
]
