"""
MaaEnd runtime bridge - drives MaaFramework using SampleProgram/MaaEnd_Release assets.

This module intentionally mirrors MaaEnd's execution model:
- load interface.json + task JSONs
- load pipeline resources via MaaFramework Resource
- run task entries through Tasker.post_task(...) with option-derived pipeline_override
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.foundation.logger import LogCategory, get_logger
from core.foundation.paths import get_project_root


def _strip_json_comments(text: str) -> str:
    """Remove // line comments and /* */ block comments from a JSON string.

    MaaFW's resource JSON (rapidjson) legitimately allows both comment styles,
    so upstream task/preset/interface files shipped under 3rd-part/maaend may
    contain them. Python's ``json`` rejects comments, so we strip them outside
    of string literals before parsing. String contents are preserved verbatim.
    """
    result: List[str] = []
    i = 0
    n = len(text)
    in_str: Optional[str] = None
    while i < n:
        ch = text[i]
        if in_str is not None:
            result.append(ch)
            if ch == "\\":
                if i + 1 < n:
                    result.append(text[i + 1])
                    i += 2
                    continue
            elif ch == in_str:
                in_str = None
            i += 1
            continue
        if ch == '"' or ch == "'":
            in_str = ch
            result.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                j = text.find("\n", i)
                if j == -1:
                    break
                i = j + 1
                continue
            if nxt == "*":
                j = text.find("*/", i + 2)
                if j == -1:
                    break
                i = j + 2
                continue
        result.append(ch)
        i += 1
    return "".join(result)


def _load_json_file(path: Path) -> Dict[str, Any]:
    """Load a JSON file, tolerating MaaFW-style // and /* */ comments.

    Falls back to comment-stripping only on a parse error, so clean JSON keeps
    the fast native path and error messages stay precise for genuinely broken files.
    """
    text = Path(path).read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(_strip_json_comments(text))

# Point maa library to MaaEnd maafw DLLs for matching versions.
_PROJECT_ROOT = get_project_root()
_maaend_agent_dir = _PROJECT_ROOT / "3rd-part" / "maaend" / "agent"
_maafw_dir = _maaend_agent_dir / "maafw"
_DEFAULT_DLL_DIR = _maafw_dir if _maafw_dir.is_dir() else None

MAAFW_AVAILABLE = False
try:
    from maa.agent_client import AgentClient
    from maa.controller import AdbController
    from maa.define import MaaAdbInputMethodEnum, MaaAdbScreencapMethodEnum, MaaLoggingLevel
    from maa.resource import Resource
    from maa.tasker import Tasker
    from maa.toolkit import Toolkit
    MAAFW_AVAILABLE = True
except ImportError:
    AgentClient = None  # type: ignore[misc,assignment]
    Resource = None  # type: ignore[misc,assignment]
    Tasker = None  # type: ignore[misc,assignment]
    AdbController = None  # type: ignore[misc,assignment]
    Toolkit = None  # type: ignore[misc,assignment]
    MaaAdbScreencapMethodEnum = None  # type: ignore[misc,assignment]
    MaaAdbInputMethodEnum = None  # type: ignore[misc,assignment]
    MaaLoggingLevel = None  # type: ignore[misc,assignment]

if AgentClient is not None:
    _original_agent_client_del = AgentClient.__del__

    def _safe_agent_client_del(self):
        try:
            _original_agent_client_del(self)
        except Exception:
            pass

    AgentClient.__del__ = _safe_agent_client_del


class MaaEndRuntime:
    """Thin wrapper around MaaFramework that behaves like MaaEnd's runner."""

    def __init__(
        self,
        maaend_root: Optional[str] = None,
        device_address: str = "localhost:16512",
        adb_path: str = "3rd-part/adb/adb.exe",
        adb_restart_on_timeout: bool = True,
    ):
        self.logger = get_logger()
        self._maaend_root = Path(maaend_root) if maaend_root else self._default_maaend_root()
        self._device_address = device_address
        self._adb_path = str(get_project_root() / adb_path)
        self._adb_restart_on_timeout = bool(adb_restart_on_timeout)
        self._resource: Optional[Any] = None
        self._tasker: Optional[Any] = None
        self._controller: Optional[Any] = None
        self._agent_client: Optional[Any] = None
        self._agent_process: Optional[subprocess.Popen] = None
        self._interface: Optional[Dict[str, Any]] = None
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._presets: Dict[str, Dict[str, Any]] = {}
        self._option_defs: Dict[str, Dict[str, Any]] = {}
        self._tasks_loaded = False
        self._presets_loaded = False
        self._connected = False
        # 队列：唯一可执行单元。预设只是任务列表，应用预设 = 用其任务覆盖队列。
        self._queue: List[Dict[str, Any]] = []
        self._load_lock = threading.Lock()  # N11: 保护 load_tasks/load_presets 并发调用
        # 集中式异常恢复：任何任务失败时执行 CloseGame → AndroidOpenGame → 重试
        self._recovering = False
        self._client_version = "CN"


    def _default_maaend_root(self) -> Path:
        return get_project_root() / "3rd-part" / "maaend"

    def _resolve_asset_path(self, *parts: str) -> Path:
        """Resolve a path relative to the MaaEnd root, supporting both
        the release layout (root-relative) and the dev layout (assets/ subdir)."""
        direct = self._maaend_root.joinpath(*parts)
        if direct.exists():
            return direct
        assets = self._maaend_root / "assets"
        if assets.is_dir():
            alt = assets.joinpath(*parts)
            if alt.exists():
                return alt
        return direct

    def _resolve_agent_root(self) -> Path:
        """Resolve the agent directory, falling back to 3rd-part if the dev tree lacks binaries or maafw."""
        direct = self._maaend_root / "agent"
        if (direct / "go-service.exe").is_file() and (direct / "maafw" / "MaaFramework.dll").is_file():
            return direct
        fallback = get_project_root() / "3rd-part" / "maaend" / "agent"
        if (fallback / "go-service.exe").is_file() and (fallback / "maafw" / "MaaFramework.dll").is_file():
            return fallback
        return direct

    @property
    def root(self) -> Path:
        return self._maaend_root

    @property
    def connected(self) -> bool:
        return self._connected

    def load_interface(self) -> Dict[str, Any]:
        path = self._resolve_asset_path("interface.json")
        try:
            self._interface = _load_json_file(path)
        except Exception as e:
            self.logger.warning(LogCategory.MAIN, "加载 interface.json 失败", path=str(path), error=str(e))
            self._interface = {}
        return self._interface or {}

    def load_tasks(self) -> Dict[str, Dict[str, Any]]:
        with self._load_lock:  # N11: 并发加载加锁，避免 self._tasks 竞争
            tasks_root = self._resolve_asset_path("tasks")
            self._tasks = {}
            self._option_defs = {}
            for json_path in tasks_root.rglob("*.json"):
                if json_path.name == "nodes.json":
                    continue
                try:
                    data = _load_json_file(json_path)
                    # 提取全局 option 定义（每个 JSON 文件顶层可能有 option 字典）
                    global_options = data.get("option")
                    if isinstance(global_options, dict):
                        self._option_defs.update(global_options)
                    task_list = data.get("task", [])
                    for task in task_list:
                        name = task.get("name")
                        if name:
                            task_copy = dict(task)
                            task_copy["_source"] = str(json_path.relative_to(self._maaend_root))
                            task_copy["_option_defs"] = dict(global_options) if isinstance(global_options, dict) else {}
                            self._tasks[name] = task_copy
                except Exception as e:  # pragma: no cover
                    self.logger.debug(LogCategory.MAIN, "加载任务定义失败", path=str(json_path), error=str(e))
            self._tasks_loaded = True  # 标志位移到循环结束后，避免空列表固化
            return self._tasks

    def load_presets(self) -> Dict[str, Dict[str, Any]]:
        with self._load_lock:  # N11: 并发加载加锁，避免 self._presets 竞争
            preset_root = self._resolve_asset_path("tasks", "preset")
            self._presets = {}
            if not preset_root.exists():
                self._presets_loaded = True
                return self._presets
            for json_path in preset_root.glob("*.json"):
                try:
                    data = _load_json_file(json_path)
                    preset_list = data.get("preset", [])
                    for preset in preset_list:
                        name = preset.get("name")
                        if name:
                            self._presets[name] = preset
                            self._presets[name]["_source"] = str(json_path.relative_to(self._maaend_root))
                except Exception as e:  # pragma: no cover
                    self.logger.debug(LogCategory.MAIN, "加载预设失败", path=str(json_path), error=str(e))
            self._presets_loaded = True  # 标志位移到循环结束后
            return self._presets

    def connect(self) -> bool:
        # 先清理可能残留的旧连接，避免 agent 进程 / Tasker 资源泄漏
        self._cleanup_partial()
        self._connected = False
        if self._device_address == "default":
            self.logger.error(LogCategory.MAIN, "设备地址为默认占位值，请先配置 device.serial 或连接设备")
            return False
        if not MAAFW_AVAILABLE:
            self.logger.error(LogCategory.MAIN, "MaaFramework 未安装，无法连接")
            return False
        try:
            if MaaLoggingLevel is not None:
                try:
                    import maa as _maa
                    _maa.Library.set_log_level(MaaLoggingLevel.MaaLogFatal)
                except Exception:
                    pass
            if Toolkit is not None:
                try:
                    config_dir = self._resolve_asset_path("config")
                    if not config_dir.exists():
                        config_dir = self._maaend_root
                    Toolkit.init_option(config_dir)
                except Exception as exc:
                    self.logger.warning(LogCategory.MAIN, "Toolkit 初始化失败", error=str(exc))
            max_attempts = 2 if self._adb_restart_on_timeout else 1
            for attempt in range(max_attempts):
                if attempt > 0:
                    self._kill_adb()
                    time.sleep(1)
                if self._connect_with_timeout(timeout=self._CONNECTION_TIMEOUT_S):
                    return True
            return False
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "MaaEnd runtime 连接异常", error=str(e))
            self._cleanup_partial()
            return False

    _CONNECTION_TIMEOUT_S = 20
    _SCRECAP_TIMEOUT_S = 10

    def _connect_once(self) -> bool:
        self._resource = Resource()
        input_methods = int((MaaAdbInputMethodEnum.AdbShell | MaaAdbInputMethodEnum.Maatouch) if MaaAdbInputMethodEnum else 1)
        screencap_methods = int(MaaAdbScreencapMethodEnum.Default if MaaAdbScreencapMethodEnum else 0)
        self._controller = AdbController(
            adb_path=Path(self._adb_path),
            address=self._device_address,
            screencap_methods=screencap_methods,
            input_methods=input_methods,
            config={},
        )
        job = self._controller.post_connection()
        job.wait()
        if not job.succeeded:
            self.logger.error(LogCategory.MAIN, "ADB 控制器连接失败", address=self._device_address)
            self._cleanup_partial()
            return False
        screencap_job = self._controller.post_screencap()
        screencap_job.wait()
        if not screencap_job.succeeded:
            self.logger.error(LogCategory.MAIN, "首次截图失败", address=self._device_address)
            self._cleanup_partial()
            return False
        self._tasker = Tasker()
        if not self._tasker.bind(self._resource, self._controller):
            self.logger.error(LogCategory.MAIN, "Tasker 绑定失败")
            self._cleanup_partial()
            return False
        # ERRSCREEN-01: Enable on_error screenshot saving so failed recognition
        # nodes save a screenshot to config/debug/on_error/ for analysis.
        try:
            self._tasker.set_save_on_error(True)
        except Exception:
            pass
        # Start Agent after Tasker is ready so it can register sinks correctly.
        self._start_agent()
        if self._agent_client is None or self._agent_process is None:
            # H-13: Agent 部分启动（client 或 process 任一缺失）即视为未就绪，中止连接，
            # 避免带着半初始化的 Agent 继续，导致后续 bind/connect 失败且难以定位。
            self.logger.error(LogCategory.MAIN, "Agent 未启动（client 或 process 缺失），连接中止")
            self._cleanup_partial()
            return False
        if self._agent_client is not None:
            try:
                self._agent_client.bind(self._resource)
                self._agent_client.register_sink(self._resource, self._controller, self._tasker)
                self._agent_client.connect()
            except Exception as e:
                self.logger.warning(LogCategory.MAIN, "AgentClient 初始化异常", error=str(e))
        self._connected = True
        self.logger.info(LogCategory.MAIN, "MaaEnd runtime 连接成功", address=self._device_address)
        return True

    def _connect_with_timeout(self, timeout: int) -> bool:
        result = {"success": False}

        def target() -> None:
            try:
                result["success"] = self._connect_once()
            except Exception as exc:
                result["success"] = False
                self.logger.exception(LogCategory.MAIN, "ADB 连接尝试异常", error=str(exc))

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            self.logger.error(LogCategory.MAIN, "ADB 连接超时", address=self._device_address, timeout=timeout)
            self._cleanup_partial()
            return False

        return result["success"]

    def _kill_adb(self) -> None:
        # 该 warning 级日志会写入 stderr，被 GUI 的 _ADB_RE 归类为 "ADB" 源，
        # 用于驱动连接页显示「正在杀死ADB并重试...」状态（device_settings_page._on_log_message）。
        self.logger.warning(LogCategory.MAIN, "adb 重启中(kill-server)：连接超时，正在重试")
        try:
            subprocess.run(
                [self._adb_path, "kill-server"],
                text=True,
                timeout=10,
            )
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "adb kill-server 失败", error=str(exc))
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "adb.exe"],
                text=True,
                timeout=10,
            )
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "taskkill adb.exe 失败", error=str(exc))

    def _cleanup_partial(self) -> None:
        """Clean up partially-created resources after a failed connect()."""
        # C7/N10: 连接失败时显式释放 MaaFW 原生资源，避免泄漏
        for attr in ("_resource", "_controller"):
            val = getattr(self, attr, None)
            if val is not None:
                try:
                    destroy = getattr(val, "destroy", None)
                    if callable(destroy):
                        destroy()
                except Exception as exc:
                    self.logger.warning(LogCategory.MAIN, f"销毁 {attr} 失败", error=str(exc))
                try:
                    setattr(self, attr, None)
                except Exception:
                    pass
        try:
            if self._tasker is not None:
                self._tasker = None
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "清理 tasker 失败", error=str(exc))
        try:
            if self._agent_client is not None:
                try:
                    self._agent_client.disconnect()
                except Exception as exc:
                    self.logger.warning(LogCategory.MAIN, "清理 agent_client 失败", error=str(exc))
                self._agent_client = None
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "清理 agent_client 失败", error=str(exc))
        try:
            if self._agent_process is not None:
                try:
                    if self._agent_process.poll() is None:
                        self._agent_process.terminate()
                        try:
                            self._agent_process.wait(timeout=3)
                        except Exception as exc:
                            self.logger.warning(LogCategory.MAIN, "terminate 超时，改用 kill", error=str(exc))
                            self._agent_process.kill()
                            try:
                                self._agent_process.wait(timeout=3)
                            except Exception:
                                pass  # 最终兜底，避免 wait 自身阻塞
                except Exception as exc:
                    self.logger.warning(LogCategory.MAIN, "清理 agent_process 失败", error=str(exc))
                self._agent_process = None
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "清理 agent_process 失败", error=str(exc))
        try:
            if self._controller is not None:
                self._controller = None
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "清理 controller 失败", error=str(exc))
        try:
            if self._resource is not None:
                self._resource = None
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "清理 resource 失败", error=str(exc))

    def disconnect(self) -> None:
        self._cleanup_partial()
        self._connected = False
        self.logger.info(LogCategory.MAIN, "MaaEnd runtime 已断开")

    def _start_agent(self) -> None:
        if self._agent_client is not None:
            return
        agent_root = self._resolve_agent_root()
        agent_exe = agent_root / "go-service.exe"
        if AgentClient is None or not agent_exe.exists():
            self.logger.warning(LogCategory.MAIN, "go-service.exe 不存在，跳过 Agent 启动", path=str(agent_exe))
            return
        agent_id = f"istina-maaend-{int(time.time() * 1000)}"
        process = None
        try:
            agent_env = os.environ.copy()
            agent_dll_dir = agent_root / "maafw"
            if agent_dll_dir.is_dir():
                agent_env["MAAFW_BINARY_PATH"] = str(agent_dll_dir.resolve())
            elif _DEFAULT_DLL_DIR is not None:
                agent_env["MAAFW_BINARY_PATH"] = str(_DEFAULT_DLL_DIR.resolve())
            process = subprocess.Popen(
                [str(agent_exe), agent_id],
                cwd=str(agent_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=agent_env,
            )
            # 等待 go-service 进程就绪：轮询确认进程未立即退出
            ready = False
            for _ in range(10):  # 最多等待 5 秒（10 次 × 0.5s）
                if process.poll() is not None:
                    # 进程已退出
                    break
                time.sleep(0.5)
                if process.poll() is None:
                    ready = True
                    break
            if not ready:
                self.logger.error(LogCategory.MAIN, "go-service 进程启动后立即退出", agent_id=agent_id)
                self._agent_client = None
                self._agent_process = None
                return
            self._agent_process = process
            self._agent_client = AgentClient(agent_id)
            self.logger.info(LogCategory.MAIN, "Agent 启动成功", port=agent_id)
        except Exception as exc:
            self.logger.error(LogCategory.MAIN, "启动 Agent 失败", error=str(exc))
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except Exception:
                        process.kill()
                except Exception:
                    pass
            self._agent_client = None
            self._agent_process = None

    def load_resource(self) -> bool:
        if not self._connected or self._resource is None:
            return False
        try:
            resource_dir = self._resolve_asset_path("resource")
            # nodes.json 是 IEA 把全部任务 pipeline 聚合后的冗余副本，与
            # resource*/pipeline 下分散的任务文件大量重名；MaaFW 会递归加载各 resource
            # 目录全部 JSON 并因 "key already exists" 整体失败。加载前将各 pipeline 目录
            # 中的聚合 nodes.json 统一移出。
            self._relocate_aggregate_nodes()
            job = self._resource.post_bundle(resource_dir)
            job.wait()
            if not job.succeeded:
                self.logger.error(LogCategory.MAIN, "Pipeline 资源加载失败", path=str(resource_dir))
                return False
            self.logger.info(LogCategory.MAIN, "Pipeline 资源加载成功", path=str(resource_dir))
            adb_resource_dir = self._resolve_asset_path("resource_adb")
            if adb_resource_dir.exists():
                job_adb = self._resource.post_bundle(adb_resource_dir)
                job_adb.wait()
                if not job_adb.succeeded:
                    self.logger.error(LogCategory.MAIN, "ADB 资源加载失败", path=str(adb_resource_dir))
                    return False
                self.logger.info(LogCategory.MAIN, "ADB 资源加载成功", path=str(adb_resource_dir))
            return True
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "Pipeline 资源加载异常", error=str(e))
            return False

    def _relocate_aggregate_nodes(self) -> None:
        """将各 resource*/pipeline/nodes.json 聚合副本移出 pipeline 目录。

        MaaFW 的 Resource.post_bundle 会递归加载每个 resource 目录下 pipeline/ 的
        全部 JSON，而 nodes.json 是 IEA 把全部任务 pipeline 聚合后的冗余副本，与分散
        的任务文件大量重名，会触发 'key already exists' 导致整个资源加载失败。该方法
        扫描 maaend 根目录下所有 pipeline/nodes.json 并移出：首个保留为
        maaend_root/nodes.json 供 IEA 自有 PipelineLoader 使用，其余冗余副本直接丢弃。
        从而在每次加载时自愈，防止重新同步 3rd-part 后该文件再次落入 pipeline 目录。
        """
        target = self._maaend_root / "nodes.json"
        for nodes in self._maaend_root.rglob("pipeline/nodes.json"):
            if not nodes.is_file():
                continue
            try:
                if target.is_file():
                    # 目标已存在则直接丢弃 pipeline 中的冗余副本
                    nodes.unlink()
                    self.logger.debug(LogCategory.MAIN, "丢弃 pipeline 目录冗余 nodes.json", path=str(nodes))
                else:
                    nodes.replace(target)
                    self.logger.warning(
                        LogCategory.MAIN,
                        "已将聚合 nodes.json 移出 pipeline 目录以避免 MaaFW 资源加载冲突",
                        target=str(target),
                    )
            except Exception as exc:
                self.logger.warning(
                    LogCategory.MAIN, "移动聚合 nodes.json 失败，资源加载可能冲突", path=str(nodes), error=str(exc)
                )

    def build_pipeline_override(self, task_name: str, options: Dict[str, Any]) -> Dict[str, Any]:
        task = self._tasks.get(task_name)
        if not task:
            return {}
        override: Dict[str, Any] = {}
        task_options = task.get("option", [])
        if not isinstance(task_options, list):
            task_options = []
        option_defs = task.get("_option_defs")
        if not isinstance(option_defs, dict) or not option_defs:
            option_defs = self._option_defs
        for opt_name in task_options:
            value = options.get(opt_name)
            opt_def = option_defs.get(opt_name, {})
            if value is None:
                default_case = opt_def.get("default_case")
                if default_case is None:
                    continue
                value = default_case
            override.update(self._apply_option(opt_def, value))
        base_override = task.get("pipeline_override") or {}
        merged = self._merge_overrides(base_override, override)
        return merged

    def _apply_option(self, opt_def: Dict[str, Any], value: Any) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        opt_type = opt_def.get("type", "switch")
        cases = opt_def.get("cases", [])
        if opt_type == "switch":
            case_name = value if isinstance(value, str) else ("Yes" if value else "No")
            for case in cases:
                if case.get("name") == case_name:
                    result.update(case.get("pipeline_override") or {})
                    nested_options = case.get("option") or []
                    nested_defs = opt_def.get("option", {}) if isinstance(opt_def.get("option"), dict) else {}
                    for nested_name in nested_options:
                        nested_value = value.get(nested_name) if isinstance(value, dict) else None
                        if nested_value is None:
                            continue
                        result.update(self._apply_option(nested_defs.get(nested_name, {}), nested_value))
                    return result
            default_case = opt_def.get("default_case")
            if default_case:
                for case in cases:
                    if case.get("name") == default_case:
                        result.update(case.get("pipeline_override") or {})
                        return result
            return result
        if opt_type == "checkbox":
            selected = value if isinstance(value, list) else ([value] if value else [])
            default_case = opt_def.get("default_case") or []
            active_cases = selected if selected else default_case
            for case in cases:
                if case.get("name") in active_cases:
                    result = self._merge_overrides(result, case.get("pipeline_override") or {})
            return result
        if opt_type == "select":
            case_name = str(value)
            default_case = str(opt_def.get("default_case")) if opt_def.get("default_case") is not None else None
            active_case = case_name if case_name else default_case
            for case in cases:
                if case.get("name") == active_case:
                    result.update(case.get("pipeline_override") or {})
                    return result
            return result
        if opt_type == "input":
            override_payload = opt_def.get("pipeline_override") or {}
            merged_payload = self._resolve_input_tokens(override_payload, value)
            result.update(merged_payload)
            return result
        return result

    def _resolve_input_tokens(self, payload: Dict[str, Any], value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            return payload
        resolved = json.loads(json.dumps(payload))
        for key, val in resolved.items():
            if isinstance(val, str):
                resolved[key] = self._replace_tokens(val, value)
            elif isinstance(val, dict):
                resolved[key] = self._resolve_input_tokens(val, value)
        return resolved

    def _replace_tokens(self, text: str, values: Dict[str, Any]) -> str:
        result = text
        for token, replacement in values.items():
            placeholder = "{" + token + "}"
            if placeholder in result:
                result = result.replace(placeholder, str(replacement))
        return result

    def _merge_overrides(self, base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
        merged = json.loads(json.dumps(base)) if base else {}
        for key, value in extra.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_overrides(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _wait_job(self, job: Any, timeout: Optional[float]) -> bool:
        """等待任务完成，支持超时（秒）。

        timeout 为 None 或 <=0 时使用框架默认（无限等待）；否则在后台线程中
        job.wait() 并 join timeout 秒，超时返回 False，避免整个 CLI 子进程卡死。

        注意：job.wait() 返回 Job 对象自身（truthy），不是任务成功与否的布尔值。
        必须用 job.succeeded 检查任务的真实状态。
        """
        if timeout is None or timeout <= 0:
            job.wait()
            return job.succeeded
        result: Dict[str, Any] = {}

        def _target() -> None:
            try:
                job.wait()
                result["ok"] = job.succeeded
            except Exception:
                result["ok"] = False

        worker = threading.Thread(target=_target, daemon=True)
        worker.start()
        worker.join(float(timeout))
        if worker.is_alive():
            self.logger.warning(LogCategory.MAIN, "任务执行超时", timeout=timeout)
            # STOP-01: Stop the MaaFW task to prevent deadlock. Without this,
            # the MaaFW task keeps running in the background, blocking all
            # subsequent post_task calls (CloseGame, AndroidOpenGame, etc.)
            # because MaaFW Tasker is single-tasked. post_stop() interrupts
            # the running task, allowing recovery tasks to start.
            if self._tasker is not None:
                try:
                    self._tasker.post_stop()
                    # Wait briefly for the stop to take effect so job.wait()
                    # in the daemon thread returns and MaaFW is ready for new
                    # tasks.
                    worker.join(5.0)
                    # STOP-01 race: the timeout may fire just as the task is
                    # about to complete naturally. post_stop() is async; by
                    # the time we join(5.0) the daemon thread may have already
                    # finished and written result["ok"]. In that case return
                    # the actual outcome instead of forcing False — otherwise
                    # a task that actually succeeded is reported as failed,
                    # triggering unnecessary recovery, and MaaFW ends up in
                    # the "stopping" state which rejects subsequent post_task
                    # calls ("stopping, ignore new post").
                    if not worker.is_alive():
                        actual = result.get("ok", False)
                        self.logger.info(
                            LogCategory.MAIN,
                            "任务在超时后实际完成",
                            succeeded=actual,
                        )
                        return actual
                except Exception as exc:
                    self.logger.warning(LogCategory.MAIN, "post_stop 失败", error=str(exc))
            return False
        return result.get("ok", False)

    def run_pipeline(self, entry: str, pipeline_override: Dict[str, Any], timeout: Optional[float] = None) -> bool:
        if not self._connected or self._tasker is None:
            self.logger.error(LogCategory.MAIN, "runtime 未连接，无法执行管道")
            return False
        self.logger.info(LogCategory.MAIN, "开始执行自定义管道", entry=entry)
        try:
            job = self._tasker.post_task(entry, pipeline_override if pipeline_override else {})
            succeeded = self._wait_job(job, timeout)
        except Exception as e:
            # 仅真正的执行异常才视为连接断开
            self._connected = False
            self.logger.exception(LogCategory.MAIN, "自定义管道执行异常", entry=entry, error=str(e))
            return False
        if succeeded:
            self.logger.info(LogCategory.MAIN, "自定义管道执行成功", entry=entry)
            return True
        # 识别未命中等「正常失败」不得污染连接态，也不触发恢复/重连
        self.logger.warning(LogCategory.MAIN, "自定义管道执行失败", entry=entry)
        return False

    def run_task(self, task_name: str, options: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> bool:
        if not self._connected or self._tasker is None:
            self.logger.error(LogCategory.MAIN, "runtime 未连接，无法执行任务", task=task_name)
            return False
        task_name, inline_options = self._normalize_task_name(task_name)
        if not self._tasks:
            self.load_tasks()
        task = self._tasks.get(task_name)
        if not task:
            self.logger.error(LogCategory.MAIN, "任务未定义", task=task_name)
            return False
        options = options or {}
        if inline_options:
            merged_options = dict(inline_options)
            merged_options.update(options)
            options = merged_options
        if options.get("ClientVersion"):
            self._client_version = options["ClientVersion"]
        override = self.build_pipeline_override(task_name, options)
        entry = task.get("entry", task_name)
        self.logger.info(LogCategory.MAIN, "开始执行任务", task=task_name, entry=entry, override=override)
        try:
            job = self._tasker.post_task(entry, override if override else {})
            succeeded = self._wait_job(job, timeout)
        except Exception as e:
            self._connected = False
            self.logger.exception(LogCategory.MAIN, "任务执行异常", task=task_name, error=str(e))
            if not self._recovering and self._try_recover(task_name):
                return self._retry_task(task_name, options, entry, timeout)
            return False
        if succeeded:
            if self._detect_task_skipped(job, task_name):
                self.logger.warning(LogCategory.MAIN, "任务被跳过（未满足执行条件，如未到计划周期）", task=task_name)
                return False
            self.logger.info(LogCategory.MAIN, "任务执行成功", task=task_name)
            return True
        self.logger.warning(LogCategory.MAIN, "任务执行失败", task=task_name)
        if self._recovering:
            self.logger.warning(LogCategory.MAIN, "恢复任务失败，不递归", task=task_name)
            return False
        return self._recover_and_retry(task_name, options, timeout)

    def _detect_task_skipped(self, job: Any, task_name: str) -> bool:
        """检测任务是否走了跳过分支（未真正执行业务）。

        MaaEnd 的 *Schedule 任务设计为 entry.next = [业务节点, 跳过节点]。
        当 ScheduleRecognition 不命中（如 attach 全 false）时走跳过节点，
        MaaFW 仍报告 status=succeeded，但任务实际未执行业务。
        通过检查节点轨迹区分跳过与真正执行。
        """
        try:
            task_detail = job.get()
            if not task_detail:
                return False
            node_names = [nd.name for nd in task_detail.nodes if nd and nd.name]
            if not node_names:
                return False
            self.logger.info(LogCategory.MAIN, "任务节点轨迹", task=task_name, nodes=node_names)
            has_skip = any(n.endswith(("End", "Done", "Skip")) for n in node_names)
            has_biz = any(any(k in n for k in ("Main", "Start", "Loop")) for n in node_names)
            return has_skip and not has_biz
        except Exception as e:
            self.logger.warning(LogCategory.MAIN, "跳过检测异常", task=task_name, error=str(e))
            return False

    # ------------------------------------------------------------------
    # 队列（唯一可执行单元）
    # ------------------------------------------------------------------
    def apply_preset(self, preset_name: str) -> bool:
        """应用预设：用预设包含的任务及其设置覆盖队列（清空旧队列再填充）。

        预设只是一个任务列表，本身不可直接执行；可被执行的只有队列。
        """
        if not self._presets:
            self.load_presets()
        preset = self._presets.get(preset_name)
        if not preset:
            self.logger.error(LogCategory.MAIN, "预设未定义", preset=preset_name)
            return False
        task_list = preset.get("task", [])
        if not isinstance(task_list, list):
            self.logger.error(LogCategory.MAIN, "预设任务列表非法", preset=preset_name)
            return False
        items: List[Dict[str, Any]] = []
        for task_entry in task_list:
            if not isinstance(task_entry, dict):
                continue
            name = str(task_entry.get("name") or "").strip()
            if not name:
                continue
            options = task_entry.get("option")
            if not isinstance(options, dict):
                options = {}
            items.append({"name": name, "options": dict(options)})
        self._queue = items
        self.logger.info(LogCategory.MAIN, "已应用预设到队列", preset=preset_name, queue_size=len(items))
        return True

    def add_task(self, task_name: str, options: Optional[Dict[str, Any]] = None) -> None:
        """向队列追加一个任务（含其设置）。"""
        self._queue.append({"name": str(task_name), "options": dict(options or {})})

    def clear_queue(self) -> None:
        """清空队列。"""
        self._queue = []

    def queue(self) -> List[Dict[str, Any]]:
        """返回当前队列的副本。"""
        return [dict(item) for item in self._queue]

    def run_queue(self, timeout: Optional[float] = None) -> bool:
        """执行队列（唯一的可执行单元）。

        单个任务识别未命中等「正常失败」不影响后续任务；仅当连接真正断开时
        才中止剩余任务。返回 True 表示全部成功，False 表示存在失败或中断。
        """
        if not self._queue:
            self.logger.warning(LogCategory.MAIN, "队列为空，无可执行任务")
            return False
        self.logger.info(LogCategory.MAIN, "开始执行队列", queue_size=len(self._queue))
        failures: List[str] = []
        for item in self._queue:
            name = str(item.get("name") or "").strip()
            options = item.get("options") or {}
            if not name:
                continue
            if not self.run_task(name, options, timeout):
                failures.append(name)
                self.logger.warning(LogCategory.MAIN, "队列任务失败，继续后续", failed_task=name)
                # 若连接已真正断开，继续也无意义，及时中止剩余任务
                if not self._connected:
                    self.logger.error(LogCategory.MAIN, "队列执行中连接断开，中止")
                    break
        if failures:
            self.logger.warning(LogCategory.MAIN, "队列执行完成但存在失败任务", failed=failures)
            return False
        self.logger.info(LogCategory.MAIN, "队列执行完成")
        return True

    def run_preset(self, preset_name: str, timeout: Optional[float] = None) -> bool:
        """应用预设到队列并执行队列（便捷封装）。

        预设本身不可直接执行，故等价于 apply_preset + run_queue。
        """
        if not self.apply_preset(preset_name):
            return False
        if not self._queue:
            # 空预设：无可执行任务，视为成功（与旧行为一致）
            self.logger.info(LogCategory.MAIN, "预设任务列表为空，无需执行", preset=preset_name)
            return True
        return self.run_queue(timeout)

    def _normalize_task_name(self, task_name: str) -> tuple[str, Dict[str, Any]]:
        name = str(task_name or "").strip()
        if "|" not in name:
            return name, {}
        base, payload = name.split("|", 1)
        base = base.strip()
        payload = payload.strip()
        if not base or not payload:
            return name, {}
        if payload.startswith("{") and payload.endswith("}"):
            try:
                parsed = json.loads(payload)
                if isinstance(parsed, dict):
                    return base, parsed
            except Exception:
                return base, {"_inline": payload}
        return base, {"_inline": payload}

    def _recover_and_retry(self, task_name: str, options: Dict[str, Any], timeout: Optional[float]) -> bool:
        """集中式异常恢复：关闭游戏 → 启动游戏 → 从头重试失败任务。

        任何任务失败（识别未命中、超时等）时调用此方法。通过 _recovering 标志
        防止恢复任务自身失败时递归。仅重试一次，避免无限循环。
        """
        self.logger.info(
            LogCategory.MAIN,
            "异常恢复开始：关闭游戏 → 启动游戏 → 重试任务",
            task=task_name,
            client_version=self._client_version,
        )
        self._recovering = True
        try:
            self.logger.info(LogCategory.MAIN, "异常恢复步骤1/3：关闭游戏")
            self.run_task("CloseGame", {"ClientVersion": self._client_version})
            if not self._connected:
                self.logger.error(LogCategory.MAIN, "异常恢复中止：连接断开")
                return False

            self.logger.info(LogCategory.MAIN, "异常恢复步骤2/3：启动游戏")
            open_ok = self.run_task("AndroidOpenGame", {"ClientVersion": self._client_version})
            if not open_ok:
                self.logger.error(LogCategory.MAIN, "异常恢复失败：启动游戏失败")
                return False

            self.logger.info(LogCategory.MAIN, "异常恢复步骤3/3：重试失败任务", task=task_name)
            return self.run_task(task_name, options, timeout)
        finally:
            self._recovering = False

    def _try_recover(self, task_name: str) -> bool:
        """尝试恢复连接/设备状态，失败则重启应用。"""
        try:
            if self._controller is not None:
                job = self._controller.post_screencap()
                job.wait()
                if job.succeeded:
                    self._connected = True
                    self.logger.info(LogCategory.MAIN, "恢复连接成功", task=task_name)
                    return True
        except Exception:
            pass
        try:
            from core.capability.device.recovery import AndroidAppRestartPolicy
            restart_policy = AndroidAppRestartPolicy(
                adb_path=self._adb_path,
                package="com.hypergryph.endfield",
            )
            ok = restart_policy.restart(serial=self._device_address)
            if ok:
                self._reconnect()
                return True
        except Exception as exc:
            self.logger.error(LogCategory.MAIN, "恢复失败", task=task_name, error=str(exc))
        return False

    def _retry_task(self, task_name: str, options: Dict[str, Any], entry: str, timeout: Optional[float] = None) -> bool:
        """恢复后重试当前任务一次。"""
        if not self._connected or self._tasker is None:
            return False
        self.logger.info(LogCategory.MAIN, "重试任务", task=task_name)
        try:
            job = self._tasker.post_task(entry, self.build_pipeline_override(task_name, options) or {})
            succeeded = self._wait_job(job, timeout)
        except Exception as exc:
            self._connected = False
            self.logger.exception(LogCategory.MAIN, "重试异常", task=task_name, error=str(exc))
            return False
        if succeeded:
            if self._detect_task_skipped(job, task_name):
                self.logger.warning(LogCategory.MAIN, "重试任务被跳过", task=task_name)
                return False
            self.logger.info(LogCategory.MAIN, "重试成功", task=task_name)
            return True
        self.logger.warning(LogCategory.MAIN, "重试失败", task=task_name)
        return False

    def _reconnect(self) -> bool:
        """重新建立连接（用于在任务异常恢复时重建 runtime）。

        旧实现依赖 self._resource is not None，但真正断连后 _resource 已被
        _cleanup_partial 置空，导致该分支永远返回 False、恢复路径失效。
        现直接走完整 connect()，由 connect() 负责清理旧资源并重建。
        """
        self.logger.info(LogCategory.MAIN, "尝试重连 MaaEnd runtime")
        try:
            return self.connect()
        except Exception as exc:
            self.logger.error(LogCategory.MAIN, "重连失败", error=str(exc))
            return False

    def interface(self) -> Dict[str, Any]:
        return self._interface or self.load_interface()

    def tasks(self) -> Dict[str, Dict[str, Any]]:
        if not self._tasks_loaded:
            self.load_tasks()
        return self._tasks

    def task_option_defs(self) -> Dict[str, Dict[str, Any]]:
        if not self._tasks_loaded:
            self.load_tasks()
        return dict(self._option_defs)

    def presets(self) -> Dict[str, Dict[str, Any]]:
        if not self._presets_loaded:
            self.load_presets()
        return self._presets

    def task_groups(self) -> List[str]:
        interface = self.interface()
        return [g.get("name") for g in interface.get("group", []) if g.get("name")]

    def controllers(self) -> List[Dict[str, Any]]:
        return self.interface().get("controller", [])

    def resources(self) -> List[Dict[str, Any]]:
        return self.interface().get("resource", [])

    def agents(self) -> List[Dict[str, Any]]:
        return self.interface().get("agent", [])

    def imported_task_paths(self) -> List[str]:
        return self.interface().get("import", [])

    def screenshot(self) -> Optional[bytes]:
        if not self._connected or self._controller is None:
            return None
        try:
            job = self._controller.post_screencap()
            job.wait()
            if not job.succeeded:
                # H-02: 单次截图失败（瞬时抖动）不应翻转连接态，避免触发重连风暴；
                # 真正的连接断开由上层重试/恢复机制判定。
                self.logger.warning(LogCategory.MAIN, "截图失败（screencap 未成功），但保持连接态")
                return None
            cached = self._controller.cached_image
            if cached is None:
                return None
            import cv2
            success, buf = cv2.imencode(".png", cached)
            return buf.tobytes() if success else None
        except Exception as e:
            # H-02: 异常同样只记录，不翻转连接态
            self.logger.warning(LogCategory.MAIN, "截图异常，保持连接态", error=str(e))
            return None
