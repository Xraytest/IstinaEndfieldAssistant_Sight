import importlib.util
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication


def _load_control_page():
    module_name = "src.gui.pyqt6.pages.maaend_control_page"
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = (
        Path(__file__).resolve().parent.parent / "src" / "gui" / "pyqt6" / "pages" / "maaend_control_page.py"
    )
    if not path.exists():
        raise AssertionError("Cannot find maaend_control_page.py")
    path = str(path)
    fake_pkg = type(sys)("src.gui.pyqt6.pages")
    sys.modules["src.gui.pyqt6.pages"] = fake_pkg
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def disconnect(self, callback):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class FakeCLIBridge:
    def __init__(self):
        self.commandFinished = _FakeSignal()
        self._presets = {
            "TestPreset": {
                "task": [
                    {"name": "TaskA", "option": {}},
                    {"name": "TaskB", "option": {}},
                ]
            }
        }
        self._tasks = {"TaskA": {}, "TaskB": {}}

    def execute(self, command: str):
        if command == "preset list":
            payload = {"status": "success", "presets": self._presets}
        elif command == "task list":
            payload = {"status": "success", "tasks": self._tasks}
        else:
            payload = {"status": "success"}
        self.commandFinished.emit(command, payload)


def test_apply_preset_button_replaces_queue():
    app = QApplication.instance() or QApplication([])
    module = _load_control_page()
    bridge = FakeCLIBridge()
    page = module.MaaEndControlPage(bridge)

    page._queue_items = [{"name": "OldTask", "type": "task", "options": {}}]
    page._queue_list.addItem("[TASK] OldTask")
    page._selected_preset = "TestPreset"

    page._run_preset_btn.click()

    assert [entry["name"] for entry in page._queue_items] == ["TaskA", "TaskB"]
    assert page._queue_list.count() == 2
    app.quit()
