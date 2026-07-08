import importlib.util
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QTableWidgetItem


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
        self.commandError = _FakeSignal()
        self.logMessage = _FakeSignal()
        self._presets = {
            "TestPreset": {
                "task": [
                    {"name": "TaskA", "option": {}},
                    {"name": "TaskB", "option": {}},
                ]
            }
        }
        self._tasks = {"TaskA": {}, "TaskB": {}}
        self.calls = []

    def execute(self, command: str, params=None):
        self.calls.append((command, params or {}))
        if command == "preset list":
            payload = {"status": "success", "presets": self._presets}
        elif command == "task list":
            payload = {"status": "success", "tasks": self._tasks}
        elif command == "device info":
            payload = {"status": "success", "devices": [{"serial": "localhost:16512", "status": "ready"}]}
        else:
            payload = {"status": "success"}
        self.commandFinished.emit(command, payload)


def test_apply_preset_button_replaces_queue():
    app = QApplication.instance() or QApplication([])
    module = _load_control_page()
    bridge = FakeCLIBridge()
    page = module.MaaEndControlPage(bridge)

    state_dir = Path(tempfile.mkdtemp(prefix="maaend_state_preset_"))
    page._state_path = state_dir / "maaend_task_state.json"
    page._queue_state.set_state_path(page._state_path)

    page._queue_state.set_queue_items([{"name": "OldTask", "type": "task", "options": {}}])
    page._queue_list.setRowCount(1)
    page._queue_list.setItem(0, 0, QTableWidgetItem("[TASK] OldTask"))
    page._selected_preset = "TestPreset"
    page._presets_cache = bridge._presets

    page._apply_preset_to_queue_btn.click()

    assert [entry["name"] for entry in page._queue_state.queue_items] == ["TaskA", "TaskB"]
    assert page._queue_list.rowCount() == 2
    assert page._is_executing is False
    assert not any(command == "system connect" for command, _ in bridge.calls)
    app.quit()


