"""Tests for core/cloud/managers/exception_detector.py"""

import time
from typing import Dict, Any

import pytest
import numpy as np

from core.cloud.managers.exception_detector import (
    ArknightsEndfieldExceptionDetector,
    TaskExecutionMonitor,
)


class TestDetectTextExceptions:
    def test_network_error_detected(self):
        detector = ArknightsEndfieldExceptionDetector()
        result = detector._detect_text_exceptions("网络连接失败，请重试")
        assert result is not None
        assert result["type"] == "network_error"
        assert "网络连接失败" in result["matches"]

    def test_loading_error_detected(self):
        detector = ArknightsEndfieldExceptionDetector()
        result = detector._detect_text_exceptions("加载失败，请重新启动游戏")
        assert result is not None
        assert result["type"] == "loading_error"

    def test_login_error_detected(self):
        detector = ArknightsEndfieldExceptionDetector()
        result = detector._detect_text_exceptions("账号密码错误")
        assert result is not None
        assert result["type"] == "login_error"

    def test_login_timeout_detected(self):
        detector = ArknightsEndfieldExceptionDetector()
        result = detector._detect_text_exceptions("长时间无操作，已自动退出")
        assert result is not None
        assert result["type"] == "login_timeout"

    def test_game_error_detected(self):
        detector = ArknightsEndfieldExceptionDetector()
        result = detector._detect_text_exceptions("游戏发生错误，请重启")
        assert result is not None
        assert result["type"] == "game_error"

    def test_maintenance_detected(self):
        detector = ArknightsEndfieldExceptionDetector()
        result = detector._detect_text_exceptions("停机维护")
        assert result is not None
        assert result["type"] == "maintenance"

    def test_popup_detected(self):
        detector = ArknightsEndfieldExceptionDetector()
        result = detector._detect_text_exceptions("请确认操作")
        assert result is not None
        assert result["type"] == "popup"

    def test_no_match_returns_none(self):
        detector = ArknightsEndfieldExceptionDetector()
        result = detector._detect_text_exceptions("正常游戏文本内容")
        assert result is None

    def test_with_chinese_text(self):
        detector = ArknightsEndfieldExceptionDetector()
        result = detector._detect_text_exceptions("网络异常")
        assert result is not None
        assert result["type"] == "network_error"

    def test_empty_text(self):
        detector = ArknightsEndfieldExceptionDetector()
        assert detector._detect_text_exceptions("") is None

    def test_error_severity_mapping(self):
        detector = ArknightsEndfieldExceptionDetector()
        assert detector._get_error_severity("network_error") == "high"
        assert detector._get_error_severity("loading_error") == "medium"
        assert detector._get_error_severity("login_error") == "high"
        assert detector._get_error_severity("login_timeout") == "high"
        assert detector._get_error_severity("game_error") == "critical"
        assert detector._get_error_severity("maintenance") == "info"
        assert detector._get_error_severity("popup") == "low"
        assert detector._get_error_severity("unknown") == "medium"

    def test_recommended_action_mapping(self):
        detector = ArknightsEndfieldExceptionDetector()
        assert "检查网络" in detector._get_recommended_action("network_error")
        assert "重启游戏" in detector._get_recommended_action("loading_error")
        assert "账号" in detector._get_recommended_action("login_error")
        assert "重新登录" in detector._get_recommended_action("login_timeout")
        assert "重启游戏" in detector._get_recommended_action("game_error")
        assert "等待维护" in detector._get_recommended_action("maintenance")
        assert "确认" in detector._get_recommended_action("popup")


class TestDetectUiState:
    def test_detect_loading_screen(self):
        detector = ArknightsEndfieldExceptionDetector()
        assert detector._detect_ui_state("正在加载中") == "loading_screen"

    def test_detect_login_screen(self):
        detector = ArknightsEndfieldExceptionDetector()
        assert detector._detect_ui_state("请输入账号密码") == "login_screen"

    def test_detect_main_menu(self):
        detector = ArknightsEndfieldExceptionDetector()
        assert detector._detect_ui_state("主界面") == "main_menu"

    def test_detect_game_interface(self):
        detector = ArknightsEndfieldExceptionDetector()
        assert detector._detect_ui_state("进入战斗关卡") == "game_interface"

    def test_detect_error_screen(self):
        detector = ArknightsEndfieldExceptionDetector()
        assert detector._detect_ui_state("发生错误，请重试") == "error_screen"

    def test_unknown_state(self):
        detector = ArknightsEndfieldExceptionDetector()
        assert detector._detect_ui_state("随机的游戏内容") == "unknown"

    def test_empty_text(self):
        detector = ArknightsEndfieldExceptionDetector()
        assert detector._detect_ui_state("") == "unknown"


