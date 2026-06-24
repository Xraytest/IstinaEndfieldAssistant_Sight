"""
重试机制 - 移植自 StarRailCopilot
"""
import time
import functools
from typing import Callable, Any

from core.foundation.logger import get_logger, LogCategory

# 重试次数
RETRY_TRIES = 5

# 重试等待时间（秒）序列
RETRY_SLEEP = [0, 1, 2, 5, 10]  # 索引 0-4，对应第1-5次重试


def retry_sleep(retry_count: int) -> float:
    """
    获取指定重试次数的等待时间

    Args:
        retry_count: 当前重试次数（从0开始）

    Returns:
        等待秒数
    """
    if retry_count < len(RETRY_SLEEP):
        return RETRY_SLEEP[retry_count]
    return RETRY_SLEEP[-1]  # 最大等待时间


def retry(func: Callable) -> Callable:
    """
    重试装饰器

    自动处理常见异常并重试：
    - ConnectionResetError: ADB 服务器断开
    - AdbError: ADB 命令错误
    - ImageTruncated: 图像数据不完整
    - PackageNotInstalled: 应用未安装
    - 其他异常也会重试（除了 RequestHumanTakeover）

    Args:
        func: 要装饰的函数

    Returns:
        装饰后的函数
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        logger = getattr(self, 'logger', get_logger())
        init = None

        for attempt in range(RETRY_TRIES):
            try:
                if callable(init):
                    time.sleep(retry_sleep(attempt))
                    init()
                return func(self, *args, **kwargs)

            # 不需要重试的异常
            except Exception as e:
                # 判断是否需要重试
                if _should_retry_exception(e):
                    logger.debug(LogCategory.MAIN, f"重试 {func.__name__} ({attempt + 1}/{RETRY_TRIES})",
                                error=str(e))

                    # 设置重试前的初始化函数
                    init = _get_retry_init(e, self)
                else:
                    # 直接抛出，不重试
                    raise

        logger.critical(f"重试 {func.__name__} 失败，已达最大重试次数")
        raise RuntimeError(f"重试失败: {func.__name__}")

    return wrapper


def _should_retry_exception(exception: Exception) -> bool:
    """
    判断异常是否应该重试

    Args:
        exception: 异常对象

    Returns:
        True 表示应该重试，False 表示不应该
    """
    from adbutils.errors import AdbError

    # 这些异常类型应该重试
    retryable_types = (
        ConnectionResetError,  # ADB 服务器断开
        AdbError,             # ADB 命令错误
    )

    if isinstance(exception, retryable_types):
        return True

    # 自定义异常类名称判断
    exception_name = type(exception).__name__
    if exception_name in ('ImageTruncated', 'PackageNotInstalled', 'RequestHumanTakeover'):
        # 这些异常通常也应该重试，除了明确的接管请求
        return exception_name != 'RequestHumanTakeover'

    # 其他未知异常也尝试重试（保守策略）
    return True


def _get_retry_init(exception: Exception, obj: Any) -> Optional[Callable]:
    """
    根据异常类型获取重试前的初始化函数

    Args:
        exception: 捕获到的异常
        obj: 异常发生的对象实例

    Returns:
        初始化函数或 None
    """
    from adbutils.errors import AdbError

    if isinstance(exception, ConnectionResetError):
        # ADB 服务器断开，尝试重连
        def init():
            if hasattr(obj, 'adb_reconnect'):
                obj.adb_reconnect()
            elif hasattr(obj, 'adb_manager') and hasattr(obj.adb_manager, 'start_server'):
                obj.adb_manager.start_server()
        return init

    elif isinstance(exception, AdbError):
        # ADB 错误，尝试重连
        def init():
            if hasattr(obj, 'adb_reconnect'):
                obj.adb_reconnect()
            elif hasattr(obj, 'adb_manager') and hasattr(obj.adb_manager, 'start_server'):
                obj.adb_manager.start_server()
        return init

    # 其他异常，无特殊初始化
    return None