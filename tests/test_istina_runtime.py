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
def _disable_broken_project_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    for method in ("debug", "info", "warning", "error", "critical", "log", "exception"):
        setattr(logging.Logger, method, lambda self, *args, **kwargs: None)
    # Runtime routing tests use fake MaaEnd objects and must not enter the
    # real 90-second cloud-game startup/OCR polling loop.
    from core.service.runtime import IstinaRuntime
    monkeypatch.setattr(IstinaRuntime, "_ensure_game_in_world", lambda self, *args: True)
    monkeypatch.setattr(
        IstinaRuntime,
        "_auto_collect_run",
        lambda self, params: {"status": "success", "command": "auto.collect"},
    )


def test_istina_runtime_can_be_instantiated() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    assert runtime is not None
    assert isinstance(runtime.config, dict)


def test_scale_for_screen_uses_cloud_landscape_reference() -> None:
    from core.service.runtime import IstinaRuntime

    assert IstinaRuntime._scale_for_screen((1094, 633), (1280, 720)) == (1094, 633)
    assert IstinaRuntime._scale_for_screen((1094, 633), (2560, 1440)) == (2188, 1266)


def test_cloud_package_overrides_stale_config() -> None:
    from core.service.runtime import _get_game_package
    from core.foundation.constants import GAME_PACKAGE_CLOUD_ENDFIELD

    assert _get_game_package({"device": {"package": "com.hypergryph.endfield"}}, "CloudCN") == GAME_PACKAGE_CLOUD_ENDFIELD


def test_client_version_switch_rebuilds_connected_runtime() -> None:
    from core.service.runtime import IstinaRuntime

    class _Runtime:
        client_version = "CN"
        connected = True
        _game_package = "com.hypergryph.endfield"

        def __init__(self) -> None:
            self.calls = []

        def set_client_version(self, version):
            self.calls.append(("set", version))
            if self.connected and version == "CloudCN":
                raise RuntimeError("connected")
            self.client_version = version

        def disconnect(self):
            self.calls.append(("disconnect",))
            self.connected = False

        def connect(self):
            self.calls.append(("connect",))
            self.connected = True
            return True

        def load_resource(self):
            self.calls.append(("load_resource",))
            return True

    runtime = IstinaRuntime()
    maaend = _Runtime()
    assert runtime._set_client_version(maaend, {"ClientVersion": "CloudCN"}) == "CloudCN"
    assert maaend.client_version == "CloudCN"
    assert maaend._game_package == "com.hypergryph.cloud.endfield"
    assert maaend.calls == [("set", "CloudCN"), ("disconnect",), ("set", "CloudCN"), ("connect",), ("load_resource",)]


def test_input_observation_sink_filters_completed_input_actions() -> None:
    from types import SimpleNamespace
    from core.service.maa_end import runtime as maa_end_module

    class _Observer:
        def __init__(self) -> None:
            self.events = []

        def _enqueue_input_observation(self, controller, action, param, info) -> None:
            self.events.append((controller, action, param, info))

    observer = _Observer()
    sink = maa_end_module._InputObservationSink(observer)
    sink.on_controller_action("ctrl", maa_end_module.NotificationType.Succeeded, SimpleNamespace(
        action="Click", param={"x": 1}, info={"node": "A"}
    ))
    sink.on_controller_action("ctrl", maa_end_module.NotificationType.Starting, SimpleNamespace(
        action="Swipe", param={}, info={}
    ))
    sink.on_controller_action("ctrl", maa_end_module.NotificationType.Succeeded, SimpleNamespace(
        action="Screenshot", param={}, info={}
    ))
    sink.on_raw_notification(
        "ctrl",
        "Controller.Action.Succeeded",
        {"uuid": "u1", "action": "Controller.Click", "param": {"x": 2}, "info": {"node": "B"}},
    )
    sink.on_raw_notification(
        "ctrl",
        "Controller.Action.Succeeded",
        {"uuid": "u1", "action": "Click", "param": {"x": 2}, "info": {"node": "B"}},
    )
    assert observer.events == [
        ("ctrl", "Click", {"x": 1}, {"node": "A"}),
        ("ctrl", "Click", {"x": 2}, {"node": "B"}),
    ]


