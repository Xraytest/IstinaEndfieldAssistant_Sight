"""IstinaRuntime - 统一运行时入口

封装设备层与 MaaEndRuntime，提供 GUI/CLI 统一执行接口。
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional


import cv2
import numpy as np

from core.foundation.logger import LogCategory, get_logger
from core.foundation.paths import get_project_root

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
        self._config_path = Path(config_path).resolve() if config_path else None
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
        if self._nav is None:
            self._nav = _get_navigator()(
                maaend=self.maaend(),
                screenshot_fn=self.android().screenshot,
            )
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
            self.android(serial).start_scrcpy(serial=serial)
            self._logger.info(LogCategory.MAIN, "scrcpy 预览通道启动成功", serial=serial)
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "scrcpy 预览通道启动失败", error=str(exc))
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
        options = params.get("options") or {}
        serial = params.get("serial")
        timeout = params.get("timeout")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return False
        return bool(runtime.run_task(name, options, timeout))

    def _run_preset(self, params: Dict[str, Any]) -> bool:
        name = params.get("name")
        serial = params.get("serial")
        timeout = params.get("timeout")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return False
        return bool(runtime.run_preset(name, timeout))

    def _apply_preset(self, params: Dict[str, Any]) -> bool:
        name = params.get("name")
        serial = params.get("serial")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return False
        return bool(runtime.apply_preset(name))

    def _run_queue(self, params: Dict[str, Any]) -> bool:
        serial = params.get("serial")
        timeout = params.get("timeout")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return False
        return bool(runtime.run_queue(timeout))

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
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self._logger.warning(LogCategory.MAIN, "加载配置失败，使用默认值", error=str(e))
        return {}

    def _resolve_config_path(self) -> Path:
        if self._config_path is not None:
            return self._config_path
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
        return self._wait_for_in_world(runtime, timeout=120, interval=2)

    def _wait_for_in_world(self, runtime: Any, timeout: int = 120, interval: int = 2) -> bool:
        """循环检测是否已进入大世界，最多等待 timeout 秒。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if runtime.run_pipeline("EnterGame", {}):
                    self._logger.info(LogCategory.MAIN, "已进入大世界")
                    return True
            except Exception as exc:
                self._logger.warning(LogCategory.MAIN, "进入大世界检测异常", error=str(exc))
            time.sleep(interval)
        self._logger.warning(LogCategory.MAIN, "等待进入大世界超时")
        return False


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
        return nav.to_coords_vlm(
            map_name=params.get("map_name", ""),
            x=float(params.get("x", 0)),
            y=float(params.get("y", 0)),
            level_id=params.get("level_id"),
            zone_override=params.get("zone"),
            llm_client=self._llm_client,
            max_steps=int(params.get("max_steps", 40)),
            keyevent_fn=self._vlm_keyevent,
        )

    def _nav3_to_entity(self, params: Dict[str, Any]) -> Dict[str, Any]:
        nav = self.navigator()
        return nav.to_entity_vlm(
            entity_name=params.get("name", ""),
            llm_client=self._llm_client,
            max_steps=int(params.get("max_steps", 40)),
            keyevent_fn=self._vlm_keyevent,
            limit=int(params.get("limit", 10)),
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
                    import time
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