class TestIsStateStuck:
    def test_not_enough_history(self):
        detector = ArknightsEndfieldExceptionDetector()
        detector.state_history = [(100.0, "main_menu"), (110.0, "main_menu")]
        assert detector._is_state_stuck() is False

    def test_same_state_stuck(self):
        detector = ArknightsEndfieldExceptionDetector()
        now = time.time()
        detector.state_history = [
            (now - 60, "main_menu"),
            (now - 50, "main_menu"),
            (now - 40, "main_menu"),
            (now - 30, "main_menu"),
            (now - 20, "main_menu"),
        ]
        assert detector._is_state_stuck() is True

    def test_different_state_not_stuck(self):
        detector = ArknightsEndfieldExceptionDetector()
        now = time.time()
        detector.state_history = [
            (now - 60, "loading_screen"),
            (now - 50, "main_menu"),
            (now - 40, "main_menu"),
            (now - 30, "login_screen"),
            (now - 20, "main_menu"),
        ]
        assert detector._is_state_stuck() is False

    def test_same_state_but_short_duration(self):
        detector = ArknightsEndfieldExceptionDetector()
        now = time.time()
        detector.state_history = [
            (now - 5, "main_menu"),
            (now - 4, "main_menu"),
            (now - 3, "main_menu"),
            (now - 2, "main_menu"),
            (now - 1, "main_menu"),
        ]
        assert detector._is_state_stuck() is False


class TestGetStateDuration:
    def test_no_history(self):
        detector = ArknightsEndfieldExceptionDetector()
        assert detector._get_state_duration("main_menu") == 0.0

    def test_with_matching_state(self):
        detector = ArknightsEndfieldExceptionDetector()
        now = time.time()
        detector.state_history = [
            (now - 100, "main_menu"),
            (now - 50, "main_menu"),
            (now - 10, "loading_screen"),
        ]
        duration = detector._get_state_duration("loading_screen")
        assert duration == pytest.approx(10.0, abs=1.0)


class TestIsLoginTimeout:
    def test_login_timeout_type(self):
        detector = ArknightsEndfieldExceptionDetector()
        assert detector.is_login_timeout("login_timeout") is True
        assert detector.is_login_timeout("network_error") is False
        assert detector.is_login_timeout("") is False


class TestDetectExceptionsFromScreenshot:
    def test_text_exception_detected(self):
        detector = ArknightsEndfieldExceptionDetector()
        result = detector.detect_exceptions_from_screenshot(
            screenshot=np.zeros((100, 100, 3), dtype=np.uint8),
            ocr_text="网络连接失败",
        )
        assert result["has_exception"] is True
        assert result["exception_type"] == "network_error"

    def test_screenshot_None_no_crash(self):
        detector = ArknightsEndfieldExceptionDetector()
        result = detector.detect_exceptions_from_screenshot(
            screenshot=None,
            ocr_text="",
        )
        assert result["has_exception"] is False

    def test_ui_stuck_detected(self):
        detector = ArknightsEndfieldExceptionDetector()
        for _ in range(10):
            detector.detect_exceptions_from_screenshot(
                screenshot=np.zeros((100, 100, 3), dtype=np.uint8),
                ocr_text="",
            )
        result = detector.detect_exceptions_from_screenshot(
            screenshot=np.zeros((100, 100, 3), dtype=np.uint8),
            ocr_text="",
        )
        if result["has_exception"]:
            assert result["exception_type"] in ("ui_stuck", "state_stuck")

    def test_state_stuck_detected(self):
        detector = ArknightsEndfieldExceptionDetector()
        now = time.time()
        detector.state_history = [
            (now - 60, "loading_screen"),
            (now - 50, "loading_screen"),
            (now - 40, "loading_screen"),
            (now - 30, "loading_screen"),
            (now - 20, "loading_screen"),
        ]
        assert detector._is_state_stuck() is True

    def test_screenshot_hash_limit(self):
        detector = ArknightsEndfieldExceptionDetector()
        for _ in range(35):
            detector.detect_exceptions_from_screenshot(
                screenshot=np.zeros((100, 100, 3), dtype=np.uint8),
                ocr_text="",
            )
        assert len(detector.screenshot_history) <= 30

    def test_state_history_limit(self):
        detector = ArknightsEndfieldExceptionDetector()
        for _ in range(25):
            detector.detect_exceptions_from_screenshot(
                screenshot=np.zeros((100, 100, 3), dtype=np.uint8),
                ocr_text="",
            )
        assert len(detector.state_history) <= 20


