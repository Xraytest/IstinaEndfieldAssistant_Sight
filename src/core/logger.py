"""
客户端日志系统 - 客观命名版本
"""
import os
import sys
import time
import json
import threading
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    EXCEPTION = 40
    CRITICAL = 50


class LogCategory(Enum):
    """日志分类枚举"""
    MAIN = "main"
    ADB = "adb"
    COMMUNICATION = "communication"
    EXECUTION = "execution"
    AUTHENTICATION = "authentication"
    GUI = "gui"
    EXCEPTION = "exception"
    PERFORMANCE = "performance"
    INFERENCE = "inference"


class LogRecord:
    """日志记录类"""
    
    def __init__(
        self,
        level: LogLevel,
        category: LogCategory,
        message: str,
        module: str = "",
        function: str = "",
        line: int = 0,
        thread_id: str = "",
        device_id: str = "",
        extra: Optional[Dict[str, Any]] = None,
        exception_info: Optional[str] = None
    ):
        self.level = level
        self.category = category
        self.message = message
        self.module = module
        self.function = function
        self.line = line
        self.thread_id = thread_id
        self.device_id = device_id
        self.extra = extra or {}
        self.exception_info = exception_info
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "level": self.level.name,
            "category": self.category.value if hasattr(self.category, 'value') else str(self.category),
            "module": self.module,
            "function": self.function,
            "line": self.line,
            "thread_id": self.thread_id,
            "device_id": self.device_id,
            "extra": self.extra,
            "exception_info": self.exception_info,
            "message": self.message
        }


class LogFormatter:
    """日志格式化器"""
    
    def __init__(self, format_string: Optional[str] = None):
        self.format_string = format_string or (
            "[{timestamp}] [{level}] [{module}:{function}:{line}] "
            "[{thread}] [{device}] {message}"
        )
    
    def format(self, record: LogRecord) -> str:
        """格式化日志记录"""
        category_str = record.category.value if hasattr(record.category, 'value') else str(record.category)
        formatted = self.format_string.format(
            timestamp=record.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            level=record.level.name,
            category=category_str,
            module=record.module,
            function=record.function,
            line=record.line,
            thread=record.thread_id,
            device=record.device_id or "-",
            message=record.message
        )
        
        if record.extra:
            extra_str = " | ".join(f"{k}={v}" for k, v in record.extra.items())
            formatted = f"{formatted} | {extra_str}"
        
        if record.exception_info:
            formatted = f"{formatted}\n{record.exception_info}"
        
        return formatted




class JSONLogFormatter:
    """JSON 格式日志格式化器"""

    def format(self, record: LogRecord) -> str:
        """将日志记录格式化为 JSON 字符串"""
        return json.dumps(record.to_dict(), ensure_ascii=False, default=str)

class LogHandler:
    """日志处理器基类"""
    
    def __init__(self, formatter: Optional[LogFormatter] = None):
        self.formatter = formatter or LogFormatter()
        self._lock = threading.Lock()
    
    def emit(self, record: LogRecord) -> None:
        """输出日志记录"""
        raise NotImplementedError
    
    def format(self, record: LogRecord) -> str:
        """格式化日志记录"""
        return self.formatter.format(record)


class ConsoleHandler(LogHandler):
    """控制台日志处理器"""
    
    def __init__(self, formatter: Optional[LogFormatter] = None, min_level: LogLevel = LogLevel.DEBUG):
        super().__init__(formatter)
        self.min_level = min_level
    
    def emit(self, record: LogRecord) -> None:
        """输出到控制台"""
        if record.level.value < self.min_level.value:
            return
        
        with self._lock:
            print(self.format(record))


