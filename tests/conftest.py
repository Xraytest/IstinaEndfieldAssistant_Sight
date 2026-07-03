import os
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


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


class _FakeProcess:
    def __init__(self) -> None:
        self.state = lambda: None
        self.waitForStarted = lambda *args, **kwargs: True


@pytest.fixture()
def mock_bridge(monkeypatch, qapp):
    from gui.pyqt6.cli_bridge import CLIBridge

    bridge = CLIBridge()
    bridge._process = _FakeProcess()
    monkeypatch.setattr("gui.pyqt6.cli_bridge.QProcess", lambda *args, **kwargs: bridge._process)
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
