"""Tests for core/logger.py"""

import os
import json
import threading
import tempfile
from pathlib import Path
from datetime import datetime

import pytest

from core.logger import (
    LogLevel,
    LogCategory,
    LogRecord,
    LogFormatter,
    LogHandler,
    ConsoleHandler,
    FileHandler,
    LogRotator,
    PerformanceMonitor,
    ClientLogger,
)


class TestLogLevel:
    def test_values(self):
        assert LogLevel.DEBUG.value == 10
        assert LogLevel.INFO.value == 20
        assert LogLevel.WARNING.value == 30
        assert LogLevel.EXCEPTION.value == 40
        assert LogLevel.CRITICAL.value == 50

    def test_ordering(self):
        assert LogLevel.DEBUG.value < LogLevel.INFO.value
        assert LogLevel.INFO.value < LogLevel.WARNING.value
        assert LogLevel.WARNING.value < LogLevel.EXCEPTION.value
        assert LogLevel.EXCEPTION.value < LogLevel.CRITICAL.value


class TestLogCategory:
    def test_values(self):
        assert LogCategory.MAIN.value == "main"
        assert LogCategory.ADB.value == "adb"
        assert LogCategory.COMMUNICATION.value == "communication"
        assert LogCategory.EXECUTION.value == "execution"
        assert LogCategory.AUTHENTICATION.value == "authentication"
        assert LogCategory.GUI.value == "gui"
        assert LogCategory.EXCEPTION.value == "exception"
        assert LogCategory.PERFORMANCE.value == "performance"

    def test_all_categories_present(self):
        assert len(LogCategory) == 8


class TestLogRecord:
    def test_minimal_creation(self):
        record = LogRecord(
            level=LogLevel.INFO,
            category=LogCategory.MAIN,
            message="测试消息",
        )
        assert record.level == LogLevel.INFO
        assert record.category == LogCategory.MAIN
        assert record.message == "测试消息"
        assert record.module == ""
        assert record.extra == {}
        assert isinstance(record.timestamp, datetime)

    def test_full_creation(self):
        record = LogRecord(
            level=LogLevel.EXCEPTION,
            category=LogCategory.COMMUNICATION,
            message="连接失败",
            module="communicator",
            function="send_request",
            line=42,
            thread_id="MainThread",
            device_id="device_001",
            extra={"attempt": 3},
            exception_info="Traceback...",
        )
        assert record.module == "communicator"
        assert record.function == "send_request"
        assert record.line == 42
        assert record.extra["attempt"] == 3
        assert record.exception_info == "Traceback..."

    def test_to_dict(self):
        record = LogRecord(
            level=LogLevel.INFO,
            category=LogCategory.MAIN,
            message="hello",
            module="test",
            function="func",
            line=10,
            extra={"key": "val"},
        )
        d = record.to_dict()
        assert d["level"] == "INFO"
        assert d["category"] == "main"
        assert d["message"] == "hello"
        assert d["module"] == "test"
        assert d["function"] == "func"
        assert d["line"] == 10
        assert d["extra"] == {"key": "val"}
        assert "timestamp" in d

    def test_to_dict_timestamp_format(self):
        record = LogRecord(level=LogLevel.INFO, category=LogCategory.MAIN, message="m")
        d = record.to_dict()
        assert len(d["timestamp"]) == 23  # "2026-06-10 01:00:00.000"

    def test_to_dict_exception_info(self):
        record = LogRecord(
            level=LogLevel.EXCEPTION,
            category=LogCategory.MAIN,
            message="err",
            exception_info="Traceback...",
        )
        d = record.to_dict()
        assert d["exception_info"] == "Traceback..."

    def test_to_dict_no_extra(self):
        record = LogRecord(level=LogLevel.INFO, category=LogCategory.MAIN, message="m")
        d = record.to_dict()
        assert d["extra"] == {}


class TestLogFormatter:
    def test_default_format(self):
        formatter = LogFormatter()
        record = LogRecord(
            level=LogLevel.INFO,
            category=LogCategory.MAIN,
            message="消息",
            module="mod",
            function="fn",
            line=5,
            thread_id="T1",
            device_id="dev1",
        )
        formatted = formatter.format(record)
        assert "INFO" in formatted
        assert "消息" in formatted
        assert "mod" in formatted
        assert "T1" in formatted
        assert "dev1" in formatted

    def test_format_with_extra(self):
        formatter = LogFormatter()
        record = LogRecord(
            level=LogLevel.WARNING,
            category=LogCategory.ADB,
            message="adb warn",
            extra={"retry": 2, "code": 127},
        )
        formatted = formatter.format(record)
        assert "retry=2" in formatted
        assert "code=127" in formatted

    def test_format_with_exception_info(self):
        formatter = LogFormatter()
        record = LogRecord(
            level=LogLevel.EXCEPTION,
            category=LogCategory.MAIN,
            message="error",
            exception_info="Trace:\n  File x.py",
        )
        formatted = formatter.format(record)
        assert "Trace:\n  File x.py" in formatted

    def test_format_without_extra(self):
        formatter = LogFormatter()
        record = LogRecord(
            level=LogLevel.INFO,
            category=LogCategory.MAIN,
            message="plain",
        )
        formatted = formatter.format(record)
        assert "plain" in formatted