class FileHandler(LogHandler):
    """文件日志处理器 - 按分类过滤 + 大小轮转"""
    
    def __init__(
        self,
        log_dir: str,
        category: LogCategory,
        formatter: Optional[LogFormatter] = None,
        min_level: LogLevel = LogLevel.DEBUG,
        max_size: int = 50 * 1024 * 1024,
        encoding: str = "utf-8",
        backup_count: int = 5
    ):
        super().__init__(formatter)
        self.log_dir = log_dir
        self.category = category
        self.min_level = min_level
        self.max_size = max_size
        self.encoding = encoding
        self.backup_count = backup_count
        self._ensure_log_dir()
    
    def _ensure_log_dir(self) -> None:
        """确保日志目录存在"""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
    
    def _get_log_filename(self) -> str:
        """获取日志文件名"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"{self.category.value}_{date_str}.log")

    def _rotate(self, filepath: str) -> None:
        """日志文件轮转 - 按序号重命名旧文件"""
        if not os.path.exists(filepath):
            return
        oldest = f"{filepath}.{self.backup_count}"
        if os.path.exists(oldest):
            os.remove(oldest)
        for bi in range(self.backup_count - 1, 0, -1):
            old_file = f"{filepath}.{bi}"
            new_file = f"{filepath}.{bi + 1}"
            if os.path.exists(old_file):
                os.rename(old_file, new_file)
        os.rename(filepath, f"{filepath}.1")
    
    def emit(self, record: LogRecord) -> None:
        """写入文件 - 仅处理匹配分类的日志"""
        if record.category != self.category:
            return
        if record.level.value < self.min_level.value:
            return
        with self._lock:
            filepath = self._get_log_filename()
            if self.max_size > 0:
                current_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
                if current_size >= self.max_size:
                    self._rotate(filepath)
            try:
                with open(filepath, "a", encoding=self.encoding) as f:
                    f.write(self.format(record) + "\n")
            except Exception as e:
                print(f"日志写入异常：{e}")
class GUIHandler(LogHandler):
    """GUI日志处理器"""
    
    def __init__(
        self,
        log_widget,
        formatter: Optional[LogFormatter] = None,
        min_level: LogLevel = LogLevel.INFO,
        max_lines: int = 1000
    ):
        super().__init__(formatter)
        self.log_widget = log_widget
        self.min_level = min_level
        self.max_lines = max_lines
        self._line_count = 0
    
    def emit(self, record: LogRecord) -> None:
        """输出到GUI"""
        if record.level.value < self.min_level.value or self.log_widget is None:
            return
        
        with self._lock:
            try:
                self.log_widget.insert("end", self.format(record) + "\n")
                self.log_widget.see("end")

                self._line_count += 1
                if self._line_count > self.max_lines:
                    self.log_widget.delete("1.0", "2.0")
                    self._line_count = self.max_lines
            except Exception as e:
                print(f"GUI 日志输出异常：{e}")
                pass


class LogRotator:
    """日志轮转器"""
    
    def __init__(self, log_dir: str, retention_days: int = 3):
        self.log_dir = log_dir
        self.retention_days = retention_days
    
    def rotate(self) -> None:
        """执行日志轮转（按日期自动轮转）"""
        pass  # 文件处理器已按日期自动创建文件
    
    def clean_old_logs(self) -> List[str]:
        """清理超过保留天数的日志"""
        if not os.path.exists(self.log_dir):
            return []
        
        current_time = time.time()
        removed_files = []
        
        for filename in os.listdir(self.log_dir):
            filepath = os.path.join(self.log_dir, filename)
            
            if not os.path.isfile(filepath):
                continue
            
            if not filename.endswith(".log"):
                continue
            
            file_age = current_time - os.path.getmtime(filepath)
            days_old = file_age / (24 * 60 * 60)
            
            if days_old > self.retention_days:
                try:
                    os.remove(filepath)
                    removed_files.append(filename)
                except Exception as e:
                    print(f"删除日志文件异常: {filepath}, {e}")
        
        return removed_files


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self._operations: Dict[str, List[float]] = {}
        self._lock = threading.Lock()
    
    def record_operation(self, operation_name: str, duration_ms: float) -> None:
        """记录操作耗时"""
        with self._lock:
            if operation_name not in self._operations:
                self._operations[operation_name] = []
            self._operations[operation_name].append(duration_ms)
    
    def get_statistics(self, operation_name: str) -> Optional[Dict[str, float]]:
        """获取操作统计信息"""
        with self._lock:
            if operation_name not in self._operations or not self._operations[operation_name]:
                return None
            
            durations = self._operations[operation_name]
            return {
                "count": len(durations),
                "total_ms": sum(durations),
                "avg_ms": sum(durations) / len(durations),
                "min_ms": min(durations),
                "max_ms": max(durations)
            }


class ClientLogger:
    """客户端日志系统核心类"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化日志系统
        
        Args:
            config_path: 配置文件路径
        """
        self._handlers: List[LogHandler] = []
        self._device_context = ""
        self._config = self._load_config(config_path)
        # 将日志目录转换为绝对路径
        log_dir = self._config.get("log_dir", "logs")
        if not os.path.isabs(log_dir):
            # logger.py 在 src/core/，向上 3 层到项目根目录
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            log_dir = os.path.join(project_root, log_dir)
        self._config["log_dir"] = log_dir
        
        self._performance_monitor = PerformanceMonitor()
        self._rotator = LogRotator(
            log_dir,
            self._config.get("retention_days", 3)
        )
        
        # 自动清理线程控制
        self._cleanup_thread = None
        self._cleanup_stop_event = threading.Event()
        self._cleanup_interval = self._config.get("cleanup_interval_hours", 24) * 3600  # 默认24小时
        
        self._setup_handlers()
        self._clean_old_logs_on_startup()
        
        # 启动定期清理线程
        self._start_cleanup_thread()
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """加载配置"""
        default_config = {
            "enabled": True,
            "log_dir": "logs",
            "retention_days": 3,
            "cleanup_interval_hours": 24,
            "global_level": "DEBUG",
            "handlers": {
                "file": {
                    "enabled": True,
                    "max_size": 50 * 1024 * 1024,
                    "encoding": "utf-8"
                },
                "console": {
                    "enabled": True,
                    "level": "INFO"
                },
                "gui": {
                    "enabled": False,
                    "level": "INFO",
                    "max_lines": 1000
                }
            },
            "performance": {
                "enabled": True,
                "log_slow_operations": True,
                "slow_threshold_ms": 1000
            }
        }
        
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                    self._merge_config(default_config, user_config)
            except Exception as e:
                print(f"加载日志配置异常: {e}")
        
        return default_config
    
    def _merge_config(self, base: Dict, update: Dict) -> None:
        """合并配置"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def _setup_handlers(self) -> None:
        """设置处理器"""
        log_format = self._config.get("format", "text")
        formatter = JSONLogFormatter() if log_format == "json" else LogFormatter()
        
        # 文件处理器
        if self._config["handlers"]["file"]["enabled"]:
            for category in LogCategory:
                handler = FileHandler(
                    log_dir=self._config["log_dir"],
                    category=category,
                    formatter=formatter,
                    max_size=self._config["handlers"]["file"]["max_size"],
                    encoding=self._config["handlers"]["file"]["encoding"]
                )
                self._handlers.append(handler)
        
        # 控制台处理器
        if self._config["handlers"]["console"]["enabled"]:
            level = LogLevel[self._config["handlers"]["console"]["level"]]
            handler = ConsoleHandler(formatter=formatter, min_level=level)
            self._handlers.append(handler)
    
    def _clean_old_logs_on_startup(self) -> None:
        """启动时清理旧日志"""
        removed = self._rotator.clean_old_logs()
        if removed:
            self.log(
                LogLevel.INFO,
                LogCategory.MAIN,
                f"清理旧日志文件: {', '.join(removed)}"
            )
    
    def _start_cleanup_thread(self) -> None:
        """启动定期清理日志的后台线程"""
        if self._cleanup_interval > 0:
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_worker,
                daemon=True,
                name="LogCleanupThread"
            )
            self._cleanup_thread.start()
            self.log(
                LogLevel.INFO,
                LogCategory.MAIN,
                f"日志自动清理线程已启动，清理间隔: {self._cleanup_interval // 3600}小时"
            )
    
    def _cleanup_worker(self) -> None:
        """定期清理日志的工作线程"""
        while not self._cleanup_stop_event.is_set():
            # 等待清理间隔或停止事件
            self._cleanup_stop_event.wait(self._cleanup_interval)
            
            if self._cleanup_stop_event.is_set():
                break
            
            # 执行清理
            try:
                removed = self._rotator.clean_old_logs()
                if removed:
                    self.log(
                        LogLevel.INFO,
                        LogCategory.MAIN,
                        f"定期清理旧日志文件: {', '.join(removed)}"
                    )
            except Exception as e:
                print(f"定期清理日志异常: {e}")
    
    def stop_cleanup_thread(self) -> None:
        """停止定期清理线程"""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_stop_event.set()
            self._cleanup_thread.join(timeout=5)
            self.log(
                LogLevel.INFO,
                LogCategory.MAIN,
                "日志自动清理线程已停止"
            )
    
    def set_gui_handler(self, log_widget) -> None:
        """设置GUI处理器"""
        if self._config["handlers"]["gui"]["enabled"]:
            formatter = LogFormatter()
            level = LogLevel[self._config["handlers"]["gui"]["level"]]
            handler = GUIHandler(
                log_widget=log_widget,
                formatter=formatter,
                min_level=level,
                max_lines=self._config["handlers"]["gui"]["max_lines"]
            )
            self._handlers.append(handler)
    
    def set_device_context(self, device_serial: str) -> None:
        """设置设备上下文"""
        self._device_context = device_serial
    
    def clear_device_context(self) -> None:
        """清除设备上下文"""
        self._device_context = ""
    
    def _get_caller_info(self) -> tuple:
        """获取调用者信息"""
        frame = sys._getframe(2)
        module = frame.f_globals.get("__name__", "")
        function = frame.f_code.co_name
        line = frame.f_lineno
        return module, function, line
    
    def log(
        self,
        level: LogLevel,
        category: LogCategory,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exception_info: Optional[str] = None
    ) -> None:
        """记录日志"""
        if not self._config.get("enabled", True):
            return
        
        module, function, line = self._get_caller_info()
        thread_id = threading.current_thread().name
        
        record = LogRecord(
            level=level,
            category=category,
            message=message,
            module=module,
            function=function,
            line=line,
            thread_id=thread_id,
            device_id=self._device_context,
            extra=extra,
            exception_info=exception_info
        )
        
        for handler in self._handlers:
            try:
                handler.emit(record)
            except Exception as e:
                print(f"日志处理器异常: {e}")
    
    def debug(self, category: LogCategory, message: str, **extra) -> None:
        """DEBUG级别日志"""
        self.log(LogLevel.DEBUG, category, message, extra if extra else None)
    
    def info(self, category: LogCategory, message: str, **extra) -> None:
        """INFO级别日志"""
        self.log(LogLevel.INFO, category, message, extra if extra else None)
    
    def warning(self, category: LogCategory, message: str, **extra) -> None:
        """WARNING级别日志"""
        self.log(LogLevel.WARNING, category, message, extra if extra else None)
    
    def _log_with_exception(self, level: LogLevel, category: LogCategory, message: str, exc_info: bool = False, **extra) -> None:
        """带异常信息的日志记录辅助方法"""
        exception_text = traceback.format_exc() if exc_info else None
        self.log(level, category, message, extra if extra else None, exception_text)
    
    def error(self, category: LogCategory, message: str, exc_info: bool = False, **extra) -> None:
        """ERROR级别日志"""
        self._log_with_exception(LogLevel.EXCEPTION, category, message, exc_info, **extra)
    
    def exception(self, category: LogCategory, message: str, exc_info: bool = False, **extra) -> None:
        """EXCEPTION级别日志"""
        self._log_with_exception(LogLevel.EXCEPTION, category, message, exc_info, **extra)
    
    def critical(self, category: LogCategory, message: str, exc_info: bool = False, **extra) -> None:
        """CRITICAL级别日志"""
        self._log_with_exception(LogLevel.CRITICAL, category, message, exc_info, **extra)
    
    def log_performance(self, operation_name: str, duration_ms: float, **extra) -> None:
        """记录性能数据"""
        self._performance_monitor.record_operation(operation_name, duration_ms)
        
        if self._config["performance"]["enabled"]:
            message = f"操作: {operation_name}, 耗时: {duration_ms:.3f}ms"
            self.log(
                LogLevel.DEBUG,
                LogCategory.PERFORMANCE,
                message,
                extra if extra else None
            )
            
            if (self._config["performance"]["log_slow_operations"] and
                duration_ms > self._config["performance"]["slow_threshold_ms"]):
                self.log(
                    LogLevel.WARNING,
                    LogCategory.PERFORMANCE,
                    f"操作耗时超过阈值: {operation_name}, 阈值: {self._config['performance']['slow_threshold_ms']}ms",
                    {"actual_ms": duration_ms}
                )
    
    def get_performance_statistics(self, operation_name: str) -> Optional[Dict[str, float]]:
        """获取性能统计"""
        return self._performance_monitor.get_statistics(operation_name)
    
    def clean_old_logs(self) -> List[str]:
        """清理旧日志"""
        return self._rotator.clean_old_logs()


# 全局日志实例
_global_logger: Optional[ClientLogger] = None
_logger_lock = threading.Lock()


def get_logger(config_path: Optional[str] = None) -> ClientLogger:
    """获取全局日志实例"""
    global _global_logger
    
    with _logger_lock:
        if _global_logger is None:
            _global_logger = ClientLogger(config_path)
    
    return _global_logger


def init_logger(config_path: Optional[str] = None) -> ClientLogger:
    """初始化全局日志实例"""
    global _global_logger
    
    with _logger_lock:
        if _global_logger is None:
            _global_logger = ClientLogger(config_path)
    
    return _global_logger