def test_task_action_observation_sink_enqueues_pipeline_inputs() -> None:
    from core.service.maa_end import runtime as maa_end_module

    class _Observer:
        def __init__(self) -> None:
            self.events = []

        def _enqueue_input_observation(self, controller, action, param, info) -> None:
            self.events.append((controller, action, param, info))

    observer = _Observer()
    sink = maa_end_module._TaskActionObservationSink(observer)

    click_details = {
        "task_id": 1,
        "name": "AutoSellMain",
        "action_details": {
            "action": "Action.Click",
            "action_id": 5,
            "box": [10, 20, 30, 40],
            "detail": {"point": [25, 40]},
        },
    }
    # 输入动作入队，携带 node/box/point 观测信息
    sink.on_raw_notification("ctx", "Node.Action.Succeeded", click_details)
    # 相同 task_id:action_id 重复事件去重
    sink.on_raw_notification("ctx", "Node.Action.Succeeded", click_details)
    # 非输入动作（Screencap）过滤
    sink.on_raw_notification(
        "ctx",
        "Node.Action.Succeeded",
        {
            "task_id": 1,
            "name": "ShotNode",
            "action_details": {"action": "Action.Screencap", "action_id": 6, "detail": {}},
        },
    )
    # 非 Node.Action.Succeeded 消息过滤
    sink.on_raw_notification(
        "ctx",
        "Node.Recognition.Succeeded",
        {
            "task_id": 1,
            "name": "AutoSellMain",
            "action_details": {"action": "Action.Click", "action_id": 7, "detail": {}},
        },
    )
    # 缺少 action_details 过滤
    sink.on_raw_notification("ctx", "Node.Action.Succeeded", {"task_id": 1})
    # Swipe 动作入队，缺失 detail.point 时为 None
    sink.on_raw_notification(
        "ctx",
        "Node.Action.Succeeded",
        {
            "task_id": 2,
            "name": "SomeSwipe",
            "action_details": {"action": "Swipe", "action_id": 8},
        },
    )

    assert observer.events == [
        (
            None,
            "Click",
            {"node": "AutoSellMain", "box": [10, 20, 30, 40], "point": [25, 40]},
            {},
        ),
        (None, "Swipe", {"node": "SomeSwipe", "box": None, "point": None}, {}),
    ]


def test_task_action_observation_sink_ignores_non_dict_payloads() -> None:
    from core.service.maa_end import runtime as maa_end_module

    class _Observer:
        def __init__(self) -> None:
            self.events = []

        def _enqueue_input_observation(self, controller, action, param, info) -> None:
            self.events.append((controller, action, param, info))

    observer = _Observer()
    sink = maa_end_module._TaskActionObservationSink(observer)
    sink.on_raw_notification("ctx", "Node.Action.Succeeded", None)  # type: ignore[arg-type]
    sink.on_raw_notification("ctx", "Node.Action.Succeeded", "payload")  # type: ignore[arg-type]
    sink.on_raw_notification(
        "ctx",
        "Node.Action.Succeeded",
        {"task_id": 1, "action_details": "not-a-dict"},
    )
    assert observer.events == []


def test_input_observations_flush_completed_queue() -> None:
    from core.service.maa_end.runtime import MaaEndRuntime

    runtime = MaaEndRuntime()
    runtime._input_observation_queue.put((object(), "Click", {}, {}))
    runtime._input_observation_queue.task_done()
    assert runtime._flush_input_observations(timeout_s=0.01) is True


def test_android_returns_android_runtime() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    android = runtime.android()
    assert android is not None
    assert type(android).__name__ == "AndroidRuntime"


def test_maaend_resource_profile_switches_before_connect() -> None:
    from core.service.maa_end.runtime import MaaEndRuntime

    runtime = MaaEndRuntime(client_version="CN")
    runtime.set_client_version("CloudCN")
    assert runtime.client_version == "CloudCN"
    assert runtime._primary_resource_name() == "resource_cloud"


def test_resource_bundle_dirs_default(tmp_path) -> None:
    from core.service.maa_end.runtime import MaaEndRuntime

    for sub in ("resource", "resource_adb", "resource_cloud"):
        (tmp_path / sub).mkdir()
    runtime = MaaEndRuntime(maaend_root=str(tmp_path), client_version="CN")
    dirs = [d.name for d in runtime._resource_bundle_dirs()]
    assert dirs == ["resource", "resource_adb"]


def test_resource_bundle_dirs_cloud_overlays_base(tmp_path) -> None:
    """CloudCN 必须先载基础包 resource，再叠 resource_cloud，最后 resource_adb。

    仅加载 resource_cloud 会因缺少 image/ 导致全部 TemplateMatch 失败（见
    MaaEndRuntime._resource_bundle_dirs 的历史缺陷说明）。
    """
    from core.service.maa_end.runtime import MaaEndRuntime

    for sub in ("resource", "resource_adb", "resource_cloud"):
        (tmp_path / sub).mkdir()
    runtime = MaaEndRuntime(maaend_root=str(tmp_path), client_version="CloudCN")
    dirs = [d.name for d in runtime._resource_bundle_dirs()]
    assert dirs == ["resource", "resource_cloud", "resource_adb"]


