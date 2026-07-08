from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ISTINA_SCRIPT = PROJECT_ROOT / "src" / "cli" / "istina.py"
CLI = [sys.executable, str(ISTINA_SCRIPT)]


def _can_execute_tasks() -> bool:
    try:
        proc = subprocess.run(
            CLI + ["device", "info"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        out = proc.stdout.strip()
        if not out:
            return False
        data = json.loads(out)
        devices = data.get("devices") or []
        if not devices:
            return False
        proc2 = subprocess.run(
            CLI + ["system", "connect"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
        out2 = proc2.stdout.strip()
        if not out2:
            return False
        data2 = json.loads(out2)
        return data2.get("status") == "success" and data2.get("maaend_connected") is True
    except Exception:
        return False


_CAN_EXECUTE_TASKS = _can_execute_tasks()


def _run_cli(argv, env=None):
    if env is None:
        env = dict(os.environ)
    proc = subprocess.run(
        CLI + argv,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    parsed = None
    if out:
        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            parsed = out
    return proc.returncode, parsed, err


def test_cli_commands_output_valid_json() -> None:
    for command in [["system", "env"], ["system", "disk"], ["device", "info"], ["nav", "hub"]]:
        returncode, parsed, _ = _run_cli(command)
        assert returncode in (0, 1)
        assert parsed is not None
        assert isinstance(parsed, dict)


def test_device_info_returns_success_with_devices_list() -> None:
    returncode, parsed, _ = _run_cli(["device", "info"])
    assert returncode in (0, 1)
    assert parsed.get("status") == "success"
    assert "devices" in parsed
    assert isinstance(parsed["devices"], list)


def test_device_status_returns_success_with_adb_server_info() -> None:
    returncode, parsed, _ = _run_cli(["device", "status"])
    assert returncode in (0, 1)
    assert parsed.get("status") == "success"
    assert "adb_server" in parsed
    assert "devices" in parsed


def test_system_env_returns_success_with_env_dict() -> None:
    returncode, parsed, _ = _run_cli(["system", "env"])
    assert returncode == 0
    assert parsed.get("status") == "success"
    env = parsed.get("env")
    assert isinstance(env, dict)
    assert "python_version" in env
    assert "os" in env
    assert "cwd" in env


def test_system_disk_returns_success_with_disk_usage() -> None:
    returncode, parsed, _ = _run_cli(["system", "disk"])
    assert returncode == 0
    assert parsed.get("status") == "success"
    assert parsed.get("path") == str(PROJECT_ROOT)
    assert "free_bytes" in parsed
    assert "total_bytes" in parsed


def test_config_get_set_works(tmp_path) -> None:
    config_file = tmp_path / "client_config.json"
    config_file.write_text(json.dumps({"existing_key": "existing_value"}, ensure_ascii=False))

    returncode_get, parsed_get, _ = _run_cli(["--config", str(config_file), "config", "get", "existing_key"])
    assert returncode_get == 0
    assert parsed_get.get("status") == "success"
    assert parsed_get.get("value") == "existing_value"

    returncode_set, parsed_set, _ = _run_cli(["--config", str(config_file), "config", "set", "new_key", "new_value"])
    assert returncode_set == 0
    assert parsed_set.get("status") == "success"
    assert parsed_set.get("key") == "new_key"
    assert parsed_set.get("value") == "new_value"


def test_task_and_preset_commands_accept_serial_arg() -> None:
    returncode, parsed, _ = _run_cli(["task", "list", "--serial", "192.168.1.12:16512"])
    assert returncode in (0, 1)
    assert parsed.get("status") == "success"
    assert "tasks" in parsed
    assert "task_option_defs" in parsed

    returncode, parsed, _ = _run_cli(["preset", "list", "--serial", "192.168.1.12:16512"])
    assert returncode in (0, 1)
    assert parsed.get("status") == "success"
    assert "presets" in parsed


def test_task_run_accepts_timeout_arg() -> None:
    from cli.istina import build_parser

    args = build_parser().parse_args(["task", "run", "EnvironmentMonitoring", "--timeout", "1.5"])
    assert args.command == "task"
    assert args.action == "run"
    assert args.timeout == 1.5


@pytest.mark.skipif(not _CAN_EXECUTE_TASKS, reason="device/MaaEnd not available")
def test_nav_command_returns_success_with_target() -> None:
    returncode, parsed, _ = _run_cli(["nav", "hub"])
    assert returncode in (0, 1)
    assert parsed.get("status") == "success"
    assert parsed.get("command") == "nav.to"
    assert parsed.get("target") == "hub"


@pytest.mark.skipif(not _CAN_EXECUTE_TASKS, reason="device/MaaEnd not available")
def test_daily_returns_success() -> None:
    returncode, parsed, _ = _run_cli(["daily"])
    assert returncode in (0, 1)
    assert parsed.get("status") == "success"
    assert parsed.get("command") == "daily.run"
    assert parsed.get("flow") == "daily_quest"


@pytest.mark.skipif(not _CAN_EXECUTE_TASKS, reason="device/MaaEnd not available")
def test_harvest_returns_success() -> None:
    returncode, parsed, _ = _run_cli(["harvest"])
    assert returncode in (0, 1)
    assert parsed.get("status") == "success"
    assert parsed.get("command") == "harvest.run"
    assert parsed.get("flow") == "entity_harvest"


@pytest.mark.skipif(not _CAN_EXECUTE_TASKS, reason="device/MaaEnd not available")
def test_analyze_returns_success() -> None:
    returncode, parsed, _ = _run_cli(["analyze"])
    assert returncode in (0, 1)
    assert parsed.get("status") == "success"
    assert parsed.get("command") == "analyze.run"


@pytest.mark.skipif(not _CAN_EXECUTE_TASKS, reason="device/MaaEnd not available")
def test_explore_returns_success() -> None:
    returncode, parsed, _ = _run_cli(["explore"])
    assert returncode in (0, 1)
    assert parsed.get("status") == "success"
    assert parsed.get("command") == "explore.run"