class TestConsoleHandler:
    def test_emit_min_level_filter(self, capsys):
        handler = ConsoleHandler(min_level=LogLevel.WARNING)
        record_debug = LogRecord(LogLevel.DEBUG, LogCategory.MAIN, "debug")
        record_warning = LogRecord(LogLevel.WARNING, LogCategory.MAIN, "warning")

        handler.emit(record_debug)
        captured = capsys.readouterr()
        assert captured.out == ""

        handler.emit(record_warning)
        captured = capsys.readouterr()
        assert "warning" in captured.out

    def test_emit_prints_formatted(self, capsys):
        handler = ConsoleHandler()
        record = LogRecord(LogLevel.INFO, LogCategory.MAIN, "hello console")
        handler.emit(record)
        captured = capsys.readouterr()
        assert "hello console" in captured.out


class TestFileHandler:
    def test_emit_creates_file(self, tmp_log_dir: Path):
        handler = FileHandler(
            log_dir=str(tmp_log_dir),
            category=LogCategory.MAIN,
        )
        record = LogRecord(LogLevel.INFO, LogCategory.MAIN, "file test")
        handler.emit(record)

        files = list(tmp_log_dir.iterdir())
        assert len(files) >= 1
        content = files[0].read_text("utf-8")
        assert "file test" in content

    def test_emit_respects_min_level(self, tmp_log_dir: Path):
        handler = FileHandler(
            log_dir=str(tmp_log_dir),
            category=LogCategory.MAIN,
            min_level=LogLevel.WARNING,
        )
        handler.emit(LogRecord(LogLevel.DEBUG, LogCategory.MAIN, "should not appear"))
        files = list(tmp_log_dir.iterdir())
        if files:
            content = files[0].read_text("utf-8")
            assert "should not appear" not in content

    def test_ensure_log_dir_creates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "new_logs"
            assert not new_dir.exists()
            handler = FileHandler(log_dir=str(new_dir), category=LogCategory.MAIN)
            assert new_dir.exists()


class TestLogRotator:
    def test_clean_old_logs_nonexistent_dir(self):
        rotator = LogRotator(log_dir="C:\\nonexistent_path_xyz")
        removed = rotator.clean_old_logs()
        assert removed == []

    def test_clean_old_logs_empty_dir(self, tmp_log_dir: Path):
        rotator = LogRotator(log_dir=str(tmp_log_dir), retention_days=3)
        removed = rotator.clean_old_logs()
        assert removed == []

    def test_rotate_does_nothing(self):
        rotator = LogRotator(log_dir="logs")
        result = rotator.rotate()
        assert result is None


class TestPerformanceMonitor:
    def test_record_and_get_statistics(self):
        pm = PerformanceMonitor()
        pm.record_operation("ocr", 150.0)
        pm.record_operation("ocr", 250.0)
        pm.record_operation("ocr", 200.0)

        stats = pm.get_statistics("ocr")
        assert stats is not None
        assert stats["count"] == 3
        assert stats["total_ms"] == 600.0
        assert stats["avg_ms"] == 200.0
        assert stats["min_ms"] == 150.0
        assert stats["max_ms"] == 250.0

    def test_get_statistics_nonexistent(self):
        pm = PerformanceMonitor()
        assert pm.get_statistics("nonexistent") is None

    def test_get_statistics_empty_list(self):
        pm = PerformanceMonitor()
        pm.record_operation("empty_op", 100.0)
        pm._operations["empty_op"].clear()
        assert pm.get_statistics("empty_op") is None

    def test_thread_safety(self):
        pm = PerformanceMonitor()
        results = []

        def record() -> None:
            for _ in range(100):
                pm.record_operation("thread_op", 10.0)

        threads = [threading.Thread(target=record) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = pm.get_statistics("thread_op")
        assert stats is not None
        assert stats["count"] == 400

    def test_record_with_varying_durations(self):
        pm = PerformanceMonitor()
        pm.record_operation("var", 1.0)
        pm.record_operation("var", 5.0)
        pm.record_operation("var", 3.0)
        stats = pm.get_statistics("var")
        assert stats["min_ms"] == 1.0
        assert stats["max_ms"] == 5.0
        assert stats["avg_ms"] == 3.0


class TestClientLogger:
    def test_init_without_config(self):
        logger = ClientLogger(config_path=None)
        assert logger._config["enabled"] is True
        assert logger._config["log_dir"] is not None
        assert logger._performance_monitor is not None

    def test_set_device_context(self):
        logger = ClientLogger(config_path=None)
        logger.set_device_context("device_001")
        assert logger._device_context == "device_001"
        logger.clear_device_context()
        assert logger._device_context == ""

    def test_log_disabled(self):
        logger = ClientLogger(config_path=None)
        logger._config["enabled"] = False
        logger.log(LogLevel.INFO, LogCategory.MAIN, "should not crash")
        assert len(logger._handlers) > 0  # handlers still exist

    def test_get_performance_statistics(self):
        logger = ClientLogger(config_path=None)
        logger.log_performance("test_op", 50.0)
        stats = logger.get_performance_statistics("test_op")
        assert stats is not None
        assert stats["count"] >= 1

    def test_convenience_methods(self):
        logger = ClientLogger(config_path=None)
        logger.info(LogCategory.MAIN, "info msg")
        logger.debug(LogCategory.MAIN, "debug msg")
        logger.warning(LogCategory.MAIN, "warn msg")
        logger.error(LogCategory.MAIN, "error msg")
        logger.critical(LogCategory.MAIN, "critical msg")
        logger.exception(LogCategory.MAIN, "exception msg")

    def test_init_stops_cleanup_thread(self):
        logger = ClientLogger(config_path=None)
        logger.stop_cleanup_thread()
        if logger._cleanup_thread:
            assert not logger._cleanup_thread.is_alive()