import os
import tempfile
from pathlib import Path

import pytest
from PyQt6.QtCore import QProcess, QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
workspace_tmp = Path(__file__).resolve().parent.parent / ".tmp" / "pytest-qt-temp"
workspace_tmp.mkdir(parents=True, exist_ok=True)
os.environ["TMPDIR"] = str(workspace_tmp)
os.environ["TEMP"] = str(workspace_tmp)
os.environ["TMP"] = str(workspace_tmp)
tempfile.tempdir = str(workspace_tmp)


def _ensure_src_path() -> None:
    project_root = Path(__file__).resolve().parent.parent
    src_dir = project_root / "src"
    if str(src_dir) not in os.sys.path:
        os.sys.path.insert(0, str(src_dir))


_ensure_src_path()


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def _disable_modal_message_boxes(monkeypatch):
    """Suppress modal QMessageBox dialogs in tests so timeouts can fire correctly."""
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "about", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes
    )


class _FakeProcess:
    readyReadStandardOutput = pyqtSignal()
    readyReadStandardError = pyqtSignal()
    finished = pyqtSignal(int, int)
    errorOccurred = pyqtSignal(int)
    started = pyqtSignal()

    def __init__(self) -> None:
        self._state = None

    def state(self) -> "QProcess.ProcessState":
        return self._state if self._state is not None else QProcess.ProcessState.NotRunning

    def waitForStarted(self, *args, **kwargs) -> bool:
        return True

    def start(self, *args, **kwargs) -> None:
        pass

    def write(self, *args, **kwargs) -> None:
        pass

    def readAllStandardOutput(self) -> bytes:
        return b""

    def readAllStandardError(self) -> bytes:
        return b""

    def deleteLater(self) -> None:
        pass


class _FakeQProcess:
    ProcessState = QProcess.ProcessState
    ExitStatus = QProcess.ExitStatus
    ProcessError = QProcess.ProcessError

    def __init__(self, *args, **kwargs):
        self._instance = _FakeProcess()

    def __call__(self, *args, **kwargs):
        return self._instance

    def __getattr__(self, name):
        return getattr(QProcess, name)


@pytest.fixture()
def mock_bridge(monkeypatch, qapp):
    from gui.pyqt6.cli_bridge import CLIBridge

    bridge = CLIBridge()
    bridge._process = _FakeProcess()
    monkeypatch.setattr("gui.pyqt6.cli_bridge.QProcess", _FakeQProcess())
    return bridge


@pytest.fixture()
def temp_config(tmp_path):
    import json
    config_file = tmp_path / "client_config.json"
    config_file.write_text(
        json.dumps({"server": {"host": "127.0.0.1", "port": 9999}}, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(config_file)
