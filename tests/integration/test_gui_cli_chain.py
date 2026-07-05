from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import QApplication

from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.pages.maaend_control_page import MaaEndControlPage


def test_cli_bridge_can_be_instantiated_with_mocked_process() -> None:
    bridge = CLIBridge()
    assert bridge is not None
    assert bridge._crash_count == 0
    assert bridge._max_crashes == 5


def test_cli_bridge_execute_builds_args_and_starts_process(qapp: QApplication) -> None:
    bridge = CLIBridge()
    fake_process = MagicMock(spec=QProcess)
    fake_process.waitForStarted.return_value = True

    with patch("gui.pyqt6.cli_bridge.QProcess", return_value=fake_process):
        bridge.execute("daily", {"options": {"repeat": 3}})

    assert "daily" in bridge._last_command
    assert fake_process.start.called


def test_cli_bridge_parses_stdout_json_lines(qapp: QApplication) -> None:
    bridge = CLIBridge()
    bridge._last_command = ["daily"]
    fake_process = MagicMock()
    fake_process.readAllStandardOutput.return_value = (
        b'{"status":"ok"}\n{"status":"done"}\n'
    )
    bridge._process = fake_process

    results = []
    bridge.commandFinished.connect(lambda cmd, res: results.append((cmd, res)))
    bridge._on_stdout()

    assert len(results) == 2
    assert results[0][1] == {"status": "ok"}
    assert results[1][1] == {"status": "done"}


def test_maaend_control_page_receives_bridge_and_calls_execute(
    qapp: QApplication,
) -> None:
    bridge = CLIBridge()
    fake_process = MagicMock(spec=QProcess)
    fake_process.waitForStarted.return_value = True

    with patch("gui.pyqt6.cli_bridge.QProcess", return_value=fake_process):
        page = MaaEndControlPage(bridge)
        captured = []

        def on_finished(cmd, res):
            captured.append((cmd, res))

        bridge.commandFinished.connect(on_finished)
        bridge.commandFinished.emit("preset list", {"status": "success", "presets": {}})

    assert page._bridge is bridge
    assert any(item[0] == "preset list" for item in captured)


def test_command_finished_propagates_from_bridge_to_page(
    qapp: QApplication,
) -> None:
    bridge = CLIBridge()
    fake_process = MagicMock(spec=QProcess)
    fake_process.waitForStarted.return_value = True

    with patch("gui.pyqt6.cli_bridge.QProcess", return_value=fake_process):
        page = MaaEndControlPage(bridge)
        captured = []

        def on_finished(cmd, res):
            captured.append((cmd, res))

        bridge.commandFinished.connect(on_finished)
        bridge.commandFinished.emit(
            "preset list", {"status": "success", "presets": {}}
        )

    assert len(captured) == 1
    assert captured[0][0] == "preset list"
    assert captured[0][1]["status"] == "success"


def test_maaend_page_sync_execute_receives_bridge_result(
    qapp: QApplication,
) -> None:
    bridge = CLIBridge()

    def fake_execute(command, params=None):
        bridge.commandFinished.emit(command, {"status": "success", "presets": {}})

    with patch.object(bridge, "execute", side_effect=fake_execute):
        page = MaaEndControlPage(bridge)
        result = page._sync_execute("preset list", timeout_ms=1000)

    assert result is not None
    assert result.get("status") == "success"


def test_maaend_page_can_refresh_preset_list_through_bridge(
    qapp: QApplication,
) -> None:
    bridge = CLIBridge()

    with patch.object(MaaEndControlPage, "_sync_execute") as mock_sync_execute, patch.object(
        MaaEndControlPage, "_load_options", return_value=None
    ):
        mock_sync_execute.side_effect = lambda command, timeout_ms=1200: (
            {"status": "success", "presets": {"QuickDaily": {"task": []}}}
            if command == "preset list"
            else {"status": "success", "tasks": {}}
        )
        page = MaaEndControlPage(bridge)
        page._presets_cache = {}
        page._selected_preset = "QuickDaily"
        page._refresh_preset_list()

    assert page._preset_list.count() == 1