def test_resource_bundle_dirs_cloud_missing_overlay_falls_back(tmp_path) -> None:
    from core.service.maa_end.runtime import MaaEndRuntime

    (tmp_path / "resource").mkdir()
    (tmp_path / "resource_adb").mkdir()
    runtime = MaaEndRuntime(maaend_root=str(tmp_path), client_version="CloudCN")
    dirs = [d.name for d in runtime._resource_bundle_dirs()]
    assert dirs == ["resource", "resource_adb"]


def test_cloud_ocr_model_falls_back_to_shared_resource(tmp_path) -> None:
    from core.service.maa_end.runtime import MaaEndRuntime

    model_dir = tmp_path / "resource" / "model" / "ocr"
    model_dir.mkdir(parents=True)
    for name in ("det.onnx", "rec.onnx", "keys.txt"):
        (model_dir / name).write_bytes(b"model")

    class _Job:
        succeeded = True

        def wait(self):
            return self

    class _Resource:
        def __init__(self) -> None:
            self.loaded = None

        def post_ocr_model(self, path):
            self.loaded = path
            return _Job()

    runtime = MaaEndRuntime(maaend_root=str(tmp_path), client_version="CloudCN")
    runtime._resource = _Resource()

    assert runtime._load_ocr_model() is True
    assert runtime._resource.loaded == model_dir


def test_ocr_model_missing_rejects_resource(tmp_path) -> None:
    from core.service.maa_end.runtime import MaaEndRuntime

    runtime = MaaEndRuntime(maaend_root=str(tmp_path), client_version="CloudCN")
    class _Resource:
        def post_ocr_model(self, path):
            raise AssertionError("missing models must be rejected before registration")

    runtime._resource = _Resource()
    assert runtime._load_ocr_model() is False


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


def test_execute_routes_screenshot_returns_bytes() -> None:
    from core.service.runtime import IstinaRuntime
    from unittest.mock import MagicMock, patch

    runtime = IstinaRuntime()
    runtime._maaend = _FakeMaaEndRuntime(screenshot_result=b"PNG")

    proxy = runtime.android()
    fake_android = MagicMock()
    fake_android.screenshot.return_value = None
    proxy._clients["default"] = fake_android

    # execute() 会重新加载磁盘配置，这里避免真实 device serial 干扰测试。
    runtime._config = {"device": {}}
    with patch.object(runtime, "_load_config", return_value=runtime._config):
        result = runtime.execute("screenshot", {})
    assert result == b"PNG"


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


def test_execute_routes_daily_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    runtime._maaend = _FakeMaaEndRuntime(
        run_task_result=True,
        run_pipeline_result=True,
        run_preset_result=True,
    )
    monkeypatch.setattr(runtime, "_ensure_game_in_world", lambda *args: True)
    result = runtime.execute("daily.run", {"options": {"a": 1}})
    assert isinstance(result, dict)
    assert result.get("status") == "success"
    assert result.get("command") == "daily.run"
    assert result.get("flow") == "daily_quest"



def test_execute_routes_harvest_run() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    runtime._maaend = _FakeMaaEndRuntime(run_task_result=True)
    result = runtime.execute("harvest.run", {"options": {}})
    assert isinstance(result, dict)
    assert result.get("status") == "success"
    assert result.get("command") == "harvest.run"
    assert result.get("flow") == "entity_harvest"


def test_execute_routes_analyze_run() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    runtime._maaend = _FakeMaaEndRuntime(run_task_result=True)
    result = runtime.execute("analyze.run", {"options": {}})
    assert isinstance(result, dict)
    assert result.get("status") == "success"
    assert result.get("command") == "analyze.run"


def test_execute_routes_explore_run() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    runtime._maaend = _FakeMaaEndRuntime(run_task_result=True)
    result = runtime.execute("explore.run", {"options": {}})
    assert isinstance(result, dict)
    assert result.get("status") == "success"
    assert result.get("command") == "explore.run"


def test_execute_routes_nav_to() -> None:
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    runtime._maaend = _FakeMaaEndRuntime(run_task_result=True)
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
        run_pipeline_result: bool = False,
        screenshot_result=None,
    ) -> None:
        self._connect_result = connect_result
        self._load_resource_result = load_resource_result
        self._run_task_result = run_task_result
        self._run_preset_result = run_preset_result
        self._run_pipeline_result = run_pipeline_result
        self._screenshot_result = screenshot_result
        self._connected = True


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

    def run_task(self, name: str, options: dict, timeout=None) -> bool:
        return self._run_task_result

    def run_pipeline(self, entry: str, pipeline_override: dict) -> bool:
        return self._run_pipeline_result

    def run_preset(self, name: str, timeout=None) -> bool:
        return self._run_preset_result


    def screenshot(self):
        return self._screenshot_result

    def tasks(self) -> dict:
        return {}

    def presets(self) -> dict:
        return {}


