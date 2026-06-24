"""Tests for logger.py — pure logic module, fully offline-testable."""
import sys
import os
import tempfile
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pytest
from core.logger import (
    LogLevel, LogCategory, LogRecord,
    LogFormatter, ConsoleHandler, FileHandler,
    LogRotator, PerformanceMonitor, ClientLogger,
    init_logger, get_logger,
)


class TestLogLevel:
    def test_enum_values(self):
        assert LogLevel.DEBUG.value == 10
        assert LogLevel.INFO.value == 20
        assert LogLevel.WARNING.value == 30
        assert LogLevel.EXCEPTION.value == 40
        assert LogLevel.CRITICAL.value == 50

    def test_comparison(self):
        assert LogLevel.DEBUG.value < LogLevel.INFO.value
        assert LogLevel.CRITICAL.value > LogLevel.WARNING.value


class TestLogCategory:
    def test_enum_values(self):
        assert LogCategory.MAIN.value == "main"
        assert LogCategory.ADB.value == "adb"
        assert LogCategory.COMMUNICATION.value == "communication"
        assert LogCategory.EXECUTION.value == "execution"
        assert LogCategory.AUTHENTICATION.value == "authentication"
        assert LogCategory.GUI.value == "gui"
        assert LogCategory.EXCEPTION.value == "exception"
        assert LogCategory.PERFORMANCE.value == "performance"


class TestLogRecord:
    def test_create_record(self):
        record = LogRecord(
            level=LogLevel.INFO,
            category=LogCategory.MAIN,
            message="test message",
            module="test_module",
            function="test_func",
            line=42,
        )
        assert record.level == LogLevel.INFO
        assert record.category == LogCategory.MAIN
        assert record.message == "test message"
        assert record.module == "test_module"
        assert record.function == "test_func"
        assert record.line == 42

    def test_to_dict(self):
        record = LogRecord(
            level=LogLevel.WARNING,
            category=LogCategory.ADB,
            message="adb warning",
            extra={"key": "value"},
            exception_info="traceback...",
        )
        d = record.to_dict()
        assert isinstance(d, dict)
        assert d["level"] == "WARNING"
        assert d["category"] == "adb"
        assert d["message"] == "adb warning"
        assert d["extra"] == {"key": "value"}
        assert d["exception_info"] == "traceback..."

    def test_default_values(self):
        record = LogRecord(
            level=LogLevel.DEBUG,
            category=LogCategory.GUI,
            message="debug",
        )
        assert record.module == ""
        assert record.function == ""
        assert record.line == 0


class TestLogFormatter:
    def test_basic_format(self):
        fmt = LogFormatter()
        record = LogRecord(
            level=LogLevel.INFO,
            category=LogCategory.MAIN,
            message="hello",
        )
        output = fmt.format(record)
        assert "hello" in output
        assert "INFO" in output

    def test_custom_format(self):
        fmt = LogFormatter("{level} | {message}")
        record = LogRecord(
            level=LogLevel.WARNING,
            category=LogCategory.EXECUTION,
            message="custom",
        )
        output = fmt.format(record)
        assert "WARNING" in output
        assert "custom" in output


class TestConsoleHandler:
    def test_emit_basic(self, capsys):
        handler = ConsoleHandler()
        record = LogRecord(
            level=LogLevel.INFO,
            category=LogCategory.MAIN,
            message="console test",
        )
        handler.emit(record)
        captured = capsys.readouterr()
        assert "console test" in captured.out

    def test_min_level_filter(self, capsys):
        handler = ConsoleHandler(min_level=LogLevel.WARNING)
        debug_record = LogRecord(level=LogLevel.DEBUG, category=LogCategory.MAIN, message="should not appear")
        warn_record = LogRecord(level=LogLevel.WARNING, category=LogCategory.MAIN, message="should appear")

        handler.emit(debug_record)
        handler.emit(warn_record)
        captured = capsys.readouterr()
        assert "should not appear" not in captured.out
        assert "should appear" in captured.out


class TestFileHandler:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_log_file(self):
        handler = FileHandler(log_dir=self.tmpdir, category=LogCategory.ADB)
        record = LogRecord(level=LogLevel.INFO, category=LogCategory.ADB, message="file test")
        handler.emit(record)

        files = os.listdir(self.tmpdir)
        assert len(files) >= 1
        log_file = os.path.join(self.tmpdir, files[0])
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "file test" in content

    def test_category_in_filename(self):
        handler = FileHandler(log_dir=self.tmpdir, category=LogCategory.EXECUTION)
        record = LogRecord(level=LogLevel.INFO, category=LogCategory.EXECUTION, message="exec")
        handler.emit(record)

        files = os.listdir(self.tmpdir)
        log_file = files[0]
        assert "execution" in log_file.lower()


class TestLogRotator:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_rotator_creation(self):
        rotator = LogRotator(log_dir=self.tmpdir, retention_days=3)
        assert rotator is not None

    def test_clean_old_logs_no_error(self):
        rotator = LogRotator(log_dir=self.tmpdir, retention_days=7)
        removed = rotator.clean_old_logs()
        assert isinstance(removed, list)


class TestPerformanceMonitor:
    def test_record_and_stats(self):
        monitor = PerformanceMonitor()
        monitor.record_operation("tap", 100.0)
        monitor.record_operation("tap", 200.0)
        monitor.record_operation("tap", 300.0)

        stats = monitor.get_statistics("tap")
        assert stats is not None
        assert "count" in stats
        assert stats["count"] == 3
        assert "avg_ms" in stats
        assert 190 <= stats["avg_ms"] <= 210

    def test_unknown_operation(self):
        monitor = PerformanceMonitor()
        stats = monitor.get_statistics("nonexistent")
        assert stats is None


class TestClientLogger:
    @pytest.fixture(autouse=True)
    def reset_logger(self):
        """Reset the singleton logger before each test."""
        import core.logger as logger_module
        logger_module._logger_instance = None
        yield
        logger_module._logger_instance = None

    def test_init_logger(self, tmp_path):
        logger = init_logger()
        assert logger is not None
        assert isinstance(logger, ClientLogger)

    def test_get_logger_returns_same_instance(self):
        logger1 = get_logger()
        logger2 = get_logger()
        assert logger1 is logger2

    def test_log_methods_dont_raise(self):
        logger = get_logger()
        logger.info(LogCategory.MAIN, "test info")
        logger.debug(LogCategory.ADB, "test debug")
        logger.warning(LogCategory.COMMUNICATION, "test warning")
        logger.error(LogCategory.EXECUTION, "test error")
        logger.critical(LogCategory.GUI, "test critical")

    def test_log_performance(self):
        logger = get_logger()
        logger.log_performance("tap", 150.0)
        stats = logger.get_performance_statistics("tap")
        assert stats is not None
        assert stats["count"] == 1