def test_control_page_uses_cjk_capable_font_for_chinese_ui():
    app = QApplication.instance() or QApplication([])
    module = _load_control_page()
    bridge = FakeCLIBridge()
    page = module.MaaEndControlPage(bridge)
    page.show()
    app.processEvents()

    assert page._status_label.text() == "空闲"
    assert page._apply_preset_to_queue_btn.text() == "应用预设"
    assert page._add_task_to_queue_btn.text() == "添加任务"
    assert page._status_label.font().family() in {"Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "SimSun"}
    assert page._apply_preset_to_queue_btn.font().family() in {"Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "SimSun"}
    assert page._add_task_to_queue_btn.font().family() in {"Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "SimSun"}
    assert page._log_text.font().family() in {"Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "SimSun"}
    app.quit()


def test_control_page_connect_uses_last_connected_device():
    app = QApplication.instance() or QApplication([])
    module = _load_control_page()
    bridge = FakeCLIBridge()
    page = module.MaaEndControlPage(bridge)

    workspace_tmp = Path(__file__).resolve().parent.parent / ".tmp" / "test_control_page_connect"
    config_dir = workspace_tmp / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "client_config.json").write_text(
        '{"device":{"last_connected":"127.0.0.1:16384"}}',
        encoding="utf-8",
    )

    original_get_project_root = sys.modules["core.foundation.paths"].get_project_root
    sys.modules["core.foundation.paths"].get_project_root = lambda: workspace_tmp
    try:
        result = page._sync_execute("system connect", page._resolve_connect_params())
    finally:
        sys.modules["core.foundation.paths"].get_project_root = original_get_project_root

    assert result is not None
    assert ("system connect", {"serial": "127.0.0.1:16384"}) in bridge.calls
    app.quit()


def test_queue_items_strip_inline_parameters_from_execution_name():
    app = QApplication.instance() or QApplication([])
    module = _load_control_page()
    bridge = FakeCLIBridge()
    page = module.MaaEndControlPage(bridge)

    name, inline_options = page._parse_inline_task_name('TaskA|{"repeat": 2}')
    assert name == "TaskA"
    assert inline_options == {"repeat": 2}

    runtime_name, runtime_options = page._normalize_runtime_entry(
        {"name": 'TaskA|{"repeat": 2}', "options": {"speed": "fast"}}
    )
    assert runtime_name == "TaskA"
    assert runtime_options == {"repeat": 2, "speed": "fast"}
    app.quit()


def test_control_page_persists_queue_state():
    app = QApplication.instance() or QApplication([])
    module = _load_control_page()
    bridge = FakeCLIBridge()
    page = module.MaaEndControlPage(bridge)
    state_dir = Path(tempfile.mkdtemp(prefix="maaend_state_"))
    page._state_path = state_dir / "maaend_task_state.json"
    page._queue_state.set_queue_items([
        {"name": "TaskA", "display_name": "TaskA", "type": "task", "options": {"repeat": 2}}
    ])
    page._queue_state.save_options("TaskA", {"repeat": 2})
    page._persist_state()

    content = page._state_path.read_text(encoding="utf-8")
    assert '"TaskA"' in content
    assert '"repeat": 2' in content
    app.quit()


def test_control_page_resize_keeps_fixed_layout_geometry():
    app = QApplication.instance() or QApplication([])
    module = _load_control_page()
    bridge = FakeCLIBridge()
    page = module.MaaEndControlPage(bridge)

    page.resize(1600, 980)
    app.processEvents()
    first_sizes = page._splitter.sizes()

    page.resize(1280, 820)
    app.processEvents()
    second_sizes = page._splitter.sizes()

    assert len(first_sizes) == 3
    assert len(second_sizes) == 3
    assert page._preset_list.minimumHeight() >= 60
    assert page._task_list.minimumHeight() >= 80
    assert page._queue_list.minimumHeight() >= 60
    assert page._log_text.minimumHeight() >= 60
    app.quit()


def test_apply_queue_focus_task_settings_saves_to_queue_state():
    app = QApplication.instance() or QApplication([])
    module = _load_control_page()
    bridge = FakeCLIBridge()
    page = module.MaaEndControlPage(bridge)

    page._queue_state.set_queue_items([
        {"name": "TaskA", "display_name": "TaskA", "type": "task", "options": {"speed": "fast"}}
    ])
    page._queue_list.setRowCount(1)
    page._queue_list.setItem(0, 0, QTableWidgetItem("[TASK] TaskA"))
    page._queue_list.setCurrentCell(0, 0)

    page._selected_task = "TaskA"
    page._tasks_cache = {"TaskA": {"option": []}}
    page._task_option_defs = {}
    page._option_widgets = {}
    page._collect_options = lambda: {"speed": "fast"}  # type: ignore[method-assign]

    page._save_options()

    assert page._queue_state.load_options("TaskA") == {"speed": "fast"}
    assert page._queue_state.queue_items[0]["options"] == {"speed": "fast"}
    app.quit()


def test_queue_clear_removes_specific_task_settings():
    app = QApplication.instance() or QApplication([])
    module = _load_control_page()
    bridge = FakeCLIBridge()
    page = module.MaaEndControlPage(bridge)

    page._queue_state.save_options("TaskA", {"repeat": 2})
    page._queue_state.save_options("TaskB", {"skip": True})
    page._queue_state.set_queue_items([
        {"name": "TaskA", "display_name": "TaskA", "type": "task", "options": {}},
        {"name": "TaskB", "display_name": "TaskB", "type": "task", "options": {}},
    ])
    page._queue_list.setRowCount(2)
    page._queue_list.setItem(0, 0, QTableWidgetItem("[TASK] TaskA"))
    page._queue_list.setItem(1, 0, QTableWidgetItem("[TASK] TaskB"))

    page._queue_clear()

    assert page._queue_state.load_options("TaskA") == {}
    assert page._queue_state.load_options("TaskB") == {}
    assert page._queue_state.queue_items == []
    app.quit()


def test_apply_preset_overrides_queue_and_clears_old_settings():
    app = QApplication.instance() or QApplication([])
    module = _load_control_page()
    bridge = FakeCLIBridge()
    page = module.MaaEndControlPage(bridge)

    state_dir = Path(tempfile.mkdtemp(prefix="maaend_state_override_"))
    page._state_path = state_dir / "maaend_task_state.json"
    page._queue_state.set_state_path(page._state_path)

    page._queue_state.save_options("OldTask", {"old_option": "old_value"})
    page._queue_state.save_options("TaskA", {"option_a": "value_a"})
    page._queue_state.set_queue_items([
        {"name": "OldTask", "display_name": "OldTask", "type": "task", "options": {}},
    ])
    page._queue_list.setRowCount(1)
    page._queue_list.setItem(0, 0, QTableWidgetItem("[TASK] OldTask"))
    page._selected_preset = "TestPreset"
    page._presets_cache = bridge._presets

    page._apply_preset_to_queue()

    assert page._queue_state.load_options("OldTask") == {}
    assert page._queue_state.load_options("TaskA") == {"option_a": "value_a"}
    assert [entry["name"] for entry in page._queue_state.queue_items] == ["TaskA", "TaskB"]
    app.quit()


def test_queue_task_settings_persist_through_restart():
    app = QApplication.instance() or QApplication([])
    module = _load_control_page()
    bridge = FakeCLIBridge()
    page = module.MaaEndControlPage(bridge)

    state_dir = Path(tempfile.mkdtemp(prefix="maaend_state_restart_"))
    page._state_path = state_dir / "maaend_task_state.json"

    page._queue_state.set_queue_items([
        {"name": "TaskA", "display_name": "TaskA", "type": "task", "options": {"speed": "fast"}}
    ])
    page._queue_state.save_options("TaskA", {"speed": "fast", "repeat": 3})
    page._queue_state.set_selected_task("TaskA")
    page._persist_state()

    new_page = module.MaaEndControlPage(bridge)
    new_page._state_path = state_dir / "maaend_task_state.json"
    new_page._queue_state.set_state_path(new_page._state_path)
    new_page._queue_state.load()
    new_page._restore_queue_ui()

    assert new_page._queue_state.load_options("TaskA") == {"speed": "fast", "repeat": 3}
    assert new_page._queue_state.queue_items[0]["options"] == {"speed": "fast"}
    assert new_page._selected_task == "TaskA"
    app.quit()
