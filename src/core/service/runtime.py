"""IstinaRuntime - 统一运行时入口

封装设备层与 MaaEndRuntime，提供 GUI/CLI 统一执行接口。
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional


import cv2
import numpy as np

from core.foundation.logger import LogCategory, get_logger
from core.foundation.paths import get_cache_subdir, get_project_root

if TYPE_CHECKING:
    pass

# 以下模块按需导入，避免 CLI 轻量命令（如 metadata list）触发重依赖
_AndroidRuntime = None
_ADBDeviceInfo = None
_SceneUnderstandingService = None
_Navigator = None


def _get_android_runtime():
    global _AndroidRuntime
    if _AndroidRuntime is None:
        from core.capability.device.android_runtime import AndroidRuntime
        _AndroidRuntime = AndroidRuntime
    return _AndroidRuntime


def _get_adb_device_info():
    global _ADBDeviceInfo
    if _ADBDeviceInfo is None:
        from core.capability.device.adb_manager import ADBDeviceInfo
        _ADBDeviceInfo = ADBDeviceInfo
    return _ADBDeviceInfo


def _get_scene_understanding_service():
    global _SceneUnderstandingService
    if _SceneUnderstandingService is None:
        from core.capability.element_recognition import SceneUnderstandingService
        _SceneUnderstandingService = SceneUnderstandingService
    return _SceneUnderstandingService


def _get_navigator():
    global _Navigator
    if _Navigator is None:
        from core.service.navigation import Navigator
        _Navigator = Navigator
    return _Navigator


def _get_llama_runtime(config: Dict[str, Any]) -> Any:
    from core.capability.llm.runtime import LlamaServerRuntime
    return LlamaServerRuntime.get_instance(config)


def _get_llm_client(llama_runtime: Any) -> Any:
    from core.capability.llm.client import LlmClient
    return LlmClient(base_url=llama_runtime.base_url)


class AndroidRuntimeProxy:
    """Android 交互运行时适配层，委托给跨进程单例 AndroidRuntime"""

    def __init__(
        self,
        adb_path: str = "3rd-part/adb/adb.exe",
        device_address: Optional[str] = None,
    ):
        self._adb_path = adb_path
        self._device_address = device_address
        self._logger = get_logger(__name__)
        self._clients: Dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        client = self._client_for(None)
        return getattr(client, name)

    @property
    def default_client(self):
        return self._client_for(None)

    def _client_for(self, serial: Optional[str]) -> Any:
        resolved = serial or self._device_address or "default"
        client = self._clients.get(resolved)
        if client is None:
            client = _get_android_runtime()(serial=resolved, adb_path=self._adb_path)
            self._clients[resolved] = client
        return client


AndroidRuntimeProxy.__name__ = "AndroidRuntime"


class IstinaRuntime:
    """Istina 统一运行时门面，聚合设备、MaaEnd、LLM、场景理解等服务。"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            cfg = Path(config_path).resolve()
            root = get_project_root().resolve()
            if root not in cfg.parents and cfg != root:
                raise ValueError(f"config_path 必须在项目目录内: {config_path}")
            self._config_path = cfg
        else:
            self._config_path = None
        self._logger = get_logger(__name__)
        self._config = self._load_config()
        self._android_clients: Dict[str, AndroidRuntimeProxy] = {}
        self._maaend_clients: Dict[str, Any] = {}
        self._clients_lock = threading.Lock()  # 保护客户端字典的并发创建
        self._maaend: Optional[Any] = None
        self._llm_runtime: Optional[Any] = None
        self._llm_client: Optional[Any] = None
        self._scene_svc: Optional[Any] = None
        self._nav: Optional[Any] = None
        self._nav_android: Optional[Any] = None

    @property
    def _llm_runtime_instance(self) -> Any:
        if self._llm_runtime is None:
            self._llm_runtime = _get_llama_runtime(self._config)
        return self._llm_runtime

    @property
    def _llm_client_instance(self) -> Any:
        if self._llm_client is None:
            self._llm_client = _get_llm_client(self._llm_runtime_instance)
        return self._llm_client

    @property
    def config(self) -> Dict[str, Any]:
        return self._config

    @property
    def connected(self) -> bool:
        if self._maaend_clients:
            return any(runtime.connected for runtime in self._maaend_clients.values())
        legacy = getattr(self, "_maaend", None)
        return bool(legacy and legacy.connected)

    def android(self, serial: Optional[str] = None) -> AndroidRuntimeProxy:
        device_cfg = self._config.get("device", {}) or {}
        resolved = (
            serial
            or device_cfg.get("last_connected")
            or device_cfg.get("serial")
            or "localhost:16512"
        )
        runtime = self._android_clients.get(resolved)
        if runtime is None:
            with self._clients_lock:
                # 双重检查，避免锁内重复创建
                runtime = self._android_clients.get(resolved)
                if runtime is None:
                    runtime = AndroidRuntimeProxy(
                        adb_path=self._config.get("adb_path", "3rd-part/adb/adb.exe"),
                        device_address=resolved,
                    )
                    self._android_clients[resolved] = runtime
        return runtime

    def _resolve_serial(self, serial: Optional[str]) -> str:
        device_cfg = self._config.get("device", {}) or {}
        return (
            serial
            or device_cfg.get("last_connected")
            or device_cfg.get("serial")
            or "localhost:16512"
        )

    def maaend(self, serial: Optional[str] = None) -> Any:
        legacy = getattr(self, "_maaend", None)
        if legacy is not None and not self._maaend_clients:
            return legacy
        resolved = self._resolve_serial(serial)
        runtime = self._maaend_clients.get(resolved)
        if runtime is None:
            with self._clients_lock:
                # 双重检查，避免锁内重复创建
                runtime = self._maaend_clients.get(resolved)
                if runtime is None:
                    from core.service.maa_end.runtime import MaaEndRuntime
                    runtime = MaaEndRuntime(
                        maaend_root=self._config.get("maaend_root"),
                        device_address=resolved,
                        adb_path=self._config.get("adb_path", "3rd-part/adb/adb.exe"),
                        adb_restart_on_timeout=self._config.get("device", {}).get("adb_restart_on_timeout", True),
                    )
                    self._maaend_clients[resolved] = runtime
        return runtime

    def scene(self) -> Any:
        if self._scene_svc is None:
            self._scene_svc = _get_scene_understanding_service()(
                maaend_runtime=self.maaend(),
            )
        return self._scene_svc

    def navigator(self) -> Any:
        android = self.android()
        # XC-4: 设备切换时废弃旧的 screenshot_fn bound method，重新绑定新设备
        if self._nav is None or self._nav_android is not android:
            self._nav = _get_navigator()(
                maaend=self.maaend(),
                screenshot_fn=android.screenshot,
            )
            self._nav_android = android
        return self._nav

    def connect(self, serial: Optional[str] = None) -> bool:
        self._logger.info(LogCategory.MAIN, "开始连接设备", serial=serial)
        runtime = self.maaend(serial)
        if not runtime.connected:
            ok = runtime.connect()
            if not ok:
                self._logger.error(LogCategory.MAIN, "MaaEnd runtime 连接失败")
                return False
        resource_ok = runtime.load_resource()
        if not resource_ok:
            self._logger.error(LogCategory.MAIN, "MaaEnd runtime 资源加载失败")
            return False
        # 连接成功后立即启动 scrcpy 常驻图像通道，供预览按需取用。
        try:
            self._logger.info(LogCategory.MAIN, "尝试启动 scrcpy 预览通道", serial=serial)
            result = self.android(serial).start_scrcpy(serial=serial)
            if isinstance(result, dict) and result.get("error"):
                self._logger.warning(LogCategory.MAIN, "scrcpy 预览通道启动失败", error=result["error"], serial=serial)
                # 清理失败 session，允许下次连接重试
                try:
                    self.android(serial).stop_scrcpy(serial=serial)
                except Exception:
                    pass
            else:
                self._logger.info(LogCategory.MAIN, "scrcpy 预览通道启动成功", serial=serial)
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "scrcpy 预览通道启动失败", error=str(exc), serial=serial)
            try:
                self.android(serial).stop_scrcpy(serial=serial)
            except Exception:
                pass
        self._logger.info(LogCategory.MAIN, "MaaEnd runtime 已就绪")
        return True

    def _ensure_maaend_ready(self, runtime: Any) -> bool:
        if runtime.connected:
            return True
        if not runtime.connect():
            self._logger.error(LogCategory.MAIN, "MaaEnd runtime 连接失败")
            return False
        if not runtime.load_resource():
            self._logger.error(LogCategory.MAIN, "MaaEnd runtime 资源加载失败")
            return False
        return True


    def disconnect(self, serial: Optional[str] = None) -> None:
        self._logger.info(LogCategory.MAIN, "开始断开设备", serial=serial)
        legacy = getattr(self, "_maaend", None)
        if legacy is not None and not self._maaend_clients:
            try:
                legacy.disconnect()
            except Exception as e:
                self._logger.error(LogCategory.MAIN, "断开连接异常", serial=serial, error=str(e))
            return
        targets = [serial] if serial is not None else list(self._maaend_clients.keys())
        for target in targets:
            runtime = self._maaend_clients.get(target)
            if runtime is None:
                continue
            try:
                runtime.disconnect()
            except Exception as e:
                self._logger.error(LogCategory.MAIN, "断开连接异常", serial=target, error=str(e))
            self._maaend_clients.pop(target, None)
        # 断开所有设备时，同步停止 scrcpy 预览通道。
        try:
            self._logger.info(LogCategory.MAIN, "停止 scrcpy 预览通道", serial=serial)
            android = self.android(serial)
            android.stop_scrcpy(serial=serial)
            self._logger.info(LogCategory.MAIN, "scrcpy 预览通道已停止", serial=serial)
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "停止 scrcpy 预览通道失败", error=str(exc))

    def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> Any:
        params = params or {}
        parts = command.split(".")
        if len(parts) == 2:
            domain, action = parts
        elif len(parts) == 1:
            domain, action = parts[0], ""
        else:
            domain, action = "unknown", command

        if domain == "task" and action == "run":
            return self._run_task(params)
        if domain == "task" and action == "list":
            return self._list_tasks(params)
        if domain == "preset" and action == "run":
            return self._run_preset(params)
        if domain == "preset" and action == "apply":
            return self._apply_preset(params)
        if domain == "preset" and action == "list":
            return self._list_presets(params)
        if domain == "queue" and action == "run":
            return self._run_queue(params)
        if domain == "queue" and action == "list":
            return self._list_queue(params)
        if domain == "queue" and action == "clear":
            return self._clear_queue(params)
        if domain == "metadata" and action == "list":
            return self._list_metadata(params)
        if domain == "screenshot":
            return self._screenshot(params)
        if domain == "system" and action == "connect":
            return self.connect(params.get("serial"))
        if domain == "system" and action == "disconnect":
            self.disconnect(params.get("serial"))
            return True
        if domain == "daily" and action == "run":
            return self._daily_run(params)
        if domain == "harvest" and action == "run":
            return self._harvest_run(params)
        if domain == "analyze" and action == "run":
            return self._analyze_run(params)
        if domain == "explore" and action == "run":
            return self._explore_run(params)
        if domain == "material" and action == "farm":
            return self._material_farm_run(params)
        if domain == "material" and action == "collect":
            return self._material_collect_run(params)
        if domain == "readtask" and action == "run":
            return self._read_task_list_run(params)
        if domain == "readtask" and action == "run_blue":
            return self._run_category_tasks(params)
        if domain == "readtask" and action == "run_category":
            return self._run_category_tasks(params)
        if domain == "readtask" and action == "list_categorized":
            return self._list_categorized_tasks(params)
        if domain == "readtask" and action == "list_blue":
            return self._list_blue_tasks(params)
        if domain == "nav" and action == "to":
            return self._nav_to(params)
        if domain == "nav2" and action == "to_coords":
            return self._nav2_to_coords(params)
        if domain == "nav2" and action == "to_entity":
            return self._nav2_to_entity(params)
        if domain == "nav2" and action == "where":
            return self._nav2_where(params)
        if domain == "nav2" and action == "list_entities":
            return self._nav2_list_entities(params)
        if domain == "nav2" and action == "list_maps":
            return self._nav2_list_maps(params)
        if domain == "nav3" and action == "walk":
            return self._nav3_walk(params)
        if domain == "nav3" and action == "walk_tracking":
            return self._nav3_walk_tracking(params)
        if domain == "nav3" and action == "to_entity":
            return self._nav3_to_entity(params)
        if domain == "nav3" and action == "status":
            return {"status": "success", "nav3_available": True}
        if domain == "scene" and action == "identify":
            return self._scene_identify(params)
        if domain == "scene" and action == "verify":
            return self._scene_verify(params)
        if domain == "scene" and action == "elements":
            return self._scene_analyze_elements(params)
        if domain == "scene" and action == "context":
            return self._scene_context(params)
        if domain == "llm":
            if action in ("chat", "prompt", "run"):
                return self._llm_run(params)
            if action == "status":
                return self._llm_status()
            return {"status": "error", "message": f"unknown llm action: {action}"}
        self._logger.warning(LogCategory.MAIN, "未知命令", command=command)
        return None

    @staticmethod
    def _placeholder(command: str, target: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
        result: Dict[str, Any] = {"status": "not_implemented", "command": command}
        if target is not None:
            result["target"] = target
        result.update(kwargs)
        return result

    def _list_tasks(self, params: Dict[str, Any]) -> Dict[str, Any]:
        serial = params.get("serial")
        runtime = self.maaend(serial)
        return runtime.tasks()

    def _list_presets(self, params: Dict[str, Any]) -> Dict[str, Any]:
        serial = params.get("serial")
        runtime = self.maaend(serial)
        return runtime.presets()

    def _list_metadata(self, params: Dict[str, Any]) -> Dict[str, Any]:
        serial = params.get("serial")
        runtime = self.maaend(serial)
        return {
            "tasks": runtime.tasks(),
            "presets": runtime.presets(),
            "task_option_defs": runtime.task_option_defs(),
        }

    def _run_task(self, params: Dict[str, Any]) -> bool:
        name = params.get("name")
        # 全智能分类任务由 Python 编排器接管：MaaFW pipeline 仅承担 UI/传送/战斗，
        # VLM 步行导航与多阶段串联在编排器内完成，避免 MaaEnd 盲走 navmesh。
        if name == "MaterialFarm":
            result = self._material_farm_run(params)
            return bool(result.get("status") == "success")
        if name == "MaterialCollect":
            result = self._material_collect_run(params)
            return bool(result.get("status") == "success")
        if name == "ReadAllTasks":
            result = self._read_task_list_run(params)
            return bool(result.get("status") == "success")
        if name == "TaskExecute":
            result = self._run_category_tasks(params)
            return bool(result.get("status") == "success")
        options = params.get("options") or {}
        serial = params.get("serial")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return False
        return bool(runtime.run_task(name, options))

    def _run_preset(self, params: Dict[str, Any]) -> bool:
        name = params.get("name")
        serial = params.get("serial")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return False
        return bool(runtime.run_preset(name))

    def _apply_preset(self, params: Dict[str, Any]) -> bool:
        name = params.get("name")
        serial = params.get("serial")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return False
        return bool(runtime.apply_preset(name))

    def _run_queue(self, params: Dict[str, Any]) -> bool:
        serial = params.get("serial")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return False
        return bool(runtime.run_queue())

    def _list_queue(self, params: Dict[str, Any]) -> Dict[str, Any]:
        serial = params.get("serial")
        runtime = self.maaend(serial)
        return {"queue": runtime.queue()}

    def _clear_queue(self, params: Dict[str, Any]) -> Dict[str, Any]:
        serial = params.get("serial")
        runtime = self.maaend(serial)
        runtime.clear_queue()
        return {"status": "success"}

    def _screenshot(self, params: Dict[str, Any]) -> Optional[bytes]:
        serial = params.get("serial")
        self._logger.debug(LogCategory.MAIN, "_screenshot 开始", serial=serial)
        # 优先使用 AndroidRuntime (scrcpy 常驻通道)，失败则回退到 MaaEndRuntime (AdbController)。
        try:
            android = self.android(serial)
            data = android.screenshot(serial)
            if data is not None:
                self._logger.debug(LogCategory.MAIN, "_screenshot AndroidRuntime 成功", serial=serial, size=len(data) if data else None)
                return data
            self._logger.warning(LogCategory.MAIN, "_screenshot AndroidRuntime 返回 None", serial=serial)
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "scrcpy 预览取帧失败，回退到 MaaEnd", error=str(exc))
        legacy = getattr(self, "_maaend", None)
        if legacy is not None and not self._maaend_clients:
            data = legacy.screenshot()
            self._logger.debug(LogCategory.MAIN, "_screenshot legacy MaaEnd 完成", size=len(data) if data else None)
            return data
        runtime = self.maaend(serial)
        data = runtime.screenshot()
        self._logger.debug(LogCategory.MAIN, "_screenshot MaaEndRuntime 完成", size=len(data) if data else None)
        return data

    def _load_config(self) -> Dict[str, Any]:
        path = self._resolve_config_path()
        if not path.exists():
            self._logger.info(LogCategory.MAIN, "配置文件不存在，使用默认值", path=str(path))
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:  # CFG-12/15: 拆分异常类型，给出可定位的错误
            self._logger.error(LogCategory.MAIN, "配置 JSON 解析失败", path=str(path), error=str(e))
            return {}
        except PermissionError as e:
            self._logger.error(LogCategory.MAIN, "配置无读取权限", path=str(path), error=str(e))
            return {}
        except OSError as e:
            self._logger.error(LogCategory.MAIN, "配置读取失败", path=str(path), error=str(e))
            return {}
        if not isinstance(data, dict):
            self._logger.error(LogCategory.MAIN, "配置根不是对象", path=str(path))
            return {}
        # 最小 schema 校验：关键字段缺失给出明确告警
        llm = data.get("llm", {}) or {}
        if not str(llm.get("model_path", "")).strip():
            self._logger.warning(LogCategory.MAIN, "配置缺少 llm.model_path，LLM 将无法启动", path=str(path))
        return data

    def _resolve_config_path(self) -> Path:
        if self._config_path is not None:
            p = Path(self._config_path).expanduser().resolve()
            root = get_project_root().resolve()
            if root not in p.parents and p != root:  # CFG-09: 约束 --config 在项目根内
                self._logger.warning(LogCategory.MAIN, "config 路径越界，回退默认", path=str(p))
                return root / "config" / "client_config.json"
            return p
        return get_project_root() / "config" / "client_config.json"

    def save_config(self) -> None:
        path = self._resolve_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)

    def reload_config(self) -> None:
        self._config = self._load_config()
        device_cfg = self._config.get("device", {}) or {}
        adb_restart_on_timeout = bool(device_cfg.get("adb_restart_on_timeout", True))
        for runtime in self._maaend_clients.values():
            runtime._adb_restart_on_timeout = adb_restart_on_timeout

    def _daily_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        options = params.get("options") or {}
        preset_name = options.get("preset", "DailyFull")
        client_version = options.get("ClientVersion", "CN")
        serial = params.get("serial")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return {
                "status": "error",
                "command": "daily.run",
                "flow": "daily_quest",
                "preset": preset_name,
                "options": options,
                "maaend_connected": False,
            }
        # 在运行每日预设前，确保游戏已启动并进入大世界。
        if not self._ensure_game_in_world(runtime, serial, client_version):
            return {
                "status": "error",
                "command": "daily.run",
                "flow": "daily_quest",
                "preset": preset_name,
                "options": options,
                "maaend_connected": self.connected,
                "message": "启动游戏或等待进入大世界失败",
            }
        ok = self.execute("preset.run", {"name": preset_name, "serial": serial})
        return {
            "status": "success" if ok else "error",
            "command": "daily.run",
            "flow": "daily_quest",
            "preset": preset_name,
            "options": options,
            "maaend_connected": self.connected,
        }

    def _ensure_game_in_world(self, runtime: Any, serial: Optional[str], client_version: str) -> bool:
        """启动游戏并等待进入大世界。"""
        try:
            android = self.android(serial)
            pid = android.shell("pidof com.hypergryph.endfield").strip()
            if pid:
                self._logger.info(LogCategory.MAIN, "游戏进程已在运行", pid=pid)
            else:
                self._logger.info(LogCategory.MAIN, "游戏未运行，准备启动")
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "检查游戏进程失败", error=str(exc))

        # AndroidOpenGame 任务会启动游戏并等待进入大世界
        if not runtime.run_task("AndroidOpenGame", {"ClientVersion": client_version}):
            self._logger.error(LogCategory.MAIN, "AndroidOpenGame 执行失败")
            return False

        # 额外等待大世界稳定，防止部分加载界面导致后续任务误判
        return self._wait_for_in_world(runtime, interval=2)

    def _wait_for_in_world(self, runtime: Any, interval: int = 2) -> bool:
        """循环检测是否已进入大世界，无限等待直到成功。"""
        while True:
            try:
                if runtime.run_pipeline("EnterGame", {}):
                    self._logger.info(LogCategory.MAIN, "已进入大世界")
                    return True
            except Exception as exc:
                self._logger.warning(LogCategory.MAIN, "进入大世界检测异常", error=str(exc))
            time.sleep(interval)


    def _harvest_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        options = params.get("options") or {}
        task_name = options.get("task", "AutoCollect")
        serial = params.get("serial")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return {
                "status": "error",
                "command": "harvest.run",
                "flow": "entity_harvest",
                "task": task_name,
                "options": options,
                "maaend_connected": False,
            }
        ok = self.execute("task.run", {"name": task_name, "options": options, "serial": serial})
        return {
            "status": "success" if ok else "error",
            "command": "harvest.run",
            "flow": "entity_harvest",
            "task": task_name,
            "options": options,
            "maaend_connected": self.connected,
        }

    def _analyze_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        mode = params.get("mode", "default")
        options = params.get("options") or {}
        task_name = options.get("task", "EnvironmentMonitoring")
        serial = params.get("serial")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return {
                "status": "error",
                "command": "analyze.run",
                "mode": mode,
                "task": task_name,
                "options": options,
                "maaend_connected": False,
            }
        ok = self.execute("task.run", {"name": task_name, "options": options, "serial": serial})
        return {
            "status": "success" if ok else "error",
            "command": "analyze.run",
            "mode": mode,
            "task": task_name,
            "options": options,
            "maaend_connected": self.connected,
        }

    def _explore_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        mode = params.get("mode", "default")
        options = params.get("options") or {}
        task_name = options.get("task", "PuzzleSolver")
        serial = params.get("serial")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return {
                "status": "error",
                "command": "explore.run",
                "mode": mode,
                "task": task_name,
                "options": options,
                "maaend_connected": False,
            }
        ok = self.execute("task.run", {"name": task_name, "options": options, "serial": serial})
        return {
            "status": "success" if ok else "error",
            "command": "explore.run",
            "mode": mode,
            "task": task_name,
            "options": options,
            "maaend_connected": self.connected,
        }

    # ------------------------------------------------------------------
    # 全智能分类：材料刷取 / 材料收取
    #
    # 这两个任务采用 Python 编排混合流程（类似 daily.run）：
    #   - MaaFW pipeline 负责 UI 导航 / 传送 / 战斗 / 奖励
    #   - Python 编排器在传送后调用 nav.to_coords_vlm 完成 VLM 步行导航
    #   - LLM 机制已完善（chat_async + 步级超时），单步卡死不会拖垮整条
    #     导航循环，避免用户长时间观感无响应
    # ------------------------------------------------------------------

    # 区域 → 传送场景节点 + VLM 导航目标坐标。
    # 坐标需结合设备端校准；只有 VFTheHub 当前有近似坐标（复用 AutoEssence
    # RegionNodes/VFTheHub.json 的锚点）。其他区域 target=None 表示待校准，
    # 编排器将跳过 VLM 步行、直接进入战斗阶段。
    _MATERIAL_REGION_INFO: Dict[str, Dict[str, Any]] = {
        "VFTheHub": {
            "teleport_node": "SceneEnterWorldValleyIVTheHub1",
            "map_name": "map01_lv001",
            "target": (385.0, 496.0),
            "level_id": "lv001",
        },
        "VFOriginiumSciencePark": {
            "teleport_node": "SceneEnterWorldValleyIVOriginiumSciencePark1",
            "map_name": "map01_lv001",
            "target": None,
            "level_id": "lv001",
        },
        "VFOriginLodespring": {
            "teleport_node": "SceneEnterWorldValleyIVOriginLodespring1",
            "map_name": "map01_lv001",
            "target": None,
            "level_id": "lv001",
        },
        "VFPowerPlateau": {
            "teleport_node": "SceneEnterWorldValleyIVPowerPlateau1",
            "map_name": "map01_lv001",
            "target": None,
            "level_id": "lv001",
        },
        "WLWulingCity": {
            "teleport_node": "SceneEnterWorldWulingWulingCity1",
            "map_name": "map02_lv001",
            "target": None,
            "level_id": "lv001",
        },
        "WLQingboStockade": {
            "teleport_node": "SceneEnterWorldWulingQingboStockade1",
            "map_name": "map02_lv001",
            "target": None,
            "level_id": "lv001",
        },
        "WLMarkerStone": {
            "teleport_node": "SceneEnterWorldWulingMarkerStone1",
            "map_name": "map02_lv001",
            "target": None,
            "level_id": "lv001",
        },
        "WLTestArea": {
            "teleport_node": "SceneEnterWorldWulingTestArea1",
            "map_name": "map02_lv001",
            "target": None,
            "level_id": "lv001",
        },
        "WLSwordVaultDale": {
            "teleport_node": "SceneEnterWorldWulingSwordVaultDale1",
            "map_name": "map02_lv001",
            "target": None,
            "level_id": "lv001",
        },
    }

    # 材料收取路线 → 采集点列表（map_name, x, y, level_id）。
    # 坐标需结合设备端校准；当前全部为 None，编排器将依赖 VLM 读取任务追踪
    # 标识步行，到达后按 F 交互收取。
    _MATERIAL_COLLECT_ROUTES: Dict[str, List[Dict[str, Any]]] = {
        "Route1": [],
        "Route2": [],
        "Route3": [],
        "Route4": [],
        "Route5": [],
    }

    def _material_farm_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """材料刷取编排器：传送 → VLM 步行导航 → 自动战斗 → 奖励领取。"""
        options = params.get("options") or {}
        client_version = options.get("ClientVersion", "CN")
        serial = params.get("serial")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return {
                "status": "error",
                "command": "material.farm",
                "flow": "material_farm",
                "options": options,
                "maaend_connected": False,
            }
        if not self._ensure_game_in_world(runtime, serial, client_version):
            return {
                "status": "error",
                "command": "material.farm",
                "flow": "material_farm",
                "options": options,
                "maaend_connected": self.connected,
                "message": "启动游戏或等待进入大世界失败",
            }

        # 启动 scrcpy 图像通道（默认 wait_first_frame=True，等待首帧就绪）
        # 每次 CLI 调用新建 daemon 进程，需显式启动 scrcpy 供 VLM 步行/MaaFW 截图使用
        try:
            result = self.android(serial).start_scrcpy(serial=serial)
            if isinstance(result, dict) and result.get("error"):
                self._logger.warning(LogCategory.MAIN, "scrcpy 启动失败，VLM 步行/截图将不可用", error=result["error"], serial=serial)
            else:
                self._logger.info(LogCategory.MAIN, "scrcpy 图像通道已就绪", serial=serial)
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "scrcpy 启动异常", error=str(exc), serial=serial)

        # 解析选项
        locations = options.get("MaterialFarmChooseLocation", ["VFTheHub"])
        if isinstance(locations, str):
            locations = [locations]
        if not locations:
            locations = ["VFTheHub"]
        try:
            repeat_count = int(options.get("MaterialFarmRepeatCountValue", 1))
        except (TypeError, ValueError):
            repeat_count = 1
        repeat_count = max(1, min(repeat_count, 199))
        vlm_enabled = options.get("MaterialFarmVlmNavigation", "Yes") != "No"
        try:
            vlm_max_steps = int(options.get("MaterialFarmVlmMaxStepsValue", 40))
        except (TypeError, ValueError):
            vlm_max_steps = 40
        try:
            vlm_step_timeout = float(options.get("MaterialFarmVlmStepTimeoutValue", 30))
        except (TypeError, ValueError):
            vlm_step_timeout = 30.0

        self._logger.info(
            LogCategory.MAIN, "材料刷取开始",
            locations=locations, repeat=repeat_count,
            vlm=vlm_enabled, max_steps=vlm_max_steps, step_timeout=vlm_step_timeout,
        )

        results: List[Dict[str, Any]] = []
        overall_ok = True
        for region in locations:
            info = self._MATERIAL_REGION_INFO.get(region)
            if info is None:
                self._logger.warning(LogCategory.MAIN, "未知材料刷取区域，跳过", region=region)
                results.append({"region": region, "status": "skipped", "reason": "unknown_region"})
                continue
            for attempt in range(repeat_count):
                self._logger.info(
                    LogCategory.MAIN, "材料刷取 region=%s attempt=%d/%d",
                    region, attempt + 1, repeat_count,
                )
                step_status = self._material_farm_once(
                    runtime, region, info, vlm_enabled,
                    vlm_max_steps, vlm_step_timeout, options, serial,
                )
                results.append({
                    "region": region,
                    "attempt": attempt + 1,
                    "status": step_status,
                })
                if step_status != "success":
                    overall_ok = False

        return {
            "status": "success" if overall_ok else "error",
            "command": "material.farm",
            "flow": "material_farm",
            "options": options,
            "results": results,
            "maaend_connected": self.connected,
        }

    def _material_farm_once(
        self,
        runtime: Any,
        region: str,
        info: Dict[str, Any],
        vlm_enabled: bool,
        vlm_max_steps: int,
        vlm_step_timeout: float,
        options: Dict[str, Any],
        serial: Optional[str],
    ) -> str:
        """单次材料刷取：准备 → 传送 → VLM 步行 → 战斗 → 奖励。"""
        # 1. 准备阶段：打开副本标签页、选择材料副本、选中追踪、确认追踪。
        #    TODO[模板校准]: 这些 pipeline 节点尚未配置 OCR/模板识别，暂跳过。
        self._logger.info(LogCategory.MAIN, "材料刷取准备阶段（TODO 模板校准，跳过）", region=region)
        try:
            runtime.run_pipeline("MaterialFarmPrepare", {})
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "MaterialFarmPrepare 异常", error=str(exc))

        # 2. 传送到最近锚点
        teleport_node = info.get("teleport_node")
        if teleport_node:
            self._logger.info(LogCategory.MAIN, "传送到区域锚点", region=region, node=teleport_node)
            try:
                if not runtime.run_pipeline(teleport_node, {}):
                    self._logger.warning(LogCategory.MAIN, "传送失败", region=region)
                    return "teleport_failed"
            except Exception as exc:
                self._logger.error(LogCategory.MAIN, "传送异常", region=region, error=str(exc))
                return "teleport_error"

        # 3. VLM 步行导航：VLM 识别任务追踪标识方向并控制前进
        target = info.get("target")
        if vlm_enabled and target is not None:
            self._logger.info(
                LogCategory.MAIN, "VLM 步行导航开始",
                region=region, map=info.get("map_name"), target=target,
            )
            try:
                walk_result = self.execute(
                    "nav3.walk",
                    {
                        "map_name": info.get("map_name", ""),
                        "x": target[0],
                        "y": target[1],
                        "level_id": info.get("level_id"),
                        "max_steps": vlm_max_steps,
                        "step_timeout": vlm_step_timeout,
                        "serial": serial,
                    },
                )
                if isinstance(walk_result, dict):
                    self._logger.info(
                        LogCategory.MAIN, "VLM 步行导航结束",
                        region=region, status=walk_result.get("status"),
                    )
                else:
                    self._logger.warning(LogCategory.MAIN, "VLM 步行导航无结果", region=region)
            except Exception as exc:
                self._logger.warning(LogCategory.MAIN, "VLM 步行导航异常，继续战斗", region=region, error=str(exc))
        elif vlm_enabled and target is None:
            # 区域无校准坐标：改用任务追踪标识驱动导航（VLM 识别屏幕追踪
            # 标识自主决定方向），不依赖精确坐标即可到达副本入口。
            self._logger.info(
                LogCategory.MAIN, "区域无校准坐标，改用任务追踪标识驱动 VLM 步行",
                region=region,
            )
            try:
                walk_result = self.execute(
                    "nav3.walk_tracking",
                    {
                        "max_steps": vlm_max_steps,
                        "step_timeout": vlm_step_timeout,
                        "serial": serial,
                    },
                )
                if isinstance(walk_result, dict):
                    self._logger.info(
                        LogCategory.MAIN, "VLM 追踪标识步行结束",
                        region=region, status=walk_result.get("status"),
                    )
                else:
                    self._logger.warning(LogCategory.MAIN, "VLM 追踪标识步行无结果", region=region)
            except Exception as exc:
                self._logger.warning(LogCategory.MAIN, "VLM 追踪标识步行异常，继续战斗", region=region, error=str(exc))

        # 4. 战斗阶段：委托 AutoFight 自动战斗
        self._logger.info(LogCategory.MAIN, "进入战斗阶段", region=region)
        try:
            if not runtime.run_pipeline("AutoFight", {}):
                self._logger.warning(LogCategory.MAIN, "AutoFight 执行失败", region=region)
                return "combat_failed"
        except Exception as exc:
            self._logger.error(LogCategory.MAIN, "AutoFight 异常", region=region, error=str(exc))
            return "combat_error"

        # 5. 奖励领取：TODO[模板校准] 战斗结算面板识别与领取按钮模板
        self._logger.info(LogCategory.MAIN, "奖励领取阶段（TODO 模板校准）", region=region)
        try:
            runtime.run_pipeline("MaterialFarmRewards", {})
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "MaterialFarmRewards 异常", error=str(exc))

        return "success"

    def _material_collect_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """材料收取编排器：VLM 导航到采集点 → 交互收取 → 领取奖励。

        使用 VLM 优化导航稳定性与准确性：每一步通过 chat_async + 步级超时
        决策，单步推理卡死不会拖垮整条路线。
        """
        options = params.get("options") or {}
        client_version = options.get("ClientVersion", "CN")
        serial = params.get("serial")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return {
                "status": "error",
                "command": "material.collect",
                "flow": "material_collect",
                "options": options,
                "maaend_connected": False,
            }
        if not self._ensure_game_in_world(runtime, serial, client_version):
            return {
                "status": "error",
                "command": "material.collect",
                "flow": "material_collect",
                "options": options,
                "maaend_connected": self.connected,
                "message": "启动游戏或等待进入大世界失败",
            }

        # 启动 scrcpy 图像通道（默认 wait_first_frame=True，等待首帧就绪）
        # 每次 CLI 调用新建 daemon 进程，需显式启动 scrcpy 供 VLM 步行/MaaFW 截图使用
        try:
            result = self.android(serial).start_scrcpy(serial=serial)
            if isinstance(result, dict) and result.get("error"):
                self._logger.warning(LogCategory.MAIN, "scrcpy 启动失败，VLM 步行/截图将不可用", error=result["error"], serial=serial)
            else:
                self._logger.info(LogCategory.MAIN, "scrcpy 图像通道已就绪", serial=serial)
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "scrcpy 启动异常", error=str(exc), serial=serial)

        routes = options.get("MaterialCollectRoute", ["Route1"])
        if isinstance(routes, str):
            routes = [routes]
        if not routes:
            routes = ["Route1"]
        try:
            vlm_max_steps = int(options.get("MaterialCollectVlmMaxStepsValue", 40))
        except (TypeError, ValueError):
            vlm_max_steps = 40
        try:
            vlm_step_timeout = float(options.get("MaterialCollectVlmStepTimeoutValue", 30))
        except (TypeError, ValueError):
            vlm_step_timeout = 30.0
        try:
            arrived_radius = float(options.get("MaterialCollectArrivedRadiusValue", 10))
        except (TypeError, ValueError):
            arrived_radius = 10.0

        self._logger.info(
            LogCategory.MAIN, "材料收取开始",
            routes=routes, max_steps=vlm_max_steps,
            step_timeout=vlm_step_timeout, arrived_radius=arrived_radius,
        )

        results: List[Dict[str, Any]] = []
        overall_ok = True
        for route in routes:
            points = self._MATERIAL_COLLECT_ROUTES.get(route, [])
            self._logger.info(
                LogCategory.MAIN, "材料收取路线", route=route, points=len(points),
            )
            if not points:
                # 路线无校准坐标：改用任务追踪标识驱动 VLM 步行到采集点
                self._logger.info(
                    LogCategory.MAIN, "路线无校准坐标，改用任务追踪标识驱动 VLM 步行",
                    route=route,
                )
                point_ok = True
                try:
                    walk_result = self.execute(
                        "nav3.walk_tracking",
                        {
                            "max_steps": vlm_max_steps,
                            "step_timeout": vlm_step_timeout,
                            "serial": serial,
                        },
                    )
                    if not (isinstance(walk_result, dict) and walk_result.get("status") == "success"):
                        self._logger.warning(
                            LogCategory.MAIN, "VLM 追踪步行未到达采集点",
                            route=route,
                        )
                        point_ok = False
                except Exception as exc:
                    self._logger.error(
                        LogCategory.MAIN, "VLM 追踪步行异常",
                        route=route, error=str(exc),
                    )
                    point_ok = False
                if point_ok:
                    # 交互收取：按 F
                    try:
                        self.android(serial).keyevent("KEYCODE_F")
                        time.sleep(1.0)
                    except Exception as exc:
                        self._logger.warning(LogCategory.MAIN, "交互收取异常", error=str(exc))
                    # 领取/确认面板
                    try:
                        runtime.run_pipeline("MaterialCollectClaim", {})
                    except Exception as exc:
                        self._logger.warning(LogCategory.MAIN, "MaterialCollectClaim 异常", error=str(exc))
                results.append({
                    "route": route,
                    "status": "success" if point_ok else "partial",
                    "points": 0,
                })
                if not point_ok:
                    overall_ok = False
                continue
            route_ok = True
            for idx, point in enumerate(points):
                self._logger.info(
                    LogCategory.MAIN, "材料收取 route=%s point=%d/%d",
                    route, idx + 1, len(points),
                )
                # VLM 步行到采集点
                try:
                    walk_result = self.execute(
                        "nav3.walk",
                        {
                            "map_name": point.get("map_name", ""),
                            "x": float(point.get("x", 0)),
                            "y": float(point.get("y", 0)),
                            "level_id": point.get("level_id"),
                            "max_steps": vlm_max_steps,
                            "step_timeout": vlm_step_timeout,
                            "target_radius": arrived_radius,
                            "serial": serial,
                        },
                    )
                    if not (isinstance(walk_result, dict) and walk_result.get("status") == "success"):
                        self._logger.warning(
                            LogCategory.MAIN, "VLM 步行未到达采集点",
                            route=route, point=idx + 1,
                        )
                        route_ok = False
                        continue
                except Exception as exc:
                    self._logger.error(
                        LogCategory.MAIN, "VLM 步行异常",
                        route=route, point=idx + 1, error=str(exc),
                    )
                    route_ok = False
                    continue
                # 交互收取：按 F
                try:
                    self.android(serial).keyevent("KEYCODE_F")
                    time.sleep(1.0)
                except Exception as exc:
                    self._logger.warning(LogCategory.MAIN, "交互收取异常", error=str(exc))
                # 领取/确认面板
                try:
                    runtime.run_pipeline("MaterialCollectClaim", {})
                except Exception as exc:
                    self._logger.warning(LogCategory.MAIN, "MaterialCollectClaim 异常", error=str(exc))
            results.append({
                "route": route,
                "status": "success" if route_ok else "partial",
                "points": len(points),
            })
            if not route_ok:
                overall_ok = False

        return {
            "status": "success" if overall_ok else "error",
            "command": "material.collect",
            "flow": "material_collect",
            "options": options,
            "results": results,
            "maaend_connected": self.connected,
        }

    def _is_task_list_page(self, serial: Optional[str]) -> bool:
        """检查当前画面是否为任务列表页（左上角出现 '//任务' 标题）。"""
        ocr_check = self.execute(
            "scene.elements",
            {
                "serial": serial,
                "enable_ocr": True,
                "enable_template": False,
                "enable_color": False,
            },
        )
        check_elements = []
        if isinstance(ocr_check, dict) and ocr_check.get("status") == "success":
            check_elements = ocr_check.get("elements", [])
        check_text = "".join(
            e.get("label", "") for e in check_elements if isinstance(e, dict)
        )
        return "//任务" in check_text

    def _read_task_list_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """读取全部任务列表编排器：主世界点击任务图标 → OCR 整页 → 格式化缓存。

        全智能分类任务：确保游戏在主世界后，直接点击 Baker/TaskOptions.png
        任务列表图标（主世界页面上的任务入口，非 Baker 内部的页签切换），
        OCR 整页识别任务文本，按阅读顺序格式化并缓存到 cache/task_list/。
        """
        options = params.get("options") or {}
        client_version = options.get("ClientVersion", "CN")
        serial = params.get("serial")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return {
                "status": "error",
                "command": "readtask.run",
                "flow": "read_task_list",
                "options": options,
                "maaend_connected": False,
            }

        # 若已在任务列表页，直接读取；否则确保在大世界
        if not self._is_task_list_page(serial):
            # 快速检测是否已在大世界，避免重复执行耗时的 AndroidOpenGame
            try:
                already_in_world = runtime.run_pipeline("InWorld", {})
            except Exception:
                already_in_world = False
            if not already_in_world and not self._ensure_game_in_world(runtime, serial, client_version):
                return {
                    "status": "error",
                    "command": "readtask.run",
                    "flow": "read_task_list",
                    "options": options,
                    "maaend_connected": self.connected,
                    "message": "启动游戏或等待进入大世界失败",
                }

        # 解析选项
        try:
            ocr_confidence = float(options.get("ReadAllTasksOcrConfidenceValue", 0.3))
        except (TypeError, ValueError):
            ocr_confidence = 0.3
        save_screenshot = options.get("ReadAllTasksSaveScreenshot", "Yes") != "No"
        try:
            dedup_distance = float(options.get("ReadAllTasksDedupDistanceValue", 0.02))
        except (TypeError, ValueError):
            dedup_distance = 0.02

        self._logger.info(
            LogCategory.MAIN, "读取全部任务列表开始",
            ocr_confidence=ocr_confidence, save_screenshot=save_screenshot,
            dedup_distance=dedup_distance,
        )

        steps: List[Dict[str, Any]] = []

        # 1. 在主世界页面直接点击任务列表图标（Baker/TaskOptions.png）
        # 注意：TaskOptions.png 是主世界页面上的任务入口图标，不是 Baker 内部的页签切换。
        # 不进入 Baker 界面，直接在主世界全屏匹配并点击。
        self._logger.info(LogCategory.MAIN, "点击主世界任务列表图标")
        click_ok = False
        for attempt in range(3):
            try:
                ok = runtime.run_pipeline("ReadTaskListClickTaskIcon", {})
                if ok:
                    click_ok = True
                    steps.append({"step": "click_task_icon", "status": "success", "attempt": attempt + 1})
                    break
                self._logger.warning(LogCategory.MAIN, "点击任务列表图标失败", attempt=attempt + 1)
            except Exception as exc:
                self._logger.error(LogCategory.MAIN, "点击任务列表图标异常", error=str(exc), attempt=attempt + 1)
            if attempt < 2:
                time.sleep(2.0)

        # 1.5 模板匹配失败时使用已知坐标兜底点击
        # 经实际屏幕扫描验证，任务列表入口按钮位于主世界左上角小地图左下角，
        # 在 1280x720 分辨率下坐标约为 (35, 155)。
        if not click_ok:
            self._logger.warning(LogCategory.MAIN, "模板匹配点击失败，使用固定坐标兜底点击任务图标")
            try:
                android = self.android(serial)
                android.tap(35, 155)
                time.sleep(1.5)
                click_ok = True
                steps.append({"step": "click_task_icon", "status": "success", "attempt": "fallback_coord"})
            except Exception as exc:
                self._logger.error(LogCategory.MAIN, "兜底点击任务图标异常", error=str(exc))

        if not click_ok:
            steps.append({"step": "click_task_icon", "status": "failed"})

        # 2. 等待任务列表页稳定
        time.sleep(2.0)

        # 2.5 页面校验：任务列表页必须有 "//任务" 标题，否则重试一次点击
        if not self._is_task_list_page(serial):
            self._logger.warning(LogCategory.MAIN, "首次点击后未识别到任务列表标题，重试一次")
            time.sleep(1.0)
            ok_retry = runtime.run_pipeline("ReadTaskListClickTaskIcon", {})
            if ok_retry:
                click_ok = True
                steps.append({"step": "click_task_icon", "status": "success", "attempt": "retry"})
            time.sleep(2.0)
            if not self._is_task_list_page(serial):
                self._logger.error(LogCategory.MAIN, "重试后仍未进入任务列表页，放弃读取")
                return {
                    "status": "error",
                    "command": "readtask.run",
                    "flow": "read_task_list",
                    "options": options,
                    "message": "未能进入任务列表页",
                    "steps": steps,
                    "maaend_connected": self.connected,
                }

        # 3. 滚动读取任务列表
        self._logger.info(LogCategory.MAIN, "开始滚动读取任务列表")
        android = self.android(serial)
        # 任务列表滚动区域：左侧面板（列表可滚动区域）
        scroll_region = [80, 160, 420, 520]
        swipe_distance = 280

        page_result = self._read_task_list_page(
            android, serial, scroll_region=scroll_region, swipe_distance=swipe_distance,
            wait_seconds=0.5, ocr_confidence=ocr_confidence, dedup_distance=dedup_distance
        )
        all_elements = page_result["all_elements"]
        formatted = page_result["formatted"]
        steps.extend(page_result["steps"])

        # 4. 缓存格式化结果 + 可选保存截图
        cache_path = self._cache_task_list(formatted, all_elements, serial, save_screenshot, serial_param=serial)
        steps.append({"step": "cache", "status": "success", "path": str(cache_path)})

        self._logger.info(
            LogCategory.MAIN, "读取全部任务列表完成",
            raw_count=len(all_elements), line_count=len(formatted["lines"]),
            cache_path=str(cache_path),
        )

        return {
            "status": "success",
            "command": "readtask.run",
            "flow": "read_task_list",
            "options": options,
            "raw_ocr_count": len(all_elements),
            "formatted_line_count": len(formatted["lines"]),
            "formatted_lines": formatted["lines"],
            "cache_path": str(cache_path),
            "steps": steps,
            "maaend_connected": self.connected,
        }

    @staticmethod
    def _deduplicate_task_list_elements_by_label(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """滚动读取时同一任务文本可能出现在多屏，按标签文本去重并保留置信度最高者。"""
        best: Dict[str, Dict[str, Any]] = {}
        for elem in elements:
            label = str(elem.get("label", "")).strip()
            if not label:
                continue
            conf = float(elem.get("confidence", 0.5))
            if label not in best or conf > float(best[label].get("confidence", 0.5)):
                best[label] = elem
        return list(best.values())

    @staticmethod
    def _is_task_list_ocr_noise(label: str) -> bool:
        """过滤任务列表 OCR 中由图标、UI 元素产生的噪声文本。"""
        import re
        text = str(label).strip()
        if not text:
            return True
        # 已知噪声模式：UID、延迟、纯图标符号
        if re.search(r"UID|ms$|^[\s]*$", text):
            return True
        # 单字符噪声（除 CJK 汉字外）
        if len(text) == 1 and not re.search(r"[\u4e00-\u9fff]", text):
            return True
        # 纯感叹号/点/特殊符号组合（任务优先级图标）
        if re.fullmatch(r"[!\.\×xXQq口日○〇]+", text):
            return True
        # 单个数字或纯短数字串（通常是图标而非任务名）——保留 3 位以上数字（如 738）
        if re.fullmatch(r"\d{1,2}", text):
            return True
        return False

    @staticmethod
    def _format_task_list_ocr(
        elements: List[Dict[str, Any]], dedup_distance: float = 0.02,
    ) -> Dict[str, Any]:
        """将 OCR 元素列表格式化为按阅读顺序排列的文本行。

        格式化策略：
        1. 过滤空标签与图标噪声
        2. 按位置去重：中心点距离小于 dedup_distance（归一化坐标）的同标签元素只保留置信度最高的
        3. 按阅读顺序排序：先按 y 分行（行容差 0.04），行内按 x 排序
        4. 同行元素用空格连接为一条文本行
        """
        # 过滤空标签与噪声
        candidates = [
            e for e in elements
            if e.get("label")
            and str(e["label"]).strip()
            and not IstinaRuntime._is_task_list_ocr_noise(str(e["label"]))
        ]
        # 去重：同标签 + 位置相近 → 保留置信度最高
        deduped: List[Dict[str, Any]] = []
        for elem in candidates:
            center = elem.get("center") or [0.5, 0.5]
            cx, cy = float(center[0]), float(center[1])
            label = str(elem["label"]).strip()
            conf = float(elem.get("confidence", 0.5))
            replaced = False
            for existing in deduped:
                ec = existing.get("center") or [0.5, 0.5]
                if (
                    str(existing["label"]).strip() == label
                    and abs(cx - float(ec[0])) < dedup_distance
                    and abs(cy - float(ec[1])) < dedup_distance
                ):
                    if conf > float(existing.get("confidence", 0.5)):
                        deduped.remove(existing)
                        deduped.append(elem)
                    replaced = True
                    break
            if not replaced:
                deduped.append(elem)

        # 按阅读顺序排序：y 分行（容差 0.04），行内按 x
        row_tolerance = 0.04
        sorted_elems = sorted(deduped, key=lambda e: (float((e.get("center") or [0.5, 0.5])[1]), float((e.get("center") or [0.5, 0.5])[0])))
        rows: List[List[Dict[str, Any]]] = []
        for elem in sorted_elems:
            cy = float((elem.get("center") or [0.5, 0.5])[1])
            placed = False
            for row in rows:
                row_y = float((row[0].get("center") or [0.5, 0.5])[1])
                if abs(cy - row_y) < row_tolerance:
                    row.append(elem)
                    placed = True
                    break
            if not placed:
                rows.append([elem])

        lines: List[str] = []
        for row in rows:
            row_sorted = sorted(row, key=lambda e: float((e.get("center") or [0.5, 0.5])[0]))
            line_text = "  ".join(str(e["label"]).strip() for e in row_sorted)
            lines.append(line_text)

        return {
            "lines": lines,
            "element_count": len(deduped),
            "row_count": len(rows),
        }

    def _cache_task_list(
        self,
        formatted: Dict[str, Any],
        raw_elements: List[Dict[str, Any]],
        serial: Optional[str],
        save_screenshot: bool,
        serial_param: Optional[str] = None,
    ) -> Path:
        """将格式化后的任务列表缓存到 cache/task_list/ 目录。

        写入 task_list_cache.json（最新快照）+ task_list_<timestamp>.json（历史归档）。
        若 save_screenshot=True，额外保存当前截图到同目录。
        """
        from datetime import datetime
        cache_dir = get_cache_subdir("task_list")
        cache_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        ts_file = datetime.now().strftime("%Y%m%d_%H%M%S")

        cache_data = {
            "timestamp": timestamp,
            "task": "ReadAllTasks",
            "status": "success",
            "serial": serial,
            "element_count": formatted["element_count"],
            "row_count": formatted["row_count"],
            "formatted_lines": formatted["lines"],
            "raw_elements": raw_elements,
        }

        latest_path = cache_dir / "task_list_cache.json"
        latest_path.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8")

        history_path = cache_dir / f"task_list_{ts_file}.json"
        history_path.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8")

        if save_screenshot:
            try:
                image_bytes = self.execute("screenshot", {"serial": serial_param})
                if image_bytes:
                    shot_path = cache_dir / f"task_list_{ts_file}.png"
                    shot_path.write_bytes(image_bytes)
            except Exception as exc:
                self._logger.warning(LogCategory.MAIN, "保存任务列表截图失败", error=str(exc))

        return latest_path

    # ------------------------------------------------------------------
    # 分类任务自动执行（全智能·任务执行）
    # ------------------------------------------------------------------

    # 游戏内任务列表左侧分类标签（顺序与游戏内一致）
    _CATEGORY_NAMES: Tuple[str, ...] = ("进行中", "ALL", "紧要", "重要", "次要")
    # 分类标签兜底坐标（1280x720，仅"次要"经扫描验证；其余依赖 OCR 动态检测）
    _CATEGORY_COORD_FALLBACK: Dict[str, Tuple[int, int]] = {"次要": (40, 285)}
    # 任务列表页右上角关闭按钮坐标
    _TASK_LIST_CLOSE_COORD: Tuple[int, int] = (1225, 35)
    # 主世界任务列表入口图标兜底坐标
    _TASK_LIST_ICON_COORD: Tuple[int, int] = (35, 155)

    # 任务列表 OCR 中属于 UI 控件而非任务名的文本集合
    _TASK_LIST_UI_LABELS: frozenset = frozenset({
        "//任务", "进行中", "ALL", "紧要", "重要", "次要", "区",
        "X", "×", "开始追踪", "停止追踪", "UID", "ms", "口",
    })

    def _run_category_tasks(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """逐一执行指定分类（默认次要）的任务，执行过程中频繁检查任务列表确认完成。

        全智能·任务执行编排器。流程：
        1. 确保进入任务列表页；
        2. 若提供 selected_tasks：仅执行选中任务；否则点击目标分类标签并读取该分类全部任务；
        3. 对每个任务：切到所属分类 -> 追踪 -> 关闭任务列表 -> VLM 追踪标识导航 ->
           交互/完成 -> 重新打开任务列表并确认该任务已从该分类列表中消失；
        4. 返回成功/失败任务清单。

        选项：
        - category: 目标分类（默认"次要"），当未提供 selected_tasks 时使用
        - selected_tasks: [{"category","name","center"}] 仅执行这些任务（覆盖 category 全量）
        - BlueTaskVlmMaxStepsValue / BlueTaskVlmStepTimeoutValue / BlueTaskMaxVerifyChecks
        """
        options = params.get("options") or {}
        client_version = options.get("ClientVersion", "CN")
        serial = params.get("serial")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return {
                "status": "error",
                "command": "readtask.run_category",
                "flow": "run_category_tasks",
                "options": options,
                "maaend_connected": False,
            }

        # 分类：复选框选项 TaskExecuteCategory（list）→ category 字段 → 默认"次要"
        cat_opt = options.get("TaskExecuteCategory")
        if isinstance(cat_opt, list):
            category = cat_opt[0] if cat_opt else "次要"
        elif cat_opt:
            category = str(cat_opt)
        else:
            category = str(options.get("category", "次要")) or "次要"
        selected_tasks = options.get("selected_tasks")
        # 解析选项（TaskExecute* 为主，BlueTask* 兼容旧 run_blue 调用）
        try:
            vlm_max_steps = int(options.get("TaskExecuteVlmMaxStepsValue", options.get("BlueTaskVlmMaxStepsValue", 60)))
        except (TypeError, ValueError):
            vlm_max_steps = 60
        try:
            vlm_step_timeout = float(options.get("TaskExecuteVlmStepTimeoutValue", options.get("BlueTaskVlmStepTimeoutValue", 30)))
        except (TypeError, ValueError):
            vlm_step_timeout = 30.0
        try:
            max_verification_checks = int(options.get("TaskExecuteMaxVerifyChecksValue", options.get("BlueTaskMaxVerifyChecks", 5)))
        except (TypeError, ValueError):
            max_verification_checks = 5

        self._logger.info(
            LogCategory.MAIN, "开始执行分类任务",
            category=category, selected=len(selected_tasks) if selected_tasks else 0,
            vlm_max_steps=vlm_max_steps, vlm_step_timeout=vlm_step_timeout,
            max_verification_checks=max_verification_checks,
        )

        # 启动 LLM（VLM 导航依赖 llama-server）
        try:
            if not self.warmup_llm():
                return {
                    "status": "error",
                    "command": "readtask.run_category",
                    "flow": "run_category_tasks",
                    "options": options,
                    "message": "LLM 启动失败，无法执行 VLM 任务",
                    "maaend_connected": self.connected,
                }
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "启动 LLM 异常", error=str(exc))

        # 1. 打开任务列表页（若尚未打开）
        open_result = self._open_task_list_if_needed(runtime, serial, client_version)
        if open_result.get("status") != "success":
            return {
                "status": "error",
                "command": "readtask.run_category",
                "flow": "run_category_tasks",
                "options": options,
                "message": open_result.get("message", "打开任务列表页失败"),
                "maaend_connected": self.connected,
            }

        android = self.android(serial)
        scroll_region = [80, 160, 420, 520]

        # 2. 确定要执行的任务清单
        if selected_tasks:
            tasks_to_run: List[Dict[str, Any]] = []
            for t in selected_tasks:
                if isinstance(t, dict) and t.get("name"):
                    tasks_to_run.append({
                        "name": str(t["name"]).strip(),
                        "category": str(t.get("category", category)) or category,
                        "center": t.get("center"),
                    })
        else:
            # 点击目标分类标签并读取该分类全部任务
            self._click_category_by_name(android, serial, category)
            time.sleep(1.5)
            cat_page = self._read_task_list_page(
                android, serial, scroll_region=scroll_region, swipe_distance=280,
                wait_seconds=0.5, ocr_confidence=0.3, dedup_distance=0.02,
            )
            cat_tasks = self._extract_category_tasks(
                cat_page["all_elements"], cat_page["formatted"].get("lines", []),
            )
            tasks_to_run = [
                {"name": t["name"], "category": category, "center": t.get("center")}
                for t in cat_tasks
            ]

        self._logger.info(
            LogCategory.MAIN, "识别到分类任务",
            count=len(tasks_to_run), category=category,
            tasks=[t["name"] for t in tasks_to_run],
        )

        if not tasks_to_run:
            return {
                "status": "success",
                "command": "readtask.run_category",
                "flow": "run_category_tasks",
                "options": options,
                "completed_tasks": [],
                "failed_tasks": [],
                "message": f"当前无 {category} 分类任务",
                "maaend_connected": self.connected,
            }

        # 3. 逐一执行
        completed: List[str] = []
        failed: List[str] = []
        for idx, task in enumerate(tasks_to_run):
            task_name = task["name"]
            self._logger.info(
                LogCategory.MAIN, "执行分类任务",
                index=idx + 1, total=len(tasks_to_run), task=task_name, category=task.get("category"),
            )
            exec_result = self._execute_category_task(
                runtime, android, serial, task,
                vlm_max_steps=vlm_max_steps,
                vlm_step_timeout=vlm_step_timeout,
                max_verification_checks=max_verification_checks,
            )
            if exec_result.get("status") == "success":
                completed.append(task_name)
                self._logger.info(LogCategory.MAIN, "分类任务完成", task=task_name)
            else:
                failed.append(task_name)
                self._logger.warning(LogCategory.MAIN, "分类任务失败", task=task_name, reason=exec_result.get("message"))

        self._logger.info(
            LogCategory.MAIN, "分类任务执行结束",
            category=category, completed=len(completed), failed=len(failed),
        )

        return {
            "status": "success" if not failed else "partial",
            "command": "readtask.run_category",
            "flow": "run_category_tasks",
            "options": options,
            "category": category,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "maaend_connected": self.connected,
        }

    def _list_blue_tasks(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """仅读取蓝色（次要）分类任务列表，不执行。"""
        options = params.get("options") or {}
        client_version = options.get("ClientVersion", "CN")
        serial = params.get("serial")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return {
                "status": "error",
                "command": "readtask.list_blue",
                "flow": "list_blue_tasks",
                "options": options,
                "maaend_connected": False,
            }

        open_result = self._open_task_list_if_needed(runtime, serial, client_version)
        if open_result.get("status") != "success":
            return {
                "status": "error",
                "command": "readtask.list_blue",
                "flow": "list_blue_tasks",
                "options": options,
                "message": open_result.get("message", "打开任务列表页失败"),
                "maaend_connected": self.connected,
            }

        android = self.android(serial)
        self._click_category_by_name(android, serial, "次要")
        time.sleep(1.5)

        page = self._read_task_list_page(
            android, serial, scroll_region=[80, 160, 420, 520], swipe_distance=280,
            wait_seconds=0.5, ocr_confidence=0.3, dedup_distance=0.02,
        )
        blue_tasks = self._extract_category_tasks(page["all_elements"], page["formatted"].get("lines", []))

        return {
            "status": "success",
            "command": "readtask.list_blue",
            "flow": "list_blue_tasks",
            "options": options,
            "blue_tasks": [t["name"] for t in blue_tasks],
            "blue_task_details": blue_tasks,
            "maaend_connected": self.connected,
        }

    def _list_categorized_tasks(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """读取所有分类的任务列表（不执行），返回 {categories: [{name, tasks: [...]}]}。

        供 GUI 按游戏内分类分组展示并供用户勾选。顺序与游戏内左侧分类标签一致。
        """
        options = params.get("options") or {}
        client_version = options.get("ClientVersion", "CN")
        serial = params.get("serial")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return {
                "status": "error",
                "command": "readtask.list_categorized",
                "flow": "list_categorized_tasks",
                "options": options,
                "maaend_connected": False,
            }

        open_result = self._open_task_list_if_needed(runtime, serial, client_version)
        if open_result.get("status") != "success":
            return {
                "status": "error",
                "command": "readtask.list_categorized",
                "flow": "list_categorized_tasks",
                "options": options,
                "message": open_result.get("message", "打开任务列表页失败"),
                "maaend_connected": self.connected,
            }

        android = self.android(serial)
        scroll_region = [80, 160, 420, 520]
        categories: List[Dict[str, Any]] = []
        for cat in self._CATEGORY_NAMES:
            self._click_category_by_name(android, serial, cat)
            time.sleep(1.2)
            page = self._read_task_list_page(
                android, serial, scroll_region=scroll_region, swipe_distance=280,
                wait_seconds=0.5, ocr_confidence=0.3, dedup_distance=0.02,
            )
            cat_tasks = self._extract_category_tasks(
                page["all_elements"], page["formatted"].get("lines", []),
            )
            categories.append({
                "name": cat,
                "tasks": [{"name": t["name"], "center": t.get("center")} for t in cat_tasks],
            })
            self._logger.info(LogCategory.MAIN, "读取分类任务列表", category=cat, count=len(cat_tasks))

        return {
            "status": "success",
            "command": "readtask.list_categorized",
            "flow": "list_categorized_tasks",
            "options": options,
            "categories": categories,
            "maaend_connected": self.connected,
        }

    def _open_task_list_if_needed(
        self,
        runtime: Any,
        serial: Optional[str],
        client_version: str,
    ) -> Dict[str, Any]:
        """若当前不在任务列表页，则返回大世界并点击任务列表入口。"""
        if self._is_task_list_page(serial):
            return {"status": "success", "step": "already_on_task_list"}

        # 快速检测是否已在大世界，避免重复执行耗时的 AndroidOpenGame
        try:
            already_in_world = runtime.run_pipeline("InWorld", {})
        except Exception:
            already_in_world = False
        if not already_in_world and not self._ensure_game_in_world(runtime, serial, client_version):
            return {"status": "error", "message": "启动游戏或等待进入大世界失败"}

        android = self.android(serial)
        click_ok = False
        for attempt in range(3):
            try:
                ok = runtime.run_pipeline("ReadTaskListClickTaskIcon", {})
                if ok:
                    click_ok = True
                    break
            except Exception as exc:
                self._logger.warning(LogCategory.MAIN, "打开任务列表图标失败", attempt=attempt + 1, error=str(exc))
            if attempt < 2:
                time.sleep(2.0)
        if not click_ok:
            try:
                android.tap(self._TASK_LIST_ICON_COORD[0], self._TASK_LIST_ICON_COORD[1])
                time.sleep(1.5)
                click_ok = True
            except Exception as exc:
                self._logger.error(LogCategory.MAIN, "兜底点击任务图标异常", error=str(exc))
        if not click_ok:
            return {"status": "error", "message": "点击任务列表入口失败"}

        time.sleep(2.0)
        if not self._is_task_list_page(serial):
            # 重试一次
            try:
                runtime.run_pipeline("ReadTaskListClickTaskIcon", {})
            except Exception:
                pass
            time.sleep(2.0)
            if not self._is_task_list_page(serial):
                return {"status": "error", "message": "未能进入任务列表页"}
        return {"status": "success", "step": "opened_task_list"}

    def _close_task_list(self, android: Any) -> None:
        """点击任务列表页右上角关闭按钮。"""
        try:
            android.tap(self._TASK_LIST_CLOSE_COORD[0], self._TASK_LIST_CLOSE_COORD[1])
            time.sleep(1.0)
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "关闭任务列表异常", error=str(exc))

    def _click_task_list_category(self, android: Any, coord: Tuple[int, int]) -> None:
        """点击任务列表左侧分类标签。"""
        self._logger.info(LogCategory.MAIN, "点击任务列表分类标签", coord=coord)
        try:
            android.tap(coord[0], coord[1])
            time.sleep(0.5)
        except Exception as exc:
            self._logger.error(LogCategory.MAIN, "点击分类标签异常", error=str(exc))

    def _click_category_by_name(
        self, android: Any, serial: Optional[str], category_name: str,
    ) -> bool:
        """点击任务列表左侧分类标签：优先 OCR 检测标签位置，失败则用兜底坐标。

        分类标签位于左侧栏（归一化 x < 0.12），通过 OCR 匹配标签文本定位。
        仅"次要"有经扫描验证的兜底坐标；其余分类依赖 OCR 检测。
        """
        # OCR 检测左侧栏分类标签
        try:
            ocr_result = self.execute(
                "scene.elements",
                {"serial": serial, "enable_ocr": True, "enable_template": False, "enable_color": False},
            )
            if isinstance(ocr_result, dict) and ocr_result.get("status") == "success":
                screen_size = self._get_screen_size(serial)
                for elem in ocr_result.get("elements", []):
                    label = str(elem.get("label", "")).strip()
                    if label == category_name:
                        center = elem.get("center") or [0.5, 0.5]
                        if float(center[0]) < 0.12:  # 左侧栏
                            x, y = self._norm_to_screen(center, screen_size)
                            self._logger.info(
                                LogCategory.MAIN, "OCR 检测到分类标签",
                                category=category_name, coord=(x, y),
                            )
                            android.tap(x, y)
                            time.sleep(0.5)
                            return True
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "OCR 检测分类标签异常", category=category_name, error=str(exc))

        # 兜底坐标
        coord = self._CATEGORY_COORD_FALLBACK.get(category_name)
        if coord:
            self._logger.info(LogCategory.MAIN, "使用兜底坐标点击分类标签", category=category_name, coord=coord)
            try:
                android.tap(coord[0], coord[1])
                time.sleep(0.5)
                return True
            except Exception as exc:
                self._logger.error(LogCategory.MAIN, "兜底点击分类标签异常", error=str(exc))
                return False
        self._logger.warning(LogCategory.MAIN, "未能定位分类标签", category=category_name)
        return False

    def _find_task_coord_by_name(
        self, android: Any, serial: Optional[str], task_name: str,
    ) -> Optional[Tuple[int, int]]:
        """在当前任务列表页 OCR 查找任务条目，返回其屏幕坐标，未找到返回 None。"""
        try:
            page = self._read_task_list_page(
                android, serial, scroll_region=[80, 160, 420, 520], swipe_distance=280,
                wait_seconds=0.5, ocr_confidence=0.3, dedup_distance=0.02,
            )
            tasks = self._extract_category_tasks(
                page["all_elements"], page["formatted"].get("lines", []),
            )
            for t in tasks:
                if t["name"] == task_name:
                    screen_size = self._get_screen_size(serial)
                    return self._norm_to_screen(t.get("center", [0.5, 0.5]), screen_size)
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "OCR 查找任务条目异常", task=task_name, error=str(exc))
        return None

    def _get_screen_size(self, serial: Optional[str]) -> Tuple[int, int]:
        """获取设备屏幕分辨率，失败时默认 1280x720。"""
        try:
            data = self.execute("screenshot", {"serial": serial})
            if data:
                arr = np.frombuffer(data, np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is not None:
                    return int(img.shape[1]), int(img.shape[0])
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "获取屏幕分辨率失败", error=str(exc))
        return 1280, 720

    def _norm_to_screen(
        self,
        center: List[float],
        screen_size: Tuple[int, int],
    ) -> Tuple[int, int]:
        """将归一化 OCR 中心坐标转换为屏幕坐标。"""
        w, h = screen_size
        cx = float(center[0]) if center else 0.5
        cy = float(center[1]) if len(center) > 1 else 0.5
        return int(round(cx * w)), int(round(cy * h))

    def _extract_category_tasks(
        self,
        elements: List[Dict[str, Any]],
        formatted_lines: List[str],
    ) -> List[Dict[str, Any]]:
        """从分类任务列表 OCR 结果中提取任务条目（含点击坐标）。

        适用于任意分类（进行中/ALL/紧要/重要/次要）。策略：
        - 过滤已知 UI 标签与噪声；
        - 按行分组后，取每行最左侧且非区域/前缀描述的任务名元素作为点击目标。
        """
        import re

        # 1. 过滤候选元素
        candidates: List[Dict[str, Any]] = []
        for elem in elements:
            label = str(elem.get("label", "")).strip()
            if not label or self._is_task_list_ocr_noise(label):
                continue
            if label in self._TASK_LIST_UI_LABELS:
                continue
            # 排除纯数字、纯英文缩写等噪声
            if re.fullmatch(r"\d+", label) and len(label) <= 3:
                continue
            candidates.append(elem)

        # 2. 按 y 坐标分组（行容差 0.04）
        row_tolerance = 0.04
        sorted_candidates = sorted(
            candidates,
            key=lambda e: (float((e.get("center") or [0.5, 0.5])[1]), float((e.get("center") or [0.5, 0.5])[0])),
        )
        rows: List[List[Dict[str, Any]]] = []
        for elem in sorted_candidates:
            cy = float((elem.get("center") or [0.5, 0.5])[1])
            placed = False
            for row in rows:
                row_y = float((row[0].get("center") or [0.5, 0.5])[1])
                if abs(cy - row_y) < row_tolerance:
                    row.append(elem)
                    placed = True
                    break
            if not placed:
                rows.append([elem])

        # 3. 从每行提取任务名：优先使用 formatted_lines 中匹配的行文本，
        #    点击坐标取该行最左侧元素中心。
        tasks: List[Dict[str, Any]] = []
        used_lines: set = set()
        for row in rows:
            row_sorted = sorted(row, key=lambda e: float((e.get("center") or [0.5, 0.5])[0]))
            row_text = "  ".join(str(e.get("label", "")).strip() for e in row_sorted)
            # 与 formatted_lines 匹配，找到最相似且未使用的行
            best_line = None
            best_score = 0.0
            for line in formatted_lines:
                if line in used_lines:
                    continue
                # 简单相似度：共同字符比例
                common = sum(1 for ch in set(line) if ch in row_text)
                score = common / max(len(line), 1)
                if score > best_score and score >= 0.3:
                    best_score = score
                    best_line = line
            task_name = best_line if best_line else row_text
            if best_line:
                used_lines.add(best_line)
            # 过滤仍然像 UI 的整行
            if task_name in self._TASK_LIST_UI_LABELS or not task_name.strip():
                continue
            # 点击坐标：最左侧元素中心， Fallback 为行中第一个非空元素
            click_elem = row_sorted[0] if row_sorted else None
            center = click_elem.get("center") if click_elem else [0.5, 0.5]
            tasks.append({
                "name": task_name.strip(),
                "center": center,
                "row_text": row_text,
            })

        # 4. 去重：同名任务只保留第一个
        seen: set = set()
        deduped: List[Dict[str, Any]] = []
        for t in tasks:
            if t["name"] not in seen:
                seen.add(t["name"])
                deduped.append(t)
        return deduped

    def _execute_category_task(
        self,
        runtime: Any,
        android: Any,
        serial: Optional[str],
        task: Dict[str, Any],
        vlm_max_steps: int,
        vlm_step_timeout: float,
        max_verification_checks: int,
    ) -> Dict[str, Any]:
        """执行单个分类任务：切分类 -> 追踪 -> VLM 导航 -> 交互 -> 完成确认。

        task 字典含 name / category / center（center 可缺失，缺失时用 OCR 查找）。
        """
        task_name = task["name"]
        category = task.get("category", "次要")
        screen_size = self._get_screen_size(serial)

        # 0. 确保在任务列表页并切到目标分类
        if not self._is_task_list_page(serial):
            open_result = self._open_task_list_if_needed(runtime, serial, "CN")
            if open_result.get("status") != "success":
                return {"status": "error", "message": "打开任务列表失败"}
        self._click_category_by_name(android, serial, category)
        time.sleep(1.2)

        # 1. 点击任务条目以追踪（优先存储坐标，兜底 OCR 查找）
        click_x, click_y = self._norm_to_screen(task.get("center", [0.5, 0.5]), screen_size)
        self._logger.info(LogCategory.MAIN, "点击分类任务条目", task=task_name, category=category, coord=(click_x, click_y))
        click_ok = False
        try:
            android.tap(click_x, click_y)
            click_ok = True
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "点击任务条目异常", task=task_name, error=str(exc))
        time.sleep(2.0)

        # 兜底：OCR 查找任务名重试
        if not click_ok:
            found = self._find_task_coord_by_name(android, serial, task_name)
            if found:
                self._logger.info(LogCategory.MAIN, "OCR 兜底定位任务条目", task=task_name, coord=found)
                try:
                    android.tap(found[0], found[1])
                    click_ok = True
                except Exception as exc:
                    self._logger.warning(LogCategory.MAIN, "OCR 兜底点击异常", task=task_name, error=str(exc))
                time.sleep(2.0)
        if not click_ok:
            return {"status": "error", "message": f"未找到任务条目: {task_name}"}

        # 2. 若仍在任务列表页，尝试点击右侧的"开始追踪"按钮
        if self._is_task_list_page(serial):
            ocr_result = self.execute(
                "scene.elements",
                {"serial": serial, "enable_ocr": True, "enable_template": False, "enable_color": False},
            )
            track_elements: List[Dict[str, Any]] = []
            if isinstance(ocr_result, dict) and ocr_result.get("status") == "success":
                track_elements = ocr_result.get("elements", [])
            for elem in track_elements:
                label = str(elem.get("label", "")).strip()
                if "追踪" in label or "开始" in label:
                    ecx, ecy = self._norm_to_screen(elem.get("center", [0.5, 0.5]), screen_size)
                    self._logger.info(LogCategory.MAIN, "点击追踪按钮", task=task_name, label=label, coord=(ecx, ecy))
                    try:
                        android.tap(ecx, ecy)
                    except Exception as exc:
                        self._logger.warning(LogCategory.MAIN, "点击追踪按钮异常", error=str(exc))
                    time.sleep(2.0)
                    break

        # 3. 关闭任务列表，进入大世界
        self._close_task_list(android)
        time.sleep(1.5)

        # 4. VLM 追踪标识导航
        self._logger.info(LogCategory.MAIN, "VLM 追踪标识导航开始", task=task_name, category=category)
        try:
            walk_result = self.execute(
                "nav3.walk_tracking",
                {
                    "max_steps": vlm_max_steps,
                    "step_timeout": vlm_step_timeout,
                    "serial": serial,
                },
            )
            self._logger.info(
                LogCategory.MAIN, "VLM 追踪标识导航结束",
                task=task_name, status=walk_result.get("status") if isinstance(walk_result, dict) else "invalid",
            )
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "VLM 追踪导航异常", task=task_name, error=str(exc))

        # 5. 到达后尝试交互（F），部分任务需要拾取/确认
        try:
            android.keyevent("KEYCODE_F")
            time.sleep(1.0)
            android.keyevent("KEYCODE_F")
            time.sleep(1.0)
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "任务交互按键异常", task=task_name, error=str(exc))

        # 6. 频繁检查任务列表，确认任务完成
        self._logger.info(LogCategory.MAIN, "开始验证分类任务完成状态", task=task_name, category=category)
        for check_idx in range(max_verification_checks):
            # 重新打开任务列表
            open_result = self._open_task_list_if_needed(runtime, serial, "CN")
            if open_result.get("status") != "success":
                self._logger.warning(LogCategory.MAIN, "验证时重新打开任务列表失败", task=task_name, attempt=check_idx + 1)
                time.sleep(3.0)
                continue

            # 切回目标分类
            self._click_category_by_name(android, serial, category)
            time.sleep(1.0)

            # 读取该分类任务列表
            page = self._read_task_list_page(
                android, serial, scroll_region=[80, 160, 420, 520], swipe_distance=280,
                wait_seconds=0.5, ocr_confidence=0.3, dedup_distance=0.02,
            )
            current_tasks = self._extract_category_tasks(page["all_elements"], page["formatted"].get("lines", []))
            current_names = {t["name"] for t in current_tasks}

            self._logger.info(
                LogCategory.MAIN, "分类任务完成状态检查",
                task=task_name, category=category, attempt=check_idx + 1, remaining_tasks=list(current_names),
            )

            if task_name not in current_names:
                return {"status": "success", "task": task_name, "checks": check_idx + 1}

            # 尚未完成，等待后再次检查
            self._close_task_list(android)
            time.sleep(5.0)

        return {
            "status": "error",
            "task": task_name,
            "message": f"经过 {max_verification_checks} 次检查，任务仍存在于 {category} 列表中",
        }

    def _read_task_list_page(
        self,
        android: Any,
        serial: Optional[str],
        scroll_region: List[int],
        swipe_distance: int = 320,
        wait_seconds: float = 0.5,
        ocr_confidence: float = 0.3,
        dedup_distance: float = 0.02,
    ) -> Dict[str, Any]:
        """读取当前任务列表页（不点击入口图标），滚动到顶后逐屏 OCR 并格式化。"""
        steps: List[Dict[str, Any]] = []

        # 3.1 从下往上滑动至顶端
        top_reached = self._scroll_task_list_to_top(
            android, serial, scroll_region, swipe_distance=swipe_distance, wait_seconds=wait_seconds
        )
        steps.append({"step": "scroll_to_top", "status": "success", "top_reached": top_reached})

        # 3.2 从顶端向下滑动，逐屏 OCR 并累积全部任务元素
        all_elements = self._scroll_task_list_read_down(
            android, serial, scroll_region, swipe_distance=swipe_distance, wait_seconds=wait_seconds,
            ocr_confidence=ocr_confidence
        )
        steps.append({"step": "scroll_read", "status": "success", "screen_element_count": len(all_elements)})

        # 3.3 格式化 OCR 结果
        deduped_elements = self._deduplicate_task_list_elements_by_label(all_elements)
        formatted = self._format_task_list_ocr(deduped_elements, dedup_distance=dedup_distance)
        steps.append({"step": "format", "status": "success", "line_count": len(formatted["lines"]), "deduped_element_count": len(deduped_elements)})

        return {
            "all_elements": all_elements,
            "formatted": formatted,
            "steps": steps,
        }

    def _capture_screenshot_array(self, serial: Optional[str]) -> Optional[np.ndarray]:
        """捕获设备截图并解码为 BGR numpy 数组。"""
        image_bytes = self.execute("screenshot", {"serial": serial})
        if not image_bytes:
            return None
        arr = np.frombuffer(image_bytes, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    @staticmethod
    def _region_similar(
        prev_img: Optional[np.ndarray], curr_img: Optional[np.ndarray], region: List[int], threshold: float = 0.02
    ) -> bool:
        """比较两图在指定区域的相似度，返回是否基本无变化。"""
        if prev_img is None or curr_img is None:
            return False
        x, y, w, h = region
        # 限制在有效范围内
        ph, pw = prev_img.shape[:2]
        ch, cw = curr_img.shape[:2]
        x = min(max(x, 0), pw - 1, cw - 1)
        y = min(max(y, 0), ph - 1, ch - 1)
        w = min(w, pw - x, cw - x)
        h = min(h, ph - y, ch - y)
        if w <= 0 or h <= 0:
            return False
        prev_crop = prev_img[y:y+h, x:x+w]
        curr_crop = curr_img[y:y+h, x:x+w]
        # 下采样后计算归一化平均绝对差
        prev_small = cv2.resize(prev_crop, (64, 64))
        curr_small = cv2.resize(curr_crop, (64, 64))
        diff = cv2.absdiff(prev_small, curr_small).astype(np.float32) / 255.0
        return diff.mean() < threshold

    def _scroll_task_list_to_top(
        self,
        android: Any,
        serial: Optional[str],
        region: List[int],
        swipe_distance: int = 320,
        wait_seconds: float = 0.5,
        max_swipes: int = 20,
    ) -> bool:
        """持续从下往上滑动任务列表，直到连续 3 次画面相同（判定为已到达顶端）。"""
        x, y, w, h = region
        center_x = x + w // 2
        bottom_y = y + h - 40
        top_y = y + 40
        actual_distance = min(swipe_distance, bottom_y - top_y)
        if actual_distance <= 0:
            self._logger.warning(LogCategory.MAIN, "任务列表滚动区域高度无效", region=region)
            return False

        stable_count = 0
        prev_screen: Optional[np.ndarray] = None
        for i in range(max_swipes):
            android.swipe(center_x, bottom_y, center_x, bottom_y - actual_distance, duration_ms=300)
            time.sleep(wait_seconds)
            screen = self._capture_screenshot_array(serial)
            if self._region_similar(prev_screen, screen, region):
                stable_count += 1
                self._logger.debug(LogCategory.MAIN, "滚动到顶端检测", stable_count=stable_count, swipe=i+1)
                if stable_count >= 3:
                    self._logger.info(LogCategory.MAIN, "已到达任务列表顶端", swipes=i+1)
                    return True
            else:
                stable_count = 0
            prev_screen = screen
        self._logger.warning(LogCategory.MAIN, "到达顶端检测未稳定，已达最大滑动次数", max_swipes=max_swipes)
        return False

    def _scroll_task_list_read_down(
        self,
        android: Any,
        serial: Optional[str],
        region: List[int],
        swipe_distance: int = 320,
        wait_seconds: float = 0.5,
        ocr_confidence: float = 0.3,
        max_screens: int = 20,
    ) -> List[Dict[str, Any]]:
        """从任务列表顶端开始逐屏向下滑动并 OCR，累积全部任务元素。"""
        x, y, w, h = region
        center_x = x + w // 2
        top_y = y + 40
        bottom_y = y + h - 40
        actual_distance = min(swipe_distance, bottom_y - top_y)
        all_elements: List[Dict[str, Any]] = []

        stable_count = 0
        prev_screen: Optional[np.ndarray] = None
        for i in range(max_screens):
            # OCR 当前整页
            ocr_result = self.execute(
                "scene.elements",
                {
                    "serial": serial,
                    "enable_ocr": True,
                    "enable_template": False,
                    "enable_color": False,
                },
            )
            if isinstance(ocr_result, dict) and ocr_result.get("status") == "success":
                for e in ocr_result.get("elements", []):
                    if e.get("source") == "ocr" and e.get("confidence", 0.0) >= ocr_confidence:
                        all_elements.append(e)
            else:
                self._logger.warning(
                    LogCategory.MAIN, "滑动读取 OCR 未返回有效结果",
                    screen=i+1,
                    status=ocr_result.get("status") if isinstance(ocr_result, dict) else "invalid",
                )

            # 向下滑动
            android.swipe(center_x, top_y, center_x, top_y + actual_distance, duration_ms=300)
            time.sleep(wait_seconds)

            # 检测是否已到达底部：连续 3 次画面相同
            screen = self._capture_screenshot_array(serial)
            if self._region_similar(prev_screen, screen, region):
                stable_count += 1
                if stable_count >= 3:
                    self._logger.info(LogCategory.MAIN, "已到达任务列表底部", screens=i+1)
                    break
            else:
                stable_count = 0
            prev_screen = screen
        else:
            self._logger.warning(LogCategory.MAIN, "向下滑动读取达到最大屏数", max_screens=max_screens)

        return all_elements

    def _nav_to(self, params: Dict[str, Any]) -> Dict[str, Any]:
        target = params.get("target")
        options = params.get("options") or {}
        task_name = options.get("task", target)
        serial = params.get("serial")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return {
                "status": "error",
                "command": "nav.to",
                "target": target,
                "task": task_name,
                "options": options,
                "maaend_connected": False,
            }
        if not task_name:
            return {"status": "error", "message": "nav target 为空", "command": "nav.to"}
        ok = self.execute("task.run", {"name": task_name, "options": options, "serial": serial})
        return {
            "status": "success" if ok else "error",
            "command": "nav.to",
            "target": target,
            "task": task_name,
            "options": options,
            "maaend_connected": self.connected,
        }

    # ------------------------------------------------------------------
    # Nav2 commands – scrcpy-based 3D world navigation
    # ------------------------------------------------------------------

    def _nav2_to_coords(self, params: Dict[str, Any]) -> Dict[str, Any]:
        nav = self.navigator()
        return nav.to_coords(
            map_name=params.get("map_name", ""),
            x=float(params.get("x", 0)),
            y=float(params.get("y", 0)),
            level_id=params.get("level_id"),
            zone_override=params.get("zone"),
        )

    def _nav2_to_entity(self, params: Dict[str, Any]) -> Dict[str, Any]:
        nav = self.navigator()
        return nav.to_entity(
            entity_name=params.get("name", ""),
            limit=int(params.get("limit", 10)),
        )

    def _nav2_where(self, params: Dict[str, Any]) -> Dict[str, Any]:
        nav = self.navigator()
        return nav.where_am_i()

    def _nav2_list_entities(self, params: Dict[str, Any]) -> Dict[str, Any]:
        nav = self.navigator()
        return nav.list_entities(
            category=params.get("category"),
            map_name=params.get("map_name"),
            name_filter=params.get("name"),
            limit=int(params.get("limit", 50)),
        )

    def _nav2_list_maps(self, params: Dict[str, Any]) -> Dict[str, Any]:
        nav = self.navigator()
        return nav.list_maps()

    # ------------------------------------------------------------------
    # nav3 - VLM-driven walking
    # ------------------------------------------------------------------

    def _nav3_walk(self, params: Dict[str, Any]) -> Dict[str, Any]:
        nav = self.navigator()
        step_timeout = params.get("step_timeout")
        target_radius = params.get("target_radius")
        return nav.to_coords_vlm(
            map_name=params.get("map_name", ""),
            x=float(params.get("x", 0)),
            y=float(params.get("y", 0)),
            level_id=params.get("level_id"),
            zone_override=params.get("zone"),
            llm_client=self._llm_client_instance,
            max_steps=int(params.get("max_steps", 40)),
            keyevent_fn=self._vlm_keyevent,
            step_timeout=float(step_timeout) if step_timeout is not None else None,
            target_radius=float(target_radius) if target_radius is not None else None,
        )

    def _nav3_walk_tracking(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """VLM 任务追踪标识驱动步行导航（不需要目标坐标）。

        VLM 通过识别屏幕上的任务追踪标识（箭头/路径/小地图标记/目标光柱）
        自主决定方向并控制前进，到达目的地后输出 arrived。
        """
        nav = self.navigator()
        step_timeout = params.get("step_timeout")
        return nav.to_tracking_vlm(
            llm_client=self._llm_client_instance,
            max_steps=int(params.get("max_steps", 40)),
            keyevent_fn=self._vlm_keyevent,
            step_timeout=float(step_timeout) if step_timeout is not None else None,
        )

    def _nav3_to_entity(self, params: Dict[str, Any]) -> Dict[str, Any]:
        nav = self.navigator()
        step_timeout = params.get("step_timeout")
        target_radius = params.get("target_radius")
        return nav.to_entity_vlm(
            entity_name=params.get("name", ""),
            llm_client=self._llm_client_instance,
            max_steps=int(params.get("max_steps", 40)),
            keyevent_fn=self._vlm_keyevent,
            limit=int(params.get("limit", 10)),
            step_timeout=float(step_timeout) if step_timeout is not None else None,
            target_radius=float(target_radius) if target_radius is not None else None,
        )

    def _vlm_keyevent(self, key: str, duration: Optional[float]) -> None:
        """Send a key event to the device for a given duration.

        For short taps (duration is None), sends a single keyevent.
        For held keys, simulates multiple taps at intervals.
        """
        try:
            android = self.android()
            if duration is not None and duration > 0.3:
                # Simulate hold via repeated taps
                repeats = max(1, int(duration / 0.15))
                for _ in range(repeats):
                    android.keyevent(key)
                    time.sleep(0.12)
            else:
                android.keyevent(key)
        except Exception as exc:
            self._logger.warning("VLM keyevent '%s' failed: %s", key, exc)
    # ------------------------------------------------------------------
    # Scene understanding commands
    # ------------------------------------------------------------------

    def _decode_image(self, image_bytes: bytes) -> Optional[np.ndarray]:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    def _prepare_screen(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """统一处理截图获取与解码。"""
        import base64

        serial = params.get("serial")
        image_data = params.get("image")
        if image_data is not None:
            try:
                image_bytes = base64.b64decode(image_data)
            except Exception:
                return {"status": "error", "message": "base64 解码失败"}
        else:
            image_bytes = self.android(serial).screenshot(serial=serial)
        if image_bytes is None:
            return {"status": "error", "message": "无法获取截图"}
        screen = self._decode_image(image_bytes)
        if screen is None:
            return {"status": "error", "message": "截图解码失败"}
        return {"status": "success", "screen": screen}

    def _scene_identify(self, params: Dict[str, Any]) -> Dict[str, Any]:
        svc = self.scene()
        prepared = self._prepare_screen(params)
        if "status" in prepared and prepared["status"] == "error":
            return prepared
        screen = prepared["screen"]
        page = svc.identify(screen)
        context = svc.get_scene_context()
        dominant_page, dominant_ratio = svc.get_dominant_page()
        return {
            "status": "success",
            "command": "scene.identify",
            "page_type": page.page_type,
            "confidence": page.confidence,
            "element_count": len(page.elements),
            "elements": [
                {
                    "label": e.label,
                    "type": e.element_type,
                    "source": e.source,
                    "confidence": e.confidence,
                    "center": e.center,
                }
                for e in page.elements[:50]
            ],
            "features": page.features,
            "gameplay_info": page.metadata.get("gameplay_info"),
            "scene_context": context,
            "dominant_page": dominant_page,
            "dominant_ratio": dominant_ratio,
        }

    def _scene_verify(self, params: Dict[str, Any]) -> Dict[str, Any]:
        expected = params.get("expected")
        if not expected:
            return {"status": "error", "message": "缺少 expected 参数"}
        svc = self.scene()
        prepared = self._prepare_screen(params)
        if "status" in prepared and prepared["status"] == "error":
            return prepared
        screen = prepared["screen"]
        is_match, page = svc.verify(screen, expected)
        return {
            "status": "success",
            "command": "scene.verify",
            "expected": expected,
            "is_match": is_match,
            "actual_page": page.page_type,
            "confidence": page.confidence,
        }

    def _scene_analyze_elements(self, params: Dict[str, Any]) -> Dict[str, Any]:
        svc = self.scene()
        prepared = self._prepare_screen(params)
        if "status" in prepared and prepared["status"] == "error":
            return prepared
        screen = prepared["screen"]
        enable_template = params.get("enable_template", True)
        enable_ocr = params.get("enable_ocr", True)
        enable_color = params.get("enable_color", True)
        page = svc.analyze_elements(screen, enable_template=enable_template, enable_ocr=enable_ocr, enable_color=enable_color)
        return {
            "status": "success",
            "command": "scene.elements",
            "page_type": page.page_type,
            "confidence": page.confidence,
            "elements": [
                {
                    "label": e.label,
                    "type": e.element_type,
                    "source": e.source,
                    "confidence": e.confidence,
                    "center": e.center,
                    "bbox": e.bbox,
                    "action": e.action,
                }
                for e in page.elements
            ],
            "features": page.features,
        }

    def _scene_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        svc = self.scene()
        context = svc.get_scene_context()
        dominant, ratio = svc.get_dominant_page()
        return {
            "status": "success",
            "command": "scene.context",
            "scene_context": context,
            "dominant_page": dominant,
            "dominant_ratio": ratio,
        }

    # ------------------------------------------------------------------
    # LLM 生命周期
    # ------------------------------------------------------------------

    def warmup_llm(self) -> bool:
        if self._llm_runtime_instance.ready:
            return True
        return self._llm_runtime_instance.start()

    def cooldown_llm(self) -> None:
        try:
            self._llm_runtime_instance.stop()
        except Exception as exc:
            self._logger.warning("cooldown_llm 异常: %s", exc)

    def _llm_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self._llm_runtime_instance.ready:
            ok = self._llm_runtime_instance.start()
            if not ok:
                return {"status": "error", "message": "llama-server 启动失败"}
        prompt = params.get("prompt") or params.get("text") or ""
        system = params.get("system")
        temperature = params.get("temperature")
        max_tokens = params.get("max_tokens")
        image = params.get("image")
        try:
            output = self._llm_client_instance.chat(
                prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                image=image,
            )
            return {"status": "success", "command": "llm.chat", "output": output}
        except Exception as exc:
            return {"status": "error", "command": "llm.chat", "message": str(exc)}

    def _llm_status(self) -> Dict[str, Any]:
        try:
            runtime = self._llm_runtime_instance
        except Exception as exc:
            return {
                "status": "error",
                "command": "llm.status",
                "message": f"LLM runtime init failed: {exc}",
            }
        return {
            "status": "success",
            "command": "llm.status",
            "enabled": self._config.get("llm", {}).get("enabled", True),
            "ready": runtime.ready,
            "port": runtime.port,
            "base_url": runtime.base_url,
        }
