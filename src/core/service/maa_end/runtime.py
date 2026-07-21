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
        # _recovering 标志：仅 _recover_and_retry 被显式调用时置位，防止 RecoverGame 自身失败时递归
        # 注意：run_task 不再对识别未命中（正常失败）自动触发异常恢复，与 run_pipeline 一致
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
            # 加载 assets/tasks/ 下的自定义任务（覆盖 3rd-part 中的同名任务）
            custom_tasks_root = _PROJECT_ROOT / "assets" / "tasks"
            if custom_tasks_root.is_dir():
                for json_path in custom_tasks_root.rglob("*.json"):
                    if json_path.name == "nodes.json":
                        continue
                    if "preset" in json_path.parts:
                        continue
                    try:
                        data = _load_json_file(json_path)
                        global_options = data.get("option")
                        if isinstance(global_options, dict):
                            self._option_defs.update(global_options)
                        task_list = data.get("task", [])
                        for task in task_list:
                            name = task.get("name")
                            if name:
                                task_copy = dict(task)
                                task_copy["_source"] = str(json_path.relative_to(_PROJECT_ROOT))
                                task_copy["_option_defs"] = dict(global_options) if isinstance(global_options, dict) else {}
                                self._tasks[name] = task_copy
                    except Exception as e:  # pragma: no cover
                        self.logger.debug(LogCategory.MAIN, "加载自定义任务定义失败", path=str(json_path), error=str(e))
            self._tasks_loaded = True  # 标志位移到循环结束后，避免空列表固化
            return self._tasks

    def load_presets(self) -> Dict[str, Dict[str, Any]]:
        with self._load_lock:  # N11: 并发加载加锁，避免 self._presets 竞争
            preset_root = self._resolve_asset_path("tasks", "preset")
            self._presets = {}
            if preset_root.exists():
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
            # 加载 assets/tasks/preset/ 下的自定义预设（覆盖 3rd-part 中的同名预设）
            custom_preset_root = _PROJECT_ROOT / "assets" / "tasks" / "preset"
            if custom_preset_root.is_dir():
                for json_path in custom_preset_root.glob("*.json"):
                    try:
                        data = _load_json_file(json_path)
                        preset_list = data.get("preset", [])
                        for preset in preset_list:
                            name = preset.get("name")
                            if name:
                                self._presets[name] = preset
                                self._presets[name]["_source"] = str(json_path.relative_to(_PROJECT_ROOT))
                    except Exception as e:  # pragma: no cover
                        self.logger.debug(LogCategory.MAIN, "加载自定义预设失败", path=str(json_path), error=str(e))
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
    _MAX_TASK_RETRIES = 1

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
        if not self._wait_job(job, timeout_s=float(self._CONNECTION_TIMEOUT_S)):
            self.logger.error(LogCategory.MAIN, "ADB 控制器连接失败或超时", address=self._device_address)
            self._cleanup_partial()
            return False
        screencap_job = self._controller.post_screencap()
        if not self._wait_job(screencap_job, timeout_s=float(self._SCRECAP_TIMEOUT_S)):
            self.logger.error(LogCategory.MAIN, "首次截图失败或超时", address=self._device_address)
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

    def post_stop(self) -> bool:
        """中止当前正在运行的 MaaFW 任务（pipeline / recognition）。

        MaaFW Tasker 的 post_stop() 是异步操作，会立即返回一个 Job 对象，
        中止信号会让当前运行的 job 尽快退出。本方法等待中止完成（最长 5s），
        确保下一个 post_task 不会因 MaaFW 仍在处理中止而无限等待。
        用于 _run_pipeline_with_timeout 超时后释放 MaaFW，
        避免后续 pipeline / OCR 因 MaaFW 忙而级联超时。
        """
        if not self._connected or self._tasker is None:
            return False
        try:
            stop_job = self._tasker.post_stop()
            self.logger.info(LogCategory.MAIN, "MaaFW post_stop() 已发送中止信号")
            # post_stop() 是异步的，等待中止完成（最长 5s）
            if stop_job is not None and hasattr(stop_job, "wait"):
                try:
                    stop_job.wait(timeout=5000)  # ms
                except Exception:
                    # 某些 MaaFW 版本 wait() 不支持 timeout 参数，尝试不带 timeout
                    try:
                        stop_job.wait()
                    except Exception as exc:
                        self.logger.warning(
                            LogCategory.MAIN, "post_stop Job.wait() 失败", error=str(exc),
                        )
            return True
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "MaaFW post_stop() 失败", error=str(exc))
            return False

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
            # BUNDLE-HARD-TIMEOUT: 资源加载若 MaaFW 内部死锁会无限阻塞
            if not self._wait_job(job, timeout_s=60.0):
                self.logger.error(LogCategory.MAIN, "Pipeline 资源加载失败或超时", path=str(resource_dir))
                return False
            self.logger.info(LogCategory.MAIN, "Pipeline 资源加载成功", path=str(resource_dir))
            adb_resource_dir = self._resolve_asset_path("resource_adb")
            if adb_resource_dir.exists():
                job_adb = self._resource.post_bundle(adb_resource_dir)
                if not self._wait_job(job_adb, timeout_s=60.0):
                    self.logger.error(LogCategory.MAIN, "ADB 资源加载失败或超时", path=str(adb_resource_dir))
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

    def _wait_job(self, job: Any, timeout_s: Optional[float] = None) -> bool:
        """等待任务完成。

        注意：job.wait() 返回 Job 对象自身（truthy），不是任务成功与否的布尔值。
        必须用 job.succeeded 检查任务的真实状态。

        如果指定 timeout_s，使用线程 + join(timeout) 包装，避免 MaaFramework
        并发限制导致 job.wait() 无限阻塞。超时返回 False。
        """
        if timeout_s is None:
            job.wait()
            return job.succeeded
        import threading as _threading
        box: dict = {"succeeded": False, "error": None}

        def _do_wait() -> None:
            try:
                job.wait()
                box["succeeded"] = bool(job.succeeded)
            except BaseException as exc:
                box["error"] = exc

        t = _threading.Thread(target=_do_wait, daemon=True, name="maafw-wait-job")
        t.start()
        t.join(timeout=timeout_s)
        if t.is_alive():
            self.logger.warning(
                LogCategory.MAIN, "job.wait() 超时，放弃等待",
                timeout_s=timeout_s,
            )
            return False
        if box["error"] is not None:
            return False
        return box["succeeded"]

    def run_pipeline(self, entry: str, pipeline_override: Dict[str, Any]) -> bool:
        if not self._connected or self._tasker is None:
            self.logger.error(LogCategory.MAIN, "runtime 未连接，无法执行管道")
            return False
        self.logger.info(LogCategory.MAIN, "开始执行自定义管道", entry=entry)
        try:
            job = self._tasker.post_task(entry, pipeline_override if pipeline_override else {})
            succeeded = self._wait_job(job)
        except Exception as e:
            self._connected = False
            self.logger.exception(LogCategory.MAIN, "自定义管道执行异常", entry=entry, error=str(e))
            return False
        if succeeded:
            self.logger.info(LogCategory.MAIN, "自定义管道执行成功", entry=entry)
            return True
        self.logger.warning(LogCategory.MAIN, "自定义管道执行失败", entry=entry)
        return False

    def run_task(self, task_name: str, options: Optional[Dict[str, Any]] = None) -> bool:
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
        return self._run_task_with_retry(task_name, options, entry, override)

    def _run_task_with_retry(self, task_name: str, options: Dict[str, Any], entry: str, override: Dict[str, Any]) -> bool:
        for attempt in range(1 + self._MAX_TASK_RETRIES):
            if attempt > 0:
                self.logger.warning(LogCategory.MAIN, "任务自动重试", task=task_name, attempt=attempt)
            result = self._run_task_once(task_name, options, entry, override)
            if result is True:
                return True
            if result is None:
                self.logger.warning(LogCategory.MAIN, "任务执行异常（连接断开），尝试恢复", task=task_name)
                if not self._recovering and self._try_recover_connection(task_name):
                    self.logger.info(LogCategory.MAIN, "连接恢复成功，重试任务", task=task_name)
                    result2 = self._run_task_once(task_name, options, entry, override)
                    return bool(result2 is True)
                self.logger.error(LogCategory.MAIN, "连接恢复失败，无法重试", task=task_name)
                return False
            if self._recovering or attempt >= self._MAX_TASK_RETRIES:
                break
            if self._connected and self._lightweight_recover_ui():
                self.logger.info(LogCategory.MAIN, "轻量恢复完成，重试任务", task=task_name)
                retry_result = self._run_task_once(task_name, options, entry, override)
                if retry_result is True:
                    return True
            self.logger.info(LogCategory.MAIN, "轻量恢复后仍失败，尝试完整恢复", task=task_name)
            recover_ok = self._recover_and_retry(task_name, options)
            if recover_ok:
                return True
            return False
        self.logger.warning(LogCategory.MAIN, "任务执行失败（含重试）", task=task_name)
        return False

    def _run_task_once(self, task_name: str, options: Dict[str, Any], entry: str, override: Dict[str, Any]) -> Optional[bool]:
        self.logger.info(LogCategory.MAIN, "开始执行任务", task=task_name, entry=entry, override=override)
        watchdog_stop = threading.Event()
        watchdog_thread = threading.Thread(
            target=self._connection_watchdog, args=(task_name, watchdog_stop), daemon=True,
        )
        watchdog_thread.start()
        try:
            job = self._tasker.post_task(entry, override if override else {})
            succeeded = self._wait_job(job)
        except Exception as e:
            self._connected = False
            self.logger.exception(LogCategory.MAIN, "任务执行异常", task=task_name, error=str(e))
            return None
        finally:
            watchdog_stop.set()
        if succeeded:
            if self._detect_task_skipped(job, task_name, entry):
                self.logger.warning(LogCategory.MAIN, "任务被跳过（未满足执行条件，如未到计划周期）", task=task_name)
                return False
            self.logger.info(LogCategory.MAIN, "任务执行成功", task=task_name)
            return True
        if not self._connected:
            return None
        self.logger.warning(LogCategory.MAIN, "任务执行失败", task=task_name)
        return False

    def _connection_watchdog(self, task_name: str, stop_event: threading.Event) -> None:
        started = time.monotonic()
        while not stop_event.is_set():
            for _ in range(100):
                if stop_event.is_set():
                    return
                time.sleep(0.1)
            if stop_event.is_set():
                return
            if not self._check_adb_health():
                self.logger.warning(LogCategory.MAIN, "看门狗：ADB 连接断开，中断任务", task=task_name)
                self._connected = False
                try:
                    if self._tasker is not None:
                        self._tasker.post_stop()
                except Exception:
                    pass
                return
            elapsed = time.monotonic() - started
            if elapsed > 300:
                self.logger.warning(LogCategory.MAIN, "看门狗：任务疑似卡死，发送中断信号", task=task_name, elapsed_s=int(elapsed))
                self._connected = False
                try:
                    if self._tasker is not None:
                        self._tasker.post_stop()
                except Exception:
                    pass
                return

    def _detect_task_skipped(self, job: Any, task_name: str, entry: str = "") -> bool:
        """检测任务是否走了跳过分支（未真正执行业务）。

        MaaEnd 的 *Schedule 任务设计为 entry.next = [业务节点, 跳过节点]。
        当 ScheduleRecognition 不命中（如 attach 全 false）时走跳过节点，
        MaaFW 仍报告 status=succeeded，但任务实际未执行业务。
        通过检查节点轨迹区分跳过与真正执行。

        仅对 entry 包含 "Schedule" 的任务应用此启发式检测，避免对普通任务
        （如 DijiangRewards，其节点轨迹天然含 End/Done 但不含 Main/Start/Look）
        产生误判。
        """
        if "Schedule" not in (entry or ""):
            return False
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

    def run_queue(self) -> bool:
        """执行队列（唯一的可执行单元）。

        每个任务执行前进行健康检查（ADB + 截图验证），连接异常时自动恢复。
        单个任务失败不影响后续任务；仅当连接彻底无法恢复时才中止。
        """
        if not self._queue:
            self.logger.warning(LogCategory.MAIN, "队列为空，无可执行任务")
            return False
        self.logger.info(LogCategory.MAIN, "开始执行队列", queue_size=len(self._queue))
        failures: List[str] = []
        total = len(self._queue)
        for idx, item in enumerate(self._queue):
            name = str(item.get("name") or "").strip()
            options = item.get("options") or {}
            if not name:
                continue
            if not self._ensure_queue_connection(name, idx, total):
                failures.append(name)
                break
            self.logger.info(LogCategory.MAIN, "队列进度", current=idx + 1, total=total, task=name)
            if not self.run_task(name, options):
                failures.append(name)
                self.logger.warning(LogCategory.MAIN, "队列任务失败，继续后续", failed_task=name, failed_index=idx + 1)
                if not self._connected:
                    self.logger.warning(LogCategory.MAIN, "任务后连接断开，尝试恢复继续队列")
                    if not self._ensure_queue_connection(name, idx, total):
                        break
        if failures:
            self.logger.warning(LogCategory.MAIN, "队列执行完成但存在失败任务", failed=failures, total=len(failures))
            return False
        self.logger.info(LogCategory.MAIN, "队列执行完成，全部成功", total=total)
        return True

    def _ensure_queue_connection(self, task_name: str, idx: int, total: int) -> bool:
        if self._connected and self._check_adb_health():
            if self._verify_connection_alive():
                return True
            self.logger.warning(LogCategory.MAIN, "控制器失效，尝试重建")
            if self._rebuild_controller():
                return True
        self.logger.warning(LogCategory.MAIN, "队列任务执行前连接异常，尝试恢复", task=task_name)
        if self._quick_reconnect_adb():
            self.logger.info(LogCategory.MAIN, "队列连接恢复成功", task=task_name)
            return True
        if self._reconnect_with_retry():
            self.logger.info(LogCategory.MAIN, "队列完整重连成功", task=task_name)
            return True
        self.logger.error(LogCategory.MAIN, "队列连接恢复失败，中止剩余任务", remaining=total - idx)
        return False

    def run_preset(self, preset_name: str) -> bool:
        """应用预设到队列并执行队列（便捷封装）。

        预设本身不可直接执行，故等价于 apply_preset + run_queue。
        """
        if not self.apply_preset(preset_name):
            return False
        if not self._queue:
            # 空预设：无可执行任务，视为成功（与旧行为一致）
            self.logger.info(LogCategory.MAIN, "预设任务列表为空，无需执行", preset=preset_name)
            return True
        return self.run_queue()

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

    def _recover_and_retry(self, task_name: str, options: Dict[str, Any]) -> bool:
        """分级异常恢复：优先轻量 UI 修正，最终手段才重启游戏。

        恢复层级：
        1. 验证 ADB 连接可用（不可用则先重连）
        2. 执行 RecoverGame 任务（StopApp → StartApp → OpenGame）
        3. 等待游戏完全加载 + 关闭弹窗
        4. 重试失败任务
        """
        self.logger.info(
            LogCategory.MAIN,
            "异常恢复开始：验证连接 → RecoverGame → 重试任务",
            task=task_name,
            client_version=self._client_version,
        )
        self._recovering = True
        try:
            if self._controller is None or self._tasker is None or not self._connected:
                self.logger.info(LogCategory.MAIN, "异常恢复：需要完整重连")
                if not self._reconnect_with_retry():
                    self.logger.error(LogCategory.MAIN, "异常恢复：重连失败")
                    return False

            self.logger.info(LogCategory.MAIN, "异常恢复：执行 RecoverGame 任务")
            recover_ok = self.run_task("RecoverGame", {"ClientVersion": self._client_version})
            if not recover_ok:
                self.logger.error(LogCategory.MAIN, "异常恢复失败：RecoverGame 任务失败")
                return False

            self._post_game_restart_cleanup()

            self.logger.info(LogCategory.MAIN, "异常恢复：重试失败任务", task=task_name)
            return self.run_task(task_name, options)
        finally:
            self._recovering = False

    def _post_game_restart_cleanup(self) -> None:
        """游戏重启后的清理：等待加载 + 关闭弹窗。"""
        self.logger.info(LogCategory.MAIN, "游戏重启后清理：等待加载 + 关闭弹窗")
        time.sleep(8.0)
        for i in range(8):
            try:
                subprocess.run(
                    [self._adb_path, "-s", self._device_address, "shell", "input", "keyevent", "4"],
                    text=True, timeout=5, capture_output=True,
                )
                time.sleep(1.0)
            except Exception:
                pass
        time.sleep(3.0)
        self.logger.info(LogCategory.MAIN, "游戏重启后清理完成")

    def _try_recover(self, task_name: str) -> bool:
        """尝试恢复连接/设备状态，失败则重启应用。"""
        try:
            if self._controller is not None:
                job = self._controller.post_screencap()
                # RECOVER-SCREENCAP-TIMEOUT: 恢复时 screencap 也可能阻塞
                if self._wait_job(job, timeout_s=float(self._SCRECAP_TIMEOUT_S)):
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

    def _try_recover_connection(self, task_name: str) -> bool:
        """专注于连接恢复：先尝试轻量重连，失败则完整重建。"""
        self.logger.info(LogCategory.MAIN, "尝试恢复连接", task=task_name)
        if self._controller is None or self._tasker is None:
            self.logger.info(LogCategory.MAIN, "资源已清理，执行完整重连")
            return self._reconnect_with_retry()
        if self._check_adb_health():
            if self._verify_connection_alive():
                self.logger.info(LogCategory.MAIN, "连接仍然可用", task=task_name)
                return True
            self.logger.info(LogCategory.MAIN, "ADB 可用但控制器失效，重建控制器")
            if self._rebuild_controller():
                return True
        self.logger.info(LogCategory.MAIN, "轻量恢复不够，尝试 ADB 快速重连")
        if self._quick_reconnect_adb():
            return True
        self.logger.info(LogCategory.MAIN, "ADB 重连失败，尝试完整重建连接")
        return self._reconnect_with_retry()

    def _reconnect_with_retry(self) -> bool:
        """带重试的完整重连。模拟器重启后 ADB 可能需要时间恢复。"""
        for attempt in range(3):
            if attempt > 0:
                self.logger.info(LogCategory.MAIN, f"完整重连重试 {attempt}/3")
                time.sleep(3.0 * attempt)
            if self._reconnect():
                return True
            if not self._check_adb_health():
                self.logger.info(LogCategory.MAIN, "ADB 不可用，等待后重试")
                time.sleep(3.0)
                self._quick_reconnect_adb()
        return False

    def _retry_task(self, task_name: str, options: Dict[str, Any], entry: str) -> bool:
        """恢复后重试当前任务一次。"""
        if not self._connected or self._tasker is None:
            return False
        self.logger.info(LogCategory.MAIN, "重试任务", task=task_name)
        try:
            job = self._tasker.post_task(entry, self.build_pipeline_override(task_name, options) or {})
            succeeded = self._wait_job(job)
        except Exception as exc:
            self._connected = False
            self.logger.exception(LogCategory.MAIN, "重试异常", task=task_name, error=str(exc))
            return False
        if succeeded:
            if self._detect_task_skipped(job, task_name, entry):
                self.logger.warning(LogCategory.MAIN, "重试任务被跳过", task=task_name)
                return False
            self.logger.info(LogCategory.MAIN, "重试成功", task=task_name)
            return True
        self.logger.warning(LogCategory.MAIN, "重试失败", task=task_name)
        return False

    def _send_key_back(self) -> bool:
        try:
            subprocess.run(
                [self._adb_path, "-s", self._device_address, "shell", "input", "keyevent", "4"],
                text=True, timeout=5, capture_output=True,
            )
            time.sleep(0.8)
            self.logger.info(LogCategory.MAIN, "已发送 BACK 关闭弹窗")
            return True
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "发送 BACK 键失败", error=str(exc))
            return False

    def _check_adb_health(self) -> bool:
        try:
            result = subprocess.run(
                [self._adb_path, "-s", self._device_address, "shell", "echo", "ok"],
                text=True, timeout=5, capture_output=True,
            )
            return result.returncode == 0 and "ok" in result.stdout
        except Exception:
            return False

    def _quick_reconnect_adb(self) -> bool:
        self.logger.info(LogCategory.MAIN, "快速 ADB 重连")
        for attempt in range(3):
            if attempt > 0:
                self.logger.info(LogCategory.MAIN, f"ADB 重连重试 {attempt}/3")
                time.sleep(2.0 * attempt)
            try:
                result = subprocess.run(
                    [self._adb_path, "connect", self._device_address],
                    text=True, timeout=10, capture_output=True,
                )
                if "connected" in result.stdout.lower():
                    time.sleep(0.5)
                    if self._rebuild_controller():
                        return True
            except Exception as exc:
                self.logger.warning(LogCategory.MAIN, "快速 ADB 重连失败", attempt=attempt, error=str(exc))
        self.logger.info(LogCategory.MAIN, "快速重连失败，重启 ADB 服务后重试")
        try:
            self._kill_adb()
            time.sleep(1)
            for attempt in range(2):
                try:
                    subprocess.run(
                        [self._adb_path, "connect", self._device_address],
                        text=True, timeout=10, capture_output=True,
                    )
                    time.sleep(1)
                    if self._rebuild_controller():
                        return True
                except Exception:
                    time.sleep(2)
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "ADB 重启后重连失败", error=str(exc))
        return False

    def _rebuild_controller(self) -> bool:
        if not MAAFW_AVAILABLE:
            return False
        try:
            screencap_ok = False
            if self._controller is not None:
                try:
                    job = self._controller.post_screencap()
                    screencap_ok = self._wait_job(job, timeout_s=float(self._SCRECAP_TIMEOUT_S))
                except Exception:
                    pass
            if screencap_ok:
                self._connected = True
                self.logger.info(LogCategory.MAIN, "控制器复用成功（截图验证通过）")
                return True
            self.logger.info(LogCategory.MAIN, "控制器不可复用，重建完整连接")
            return self._reconnect()
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "控制器重建失败", error=str(exc))
            return False

    def _lightweight_recover_ui(self) -> bool:
        if not self._connected:
            return False
        self.logger.info(LogCategory.MAIN, "轻量恢复：多次 BACK 关闭弹窗/对话框")
        for _ in range(3):
            if not self._send_key_back():
                return False
        if not self._verify_connection_alive():
            return False
        time.sleep(1.5)
        return True

    def _verify_connection_alive(self) -> bool:
        if not self._connected or self._controller is None:
            return False
        try:
            job = self._controller.post_screencap()
            ok = self._wait_job(job, timeout_s=float(self._SCRECAP_TIMEOUT_S))
            if ok:
                return True
        except Exception:
            pass
        self._connected = False
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

    def screenshot(self, timeout_s: float = 8.0) -> Optional[bytes]:
        # SCREENCAP-HARD-TIMEOUT: MaaFramework 的 post_screencap() 和 job.done
        # 都可能阻塞：
        # 1. job.wait() 无超时参数，若 MaaFramework 与设备的 ADB screencap 通道
        #    卡死（如 scrcpy 会话冲突、设备休眠），wait() 会无限阻塞
        # 2. post_screencap() 本身可能阻塞：当 _run_pipeline_with_timeout 的
        #    孤儿线程仍在运行 job.wait()（pipeline 任务未完成）时，MaaFramework
        #    内部可能拒绝并发操作，导致 post_screencap() 阻塞等待 pipeline 完成
        # 解决方案：把 post_screencap() + 轮询 job.done 全部放入子线程，
        # 主线程用 join(timeout) 等待，超时即放弃。子线程为 daemon，自然消亡。
        if not self._connected or self._controller is None:
            return None

        import threading as _threading

        result_box: dict = {"data": None, "error": None}

        def _do_screencap() -> None:
            try:
                job = self._controller.post_screencap()
                # 子线程内用剩余时间轮询 job.done
                inner_deadline = time.monotonic() + float(timeout_s)
                while not job.done:
                    if time.monotonic() >= inner_deadline:
                        self.logger.warning(
                            LogCategory.MAIN,
                            "截图子线程：screencap 未在限定时间内完成",
                            timeout_s=timeout_s,
                        )
                        return
                    time.sleep(0.05)
                if not job.succeeded:
                    self.logger.warning(LogCategory.MAIN, "截图失败（screencap 未成功），但保持连接态")
                    return
                cached = self._controller.cached_image
                if cached is None:
                    return
                import cv2
                success, buf = cv2.imencode(".png", cached)
                if success:
                    result_box["data"] = buf.tobytes()
            except BaseException as exc:  # noqa: BLE001
                result_box["error"] = exc

        t = _threading.Thread(target=_do_screencap, daemon=True, name="maaend-screenshot")
        t.start()
        t.join(timeout=timeout_s + 2.0)  # 主线程给 2s 余量
        if t.is_alive():
            self.logger.warning(
                LogCategory.MAIN,
                "截图超时（post_screencap 阻塞或 job 不完成），放弃本次截图",
                timeout_s=timeout_s,
            )
            return None
        if result_box["error"] is not None:
            self.logger.warning(LogCategory.MAIN, "截图异常，保持连接态", error=str(result_box["error"]))
            return None
        return result_box["data"]
