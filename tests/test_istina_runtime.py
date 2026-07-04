from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@pytest.fixture(autouse=True)
def _disable_broken_project_logging() -> None:
    for method in ("debug", "info", "warning", "error", "critical", "log", "exception"):
        setattr(logging.Logger, method, lambda self, *args, **kwargs: None)


def test_istina_runtime_can_be_instantiated() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    assert runtime is not None
    assert isinstance(runtime.config, dict)


def test_android_returns_android_runtime() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    android = runtime.android()
    assert android is not None
    assert type(android).__name__ == "AndroidRuntime"


def test_maaend_returns_maa_end_runtime() -> None:
    from core.service.runtime import IstinaRuntime
    from core.service.maa_end import runtime as maa_end_runtime_module
    from core.service.maa_end.runtime import MaaEndRuntime

    runtime = IstinaRuntime()
    target_root = PROJECT_ROOT / "3rd-part" / "maaend"
    target_root.mkdir(parents=True, exist_ok=True)

    original_default = maa_end_runtime_module.MaaEndRuntime._default_maaend_root
    try:
        maa_end_runtime_module.MaaEndRuntime._default_maaend_root = lambda self: target_root
        maaend = runtime.maaend()
    finally:
        maa_end_runtime_module.MaaEndRuntime._default_maaend_root = original_default

    assert maaend is not None
    assert isinstance(maaend, MaaEndRuntime)


def test_execute_routes_task_run() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    runtime._maaend = _FakeMaaEndRuntime(run_task_result=True)

    result = runtime.execute("task.run", {"name": "demo", "options": {}})
    assert result is True


def test_execute_routes_preset_run() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    runtime._maaend = _FakeMaaEndRuntime(run_preset_result=True)

    result = runtime.execute("preset.run", {"name": "demo"})
    assert result is True


def test_execute_routes_screenshot_returns_none() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    runtime._maaend = _FakeMaaEndRuntime(screenshot_result=b"PNG")

    result = runtime.execute("screenshot", {})
    assert result is None


def test_execute_routes_system_connect() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    runtime._maaend = _FakeMaaEndRuntime(connect_result=True, load_resource_result=True)

    result = runtime.execute("system.connect", {"serial": "serial1"})
    assert result is True
    assert runtime.connected is True


def test_execute_routes_system_disconnect() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    runtime._maaend = _FakeMaaEndRuntime()
    runtime._maaend._connected = True

    result = runtime.execute("system.disconnect", {"serial": "serial1"})
    assert result is True
    assert runtime.connected is False


def test_execute_routes_daily_run() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    result = runtime.execute("daily.run", {"options": {"a": 1}})
    assert isinstance(result, dict)
    assert result.get("status") == "success"
    assert result.get("command") == "daily.run"
    assert result.get("flow") == "daily_quest"


def test_execute_routes_harvest_run() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    result = runtime.execute("harvest.run", {"options": {}})
    assert isinstance(result, dict)
    assert result.get("status") == "success"
    assert result.get("command") == "harvest.run"
    assert result.get("flow") == "entity_harvest"


def test_execute_routes_analyze_run() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    result = runtime.execute("analyze.run", {"options": {}})
    assert isinstance(result, dict)
    assert result.get("status") == "success"
    assert result.get("command") == "analyze.run"


def test_execute_routes_explore_run() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    result = runtime.execute("explore.run", {"options": {}})
    assert isinstance(result, dict)
    assert result.get("status") == "success"
    assert result.get("command") == "explore.run"


def test_execute_routes_nav_to() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    result = runtime.execute("nav.to", {"target": "main"})
    assert isinstance(result, dict)
    assert result.get("status") == "success"
    assert result.get("command") == "nav.to"
    assert result.get("target") == "main"


def test_execute_returns_none_for_unknown_command() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    result = runtime.execute("unknown.command", {})
    assert result is None


class _FakeMaaEndRuntime:
    def __init__(
        self,
        connect_result: bool = False,
        load_resource_result: bool = False,
        run_task_result: bool = False,
        run_preset_result: bool = False,
        screenshot_result=None,
    ) -> None:
        self._connect_result = connect_result
        self._load_resource_result = load_resource_result
        self._run_task_result = run_task_result
        self._run_preset_result = run_preset_result
        self._screenshot_result = screenshot_result
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> bool:
        self._connected = self._connect_result
        return self._connected

    def load_resource(self) -> bool:
        return self._load_resource_result

    def disconnect(self) -> None:
        self._connected = False

    def run_task(self, name: str, options: dict) -> bool:
        return self._run_task_result

    def run_preset(self, name: str) -> bool:
        return self._run_preset_result

    def screenshot(self):
        return self._screenshot_result

    def tasks(self) -> dict:
        return {}

    def presets(self) -> dict:
        return {}