class _NeverDoneJob:
    wait_called = False
    succeeded = False

    @property
    def done(self) -> bool:
        return False

    def wait(self):
        self.wait_called = True
        return self


class _FakeLogger:
    def warning(self, *args, **kwargs) -> None:
        pass


# ── 测试态 fatal 收集循环（生产隔离）──────────────────────────────

def test_fatal_loop_disabled_by_default_aborts_without_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    """生产默认（未设环境变量）：fatal 即中止，不重启游戏，行为与旧版一致。"""
    monkeypatch.delenv("ISTINA_FATAL_RESTART_LOOP", raising=False)
    from core.service.maa_end.runtime import MaaEndRuntime

    runtime = MaaEndRuntime()
    runtime._queue = [{"name": "TaskA"}, {"name": "TaskB"}]
    calls = {"ensure": 0, "restart": 0}

    monkeypatch.setattr(runtime, "_ensure_queue_connection",
                        lambda name, idx, total: (calls.__setitem__("ensure", calls["ensure"] + 1), False)[1])
    monkeypatch.setattr(runtime, "_force_restart_to_world",
                        lambda: (calls.__setitem__("restart", calls["restart"] + 1), True)[1])

    assert runtime.run_queue() is False
    assert calls["ensure"] == 1  # 首个任务 fatal 即中止，不触及后续任务
    assert calls["restart"] == 0  # 生产路径绝不触发游戏重启


def test_fatal_loop_test_mode_restarts_and_collects_blockers(monkeypatch: pytest.MonkeyPatch) -> None:
    """测试态：fatal 截屏留档→重启云终末地→从头再跑；卡点入汇总；多轮允许不完整跑通。"""
    monkeypatch.setenv("ISTINA_FATAL_RESTART_LOOP", "1")
    monkeypatch.setenv("ISTINA_FATAL_MAX_RESTARTS", "2")
    monkeypatch.setenv("ISTINA_FATAL_MAX_ROUNDS", "2")
    from core.service.maa_end.runtime import MaaEndRuntime

    runtime = MaaEndRuntime()
    runtime._queue = [{"name": "TaskA"}, {"name": "TaskB"}]
    state = {"ensure": 0, "restarts": 0, "captured": [], "summary": []}

    def fake_ensure(name: str, idx: int, total: int) -> bool:
        state["ensure"] += 1
        return state["ensure"] > 1  # 仅首次连接检查 fatal，其后恢复

    def fake_capture(task: str, reason: str):
        state["captured"].append((task, reason))
        return None

    monkeypatch.setattr(runtime, "_ensure_queue_connection", fake_ensure)
    monkeypatch.setattr(runtime, "_force_restart_to_world",
                        lambda: (state.__setitem__("restarts", state["restarts"] + 1), True)[1])
    monkeypatch.setattr(runtime, "_capture_fatal_context", fake_capture)
    monkeypatch.setattr(runtime, "_write_blocker_summary", lambda blockers: state["summary"].extend(blockers))
    monkeypatch.setattr(runtime, "run_task", lambda name, options=None: True)

    assert runtime.run_queue() is True
    # 第 1 轮：TaskA fatal → 重启 → 从头跑通；第 2 轮：完整跑通。
    assert state["restarts"] == 1
    assert state["captured"] == [("TaskA", "连接恢复失败（fatal）")]
    assert state["ensure"] == 5  # 轮1: A(fatal)+A+B，轮2: A+B
    assert [b["type"] for b in state["summary"]] == ["fatal_connection"]
    assert state["summary"][0]["task"] == "TaskA"


def test_fatal_loop_respects_max_restarts(monkeypatch: pytest.MonkeyPatch) -> None:
    """测试态：重启次数耗尽仍 fatal 时中止本轮，避免无限重启循环。"""
    monkeypatch.setenv("ISTINA_FATAL_RESTART_LOOP", "1")
    monkeypatch.setenv("ISTINA_FATAL_MAX_RESTARTS", "1")
    monkeypatch.setenv("ISTINA_FATAL_MAX_ROUNDS", "2")
    from core.service.maa_end.runtime import MaaEndRuntime

    runtime = MaaEndRuntime()
    runtime._queue = [{"name": "TaskA"}]
    state = {"restarts": 0}
    monkeypatch.setattr(runtime, "_ensure_queue_connection", lambda name, idx, total: False)
    monkeypatch.setattr(runtime, "_force_restart_to_world",
                        lambda: (state.__setitem__("restarts", state["restarts"] + 1), True)[1])
    monkeypatch.setattr(runtime, "_capture_fatal_context", lambda task, reason: None)
    monkeypatch.setattr(runtime, "_write_blocker_summary", lambda blockers: None)

    assert runtime.run_queue() is False
    # 每轮最多重启 1 次；2 轮共 2 次，不会无限重启。
    assert state["restarts"] == 2
