import json
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QProcess, QTimer
from PyQt6.QtWidgets import QApplication

from gui.pyqt6.cli_bridge import CLIBridge


def test_cli_bridge_can_be_instantiated() -> None:
    bridge = CLIBridge()
    assert bridge is not None
    assert bridge._crash_count == 0
    assert bridge._max_crashes == 5


def test_cli_bridge_execute_stores_command_and_starts_process(qapp: QApplication) -> None:
    bridge = CLIBridge()
    captured_args = {}

    fake_process = MagicMock(spec=QProcess)
    fake_process.state.return_value = QProcess.ProcessState.NotRunning
    fake_process.waitForStarted.return_value = True

    with patch("gui.pyqt6.cli_bridge.QProcess", return_value=fake_process) as mock_qprocess:
        bridge.execute("daily", {"arg1": "value1"})
        captured_args["last_command"] = list(bridge._last_command)
        captured_args["started_command"] = mock_qprocess.return_value.start.call_args

    assert "daily" in captured_args["last_command"]
    assert "--arg1" in captured_args["last_command"]
    assert "value1" in captured_args["last_command"]
    assert captured_args["started_command"] is not None


def test_cli_bridge_on_stdout_parses_json_lines(qapp: QApplication) -> None:
    bridge = CLIBridge()
    bridge._last_command = ["daily"]

    fake_process = MagicMock()
    fake_process.readAllStandardOutput.return_value = b'{"status":"ok"}\n{"status":"done"}\n'
    bridge._process = fake_process

    finished_results = []

    def capture(command, result):
        finished_results.append((command, result))

    bridge.commandFinished.connect(capture)
    bridge._on_stdout()

    assert len(finished_results) == 2
    assert finished_results[0][1] == {"status": "ok"}
    assert finished_results[1][1] == {"status": "done"}


def test_cli_bridge_on_error_increments_crash_count_and_restarts(qapp: QApplication) -> None:
    bridge = CLIBridge()
    bridge._last_command = ["daily"]
    bridge._process = MagicMock()

    finished_crashes = []

    def capture(count):
        finished_crashes.append(count)

    bridge.processCrashed.connect(capture)

    with patch.object(QTimer, "singleShot") as mock_timer:
        bridge._on_error(QProcess.ProcessError.Crashed)
        assert bridge._crash_count == 1
        assert finished_crashes == [1]
        assert mock_timer.call_count == 1


def test_cli_bridge_on_error_shows_dialog_after_max_crashes(qapp: QApplication) -> None:
    bridge = CLIBridge()
    bridge._crash_count = 4
    bridge._process = MagicMock()

    with patch("gui.pyqt6.cli_bridge.QMessageBox.critical") as mock_dialog:
        bridge._on_error(QProcess.ProcessError.Crashed)
        assert bridge._crash_count == 5
        assert mock_dialog.call_count == 1
