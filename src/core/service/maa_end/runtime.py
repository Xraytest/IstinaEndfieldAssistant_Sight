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
            with open(path, "r", encoding="utf-8") as f:
                self._interface = json.load(f)
        except Exception as e:
            self.logger.warning(LogCategory.MAIN, "加载 interface.json 失败", path=str(path), error=str(e))
            self._interface = {}
        return self._interface or {}

    def load_tasks(self) -> Dict[str, Dict[str, Any]]:
        tasks_root = self._resolve_asset_path("tasks")
        self._tasks = {}
        self._option_defs = {}
        for json_path in tasks_root.rglob("*.json"):
            if json_path.name == "nodes.json":
                continue
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
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
        preset_root = self._resolve_asset_path("tasks", "preset")
        self._presets = {}
        if not preset_root.exists():
            self._presets_loaded = True
            return self._presets
        for json_path in preset_root.glob("*.json"):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
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
        input_methods = int(MaaAdbInputMethodEnum.AdbShell if MaaAdbInputMethodEnum else 1)
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
        # Start Agent after Tasker is ready so it can register sinks correctly.
        self._start_agent()
        if self._agent_client is None and self._agent_process is None:
            self.logger.error(LogCategory.MAIN, "Agent 未启动，连接中止")
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
            if value is None:
                continue
            opt_def = option_defs.get(opt_name, {})
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
                    result.update(case.get("pipeline_override") or {})
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
        """
        if timeout is None or timeout <= 0:
            return job.wait()
        result: Dict[str, Any] = {}

        def _target() -> None:
            try:
                result["ok"] = job.wait()
            except Exception:
                result["ok"] = False

        worker = threading.Thread(target=_target, daemon=True)
        worker.start()
        worker.join(float(timeout))
        if worker.is_alive():
            self.logger.warning(LogCategory.MAIN, "任务执行超时", timeout=timeout)
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
        override = self.build_pipeline_override(task_name, options)
        entry = task.get("entry", task_name)
        self.logger.info(LogCategory.MAIN, "开始执行任务", task=task_name, entry=entry, override=override)
        try:
            job = self._tasker.post_task(entry, override if override else {})
            succeeded = self._wait_job(job, timeout)
        except Exception as e:
            # 仅真正的执行异常才视为连接断开并尝试恢复
            self._connected = False
            self.logger.exception(LogCategory.MAIN, "任务执行异常", task=task_name, error=str(e))
            if self._try_recover(task_name):
                return self._retry_task(task_name, options, entry, timeout)
            return False
        if succeeded:
            self.logger.info(LogCategory.MAIN, "任务执行成功", task=task_name)
            return True
        # 识别未命中等「正常失败」：仅上报失败，不污染连接态、不重启应用
        self.logger.warning(LogCategory.MAIN, "任务执行失败", task=task_name)
        return False

    def run_preset(self, preset_name: str, timeout: Optional[float] = None) -> bool:
        if not self._presets:
            self.load_presets()
        preset = self._presets.get(preset_name)
        if not preset:
            self.logger.error(LogCategory.MAIN, "预设未定义", preset=preset_name)
            return False
        task_list = preset.get("task", [])
        self.logger.info(LogCategory.MAIN, "开始执行预设", preset=preset_name, tasks=len(task_list))
        failures: List[str] = []
        for task_entry in task_list:
            name = task_entry.get("name")
            options = task_entry.get("option") or {}
            if not self.run_task(name, options, timeout):
                failures.append(name)
                self.logger.warning(LogCategory.MAIN, "预设任务失败，继续后续任务", preset=preset_name, failed_task=name)
                # 若连接已真正断开，继续也无意义，及时中止剩余任务
                if not self._connected:
                    self.logger.error(LogCategory.MAIN, "预设执行中连接断开，中止", preset=preset_name)
                    break
        if failures:
            self.logger.warning(LogCategory.MAIN, "预设执行完成但存在失败任务", preset=preset_name, failed=failures)
            return False
        self.logger.info(LogCategory.MAIN, "预设执行完成", preset=preset_name)
        return True

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
                self._connected = False
                return None
            cached = self._controller.cached_image
            if cached is None:
                return None
            import cv2
            success, buf = cv2.imencode(".png", cached)
            return buf.tobytes() if success else None
        except Exception as e:
            self._connected = False
            self.logger.exception(LogCategory.MAIN, "截图失败", error=str(e))
            return None
