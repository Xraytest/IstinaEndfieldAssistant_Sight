"""
卡死与连点检测器 - 移植自 StarRailCopilot
监控操作频率，检测异常情况并触发保护
"""
import time
from collections import deque, Counter
from typing import Deque, Optional
from itertools import islice

from core.foundation.logger import get_logger, LogCategory

logger = get_logger()


class StuckDetector:
    """
    卡死与连点检测器

    功能：
    1. 卡死检测：监控操作间隔，超过阈值触发
    2. 连点检测：记录最近点击，检测异常频率
    3. 异常记录：记录触发异常的按钮，用于上下文分析
    """

    def __init__(self,
                 stuck_timeout: float = 60.0,
                 click_history_size: int = 30,
                 max_clicks_in_15: int = 12,
                 max_two_buttons_in_15: int = 6):
        """
        初始化检测器

        Args:
            stuck_timeout: 卡死超时时间（秒）
            click_history_size: 点击历史记录长度
            max_clicks_in_15: 15次点击中同一按钮的最大次数
            max_two_buttons_in_15: 15次点击中两个按钮各出现6次以上的阈值
        """
        self.stuck_timeout = stuck_timeout
        self.click_history_size = click_history_size
        self.max_clicks_in_15 = max_clicks_in_15
        self.max_two_buttons_in_15 = max_two_buttons_in_15

        # 状态
        self.stuck_timer = time.time()
        self.click_record: Deque[str] = deque(maxlen=click_history_size)
        self.detect_record = set()  # 正在检测的按钮集合

        self.logger = logger

    def record_operation(self, operation: str = "click"):
        """
        记录一次操作（用于卡死检测）

        Args:
            operation: 操作类型（用于扩展）
        """
        self.stuck_timer = time.time()

    def record_click(self, button: str):
        """
        记录点击事件

        Args:
            button: 按钮名称或标识
        """
        self.click_record.append(str(button))

    def add_detect(self, button: str):
        """
        添加正在检测的按钮

        Args:
            button: 按钮标识
        """
        self.detect_record.add(str(button))

    def clear_detect(self):
        """清空检测记录"""
        self.detect_record.clear()

    def reset_stuck_timer(self):
        """重置卡死计时器"""
        self.stuck_timer = time.time()

    def check_stuck(self) -> Optional[str]:
        """
        检查是否卡死

        Returns:
            卡死原因描述，或 None（未卡死）
        """
        elapsed = time.time() - self.stuck_timer

        if elapsed >= self.stuck_timeout:
            self.logger.warning(LogCategory.MAIN, "检测到卡死",
                               elapsed_seconds=round(elapsed, 1),
                               waiting_for=list(self.detect_record))
            self.clear_detect()
            return f"卡死：{elapsed:.1f}秒无有效操作"

        return None

    def check_click_spam(self) -> Optional[str]:
        """
        检查连点异常

        检查最近15次点击：
        - 同一按钮出现超过 max_clicks_in_15 次
        - 两个按钮各出现超过 max_two_buttons_in_15 次

        Returns:
            异常描述，或 None（无异常）
        """
        if len(self.click_record) < 15:
            return None

        # 取最近15次
        recent_15 = list(islice(self.click_record, 0, 15))
        counter = Counter(recent_15)
        most_common = counter.most_common(2)

        if most_common[0][1] >= self.max_clicks_in_15:
            # 单个按钮点击过于频繁
            button = most_common[0][0]
            count = most_common[0][1]
            self.logger.warning(LogCategory.MAIN, "检测到连点",
                               button=button,
                               count_in_15=count,
                               threshold=self.max_clicks_in_15)
            self.click_record.clear()
            return f"连点：按钮 {button} 在15次点击中出现{count}次"

        if len(most_common) >= 2 and most_common[0][1] >= self.max_two_buttons_in_15 \
                and most_common[1][1] >= self.max_two_buttons_in_15:
            # 两个按钮交替频繁
            button1, count1 = most_common[0]
            button2, count2 = most_common[1]
            self.logger.warning(LogCategory.MAIN, "检测到交替连点",
                               button1=button1, count1=count1,
                               button2=button2, count2=count2,
                               threshold=self.max_two_buttons_in_15)
            self.click_record.clear()
            return f"交替连点：{button1}({count1}) 和 {button2}({count2}) 在15次点击中均超过{self.max_two_buttons_in_15}次"

        return None

    def before_click(self, button: str) -> Optional[str]:
        """
        点击前检查

        Args:
            button: 即将点击的按钮

        Returns:
            如果检测到异常返回原因，否则 None（允许继续）
        """
        self.add_detect(button)

        # 检查卡死
        stuck_reason = self.check_stuck()
        if stuck_reason:
            return stuck_reason

        # 检查连点
        spam_reason = self.check_click_spam()
        if spam_reason:
            return spam_reason

        return None

    def after_click(self, button: str, success: bool = True):
        """
        点击后记录

        Args:
            button: 点击的按钮
            success: 点击是否成功
        """
        if success:
            self.record_click(button)
        self.clear_detect()
        self.record_operation()

    def reset(self):
        """重置所有状态"""
        self.stuck_timer = time.time()
        self.click_record.clear()
        self.detect_record.clear()


class ErrorHandler:
    """
    错误处理器 - 统一处理各种异常并决定重试策略
    """

    def __init__(self, logger, max_retries: int = 5):
        """
        初始化错误处理器

        Args:
            logger: 日志器
            max_retries: 最大重试次数
        """
        self.logger = logger
        self.max_retries = max_retries

    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """
        判断是否应该重试

        Args:
            exception: 捕获的异常
            attempt: 当前尝试次数（从0开始）

        Returns:
            True 表示应该重试，False 表示不应该
        """
        if attempt >= self.max_retries:
            self.logger.warning(LogCategory.MAIN, "达到最大重试次数", attempt=attempt, max_retries=self.max_retries)
            return False

        exception_name = type(exception).__name__

        # 明确不应该重试的异常
        if exception_name in ('RequestHumanTakeover', 'KeyboardInterrupt', 'SystemExit'):
            self.logger.info(LogCategory.MAIN, "异常类型不重试", exception_type=exception_name)
            return False

        # 其他异常都尝试重试（保守策略）
        self.logger.debug(LogCategory.MAIN, "将重试异常", exception_type=exception_name, attempt=attempt)
        return True

    def get_retry_delay(self, attempt: int) -> float:
        """
        获取重试延迟时间

        Args:
            attempt: 当前尝试次数

        Returns:
            延迟秒数
        """
        # 指数退避：1, 2, 5, 10, 15 秒
        delays = [1, 2, 5, 10, 15]
        if attempt < len(delays):
            return delays[attempt]
        return delays[-1]

    def handle_exception(self, exception: Exception, context: str = "") -> bool:
        """
        处理异常（记录日志并决定是否继续）

        Args:
            exception: 异常对象
            context: 上下文信息

        Returns:
            True 表示可以继续，False 表示应该停止
        """
        exception_name = type(exception).__name__

        if exception_name in ('RequestHumanTakeover',):
            self.logger.error(LogCategory.MAIN, "需要人工干预，停止执行",
                             context=context, error=str(exception))
            return False

        self.logger.exception(LogCategory.MAIN, f"执行异常: {context}",
                             error=str(exception), exception_type=exception_name)
        return True