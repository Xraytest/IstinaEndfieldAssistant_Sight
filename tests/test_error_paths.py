from __future__ import annotations

import json
import logging
import subprocess
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


def test_cli_handles_invalid_options_json_gracefully() -> None:
    from cli import istina as istina_module

    runtime = istina_module.IstinaRuntime()
    runtime._maaend = _FakeMaaEndRuntime()

    result = istina_module._handle_daily(runtime, _Args({"options": "not-json"}))
    assert result.get("status") == "error"
    assert "options JSON 解析失败" in result.get("message", "")

    result = istina_module._handle_harvest(runtime, _Args({"options": "not-json"}))
    assert result.get("status") == "error"
    assert "options JSON 解析失败" in result.get("message", "")

    result = istina_module._handle_analyze(runtime, _Args({"options": "not-json"}))
    assert result.get("status") == "error"
    assert "options JSON 解析失败" in result.get("message", "")

    result = istina_module._handle_explore(runtime, _Args({"options": "not-json"}))
    assert result.get("status") == "error"
    assert "options JSON 解析失败" in result.get("message", "")


def test_cli_handles_unknown_subcommand_gracefully() -> None:
    from cli import istina as istina_module

    with pytest.raises(SystemExit) as excinfo:
        istina_module.main(["unknown-command"])
    assert excinfo.value.code == 2


def test_adb_manager_handles_missing_adb_binary_gracefully() -> None:
    from core.capability.device.adb_manager import ADBDeviceManager

    manager = ADBDeviceManager(adb_path="missing/adb.exe")
    devices = manager.get_devices()
    assert devices == []
    assert isinstance(devices, list)


def test_maa_end_runtime_connect_failure_returns_false() -> None:
    from core.service.maa_end import runtime as maa_end_runtime_module
    from core.service.maa_end.runtime import MaaEndRuntime

    original = maa_end_runtime_module.MAAFW_AVAILABLE
    try:
        maa_end_runtime_module.MAAFW_AVAILABLE = False
        runtime = MaaEndRuntime(maaend_root=str(PROJECT_ROOT / "3rd-part" / "maaend"))
        assert runtime.connect() is False
    finally:
        maa_end_runtime_module.MAAFW_AVAILABLE = original


def test_runtime_execute_with_none_params_does_not_crash() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    runtime._maaend = _FakeMaaEndRuntime()
    result = runtime.execute("task.run", None)
    assert isinstance(result, bool)


def test_cli_reports_invalid_config_file_without_secondary_failure(tmp_path) -> None:
    config_file = tmp_path / "client_config.json"
    config_file.write_text("{invalid json", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "src" / "cli" / "istina.py"), "--config", str(config_file), "system", "env"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0
    payload = json.loads(proc.stdout.strip())
    assert payload["status"] == "success"
    assert "attribute" not in proc.stderr.lower()


def test_model_download_rejects_path_traversal(monkeypatch, tmp_path) -> None:
    from cli import handlers

    monkeypatch.setattr(handlers, "get_project_root", lambda: tmp_path)

    result = handlers._handle_model_download(None, _Args({"name": "..\\escape"}))
    assert result["status"] == "error"
    assert result["message"] == "invalid model name"
    assert not (tmp_path / "escape").exists()


class _FakeMaaEndRuntime:
    def __init__(self):
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> bool:
        return False

    def load_resource(self) -> bool:
        return False

    def disconnect(self) -> None:
        self._connected = False

    def run_task(self, name: str, options: dict) -> bool:
        return False

    def run_preset(self, name: str) -> bool:
        return False

    def screenshot(self):
        return None

    def tasks(self) -> dict:
        return {}

    def presets(self) -> dict:
        return {}


class _Args:
    def __init__(self, data: dict) -> None:
        self._data = data

    def __getattr__(self, item: str) -> object:
        if item in self._data:
            return self._data[item]
        return None