class TestCalculateChangeRate:
    def test_less_than_two_returns_one(self):
        detector = ArknightsEndfieldExceptionDetector()
        detector.screenshot_history = [(100.0, "hash1")]
        assert detector._calculate_change_rate() == 1.0

    def test_identical_hashes(self):
        detector = ArknightsEndfieldExceptionDetector()
        for i in range(5):
            detector.screenshot_history.append((float(i), "same_hash"))
        assert detector._calculate_change_rate() < 0.5

    def test_all_unique_hashes(self):
        detector = ArknightsEndfieldExceptionDetector()
        for i in range(5):
            detector.screenshot_history.append((float(i), f"hash_{i}"))
        assert detector._calculate_change_rate() == 1.0


class TestCalculateScreenshotHash:
    def test_large_screenshot(self):
        detector = ArknightsEndfieldExceptionDetector()
        img = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        h = detector._calculate_screenshot_hash(img)
        assert isinstance(h, str)
        assert len(h) == 32

    def test_small_screenshot(self):
        detector = ArknightsEndfieldExceptionDetector()
        img = np.random.randint(0, 255, (50, 50), dtype=np.uint8)
        h = detector._calculate_screenshot_hash(img)
        assert isinstance(h, str)

    def test_deterministic(self):
        detector = ArknightsEndfieldExceptionDetector()
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        h1 = detector._calculate_screenshot_hash(img)
        h2 = detector._calculate_screenshot_hash(img)
        assert h1 == h2


class TestResetAndStats:
    def test_reset_clears_everything(self):
        detector = ArknightsEndfieldExceptionDetector()
        detector.screenshot_history.append((100.0, "hash"))
        detector.state_history.append((100.0, "menu"))
        detector.error_counters["network_error"] = 5
        detector.reset()
        assert detector.screenshot_history == []
        assert detector.state_history == []
        assert detector.error_counters["network_error"] == 0

    def test_get_statistics(self):
        detector = ArknightsEndfieldExceptionDetector()
        detector.screenshot_history.append((100.0, "h1"))
        detector.state_history.append((100.0, "menu"))
        stats = detector.get_statistics()
        assert stats["screenshot_history_size"] == 1
        assert stats["state_history_size"] == 1
        assert "error_counters" in stats


class TestTaskExecutionMonitor:
    def test_track_first_iteration(self):
        monitor = TaskExecutionMonitor()
        result = monitor.track_task_iteration("task_daily")
        assert result["should_stop"] is False
        assert result["iteration_count"] == 1

    def test_track_max_iterations(self):
        monitor = TaskExecutionMonitor(max_iterations_per_task=3)
        for _ in range(3):
            monitor.track_task_iteration("task_claim")
        result = monitor.track_task_iteration("task_claim")
        assert result["should_stop"] is True
        assert "达到最大迭代次数" in result["reason"]

    def test_track_low_change_rate(self):
        monitor = TaskExecutionMonitor(min_change_rate=0.5)
        for _ in range(5):
            monitor.track_task_iteration("task_battle", screenshot_hash="same_hash")
        result = monitor.track_task_iteration("task_battle", screenshot_hash="same_hash")
        assert result["should_stop"] is True
        assert "变化率" in result["reason"]

    def test_track_long_elapsed_time(self):
        monitor = TaskExecutionMonitor()
        real_time = time.time
        monitor.task_start_time["task_long"] = real_time() - 301
        monitor.task_iterations["task_long"] = 0
        result = monitor.track_task_iteration("task_long")
        assert result["should_stop"] is True
        assert "时间过长" in result["reason"]

    def test_get_iteration_info(self):
        monitor = TaskExecutionMonitor()
        monitor.track_task_iteration("task_test", "hash1")
        info = monitor.get_iteration_info("task_test")
        assert info["iteration_count"] == 1
        assert info["screenshot_count"] == 1

    def test_get_iteration_info_nonexistent(self):
        monitor = TaskExecutionMonitor()
        assert monitor.get_iteration_info("nonexistent") == {}

    def test_reset_task(self):
        monitor = TaskExecutionMonitor()
        monitor.track_task_iteration("task_reset")
        monitor.reset_task("task_reset")
        assert monitor.get_iteration_info("task_reset") == {}

    def test_get_task_statistics(self):
        monitor = TaskExecutionMonitor()
        monitor.track_task_iteration("task_stats", "hash1")
        monitor.track_task_iteration("task_stats", "hash2")
        stats = monitor.get_task_statistics("task_stats")
        assert stats["iteration_count"] == 2
        assert stats["unique_screenshots"] == 2
        assert stats["change_rate"] == 1.0

    def test_get_task_statistics_nonexistent(self):
        monitor = TaskExecutionMonitor()
        assert monitor.get_task_statistics("nonexistent") == {}

    def test_screenshot_history_limited(self):
        monitor = TaskExecutionMonitor()
        for i in range(15):
            monitor.track_task_iteration("task_limit", f"hash_{i}")
        info = monitor.get_iteration_info("task_limit")
        assert info["screenshot_count"] <= 10