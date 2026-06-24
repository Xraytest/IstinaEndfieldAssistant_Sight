"""Tests for adb_utils.py — offline-testable parts only."""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pytest
from utils.paths import get_project_root
from core.adb_utils import (
    ADB, ADBError, ScreenshotError, TimeoutError,
    VLMOptions, DEFAULT_VLM_OPTS,
    retry,
)

ADB_PROJECT_ROOT = get_project_root()


# ═══════════════════════════════════════════════════════════════
# 注意：maa_to_adb / adb_to_maa 坐标转换和 adb_tap/swipe/keyevent
# 触控操作已迁移至 MaaFw TouchManager，不再通过 adb shell input 执行。
# 测试移除对应单元测试。
# ═══════════════════════════════════════════════════════════════


class TestExceptions:
    """Exception hierarchy."""

    def test_adb_error_is_exception(self):
        assert issubclass(ADBError, Exception)

    def test_screenshot_error_inherits(self):
        assert issubclass(ScreenshotError, ADBError)

    def test_timeout_error_inherits(self):
        assert issubclass(TimeoutError, ADBError)

    def test_raise_and_catch(self):
        with pytest.raises(ADBError, match="test error"):
            raise ADBError("test error")

    def test_catch_screenshot_as_adb(self):
        with pytest.raises(ADBError):
            raise ScreenshotError("screenshot failed")


class TestVLMOptions:
    """VLMOptions dataclass."""

    def test_default_values(self):
        opts = VLMOptions()
        assert opts.model_tag == "exploration_deep"
        assert opts.timeout == 120
        assert opts.temperature == 0.01

    def test_custom_values(self):
        opts = VLMOptions(
            model_tag="vision",
            timeout=60,
            temperature=0.5,
            max_tokens=1024,
            system_prompt="test prompt",
        )
        assert opts.model_tag == "vision"
        assert opts.timeout == 60
        assert opts.temperature == 0.5
        assert opts.max_tokens == 1024
        assert opts.system_prompt == "test prompt"

    def test_default_vlm_opts(self):
        assert DEFAULT_VLM_OPTS.model_tag == "exploration_deep"
        assert DEFAULT_VLM_OPTS.timeout == 120


class TestADBClass:
    """ADB class instantiation."""

    def test_create_with_serial(self):
        adb = ADB(serial="test_serial")
        assert adb.serial == "test_serial"

    def test_create_with_default(self):
        adb = ADB()
        assert adb.serial is not None

    def test_last_screenshot_hash_initial(self):
        adb = ADB()
        assert adb._last_screenshot_hash is None


class TestRetryDecorator:
    """retry decorator behavior."""

    def test_success_first_try(self):
        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        def ok_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = ok_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_exception(self):
        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("not yet")
            return "ok"

        result = flaky()
        assert result == "ok"
        assert call_count == 2

    def test_exhaust_retries(self):
        call_count = 0

        @retry(max_attempts=2, delay=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("always")

        with pytest.raises(RuntimeError):
            always_fails()
        assert call_count == 2

    def test_preserves_callable(self):
        """retry decorator wraps function - check it stays callable."""
        @retry(max_attempts=3, delay=0.01)
        def my_func():
            return True

        assert callable(my_func)
        assert my_func() is True


class TestProjectRoot:
    """PROJECT_ROOT constant validation."""

    def test_project_root_exists(self):
        from pathlib import Path
        root = Path(ADB_PROJECT_ROOT)
        assert root.exists()
        assert (root / "src").exists()
        assert (root / "config").exists()
