from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ISTINA_SCRIPT = PROJECT_ROOT / "src" / "cli" / "istina.py"
VENV_PYTHON = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
CLI = [str(VENV_PYTHON), str(ISTINA_SCRIPT)]


def _run_cli(argv, env=None):
    if env is None:
        env = dict(os.environ)
    proc = subprocess.run(
        CLI + argv,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
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


def test_cli_subprocess_invocation_for_device_info() -> None:
    returncode, parsed, _ = _run_cli(["device", "info"])
    assert returncode in (0, 1)
    assert isinstance(parsed, dict)
    assert parsed.get("status") == "success"
    assert "devices" in parsed
    assert isinstance(parsed["devices"], list)


def test_cli_subprocess_invocation_for_device_status() -> None:
    returncode, parsed, _ = _run_cli(["device", "status"])
    assert returncode in (0, 1)
    assert isinstance(parsed, dict)
    assert parsed.get("status") == "success"
    assert "adb_server" in parsed
    assert "devices" in parsed


def test_cli_subprocess_invocation_for_system_connect() -> None:
    returncode, parsed, _ = _run_cli(["system", "connect"])
    assert returncode in (0, 1)
    assert isinstance(parsed, dict)
    assert "status" in parsed


def test_cli_subprocess_invocation_for_screenshot() -> None:
    returncode, parsed, _ = _run_cli(["screenshot"])
    assert returncode in (0, 1)
    assert isinstance(parsed, dict)


def test_all_commands_output_valid_json() -> None:
    commands = [
        ["system", "env"],
        ["system", "disk"],
        ["device", "info"],
        ["device", "status"],
        ["screenshot"],
        ["nav", "hub"],
        ["daily"],
        ["harvest"],
        ["analyze"],
        ["explore"],
    ]
    for command in commands:
        returncode, parsed, _ = _run_cli(command)
        assert returncode in (0, 1)
        assert parsed is not None
        assert isinstance(parsed, dict)


def test_implemented_commands_return_success() -> None:
    returncode, parsed, _ = _run_cli(["nav", "hub"])
    assert returncode in (0, 1)
    assert parsed.get("status") == "success"
    assert parsed.get("command") == "nav.to"
    assert parsed.get("target") == "hub"

    returncode, parsed, _ = _run_cli(["daily"])
    assert returncode in (0, 1)
    assert parsed.get("status") == "success"
    assert parsed.get("command") == "daily.run"
    assert parsed.get("flow") == "daily_quest"


def test_cli_config_get_set_uses_temp_config(tmp_path) -> None:
    config_file = tmp_path / "client_config.json"
    config_file.write_text(
        json.dumps({"existing_key": "existing_value"}, ensure_ascii=False),
        encoding="utf-8",
    )

    returncode_get, parsed_get, _ = _run_cli(
        ["--config", str(config_file), "config", "get", "existing_key"]
    )
    assert returncode_get == 0
    assert parsed_get.get("status") == "success"
    assert parsed_get.get("value") == "existing_value"

    returncode_set, parsed_set, _ = _run_cli(
        ["--config", str(config_file), "config", "set", "new_key", "new_value"]
    )
    assert returncode_set == 0
    assert parsed_set.get("status") == "success"
    assert parsed_set.get("key") == "new_key"
    assert parsed_set.get("value") == "new_value"