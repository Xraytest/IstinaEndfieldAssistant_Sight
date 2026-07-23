"""IstinaRuntime - 统一运行时入口

封装设备层与 MaaEndRuntime，提供 GUI/CLI 统一执行接口。
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple


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


def _load_dotenv() -> None:
    """加载 .env 环境变量（多实例分层）。

    加载顺序（后者覆盖前者，但 ``os.environ`` 已有值不被覆盖）：
        1. **全局** ``<project_root>/.env``：仅含 ``LLM_PROVIDER`` / ``LLM_CLOUD_*``
           等 LLM 配置，对所有实例共享
        2. **实例** ``<instance_root>/.env``：实例私有 env（预留扩展位，
           目前为空）。若出现 ``LLM_*`` 键会被忽略并 warning（防误改全局 LLM）

    轻量实现：仅解析 ``KEY=VALUE`` 行，跳过注释/空行。不引入 python-dotenv
    依赖，避免 requirements.txt 改动。.env 已被 .gitignore 忽略。
    """
    from core.foundation.instance import get_instance_root

    global_env_path = get_project_root() / ".env"
    instance_env_path = get_instance_root() / ".env"

    # 实例 .env 中禁止覆盖的键（LLM 全局共享）
    _GLOBAL_ONLY_KEYS = {
        "LLM_PROVIDER",
        "LLM_CLOUD_BASE_URL",
        "LLM_CLOUD_API_KEY",
        "LLM_CLOUD_MODEL",
        "LLM_PORT",
    }

    for env_path, is_global in ((global_env_path, True), (instance_env_path, False)):
        if not env_path.exists():
            continue
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if not key:
                        continue
                    if not is_global and key in _GLOBAL_ONLY_KEYS:
                        # 实例 .env 中的 LLM_* 键忽略，防误改全局配置
                        continue
                    if key not in os.environ:
                        os.environ[key] = value
        except OSError:
            pass


def _llm_provider() -> str:
    """读取 LLM_PROVIDER 环境变量，默认 local。"""
    return (os.environ.get("LLM_PROVIDER") or "local").strip().lower()


def _instance_config_path() -> Path:
    """获取当前实例的 client_config.json 路径。

    - ``default`` 实例：``<project_root>/config/client_config.json``（向后兼容）
    - 其它实例：``<instance_root>/config/client_config.json``
    """
    from core.foundation.instance import get_instance_root
    return get_instance_root() / "config" / "client_config.json"


def _get_llm_client(llama_runtime: Any) -> Any:
    """根据 LLM_PROVIDER 创建本地或云端 LLM 客户端（互斥）。

    - provider=local：用 llama_runtime.base_url 创建无 api_key 的 LlmClient
    - provider=cloud：用 LLM_CLOUD_* 环境变量创建带 Authorization 的 LlmClient，
      不依赖 llama_runtime（但仍传入以保持调用签名兼容）
    """
    from core.capability.llm.client import LlmClient

    provider = _llm_provider()
    if provider == "cloud":
        base_url = (os.environ.get("LLM_CLOUD_BASE_URL") or "").strip()
        api_key = (os.environ.get("LLM_CLOUD_API_KEY") or "").strip()
        model = (os.environ.get("LLM_CLOUD_MODEL") or "").strip()
        if not base_url:
            raise RuntimeError("LLM_PROVIDER=cloud 但 LLM_CLOUD_BASE_URL 未设置")
        if not api_key:
            raise RuntimeError("LLM_PROVIDER=cloud 但 LLM_CLOUD_API_KEY 未设置")
        if not model:
            raise RuntimeError("LLM_PROVIDER=cloud 但 LLM_CLOUD_MODEL 未设置")
        return LlmClient(base_url=base_url, api_key=api_key, model=model)
    # 默认 local
    return LlmClient(base_url=llama_runtime.base_url)


_GAME_PACKAGE_FALLBACK = "com.hypergryph.endfield"


def _get_game_package(config: Optional[Dict[str, Any]] = None) -> str:
    """从 client_config 读取游戏包名，缺失时回退到默认值。"""
    if not isinstance(config, dict):
        return _GAME_PACKAGE_FALLBACK
    device = config.get("device") or {}
    pkg = (device.get("package") or "").strip()
    return pkg or _GAME_PACKAGE_FALLBACK


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


class _CloudLlmRuntimeStub:
    """云端 LLM 模式下的轻量占位 runtime。

    当 ``LLM_PROVIDER=cloud`` 时，无需启动本地 llama-server，但仍需满足
    ``IstinaRuntime`` 对 ``_llm_runtime_instance`` 的接口访问（``.ready``、
    ``.port``、``.base_url``、``.start()``、``.stop()``）。本 stub 提供恒
    ready 语义，``start()/stop()`` 为 no-op。
    """

    def __init__(self) -> None:
        self._logger = get_logger(__name__)

    @property
    def ready(self) -> bool:
        return True

    @property
    def port(self) -> int:
        return 0

    @property
    def base_url(self) -> str:
        # 云端模式下 _get_llm_client 不使用此字段，仅用于 _llm_status 显示
        return (os.environ.get("LLM_CLOUD_BASE_URL") or "").strip()

    def start(self) -> bool:
        self._logger.info(LogCategory.MAIN, "LLM_PROVIDER=cloud，跳过本地 llama-server 启动")
        return True

    def stop(self) -> None:
        # 云端无需停止
        pass


class IstinaRuntime:
    """Istina 统一运行时门面，聚合设备、MaaEnd、LLM、场景理解等服务。"""

    def __init__(self, config_path: Optional[str] = None):
        # 加载 .env 环境变量（云端 LLM 配置等），在任何 LLM 客户端创建前完成
        _load_dotenv()
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
        # scene_navigation.json pipeline 节点缓存：MaaEndRuntime 仅加载
        # 3rd-part/maaend/resource/ 下的 pipeline，但 _TASK_AREA_TELEPORT_MAP
        # 引用的入口节点（如 SceneEnterWorldValleyIVPowerPlateau1）定义在
        # assets/pipelines/scene_navigation.json，未被注册到 MaaFW。调用
        # run_pipeline 时把此字典作为 pipeline_override 传入，让 MaaFW 临时
        # 注册这些入口节点及其依赖的 JumpBack/Anchor 节点。
        self._scene_navigation_pipeline_cache: Optional[Dict[str, Any]] = None

    def _get_scene_navigation_pipeline(self) -> Dict[str, Any]:
        """读取并缓存 assets/pipelines/scene_navigation.json 的全部节点定义。

        作为 run_pipeline 的 pipeline_override 参数传入，让 MaaFW 临时注册
        SceneEnterWorld* 入口节点（这些节点未被 MaaEndRuntime 加载，但它们
        引用的 __ScenePrivate* 锚点节点已在 maaend 目录中被加载）。
        """
        if self._scene_navigation_pipeline_cache is None:
            path = get_project_root() / "assets" / "pipelines" / "scene_navigation.json"
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._scene_navigation_pipeline_cache = json.load(f)
                self._logger.info(
                    LogCategory.MAIN, "已加载 scene_navigation.json 作为 pipeline_override",
                    path=str(path), nodes=len(self._scene_navigation_pipeline_cache),
                )
            except Exception as exc:
                self._logger.warning(
                    LogCategory.MAIN, "加载 scene_navigation.json 失败，传送 pipeline 将无法执行",
                    path=str(path), error=str(exc),
                )
                self._scene_navigation_pipeline_cache = {}
        return self._scene_navigation_pipeline_cache

    @property
    def _llm_runtime_instance(self) -> Any:
        if self._llm_runtime is None:
            if _llm_provider() == "cloud":
                # 云端模式：不启动本地 llama-server，返回一个轻量占位对象
                # 满足 warmup_llm/cooldown_llm/_llm_status 的 .ready/.port/.base_url 访问
                self._llm_runtime = _CloudLlmRuntimeStub()
            else:
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
                    game_package = _get_game_package(self._config)
                    runtime = MaaEndRuntime(
                        maaend_root=self._config.get("maaend_root"),
                        device_address=resolved,
                        adb_path=self._config.get("adb_path", "3rd-part/adb/adb.exe"),
                        adb_restart_on_timeout=self._config.get("device", {}).get("adb_restart_on_timeout", True),
                        game_package=game_package,
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
        # SCRCPY-RECOVERY: 优先使用 maaend.screenshot()（MaaFramework screencap）
        # 作为 VLM 导航截图源。android.screenshot() 依赖 scrcpy，新进程启动时
        # scrcpy 会话需要 10-15s 才能收到首帧，期间返回 "scrcpy not ready"，
        # 导致 VLM 导航前几步拿不到截图而失败。maaend.screenshot() 走 MaaFramework
        # 自带的 screencap 通道（不依赖 scrcpy），虽然单次较慢（~0.6s vs 0.03s）
        # 但可靠性更高。VLM 单步决策本身耗时 1-5s，截图 0.6s 占比可接受。
        android = self.android()
        maaend = self.maaend()
        # XC-4: 设备切换时废弃旧的 screenshot_fn bound method，重新绑定新设备
        if self._nav is None or self._nav_android is not android:
            screenshot_fn = (
                maaend.screenshot if (maaend and maaend.connected) else android.screenshot
            )
            self._nav = _get_navigator()(
                maaend=maaend,
                screenshot_fn=screenshot_fn,
            )
            self._nav_android = android
        return self._nav

    def _try_launch_emulator_and_wait(self) -> bool:
        """连接失败时调用：检查配置中是否已填写模拟器路径，若有则启动并等待。

        等待时间由 ``device.emulator.launch_wait_seconds`` 控制（默认 30 秒）。
        模拟器以独立子进程启动（不阻塞本进程），Popen 后立即返回。
        若路径未填写或启动异常，返回 False 表示未进行模拟器拉起。

        Returns:
            True 若已成功发起模拟器启动命令并完成等待；
            False 若未配置模拟器路径或启动失败。
        """
        try:
            device_cfg = (self._config or {}).get("device") or {}
        except Exception:
            device_cfg = {}
        emu_cfg = device_cfg.get("emulator") or {}
        path = str(emu_cfg.get("path") or "").strip()
        if not path:
            return False
        args_str = str(emu_cfg.get("args") or "").strip()
        try:
            wait_secs = int(emu_cfg.get("launch_wait_seconds", 30))
        except (TypeError, ValueError):
            wait_secs = 30
        wait_secs = max(0, min(600, wait_secs))

        # posix=False：Windows 风格参数解析（保留引号，兼容 -s 0 / -v 0 等）
        args_list = shlex.split(args_str, posix=False) if args_str else []
        cwd = os.path.dirname(path) or None
        try:
            proc = subprocess.Popen([path] + args_list, cwd=cwd)
        except Exception as exc:
            self._logger.error(
                LogCategory.MAIN,
                "连接失败后启动模拟器异常",
                path=path,
                error=str(exc),
            )
            return False
        self._logger.info(
            LogCategory.MAIN,
            "连接失败，已启动模拟器，等待就绪",
            path=path,
            pid=proc.pid,
            wait_seconds=wait_secs,
        )
        if wait_secs > 0:
            time.sleep(wait_secs)
        return True

    def connect(self, serial: Optional[str] = None) -> bool:
        self._logger.info(LogCategory.MAIN, "开始连接设备", serial=serial)
        runtime = self.maaend(serial)
        if not runtime.connected:
            ok = runtime.connect()
            if not ok:
                # 连接失败：若已配置模拟器路径则启动模拟器并等待后重试一次
                self._logger.warning(
                    LogCategory.MAIN,
                    "首次连接失败，尝试启动模拟器后重试",
                    serial=serial,
                )
                if self._try_launch_emulator_and_wait():
                    ok = runtime.connect()
                if not ok:
                    self._logger.error(LogCategory.MAIN, "MaaEnd runtime 连接失败（模拟器拉起后仍失败）")
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
        if name == "AutoCollect":
            # AutoCollect 划归全智能分类：MaaFW pipeline 仅负责传送/背包整理，
            # VLM（云端或本地）驱动步行到采集点 + F 交互 + 领取，替代 MapTrackerMove
            result = self._auto_collect_run(params)
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
        # SCREENSHOT-PRIORITY: 优先使用 MaaEndRuntime (MaaFramework screencap)，
        # 而非 AndroidRuntime (scrcpy)。
        # 原因：
        # 1. maaend.screenshot() 已有 8s 硬超时保护（轮询 job.done），不会卡死
        # 2. scrcpy 新进程启动需 10-15s 才能收到首帧，期间返回 None 导致 pipeline 失败
        # 3. navigator() 与 _check_state.py 均验证 maaend.screenshot() 稳定可用（~0.6s）
        # 4. pipeline 节点（SceneEnterWorld* 等）依赖 _screenshot，scrcpy 未就绪时会超时
        # 仅当 maaend 不可用（未连接/无 controller）时回退到 AndroidRuntime。
        legacy = getattr(self, "_maaend", None)
        if legacy is not None and not self._maaend_clients:
            data = legacy.screenshot()
            if data is not None:
                self._logger.debug(LogCategory.MAIN, "_screenshot legacy MaaEnd 成功", size=len(data))
                return data
            self._logger.warning(LogCategory.MAIN, "_screenshot legacy MaaEnd 返回 None", serial=serial)
        try:
            runtime = self.maaend(serial)
            data = runtime.screenshot()
            if data is not None:
                self._logger.debug(LogCategory.MAIN, "_screenshot MaaEndRuntime 成功", serial=serial, size=len(data))
                return data
            self._logger.warning(LogCategory.MAIN, "_screenshot MaaEndRuntime 返回 None，回退到 AndroidRuntime", serial=serial)
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "_screenshot MaaEndRuntime 异常，回退到 AndroidRuntime", error=str(exc))
        # 最后兜底：AndroidRuntime (scrcpy)
        try:
            android = self.android(serial)
            data = android.screenshot(serial)
            if data is not None:
                self._logger.debug(LogCategory.MAIN, "_screenshot AndroidRuntime 兜底成功", serial=serial, size=len(data))
                return data
            self._logger.warning(LogCategory.MAIN, "_screenshot AndroidRuntime 兜底也返回 None", serial=serial)
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "_screenshot AndroidRuntime 兜底异常", error=str(exc))
        return None

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
                return _instance_config_path()
            return p
        return _instance_config_path()

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
        """启动游戏并等待进入大世界。

        优化：游戏进程已运行时优先用 EnterGame + OCR 备用判据验证，跳过 AndroidOpenGame
        （AndroidOpenGame 内部 OpenGame 节点会因 InWorld 模板过时无限循环）。
        """
        game_running = False
        try:
            android = self.android(serial)
            package = _get_game_package(self._config)
            pid = android.shell(f"pidof {package}").strip()
            if not pid:
                # pidof 可能不存在于精简 Android 环境（如云终末地），回退到 ps|grep
                try:
                    ps_out = android.shell(f"ps -A | grep {package}").strip()
                    pid = ps_out.split()[1] if ps_out and len(ps_out.split()) > 1 else ""
                except Exception:
                    pid = ""
            if pid:
                self._logger.info(LogCategory.MAIN, "游戏进程已在运行", pid=pid, package=package)
                game_running = True
            else:
                self._logger.info(LogCategory.MAIN, "游戏未运行，准备启动")
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "检查游戏进程失败", error=str(exc))

        # 游戏已运行：直接验证是否在大世界，跳过 AndroidOpenGame
        if game_running:
            if self._wait_for_in_world(runtime, interval=2, max_attempts=5):
                return True
            if self._verify_in_world_by_ocr(serial):
                self._logger.info(
                    LogCategory.MAIN,
                    "OCR 备用判据确认已在大世界，跳过 AndroidOpenGame",
                )
                return True
            self._logger.warning(
                LogCategory.MAIN,
                "游戏已运行但不在大世界，回退到 AndroidOpenGame 流程",
            )

        # 游戏未运行或不在大世界：调用 AndroidOpenGame 启动游戏
        if not runtime.run_task("AndroidOpenGame", {"ClientVersion": client_version}):
            self._logger.error(LogCategory.MAIN, "AndroidOpenGame 执行失败")
            # AndroidOpenGame 失败时再尝试 OCR 备用判据（可能游戏实际已进入大世界
            # 但 OpenGame 节点因模板过时未能识别）
            if self._verify_in_world_by_ocr(serial):
                self._logger.info(
                    LogCategory.MAIN,
                    "AndroidOpenGame 失败但 OCR 备用判据确认已在大世界",
                )
                return True
            return False

        # 额外等待大世界稳定，防止部分加载界面导致后续任务误判
        if self._wait_for_in_world(runtime, interval=2):
            return True
        # EnterGame 模板匹配过时时，用 OCR 备用判据验证画面是否已在主城
        if self._verify_in_world_by_ocr(serial):
            self._logger.info(
                LogCategory.MAIN,
                "OCR 备用判据确认已在大世界，跳过 EnterGame 模板匹配",
            )
            return True
        return False

    def _wait_for_in_world(self, runtime: Any, interval: int = 2, max_attempts: int = 15) -> bool:
        """循环检测是否已进入大世界。

        加 max_attempts 上限（默认 15 次 × 2 秒 = 30 秒），避免 InWorld 模板匹配过时
        导致死循环。超时后返回 False，由调用方决定是否用 OCR/VLM 备用判据验证。
        """
        for attempt in range(1, max_attempts + 1):
            try:
                if runtime.run_pipeline("EnterGame", {}):
                    self._logger.info(LogCategory.MAIN, "已进入大世界", attempt=attempt)
                    return True
            except Exception as exc:
                self._logger.warning(LogCategory.MAIN, "进入大世界检测异常", error=str(exc))
            time.sleep(interval)
        self._logger.warning(
            LogCategory.MAIN, "EnterGame 模板匹配超时，将尝试 OCR 备用判据",
            max_attempts=max_attempts,
        )
        return False

    def _verify_in_world_by_ocr(self, serial: Optional[str]) -> bool:
        """OCR 备用判据：检测画面是否包含大世界主城特征文字。

        当 InWorld 模板匹配（RegionalDevelopmentButton/ProtosyncMenuButton）过时
        导致 EnterGame 永远识别不到时，用 scene.elements OCR 检测画面是否包含
        主城菜单按钮文字（地区建设/干员/采购中心等）作为备用判据。

        要求至少命中 _IN_WORLD_OCR_MIN_HITS 个关键词，避免单一关键词偶发误匹配
        （如签到弹窗文本 "踞渊北眺寻访凭证" 中的 "寻访" 已从关键词列表移除）。
        """
        try:
            ocr_result = self.execute(
                "scene.elements",
                {
                    "serial": serial,
                    "enable_ocr": True,
                    "enable_template": False,
                    "enable_color": False,
                },
            )
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "OCR 备用判据检测异常", error=str(exc))
            return False
        elements: List[Any] = []
        if isinstance(ocr_result, dict) and ocr_result.get("status") == "success":
            elements = ocr_result.get("elements", [])
        text = "".join(e.get("label", "") for e in elements if isinstance(e, dict))
        matched = [kw for kw in self._IN_WORLD_OCR_KEYWORDS if kw in text]
        if len(matched) >= self._IN_WORLD_OCR_MIN_HITS:
            self._logger.info(
                LogCategory.MAIN, "OCR 备用判据确认已在大世界",
                matched=matched, hit_count=len(matched),
                min_required=self._IN_WORLD_OCR_MIN_HITS,
            )
            return True
        self._logger.warning(
            LogCategory.MAIN, "OCR 备用判据未匹配足够大世界特征文字",
            matched=matched, hit_count=len(matched),
            min_required=self._IN_WORLD_OCR_MIN_HITS,
            ocr_preview=text[:200],
        )
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
            "map_area": "枢纽区",
            "map_name": "map01_lv001",
            "target": (385.0, 496.0),
            "level_id": "lv001",
        },
        "VFOriginiumSciencePark": {
            "teleport_node": "SceneEnterWorldValleyIVOriginiumSciencePark1",
            "map_area": "源石科学园",
            "map_name": "map01_lv001",
            "target": None,
            "level_id": "lv001",
        },
        "VFOriginLodespring": {
            "teleport_node": "SceneEnterWorldValleyIVOriginLodespring1",
            "map_area": "源矿源区",
            "map_name": "map01_lv001",
            "target": None,
            "level_id": "lv001",
        },
        "VFPowerPlateau": {
            "teleport_node": "SceneEnterWorldValleyIVPowerPlateau1",
            "map_area": "供能高地",
            "map_name": "map01_lv001",
            "target": None,
            "level_id": "lv001",
        },
        "WLWulingCity": {
            "teleport_node": "SceneEnterWorldWulingWulingCity1",
            "map_area": "武陵城",
            "map_name": "map02_lv001",
            "target": None,
            "level_id": "lv001",
        },
        "WLQingboStockade": {
            "teleport_node": "SceneEnterWorldWulingQingboStockade1",
            "map_area": "清波寨",
            "map_name": "map02_lv001",
            "target": None,
            "level_id": "lv001",
        },
        "WLMarkerStone": {
            "teleport_node": "SceneEnterWorldWulingMarkerStone1",
            "map_area": "界碑",
            "map_name": "map02_lv001",
            "target": None,
            "level_id": "lv001",
        },
        "WLTestArea": {
            "teleport_node": "SceneEnterWorldWulingTestArea1",
            "map_area": "试炼区",
            "map_name": "map02_lv001",
            "target": None,
            "level_id": "lv001",
        },
        "WLSwordVaultDale": {
            "teleport_node": "SceneEnterWorldWulingSwordVaultDale1",
            "map_area": "藏剑谷",
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
        # _vlm_teleport_to_area 需要 android 引用，提前缓存避免 NameError
        android = self.android(serial)
        # 1. 准备阶段：打开副本标签页、选择材料副本、选中追踪、确认追踪。
        #    TODO[模板校准]: 这些 pipeline 节点尚未配置 OCR/模板识别，暂跳过。
        self._logger.info(LogCategory.MAIN, "材料刷取准备阶段（TODO 模板校准，跳过）", region=region)
        try:
            runtime.run_pipeline("MaterialFarmPrepare", {})
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "MaterialFarmPrepare 异常", error=str(exc))

        # 2. 传送到最近锚点（VLM 驱动：SceneEnterMap* + VLM 点击传送点）
        map_area = info.get("map_area")
        if map_area and map_area in self._TASK_AREA_MAP_NODE:
            self._logger.info(LogCategory.MAIN, "VLM 传送到区域锚点", region=region, area=map_area)
            tp_result = self._vlm_teleport_to_area(
                android, serial, map_area, runtime=runtime,
            )
            if not tp_result.get("ok"):
                self._logger.warning(
                    LogCategory.MAIN, "VLM 传送失败",
                    region=region, area=map_area, reason=tp_result.get("reason"),
                )
                return "teleport_failed"
        else:
            self._logger.warning(
                LogCategory.MAIN, "无匹配 map_area，跳过传送",
                region=region, map_area=map_area,
            )

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
                    # 交互收取：tap 屏幕交互按钮（手机端 keyevent F 无效）
                    try:
                        self._vlm_press_interact(self.android(serial), serial)
                        time.sleep(1.0)
                    except Exception as exc:
                        self._logger.warning(LogCategory.MAIN, "交互收取异常", error=str(exc))
                        point_ok = False
                    if point_ok:
                        # 领取/确认面板
                        try:
                            runtime.run_pipeline("MaterialCollectClaim", {})
                        except Exception as exc:
                            self._logger.warning(LogCategory.MAIN, "MaterialCollectClaim 异常", error=str(exc))
                        # 采集验证：OCR 检测飘字，防止"到达但未采集到"的误判
                        collected, ocr_preview = self._verify_collect_success(serial)
                        self._logger.info(
                            LogCategory.MAIN, "采集验证（tracking 路线）",
                            route=route, collected=collected,
                            ocr_preview=ocr_preview[:120],
                        )
                        if not collected:
                            point_ok = False
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
                # 交互收取：tap 屏幕交互按钮（手机端 keyevent F 无效）
                try:
                    self._vlm_press_interact(self.android(serial), serial)
                    time.sleep(1.0)
                except Exception as exc:
                    self._logger.warning(LogCategory.MAIN, "交互收取异常", error=str(exc))
                    route_ok = False
                    continue
                # 领取/确认面板
                try:
                    runtime.run_pipeline("MaterialCollectClaim", {})
                except Exception as exc:
                    self._logger.warning(LogCategory.MAIN, "MaterialCollectClaim 异常", error=str(exc))
                # 采集验证：OCR 检测飘字，防止"到达但未采集到"的误判
                collected, ocr_preview = self._verify_collect_success(serial)
                self._logger.info(
                    LogCategory.MAIN, "采集验证（waypoint 路线）",
                    route=route, point=idx + 1, collected=collected,
                    ocr_preview=ocr_preview[:120],
                )
                if not collected:
                    route_ok = False
                    continue
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

    # 采集任务路线信息表：每条路线包含传送节点、小地图ID、采集物名称(标志物)、
    # 路线坐标点(waypoints，来自 MapTrackerMove 节点 path 字段)、pipeline 回退入口。
    # VLM 导航：把 waypoints + collect_items 作为上下文给 VLM，由 VLM 自主导航。
    # 无 waypoints 的路线(Route1/3/6仅有 MapNavigateAction)回退到 pipeline 执行。
    _AUTO_COLLECT_ROUTE_INFO: Dict[str, Dict[str, Any]] = {
        # === 专属采集路线 Route1-14 ===
        "Route1": {
            "teleport": "SceneEnterWorldWulingWulingCity5",
            "map_name": "map02_lv002",
            "collect_items": ["映火荞花"],
            "waypoints": [],  # 仅有 MapNavigateAction，回退到 pipeline
            "fallback_entry": "AutoCollectRoute1Start",
        },
        "Route2": {
            "teleport": "SceneEnterWorldWulingWulingCity2",
            "map_name": "map02_lv002",
            "collect_items": ["原木"],
            "waypoints": [
                (636.0, 537.0), (631.0, 533.3), (587.3, 533.2), (587.3, 530.8),
                (589.7, 527.0), (592.3, 519.6), (598.4, 510.7), (596.0, 503.3),
                (588.5, 494.5), (583.5, 489.5), (578.5, 484.4), (573.5, 479.5),
                (566.0, 477.1), (533.5, 472.0),  # GotoFind1
                (531.1, 465.7),  # GotoFind2
                (529.8, 469.6),  # GotoFind3
                (532.2, 472.0),  # GotoFind4
                (532.3, 475.8),  # GotoFind5
                (533.5, 478.2),  # GotoFind6
                (531.1, 476.9),  # GotoFind7
                (526.1, 475.8),  # GotoFind8
                (524.8, 473.1),  # GotoFind9
            ],
            "fallback_entry": "AutoCollectRoute2Start",
        },
        "Route3": {
            "teleport": "SceneEnterWorldWulingWulingCity7",
            "map_name": "map02_lv002",
            "collect_items": ["荞花"],
            "waypoints": [],  # 仅有 MapNavigateAction，回退到 pipeline
            "fallback_entry": "AutoCollectRoute3Start",
        },
        "Route4": {
            "teleport": "SceneEnterWorldValleyIVPowerPlateau3",
            "map_name": "map01_lv007",
            "collect_items": ["灰芦麦"],
            "waypoints": [
                (482.7, 409.3),  # GotoFind2
                (481.5, 411.8),  # GotoFind3
                (477.7, 414.3),  # GotoFind4
                (476.5, 411.8),  # GotoFind5
                (474.0, 410.4),  # GotoFind6
                (476.5, 406.8),  # GotoFind7
                (479.0, 404.3),  # GotoFind8
            ],
            "fallback_entry": "AutoCollectRoute4Start",
        },
        "Route5": {
            "teleport": "SceneEnterWorldValleyIVTheHub2",
            "map_name": "map01_lv001",
            "collect_items": ["砂叶"],
            "waypoints": [
                (476.8, 267.6), (475.4, 278.8), (474.1, 283.9), (471.9, 290.0),
                (470.7, 292.6), (470.7, 296.5), (472.0, 303.7), (472.9, 306.4),
                (473.2, 311.5), (474.1, 313.7), (474.4, 322.8), (475.7, 327.5),
                (479.1, 330.0), (479.3, 330.1),  # GotoFind1
                (486.7, 330.1),  # GotoFind2
                (485.5, 333.8),  # GotoFind3
                (486.7, 337.5),  # GotoFind4
                (479.4, 331.5),  # GotoFind6
            ],
            "fallback_entry": "AutoCollectRoute5Start",
        },
        "Route6": {
            "teleport": "SceneEnterWorldValleyIVTheHub2",
            "map_name": "map01_lv001",
            "collect_items": ["苦叶椒"],
            "waypoints": [],  # 仅有 MapNavigateAction，回退到 pipeline
            "fallback_entry": "AutoCollectRoute6Start",
        },
        "Route7": {
            "teleport": "SceneEnterWorldWulingWulingCity1",
            "map_name": "map02_lv002",
            "collect_items": ["血菌", "岩天使叶"],
            "waypoints": [
                (218.2, 515.1), (216.8, 512.0), (211.3, 511.3), (210.1, 508.8),
                (209.8, 504.8), (208.2, 500.9), (203.3, 499.9), (198.6, 496.4),
                (196.2, 495.0), (194.9, 492.6), (195.1, 486.2), (194.5, 477.5),
                (195.0, 468.9), (195.9, 467.7), (209.9, 467.4), (212.1, 465.2),
                (211.9, 457.4), (210.8, 428.2), (210.4, 406.5), (212.6, 394.7),
                (212.6, 383.3), (209.5, 378.4), (209.2, 373.4), (226.0, 372.9),
                (228.4, 383.7), (235.5, 383.6), (243.5, 383.6), (250.6, 383.6),
                (276.3, 383.7), (277.6, 383.6), (278.7, 382.4), (278.8, 355.0),
                (270.0, 353.8),  # GotoFindLine1
                (266.1, 346.2),  # GotoFind1
                (263.6, 348.8),  # GotoFind2
                (263.6, 348.8), (261.0, 348.8),  # GotoFind3
                (263.4, 345.0),  # GotoFind4
                (258.6, 346.2),  # GotoFind5
                (261.1, 343.7),  # GotoFind6
                (262.3, 341.3),  # GotoFind7
                (268.4, 341.3),  # GotoFind8
                (268.4, 341.3), (266.1, 345.0), (267.3, 348.8), (273.6, 353.8),
                (280.9, 351.3), (281.0, 316.2), (274.6, 307.5), (274.6, 301.3),
                (278.5, 301.3), (283.5, 303.7),  # GotoFindLine4
                (284.7, 303.8), (288.4, 302.6), (294.8, 305.1),  # GotoFindLine5
                (294.8, 305.1), (297.2, 305.1), (298.5, 306.2), (302.2, 306.2),
                (305.2, 304.8), (305.9, 293.7), (304.7, 290.0), (304.7, 288.8),
                (302.2, 286.3), (299.8, 287.4), (294.7, 287.4), (293.4, 286.3),
                (290.9, 286.2), (287.2, 283.8), (283.4, 282.5), (278.4, 281.1),  # GotoFindLine7
                (278.4, 281.3), (274.7, 285.0),  # GotoFind11
                (274.6, 283.7), (273.4, 286.4),  # GotoFind12
                (273.4, 286.4), (270.9, 290.0),  # GotoFind13
                (270.9, 290.0), (268.4, 291.2),  # GotoFind14
                (268.4, 291.2), (264.8, 288.7),  # GotoFind15
                (264.9, 288.7), (263.5, 283.7), (266.1, 277.5),  # GotoFind16
            ],
            "fallback_entry": "AutoCollectRoute7Start",
        },
        "Route8": {
            "teleport": "SceneEnterWorldWulingWulingCity7",
            "map_name": "map02_lv002",
            "collect_items": ["星门菌"],
            "waypoints": [
                (426.0, 851.2), (421.0, 853.8), (411.0, 855.0), (408.5, 841.3),
                (408.5, 832.5), (396.1, 830.1), (393.5, 817.6), (383.4, 815.1),  # GotoFindLine1
                (383.4, 815.1), (387.2, 805.1),  # GotoFind1
                (387.3, 805.1), (384.8, 809.9), (389.7, 803.9),  # GotoFind2
                (389.7, 803.9), (393.4, 801.3), (390.9, 797.6),  # GotoFind3
                (390.9, 797.6), (393.4, 793.8), (392.2, 800.0),  # GotoFind4
                (392.2, 800.0), (393.4, 793.8), (388.4, 797.5),  # GotoFind5
                (388.4, 797.5), (393.4, 793.8), (388.6, 795.0),  # GotoFind6
                (388.6, 795.0), (383.5, 800.1),  # GotoFind7
                (383.5, 800.1), (384.7, 803.8),  # GotoFind8
            ],
            "fallback_entry": "AutoCollectRoute8Start",
        },
        "Route9": {
            "teleport": "SceneEnterWorldWulingWulingCity7",
            "map_name": "map02_lv002",
            "collect_items": ["轻红柱状菌"],
            "waypoints": [
                (426.0, 851.3), (437.5, 841.2), (462.5, 851.3), (480.0, 866.5),
                (489.4, 886.4), (503.4, 896.0), (518.5, 897.5), (525.6, 889.7),
                (532.3, 896.2), (558.5, 901.3),  # GotoFindLine1
                (559.8, 905.0), (557.3, 908.8),  # GotoFind1
                (559.8, 905.0), (556.0, 907.4),  # GotoFind2
                (559.8, 905.0), (553.5, 908.8),  # GotoFind3
                (559.8, 905.0), (561.0, 911.2),  # GotoFind4
                (559.8, 905.0), (563.5, 911.3),  # GotoFind5
                (563.5, 907.5), (562.2, 912.5),  # GotoFind6
                (563.5, 907.5), (563.5, 914.9),  # GotoFind7
                (563.5, 907.5), (561.0, 915.0),  # GotoFind8
            ],
            "fallback_entry": "AutoCollectRoute9Start",
        },
        "Route10": {
            "teleport": "SceneEnterWorldWulingJingyuValley1",
            "map_name": "map02_lv001",
            "collect_items": ["重红柱状菌"],
            "waypoints": [
                (503.7, 187.5), (510.0, 193.8), (497.5, 213.7), (486.2, 217.5),
                (476.3, 221.3),  # GotoFindLine1
                (470.0, 216.3), (475.0, 221.2),  # GotoFind1
                (473.7, 225.0), (477.5, 222.5),  # GotoFind2
                (477.5, 222.5), (471.2, 225.0),  # GotoFind3
                (466.3, 223.8),  # GotoFind4
                (465.0, 217.5),  # GotoFind5
                (465.0, 217.5), (471.2, 215.0),  # GotoFind6
                (471.2, 215.0), (475.0, 216.2),  # GotoFind7
                (475.0, 216.2), (471.2, 213.8),  # GotoFind8
                (467.4, 216.3), (460.0, 218.8), (458.7, 188.7), (436.3, 182.5),
                (407.5, 187.5), (382.5, 206.2), (396.2, 230.0), (408.7, 226.3),  # GotoFindLine2
                (406.2, 226.2), (414.9, 225.0),  # GotoFind11
                (414.9, 225.0), (412.5, 230.0),  # GotoFind12
                (412.5, 230.0), (410.0, 226.3),  # GotoFind13
                (406.2, 226.2), (413.7, 228.7),  # GotoFind14
                (413.7, 228.7), (416.2, 223.8),  # GotoFind15
                (416.2, 223.8), (416.2, 215.0),  # GotoFind16
                (407.5, 220.1), (412.4, 226.2),  # GotoFind17
                (407.5, 220.1), (413.7, 214.9),  # GotoFind18
            ],
            "fallback_entry": "AutoCollectRoute10Start",
        },
        "Route11": {
            "teleport": "SceneEnterWorldWulingJingyuValley4",
            "map_name": "map02_lv001",
            "collect_items": ["至晶多齿叶"],
            "waypoints": [
                (263.7, 402.5), (237.5, 362.9), (235.3, 347.1), (241.8, 338.0),
                (259.9, 334.0), (274.6, 333.0), (274.1, 321.7), (244.8, 302.7),
                (236.0, 298.2), (224.8, 306.3),  # GotoFindLine1
                (226.0, 301.3), (224.7, 308.7),  # GotoFind1
                (226.0, 301.3), (223.5, 308.8),  # GotoFind2
                (226.0, 301.3), (221.0, 310.0),  # GotoFind3
                (223.5, 305.0), (223.5, 311.2),  # GotoFind4
                (223.5, 305.0), (226.0, 312.5),  # GotoFind5
                (223.5, 305.0), (222.2, 311.2),  # GotoFind6
            ],
            "fallback_entry": "AutoCollectRoute11Start",
        },
        "Route12": {
            "teleport": "SceneEnterWorldWulingMarkerStone3",
            "map_name": "map02_lv004",
            "collect_items": ["中红柱状菌"],
            "waypoints": [
                (607.5, 326.3), (635.0, 323.8), (641.0, 342.1), (633.8, 348.8),  # GotoFindLine1
                (632.5, 348.3), (623.8, 352.6),  # GotoFind1
                (632.5, 348.3), (626.3, 353.8),  # GotoFind2
                (632.5, 348.3), (628.7, 355.1),  # GotoFind3
                (632.5, 348.3), (628.7, 355.1),  # GotoFind4
                (632.5, 348.3), (630.0, 355.1),  # GotoFind5
                (632.5, 348.3), (628.7, 357.6),  # GotoFind6
                (623.7, 351.3), (631.2, 353.9),  # GotoFind7
                (623.7, 351.3), (632.5, 353.8),  # GotoFind8
            ],
            "fallback_entry": "AutoCollectRoute12Start",
        },
        "Route13": {
            "teleport": "SceneEnterWorldValleyIVOriginLodespring3",
            "map_name": "map01_lv006",
            "collect_items": ["受蚀玉化叶"],
            "waypoints": [
                (414.0, 493.2), (412.2, 486.9), (380.1, 478.6), (371.3, 443.1),
                (355.6, 421.2), (348.2, 389.3), (311.9, 393.2), (297.8, 398.3),
                (290.1, 419.4),  # GotoFindLine1
                (287.8, 423.3), (281.5, 425.7),  # GotoFind1
                (287.8, 423.3), (276.6, 421.9),  # GotoFind2
                (282.8, 424.5), (287.8, 418.3),  # GotoFind3
                (282.8, 424.5), (287.8, 417.0),  # GotoFind4
                (282.8, 424.5), (286.5, 417.0),  # GotoFind5
                (282.8, 424.5), (284.0, 419.5),  # GotoFind6
            ],
            "fallback_entry": "AutoCollectRoute13Start",
        },
        "Route14": {
            "teleport": "SceneEnterWorldValleyIVTheHub1",
            "map_name": "map01_lv001",
            "collect_items": ["晶化多齿叶"],
            "waypoints": [
                (390.4, 498.8), (410.5, 502.7), (417.9, 498.7), (444.1, 525.0),
                (492.9, 532.6), (520.3, 536.1), (544.3, 537.9), (554.3, 526.1),
                (559.1, 552.5), (545.6, 573.8),  # GotoFindLine1
                (546.8, 576.5), (558.1, 585.1),  # GotoFind1
                (546.8, 576.5), (558.1, 585.1),  # GotoFind2
                (561.5, 577.4), (563.0, 587.8),  # GotoFind3
                (561.5, 577.4), (562.0, 588.9),  # GotoFind4
                (553.1, 583.5), (555.2, 590.0),  # GotoFind5
                (553.1, 583.5), (555.3, 591.3),  # GotoFind6
            ],
            "fallback_entry": "AutoCollectRoute14Start",
        },
        # === 通用采集路线 CommonRoute1-8 ===
        "CommonRoute1": {
            "teleport": "SceneEnterWorldValleyIVTheHub1",
            "map_name": "map01_lv001",
            "collect_items": ["映火荞花"],
            "waypoints": [
                (389.1, 497.9), (376.3, 499.6), (364.6, 502.1), (349.4, 506.5),
                (326.9, 514.5), (311.9, 520.6), (311.6, 567.3), (283.1, 585.3),
                (271.0, 578.0),  # GotoFindLine1
                (272.2, 581.0), (274.1, 586.5),  # GotoFind1
                (272.2, 581.0), (271.0, 586.3),  # GotoFind2
                (272.2, 581.0), (271.3, 587.6),  # GotoFind3
                (281.9, 591.6),  # GotoFind4
                (293.6, 484.7),  # GotoFind5
            ],
            "fallback_entry": "AutoCollectCommonRoute1Start",
        },
        "CommonRoute2": {
            "teleport": "SceneEnterWorldValleyIVTheHub1",
            "map_name": "map01_lv001",
            "collect_items": ["黯银柑实"],
            "waypoints": [
                (296.6, 535.2), (270.6, 537.4), (277.0, 522.0), (298.8, 523.6),
                (299.3, 509.2), (300.9, 493.7), (301.7, 477.8), (286.5, 477.3),  # GotoFindLine2
                (198.5, 526.0),  # GotoFindLine4
                (187.2, 528.5),  # GotoFind3
                (218.4, 513.5), (223.6, 507.1),  # GotoFind4
            ],
            "fallback_entry": "AutoCollectCommonRoute2Start",
        },
        "CommonRoute3": {
            "teleport": "SceneEnterWorldWulingMarkerStone4",
            "map_name": "map02_lv004",
            "collect_items": ["灼壳虫"],
            "waypoints": [
                (520.0, 674.5), (521.9, 661.5), (506.3, 647.4), (505.6, 630.1),
                (508.9, 613.1), (522.9, 598.3), (516.3, 584.0),  # GotoFindLine1
                (508.2, 578.7),  # GotoFind1
                (519.9, 580.8),  # GotoFind2
                (516.2, 579.8), (513.8, 574.8),  # GotoFind3
                (514.7, 573.0),  # GotoFind4
                (513.7, 579.6), (506.7, 573.0), (503.8, 559.5),  # GotoFindLine2
                (510.2, 563.3),  # GotoFind5
                (511.4, 561.8),  # GotoFind6
                (512.5, 561.3),  # GotoFind7
            ],
            "fallback_entry": "AutoCollectCommonRoute3Start",
        },
        "CommonRoute4": {
            "teleport": "SceneEnterWorldWulingJingyuValley6",
            "map_name": "map02_lv001",
            "collect_items": ["萤壳虫"],
            "waypoints": [
                (490.2, 531.3), (490.2, 536.2),  # GotoFind1
                (486.6, 530.0), (481.6, 533.6),  # GotoFind2
                (485.2, 532.2),  # GotoFind3
                (482.7, 521.1), (490.3, 519.9),  # GotoFind4
                (482.7, 521.1), (480.2, 527.5),  # GotoFind5
                (482.7, 521.1), (487.8, 523.9),  # GotoFind6
            ],
            "fallback_entry": "AutoCollectCommonRoute4Start",
        },
        "CommonRoute5": {
            "teleport": "SceneEnterWorldWulingMarkerStone1",
            "map_name": "map02_lv004",
            "collect_items": ["蓬茸锦草"],
            "waypoints": [
                (497.6, 210.3), (425.1, 210.8), (416.3, 212.0),  # GotoFindLine1
                (418.7, 210.8), (417.8, 216.1),  # GotoFind1
                (418.7, 210.8), (414.4, 213.4),  # GotoFind2
                (418.7, 210.8), (414.3, 212.5),  # GotoFind3
                (418.7, 210.8), (413.1, 210.3),  # GotoFind4
            ],
            "fallback_entry": "AutoCollectCommonRoute5Start",
        },
        "CommonRoute6": {
            "teleport": "SceneEnterWorldWulingMarkerStone3",
            "map_name": "map02_lv004",
            "collect_items": ["琼叶参"],
            "waypoints": [
                (607.5, 326.9), (607.5, 327.0), (610.0, 326.9), (611.3, 325.8),
                (628.7, 325.7), (632.5, 324.5), (635.0, 327.0), (640.0, 338.2),
                (640.0, 340.7), (641.2, 342.0), (641.3, 345.7), (643.8, 364.5),
                (645.0, 367.0), (645.0, 377.0), (646.2, 379.5), (646.3, 410.8),
                (647.5, 413.3), (647.5, 417.0), (601.7, 419.4), (601.9, 433.7),
                (556.5, 433.9), (533.1, 445.0), (521.3, 452.2), (524.5, 459.9),
                (513.6, 466.4), (516.6, 473.8), (509.9, 477.5), (511.6, 481.3),
                (499.5, 487.2), (481.9, 478.2), (462.3, 475.1),  # GotoFindLine1
                (461.2, 475.8),  # GotoFind1
                (461.2, 477.0),  # GotoFind2
                (476.2, 490.7), (472.2, 484.3),  # GotoFind3
                (476.2, 490.7), (471.6, 484.7),  # GotoFind4
            ],
            "fallback_entry": "AutoCollectCommonRoute6Start",
        },
        "CommonRoute7": {
            "teleport": "SceneEnterWorldWulingMarkerStone1",
            "map_name": "map02_lv004",
            "collect_items": ["荆刺芽针"],
            "waypoints": [
                (497.6, 210.3), (425.1, 210.8), (416.3, 212.0),  # GotoFindLine1
                (415.1, 205.2),  # GotoFind1
                (416.7, 208.2),  # GotoFind2
                (412.7, 209.3),  # GotoFind3
                (418.6, 214.2),  # GotoFind4
                (413.7, 211.0),  # GotoFind5
                (417.4, 215.8), (419.6, 217.5),  # GotoFind6
            ],
            "fallback_entry": "AutoCollectCommonRoute7Start",
        },
        "CommonRoute8": {
            "teleport": "SceneEnterWorldValleyIVTestArea1",
            "map_name": "map02_lv005",
            "collect_items": ["纯晶多齿叶"],
            "waypoints": [
                (385.0, 421.8), (385.0, 426.7),  # GotoFind1
                (385.0, 421.8), (385.0, 426.7),  # GotoFind2
                (385.0, 418.1), (385.0, 424.2),  # GotoFind3
                (383.3, 423.9),  # GotoFind4
                (379.3, 427.3),  # GotoFind5
                (383.8, 420.5), (382.5, 425.5),  # GotoFind6
            ],
            "fallback_entry": "AutoCollectCommonRoute8Start",
        },
    }

    # 采集成功关键词：按 F 后屏幕出现"获得 XXX"飘字或采集确认弹窗
    _COLLECT_SUCCESS_KEYWORDS = ("获得", "采集成功", "收取成功", "已采集")
    # 每条路线最多重试轮次：pipeline 路线节点执行失败后重新传送+重跑
    _AUTO_COLLECT_MAX_ROUNDS = 5
    # 大世界特征文字：EnterGame 模板匹配过时时，用 OCR 检测这些关键词作为备用判据
    # （主城3D场景的左侧/右侧菜单固定会显示这些按钮文字）
    # 注意：不包含 "寻访" —— 签到弹窗文本 "踞渊北眺寻访凭证*5" 会误匹配
    # 要求至少命中 2 个关键词，避免单一关键词偶发误匹配
    _IN_WORLD_OCR_KEYWORDS = (
        # 主城菜单栏关键词
        "地区建设", "干员", "采购中心", "行动手册",
        "通行证", "好友", "装备加工", "编队", "百科", "档案库",
        # 大世界（野外）通用关键词：角色在野外时主城菜单不可见，
        # 但 "探索" 按钮和任务追踪文字始终存在
        "探索",
    )
    _IN_WORLD_OCR_MIN_HITS = 2

    def _verify_collect_success(self, serial: Optional[str]) -> tuple[bool, str]:
        """通过 OCR 检测采集是否成功。

        采集成功时屏幕右侧出现"获得 XXX"飘字，或中间出现采集确认对话框。
        通过 scene.elements OCR 检测特征关键词判断是否真正采集到作物。

        Returns:
            (success, ocr_text_preview): success 为 True 表示检测到采集成功特征
        """
        # 等待飘字/弹窗动画完成
        time.sleep(1.5)
        ocr_result = self.execute(
            "scene.elements",
            {
                "serial": serial,
                "enable_ocr": True,
                "enable_template": False,
                "enable_color": False,
            },
        )
        elements: List[Any] = []
        if isinstance(ocr_result, dict) and ocr_result.get("status") == "success":
            elements = ocr_result.get("elements", [])
        text = "".join(
            e.get("label", "") for e in elements if isinstance(e, dict)
        )
        matched = [kw for kw in self._COLLECT_SUCCESS_KEYWORDS if kw in text]
        return (bool(matched), text[:300])

    def _auto_collect_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """采集任务编排器（全智能分类）：VLM 携带路线信息+标志物自主导航。

        把路线坐标(waypoints)与采集物名称(collect_items 标志物)作为上下文
        提供给 VLM，由 VLM 综合截图+小地图+路线信息+标志物名称自主决定导航
        动作。这是用户要求的"将路线信息与标志物给予VLM，由其完成导航"。

        流程：
        - MaaFW pipeline 负责传送（SceneEnterWorld*）和背包整理（StashBackpackMain）
        - VLM 导航：nav3.walk_collect 沿 waypoints 路线步行，识别 collect_items
          标志物，到达采集点后按 F 交互
        - 采集验证：OCR 检测"获得/采集成功/收取成功/已采集"关键词
        - 多轮重试：失败后重新传送 + 重跑 VLM 导航，直至采集验证成功或轮次耗尽
        - 无 waypoints 的路线(Route1/3/6 仅有 MapNavigateAction)回退到 pipeline
        """
        options = params.get("options") or {}
        client_version = options.get("ClientVersion", "CN")
        serial = params.get("serial")
        runtime = self.maaend(serial)
        if not self._ensure_maaend_ready(runtime):
            return {
                "status": "error",
                "command": "auto.collect",
                "flow": "auto_collect",
                "options": options,
                "maaend_connected": False,
            }
        if not self._ensure_game_in_world(runtime, serial, client_version):
            return {
                "status": "error",
                "command": "auto.collect",
                "flow": "auto_collect",
                "options": options,
                "maaend_connected": self.connected,
                "message": "启动游戏或等待进入大世界失败",
            }

        # 启动 scrcpy 图像通道（VLM 截图 + 采集验证 OCR 依赖）
        android = self.android(serial)
        try:
            result = android.start_scrcpy(serial=serial)
            if isinstance(result, dict) and result.get("error"):
                self._logger.warning(
                    LogCategory.MAIN, "scrcpy 启动失败，VLM 导航/采集验证不可用",
                    error=result["error"], serial=serial,
                )
            else:
                self._logger.info(LogCategory.MAIN, "scrcpy 图像通道已就绪", serial=serial)
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "scrcpy 启动异常", error=str(exc), serial=serial)

        # 预热 LLM（VLM 导航依赖）。云端模式 _CloudLlmRuntimeStub.ready=True 直接返回。
        if not self.warmup_llm():
            self._logger.warning(
                LogCategory.MAIN, "LLM 预热失败，VLM 导航将不可用，回退到 pipeline 模式",
            )

        # 解析选项：选定路线（含专属 Route + 通用 CommonRoute）
        routes_raw = options.get("AutoCollectRoutes", [])
        if isinstance(routes_raw, str):
            routes_raw = [routes_raw]
        common_routes_raw = options.get("AutoCollectCommonRoutes", [])
        if isinstance(common_routes_raw, str):
            common_routes_raw = [common_routes_raw]
        # 保持 Route1-14 在前、CommonRoute1-8 在后
        selected_routes = list(routes_raw) + list(common_routes_raw)
        if not selected_routes:
            selected_routes = list(self._AUTO_COLLECT_ROUTE_INFO.keys())

        # 解析背包整理开关：AutoCollectStashBackpackSubTask 为 switch，值为 Yes/No
        stash_enabled = options.get("AutoCollectStashBackpackSubTask", "No") == "Yes"

        # 解析 VLM 步数上限（可选，默认 60 步）
        try:
            vlm_max_steps = int(options.get("AutoCollectVlmMaxStepsValue", 60))
        except (TypeError, ValueError):
            vlm_max_steps = 60

        max_rounds = self._AUTO_COLLECT_MAX_ROUNDS

        self._logger.info(
            LogCategory.MAIN, "采集任务开始（VLM 路线+标志物导航模式）",
            routes=selected_routes, stash_enabled=stash_enabled,
            max_rounds=max_rounds, vlm_max_steps=vlm_max_steps,
        )

        # 前置背包整理（防止采集过程中背包满）
        if stash_enabled:
            self._logger.info(LogCategory.MAIN, "前置背包整理")
            try:
                if not runtime.run_pipeline("StashBackpackMain", {}):
                    self._logger.warning(LogCategory.MAIN, "StashBackpackMain 前置执行失败")
            except Exception as exc:
                self._logger.warning(LogCategory.MAIN, "StashBackpackMain 异常", error=str(exc))

        # 逐路线执行：多轮重试 [传送 → VLM导航+采集 → 采集验证] 直至成功
        results: List[Dict[str, Any]] = []
        overall_ok = True
        for route in selected_routes:
            if route not in self._AUTO_COLLECT_ROUTE_INFO:
                self._logger.warning(
                    LogCategory.MAIN, "未知采集路线，跳过", route=route,
                )
                results.append({"route": route, "status": "skipped", "reason": "unknown_route"})
                overall_ok = False
                continue

            info = self._AUTO_COLLECT_ROUTE_INFO[route]
            teleport_node = info["teleport"]
            map_name = info["map_name"]
            collect_items = info["collect_items"]
            waypoints = info["waypoints"]
            fallback_entry = info["fallback_entry"]
            use_vlm = bool(waypoints)  # 无 waypoints 的路线回退到 pipeline

            self._logger.info(
                LogCategory.MAIN, "采集路线开始", route=route,
                teleport=teleport_node, map=map_name,
                collect_items=collect_items, waypoints=len(waypoints),
                mode="vlm" if use_vlm else "pipeline_fallback",
                max_rounds=max_rounds,
            )

            # 多轮重试：传送 → VLM导航+采集 / pipeline回退 → 采集验证
            route_success = False
            attempts: List[Dict[str, Any]] = []
            for attempt_idx in range(1, max_rounds + 1):
                self._logger.info(
                    LogCategory.MAIN, "采集尝试轮次",
                    route=route, attempt=attempt_idx, max_rounds=max_rounds,
                )

                # 1. 传送（VLM 驱动：SceneEnterMap* + VLM 点击传送点）
                # pipeline 只负责进入地图视图，VLM 负责点击传送点完成实际传送。
                # 传送失败时不继续 VLM 导航（避免在错误地图转圈），直接重试。
                target_area = self._teleport_node_to_area(teleport_node)
                teleport_ok = False
                if target_area and target_area in self._TASK_AREA_MAP_NODE:
                    tp_result = self._vlm_teleport_to_area(
                        android, serial, target_area, runtime=runtime,
                    )
                    teleport_ok = tp_result.get("ok", False)
                    self._logger.info(
                        LogCategory.MAIN, "VLM 传送执行结束",
                        route=route, attempt=attempt_idx,
                        teleport=teleport_node, target_area=target_area,
                        teleport_ok=teleport_ok, reason=tp_result.get("reason"),
                    )
                    # 等待传送加载完成
                    time.sleep(3.0)
                else:
                    self._logger.warning(
                        LogCategory.MAIN, "无法映射传送节点到区域名",
                        route=route, teleport=teleport_node,
                    )

                # 传送失败：清理界面后直接进入下一轮重试（不继续 VLM 导航）
                # 清理策略：多次 BACK 关闭地图/弹窗/任务追踪提示，回到主城3D场景
                # 这样下一轮传送能从干净状态开始（InMapAny 模板匹配不被任务追踪提示干扰）
                if not teleport_ok:
                    self._logger.warning(
                        LogCategory.MAIN, "传送失败，清理界面后准备重试",
                        route=route, attempt=attempt_idx,
                    )
                    try:
                        # 多次 BACK 确保关闭地图界面、弹窗、任务追踪提示
                        for back_idx in range(3):
                            self.android(serial).keyevent("KEYCODE_BACK")
                            time.sleep(0.8)
                        # 额外等待界面稳定
                        time.sleep(1.5)
                    except Exception:
                        pass
                    attempts.append({
                        "attempt": attempt_idx,
                        "teleport_ok": False,
                        "nav_ok": False,
                        "collected": False,
                        "ocr_preview": "",
                        "nav_detail": [],
                        "skip_reason": "teleport_failed",
                    })
                    continue

                # 2. 导航 + 采集（仅传送成功后执行）
                nav_ok = False
                nav_detail: Dict[str, Any] = {}
                if use_vlm:
                    # VLM 导航：把 waypoints + collect_items 作为上下文给 VLM
                    # VLM 自主视角平视环绕 360 度找指引标识赶路，不依赖固定坐标
                    try:
                        nav = self.navigator()
                        nav_result = nav.to_collect_vlm(
                            waypoints=waypoints,
                            collect_items=collect_items,
                            map_name=map_name,
                            llm_client=self._llm_client_instance,
                            max_steps=vlm_max_steps,
                            keyevent_fn=self._vlm_keyevent,
                        )
                        nav_ok = isinstance(nav_result, dict) and nav_result.get("status") == "success"
                        nav_detail = nav_result
                        self._logger.info(
                            LogCategory.MAIN, "VLM 导航执行结束",
                            route=route, attempt=attempt_idx,
                            nav_ok=nav_ok,
                            steps=nav_result.get("steps_taken") if isinstance(nav_result, dict) else None,
                            final_distance=nav_result.get("final_distance_to_target") if isinstance(nav_result, dict) else None,
                        )
                    except Exception as exc:
                        self._logger.error(
                            LogCategory.MAIN, "VLM 导航异常",
                            route=route, attempt=attempt_idx, error=str(exc),
                        )
                        nav_detail = {"status": "error", "message": str(exc)}
                else:
                    # 无 waypoints 路线回退：执行 pipeline 路线节点链
                    # Start 节点默认 enabled:false，用 pipeline_override 强制启用
                    try:
                        nav_ok = runtime.run_pipeline(
                            fallback_entry,
                            {fallback_entry: {"enabled": True}},
                        )
                        self._logger.info(
                            LogCategory.MAIN, "pipeline 回退执行结束",
                            route=route, attempt=attempt_idx,
                            entry=fallback_entry, pipeline_ok=nav_ok,
                        )
                    except Exception as exc:
                        self._logger.error(
                            LogCategory.MAIN, "pipeline 回退异常",
                            route=route, attempt=attempt_idx, error=str(exc),
                        )

                # 3. 采集验证：OCR 检测"获得"等关键词
                collected, ocr_preview = self._verify_collect_success(serial)
                self._logger.info(
                    LogCategory.MAIN, "采集验证结果",
                    route=route, attempt=attempt_idx,
                    collected=collected, ocr_preview=ocr_preview[:120],
                )

                attempts.append({
                    "attempt": attempt_idx,
                    "teleport_ok": teleport_ok,
                    "nav_ok": nav_ok,
                    "collected": collected,
                    "ocr_preview": ocr_preview,
                    "nav_detail": nav_detail.get("history", []) if isinstance(nav_detail, dict) else [],
                })

                # 4. 关闭可能的弹窗（无论成功失败都按 BACK 清理界面）
                try:
                    self.android(serial).keyevent("KEYCODE_BACK")
                    time.sleep(0.5)
                except Exception:
                    pass

                if collected:
                    route_success = True
                    self._logger.info(
                        LogCategory.MAIN, "采集成功",
                        route=route, attempt=attempt_idx,
                    )
                    break

                # 5. 未采集成功：进入下一轮重试（重新传送 + 重跑 VLM 导航）
                self._logger.warning(
                    LogCategory.MAIN, "采集未成功，准备重试",
                    route=route, attempt=attempt_idx,
                    remaining=max_rounds - attempt_idx,
                )

            route_status = "success" if route_success else "failed"
            results.append({
                "route": route,
                "status": route_status,
                "mode": "vlm" if use_vlm else "pipeline_fallback",
                "teleport": teleport_node,
                "map_name": map_name,
                "collect_items": collect_items,
                "waypoints_count": len(waypoints),
                "attempts": attempts,
                "rounds_used": len(attempts),
            })
            if not route_success:
                overall_ok = False
                self._logger.warning(
                    LogCategory.MAIN, "采集路线最终失败",
                    route=route, rounds=len(attempts),
                )

        # 后置背包整理（清理采集所得）
        if stash_enabled:
            self._logger.info(LogCategory.MAIN, "后置背包整理")
            try:
                if not runtime.run_pipeline("StashBackpackMain", {}):
                    self._logger.warning(LogCategory.MAIN, "StashBackpackMain 后置执行失败")
            except Exception as exc:
                self._logger.warning(LogCategory.MAIN, "StashBackpackMain 异常", error=str(exc))

        # 汇总
        success_count = sum(1 for r in results if r.get("status") == "success")
        failed_routes = [r["route"] for r in results if r.get("status") != "success"]
        self._logger.info(
            LogCategory.MAIN, "采集任务结束",
            overall_ok=overall_ok, routes=len(results),
            success=success_count, failed=len(failed_routes),
            failed_routes=failed_routes,
        )

        return {
            "status": "success" if overall_ok else "error",
            "command": "auto.collect",
            "flow": "auto_collect",
            "options": options,
            "results": results,
            "summary": {
                "total_routes": len(results),
                "success_count": success_count,
                "failed_routes": failed_routes,
            },
            "maaend_connected": self.connected,
        }

    def _is_task_list_page(self, serial: Optional[str]) -> bool:
        """检查当前画面是否为任务列表页。

        判据：OCR 文本中包含任务列表页的标志性元素。原先仅检查 "//任务" 标题，
        但实测任务列表页的 "//任务" 标题 OCR 识别不稳定（常被识别为其他文本）。
        现改为多特征判据：只要出现以下任一组合即判定为任务列表页：
        - 分类标签 "进行中" + "ALL"（任务列表页左侧分类栏）
        - "停止追踪" / "开始追踪" + "任务奖励"（任务条目操作按钮）
        - "//任务" 标题（保留原判据作为兜底）
        """
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
        # 原 "//任务" 标题判据（保留兜底）
        if "//任务" in check_text:
            return True
        # 多特征判据：分类标签组合
        has_jinxingzhong = "进行中" in check_text
        has_all = "ALL" in check_text
        if has_jinxingzhong and has_all:
            return True
        # 任务操作按钮组合
        has_tracking = "停止追踪" in check_text or "开始追踪" in check_text
        has_reward = "任务奖励" in check_text
        if has_tracking and has_reward:
            return True
        return False

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
            android = self.android(serial)
            # VLM 导航/交互后可能停留在 NPC 对话、消息、地图等覆盖层上，
            # 先用 BACK 反复关闭覆盖层回到大世界。
            if not self._verify_in_world_by_ocr(serial):
                self._logger.info(LogCategory.MAIN, "检测到不在大世界，尝试关闭覆盖层")
                if not self._close_overlays_return_to_world(android, serial):
                    if not self._force_restart_game(android, serial, runtime, client_version):
                        return {
                            "status": "error",
                            "command": "readtask.run",
                            "flow": "read_task_list",
                            "options": options,
                            "maaend_connected": self.connected,
                            "message": "启动游戏或等待进入大世界失败",
                        }
                else:
                    # 二次验证：_close_overlays_return_to_world 可能误判
                    if not self._verify_in_world_by_ocr(serial):
                        self._logger.warning(
                            LogCategory.MAIN,
                            "覆盖层关闭返回True但OCR仍检测不到大世界特征，强制重启",
                        )
                        if not self._force_restart_game(android, serial, runtime, client_version):
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

        # 结构化分类（紧急/重要/次要）
        structured = formatted.get("structured", {})

        return {
            "status": "success",
            "command": "readtask.run",
            "flow": "read_task_list",
            "options": options,
            "raw_ocr_count": len(all_elements),
            "formatted_line_count": len(formatted["lines"]),
            "formatted_lines": formatted["lines"],
            "structured_tasks": structured,
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

        # 结构化分类解析：从行中提取紧急/重要/次要任务
        structured = IstinaRuntime._parse_task_categories(rows)

        return {
            "lines": lines,
            "element_count": len(deduped),
            "row_count": len(rows),
            "structured": structured,
        }

    @staticmethod
    def _parse_task_categories(
        rows: List[List[Dict[str, Any]]],
        area_names: Optional[set] = None,
        ui_labels: Optional[set] = None,
    ) -> Dict[str, List[str]]:
        """从任务列表行中解析紧急、重要、次要三类任务。

        策略：对每一行检测是否包含分类标记（紧急/紧要/重要/次要/!!!等），
        将该行中符合任务名特征的文本归入对应分类。
        """
        import re

        if area_names is None:
            area_names = {
                "枢纽区", "供能高地", "源矿源区", "矿脉源区", "源石研究园",
                "源石科学园", "谷地通道", "阿伯莉采石场", "武陵城", "清波寨",
                "景玉谷", "界碑", "试炼区", "藏剑谷", "四号谷地", "塔卫二",
                "矿区营地", "谷地要塞", "滑索", "采石场", "阿伯莉", "首墩",
                "望楼", "天王坪", "清波寨外寨", "基地", "帝江号",
                "O.M.V.帝江号", "OMV帝江号", "MV帝江号",
            }
        if ui_labels is None:
            ui_labels = {
                "//任务", "进行中", "ALL", "区", "X", "×",
                "开始追踪", "停止追踪", "UID", "ms", "口",
                "行动结束，请自由探索塔卫二", "与其他任务冲突",
                "新区域", "新功能", "任务奖励",
            }

        result: Dict[str, List[str]] = {"urgent": [], "important": [], "normal": []}

        def _classify_label(label: str) -> Optional[str]:
            text = label.strip()
            if "紧急" in text or "紧要" in text:
                return "urgent"
            if "重要" in text:
                return "important"
            if "次要" in text:
                return "normal"
            if re.search(r"!{2,3}", text) or text == "!":
                return "urgent"
            return None

        def _is_task_name(label: str) -> bool:
            text = label.strip()
            if not text or len(text) < 2:
                return False
            if text in ui_labels or text in area_names:
                return False
            if re.fullmatch(r"\d{1,3}", text):
                return False
            if re.fullmatch(r"[!\.\×xXQq口日○〇]+", text):
                return False
            if text in ("紧急", "紧要", "重要", "次要"):
                return False
            return True

        for row in rows:
            row_labels = [str(e.get("label", "")).strip() for e in row]
            row_categories: set = set()
            for label in row_labels:
                cat = _classify_label(label)
                if cat:
                    row_categories.add(cat)
            task_names = [label for label in row_labels if _is_task_name(label)]
            for cat in row_categories:
                result[cat].extend(task_names)

        # 去重并保持顺序
        for cat in result:
            seen: set = set()
            unique: List[str] = []
            for name in result[cat]:
                if name not in seen:
                    seen.add(name)
                    unique.append(name)
            result[cat] = unique

        return result

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
    # 经 TaskIcon.png 模板匹配（匹配值 0.866）+ 实测点击验证确认：
    # 点击此坐标能稳定打开任务列表页（OCR 可见 "进行中"/"ALL"/"停止追踪" 等分类标签和操作按钮）。
    # 原 (35, 155) 坐标偏上 26px，点击会触发地图界面或空白区域，无法打开任务列表。
    _TASK_LIST_ICON_COORD: Tuple[int, int] = (37, 181)

    # 任务列表 OCR 中属于 UI 控件而非任务名的文本集合
    _TASK_LIST_UI_LABELS: frozenset = frozenset({
        "//任务", "进行中", "ALL", "紧要", "重要", "次要", "区",
        "X", "×", "开始追踪", "停止追踪", "UID", "ms", "口",
    })

    # VLM 任务列表解析系统提示词
    _VLM_TASKLIST_SYSTEM = (
        "你是一个游戏任务列表解析助手。你的工作是从游戏任务列表截图中提取任务名称。"
        "只输出任务名称，每行一个，不要输出任何其他内容。"
    )
    _VLM_TASKLIST_PROMPT = (
        "请仔细查看这张任务列表截图。列出所有可见的任务名称。\n"
        "要求：\n"
        "1. 每行一个任务名称，只输出任务名称本身\n"
        "2. 不要输出任务描述、区域名、奖励、进度等附加信息\n"
        "3. 不要输出 UI 按钮文字如『开始追踪』、『停止追踪』、『进行中』等\n"
        "4. 保留任务名称的完整前缀（如『探索任务』、『据点建设』等）\n"
        "5. 不要输出数字编号、等级、坐标等\n"
    )

    def _vlm_read_task_names(self, serial: Optional[str]) -> set:
        """用 VLM 从当前任务列表截图提取任务名称。

        相比 OCR + 启发式解析，VLM 能更准确地理解任务列表 UI 结构，
        产出干净一致的任务名称，避免 OCR 碎片导致的名称不一致问题。

        Returns:
            任务名称字符串集合。如果 VLM 调用失败则返回空集合。
        """
        import base64

        try:
            png_data = self.execute("screenshot", {"serial": serial})
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "VLM 任务列表截图失败", error=str(exc))
            return set()
        if not png_data:
            self._logger.warning(LogCategory.MAIN, "VLM 任务列表截图为空")
            return set()

        img_b64 = base64.b64encode(png_data).decode("ascii")
        try:
            client = self._llm_client_instance
            reply = client.chat(
                self._VLM_TASKLIST_PROMPT,
                system=self._VLM_TASKLIST_SYSTEM,
                image=img_b64,
                image_mime_type="image/png",
                max_tokens=800,
                temperature=0.1,
                timeout=1800.0,
                chat_template_kwargs={"enable_thinking": False},
            )
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "VLM 任务列表解析失败", error=str(exc))
            return set()

        # 解析 VLM 回复：每行一个任务名
        names: set = set()
        for line in reply.splitlines():
            name = line.strip()
            # 过滤空行、编号前缀、UI 文字
            if not name:
                continue
            # 去掉可能的编号前缀 "1. " "2) " 等
            import re
            name = re.sub(r"^\d+[\.\)]\s*", "", name)
            # 过滤已知 UI 文字
            if name in self._TASK_LIST_UI_LABELS:
                continue
            # 过滤过短或纯数字的噪声
            if len(name) < 2:
                continue
            if re.fullmatch(r"\d+", name):
                continue
            names.add(name)
        self._logger.info(
            LogCategory.MAIN, "VLM 任务列表解析完成",
            count=len(names), names=sorted(names),
        )
        return names

    # VLM 任务交互系统提示词：VLM 决策每一步交互动作（替代盲按 F）
    # 关键设计：单次调用（无对话历史），仅发送当前截图+任务名+可用动作集，
    # VLM 输出 JSON 决策 → 执行 → 下一帧截图再次决策。这样不会累积上下文，
    # 满足用户"不超出上下文"的要求。

    # 任务目标区域 → 传送 pipeline 节点映射表。
    # 当 VLM 决策 click_text "前往传送"时，从任务名提取目标区域，
    # 通过此表查找对应的 SceneEnterWorld* pipeline 节点直接传送，
    # 避免在复杂的传送地图 UI 中反复点击无效文字。
    _TASK_AREA_TELEPORT_MAP: Dict[str, str] = {
        # 四号谷地区域
        "枢纽区": "SceneEnterWorldValleyIVTheHub1",
        "供能高地": "SceneEnterWorldValleyIVPowerPlateau1",
        "源矿源区": "SceneEnterWorldValleyIVOriginLodespring1",
        "源石科学园": "SceneEnterWorldValleyIVOriginiumSciencePark1",
        # 武陵区域
        "武陵城": "SceneEnterWorldWulingWulingCity1",
        "清波寨": "SceneEnterWorldWulingQingboStockade1",
        "景玉谷": "SceneEnterWorldWulingJingyuValley1",
        "界碑": "SceneEnterWorldWulingMarkerStone1",
        "试炼区": "SceneEnterWorldWulingTestArea1",
        "藏剑谷": "SceneEnterWorldWulingSwordVaultDale1",
    }

    # 任务目标区域 → SceneEnterMap* pipeline 节点映射表。
    # 由于 MaaFW 的 [JumpBack][Anchor] 语法存在 bug（把 anchor key 当作
    # node name 查找，跳过 anchor map 查找），SceneEnterWorld* 系列传送
    # 节点（依赖 anchor 机制做多步地图滑动）全部失效。改用 SceneEnterMap*
    # 系列节点（仅依赖简单 [JumpBack]SceneEnterMapAny，不使用 anchor）进入
    # 目标区域地图视图，再由 VLM 识别并点击地图上的传送点完成实际传送。
    _TASK_AREA_MAP_NODE: Dict[str, str] = {
        # 四号谷地区域
        "枢纽区": "SceneEnterMapValleyIVTheHub",
        "供能高地": "SceneEnterMapValleyIVPowerPlateau",
        "源矿源区": "SceneEnterMapValleyIVOriginLodespring",
        "源石科学园": "SceneEnterMapValleyIVOriginiumSciencePark",
        "谷地通道": "SceneEnterMapValleyIVValleyPass",
        "阿伯莉采石场": "SceneEnterMapValleyIVAburreyQuarry",
        # 武陵区域
        "武陵城": "SceneEnterMapWulingWulingCity",
        "清波寨": "SceneEnterMapWulingQingboStockade",
        "景玉谷": "SceneEnterMapWulingJingyuValley",
        "界碑": "SceneEnterMapWulingMarkerStone",
        "试炼区": "SceneEnterMapWulingTestArea",
        "藏剑谷": "SceneEnterMapWulingSwordVaultDale",
    }

    # 新增：SceneEnterWorld* 节点（无数字后缀，不依赖 anchor，有专用 EnterTeleport 节点）
    # 这些节点会直接进入目标区域大世界（地图视图 + 点击传送点 + 确认传送），
    # 比 SceneEnterMap* + 通用 EnterTeleport 更可靠。
    _TASK_AREA_WORLD_NODE: Dict[str, str] = {
        # 四号谷地区域（均有专用 EnterTeleport 节点）
        "枢纽区": "SceneEnterWorldValleyIVTheHub",
        "供能高地": "SceneEnterWorldValleyIVPowerPlateau",
        "矿脉源区": "SceneEnterWorldValleyIVOriginLodespring",
        "源矿源区": "SceneEnterWorldValleyIVOriginLodespring",  # 别名
        "源石研究园": "SceneEnterWorldValleyIVOriginiumSciencePark",
        "源石科学园": "SceneEnterWorldValleyIVOriginiumSciencePark",  # 别名
        "谷地通道": "SceneEnterWorldValleyIVValleyPass",
        "阿伯莉采石场": "SceneEnterWorldValleyIVAburreyQuarry",
        # 武陵区域（均有专用 EnterTeleport 节点）
        "景玉谷": "SceneEnterWorldWulingJingyuValley",
        "清波寨": "SceneEnterWorldWulingQingboStockade",
        "藏剑谷": "SceneEnterWorldWulingSwordVaultDale",
    }

    # 专用 EnterTeleport 节点（在正确的地图视图中点击传送点进入大世界）
    # 用于 _vlm_teleport_to_area 的兜底流程：先 SceneEnterMap* 进入正确地图视图，
    # 再用专用 EnterTeleport 点击传送点（比通用 __ScenePrivateMapEnterTeleport 更可靠）
    _TASK_AREA_ENTER_TELEPORT_NODE: Dict[str, str] = {
        # 四号谷地
        "枢纽区": "__ScenePrivateMapValleyIVTheHubEnterTeleport",
        "供能高地": "__ScenePrivateMapValleyIVPowerPlateauEnterTeleport",
        "矿脉源区": "__ScenePrivateMapValleyIVOriginLodespringEnterTeleport",
        "源矿源区": "__ScenePrivateMapValleyIVOriginLodespringEnterTeleport",  # 别名
        "源石研究园": "__ScenePrivateMapValleyIVOriginiumScienceParkEnterTeleport",
        "源石科学园": "__ScenePrivateMapValleyIVOriginiumScienceParkEnterTeleport",  # 别名
        "谷地通道": "__ScenePrivateMapValleyIVValleyPassEnterTeleport",
        "阿伯莉采石场": "__ScenePrivateMapValleyIVAburreyQuarryEnterTeleport",
        # 武陵
        "景玉谷": "__ScenePrivateMapWulingJingyuValleyEnterTeleport",
        "清波寨": "__ScenePrivateMapWulingQingboStockadeEnterTeleport",
        "藏剑谷": "__ScenePrivateMapWulingSwordVaultDaleEnterTeleport",
    }

    # 区域验证关键词：传送成功后，大世界 OCR 应包含的目标区域特征词
    # 用于检测 SceneEnterWorld* 的假阳性（pipeline 返回 True 但实际未切换区域）
    # 注：大世界 OCR 可能不直接显示区域名，因此用区域特有标志物/地标
    _TASK_AREA_VERIFY_KEYWORDS: Dict[str, List[str]] = {
        # 四号谷地：大世界通常显示 "四号谷地" 或子区域名
        "枢纽区": ["四号谷地", "枢纽区"],
        "供能高地": ["四号谷地", "供能高地"],
        "矿脉源区": ["四号谷地", "矿脉源区", "矿区营地"],
        "源矿源区": ["四号谷地", "矿脉源区", "矿区营地"],
        "源石研究园": ["四号谷地", "源石", "研究"],
        "源石科学园": ["四号谷地", "源石", "研究"],
        "谷地通道": ["四号谷地", "谷地通道", "谷地要塞", "滑索"],
        "阿伯莉采石场": ["四号谷地", "采石场", "阿伯莉"],
        # 武陵：大世界通常显示 "武陵" 或子区域名
        "景玉谷": ["武陵", "景玉谷"],
        "清波寨": ["武陵", "清波寨"],
        "藏剑谷": ["武陵", "藏剑谷"],
        # 界碑区域（首墩/望楼）：游戏内子区域名包括 "首墩"、"望楼" 等，
        # 界碑本身是地图传送点，但子区域名常出现在大世界 HUD。
        "界碑": ["武陵", "首墩", "望楼", "蓄水站"],
    }

    # 武陵区域总览视图中，各子区域的点击中心坐标（基于 1280x720 基准分辨率）。
    # 当 SceneEnterMapWuling* 的 TemplateMatch (MapOverviewWulingChoose.png) 识别失败时，
    # 通过 android.tap() 直接点击目标子区域坐标切换地图。
    # 注：pipeline 中的坐标（如清波寨 [663, 293, 96, 94]→中心(711,340)）已过时，
    # 实际图标位置通过网格化点击测试确定。
    _WULING_OVERVIEW_TAP_COORDS: Dict[str, Tuple[int, int]] = {
        "景玉谷": (388, 491),       # OCR 检测到的景玉谷名称位置（默认选中）
        "清波寨": (600, 400),       # 网格化点击测试确认
        "藏剑谷": (869, 576),       # 待验证（使用 pipeline 坐标中心）
        "武陵城": (520, 180),       # pipeline target [470, 140, 100, 80]
        "界碑": (311, 334),         # pipeline target [277, 290, 69, 89] (首墩)
        "试验园区": (741, 168),     # pipeline target [699, 133, 84, 71]
    }

    _VLM_TASK_INTERACT_SYSTEM = (
        "你是一个游戏任务交互助手。给定当前游戏截图和任务名称，"
        "你的工作是决定下一步交互动作以推进任务完成。"
        "只输出一个 JSON 对象，不要输出任何其他内容。"
    )
    _VLM_TASK_INTERACT_PROMPT = (
        "当前任务：{task}\n"
        "目标区域：{area}\n\n"
        "请分析截图，决定下一步动作。可选动作（输出 JSON）：\n"
        '{{"action": "press_f"}} - 按 F 键推进对话/交互（NPC 对话、拾取、确认、与 NPC/物体交互等）\n'
        '{{"action": "click_text", "text": "按钮文字"}} - 点击屏幕上明确的 UI 按钮或地点名称\n'
        '{{"action": "wait"}} - 等待动画/加载/传送完成（不要做任何操作）\n'
        '{{"action": "task_complete"}} - 任务已完成（看到"任务完成"、"获得奖励"、结算界面、任务进度更新等）\n'
        '{{"action": "no_action"}} - 屏幕空闲无交互可用，无法推进\n\n'
        "判断规则（按优先级）：\n"
        "1. 如果看到任务完成/获得奖励/结算界面 → task_complete\n"
        "2. 如果是 NPC 对话/剧情界面（有文字框、头像、继续提示） → press_f 推进\n"
        "3. 如果在大世界看见『前往传送』按钮（表示需要传送到其他区域） → click_text 文字为『前往传送』\n"
        "4. 如果在传送地图界面（看到多个地点名+传送标签）：\n"
        "   - 在屏幕中找到目标区域的地点名称（如『枢纽区』『供能高地』『阿伯莉采石场』『四号谷地』等）\n"
        "   - click_text 文字填入该地点名称（如『枢纽区』），点击该地点条目\n"
        "   - 不要点击页面顶部的『传送』标题文字\n"
        "   - 不要点击其他不相关地点的『传送』标签\n"
        "5. 如果选中地点后弹出确认对话框（有『传送』确认按钮） → click_text 文字为『传送』\n"
        "6. 如果在加载/动画/传送过渡中（屏幕黑、转圈、进度条） → wait\n"
        "7. 如果在大世界看见明确的交互按钮（如『交谈』『拾取』『互动』等文字按钮） → click_text 文字为该按钮文字\n"
        "8. 如果在大世界看见 NPC/任务标记/光柱/箭头但无交互按钮 → no_action（角色还未足够靠近，需重新导航）\n"
        "9. 仅当大世界完全空闲、无任何 NPC/标记/提示且多次无变化 → no_action\n\n"
        "重要规则：\n"
        "- 在传送地图界面，必须点击目标『地点名称』而非『传送』二字\n"
        "- 仅当弹出传送确认对话框时才点击『传送』确认按钮\n"
        "- 大世界中只有看到明确的交互按钮（如『交谈』）才推进交互，否则 no_action\n"
        "- 看到传送动画/地图加载 → wait，不要点击\n"
        "- 任务追踪面板上的任务目标描述文字（如『前往枢纽区，与希金斯交谈』『前往清波寨完成』）不是按钮，不要点击\n"
        "- 只有显式的 UI 按钮（如『前往传送』『传送』『确认』『取消』『交谈』『拾取』）或传送地图界面上的地点条目才可点击\n\n"
        "只输出 JSON，例如：\n"
        '{{"action": "press_f"}}\n'
        '{{"action": "click_text", "text": "前往传送"}}\n'
        '{{"action": "click_text", "text": "枢纽区"}}\n'
        '{{"action": "click_text", "text": "传送"}}\n'
        '{{"action": "click_text", "text": "交谈"}}\n'
        '{{"action": "task_complete"}}'
    )

    def _vlm_decide_interaction(self, serial: Optional[str], task_name: str) -> Dict[str, Any]:
        """用 VLM 决策当前任务交互的下一步动作。

        Returns:
            解析后的动作字典，例如 {"action": "press_f"} 或
            {"action": "click_text", "text": "确认"}。
            失败时返回 {"action": "no_action"}。
        """
        import base64
        import json as _json

        try:
            png_data = self.execute("screenshot", {"serial": serial})
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "VLM 交互截图失败", error=str(exc))
            return {"action": "no_action"}
        if not png_data:
            return {"action": "no_action"}

        # 从任务名提取目标区域提示（如 "风雨欲来·枢纽区" → "枢纽区"）
        area_hint = ""
        for sep in ("·", "·", "·", "•", "・"):
            if sep in task_name:
                area_hint = task_name.rsplit(sep, 1)[1].strip()
                break
        if not area_hint:
            area_hint = "（无明确区域提示，请从截图任务追踪信息中识别）"

        img_b64 = base64.b64encode(png_data).decode("ascii")
        prompt = self._VLM_TASK_INTERACT_PROMPT.format(task=task_name, area=area_hint)
        try:
            client = self._llm_client_instance
            reply = client.chat(
                prompt,
                system=self._VLM_TASK_INTERACT_SYSTEM,
                image=img_b64,
                image_mime_type="image/png",
                max_tokens=200,
                temperature=0.1,
                timeout=1800.0,
                chat_template_kwargs={"enable_thinking": False},
            )
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "VLM 交互决策失败", error=str(exc))
            return {"action": "no_action"}

        # 解析 JSON（兼容代码块包裹和多余文本）
        text = reply.strip()
        # 去除可能的 ```json ... ``` 包裹
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [ln for ln in lines if not ln.startswith("```")]
            text = "\n".join(lines).strip()
        # 找到第一个 { ... } JSON 对象
        m_start = text.find("{")
        m_end = text.rfind("}")
        if m_start < 0 or m_end <= m_start:
            self._logger.warning(LogCategory.MAIN, "VLM 交互回复非 JSON", reply=reply[:200])
            return {"action": "no_action"}
        try:
            decision = _json.loads(text[m_start:m_end + 1])
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "VLM 交互 JSON 解析失败", error=str(exc), raw=text[:200])
            return {"action": "no_action"}
        if not isinstance(decision, dict) or "action" not in decision:
            return {"action": "no_action"}
        # CLICK-TEXT-FILTER: VLM (qwen3.5-35b free) 经常无视提示词，反复决策
        # click_text "前往X完成"（任务追踪面板上的目标描述文字，非按钮）。
        # 提示词已明确禁止但模型仍违规，需程序化过滤。
        # 这些文字点击后无任何效果（不是 UI 按钮），但会触发"前往X 模式拦截"
        # 浪费 90s（2次点击+传送+already_in_target+rewalk 60步）。
        # 处理策略：
        # 1. 从 "前往X完成" / "前往X，与XXX交谈" 中提取地名 X
        # 2. 若 X 在 _TASK_AREA_MAP_NODE（已知传送区域），转换为 click_text X
        #    让"传送地名拦截"直接触发 VLM 传送（跳过 2 次点击要求，加快流程）
        # 3. 若 X 不在已知区域，转为 no_action（让系统更快进入 rewalk 或退出循环）
        if decision.get("action") == "click_text":
            click_text_value = str(decision.get("text", "")).strip()
            import re as _re
            goto_x_match = (
                _re.match(r'^前往(.+)完成$', click_text_value)
                or _re.match(r'^前往(.+?)，.+交谈$', click_text_value)
                or _re.match(r'^前往(.+?)，.+对话$', click_text_value)
            )
            if goto_x_match:
                extracted_area = goto_x_match.group(1).strip()
                # 检查提取的地名是否在已知传送区域列表中
                if extracted_area in self._TASK_AREA_MAP_NODE:
                    self._logger.info(
                        LogCategory.MAIN, "VLM 决策点击任务追踪文字，提取地名触发传送",
                        task=task_name, raw_text=click_text_value,
                        extracted_area=extracted_area,
                    )
                    # 转换为 click_text 地名，让后续"传送地名拦截"处理
                    return {"action": "click_text", "text": extracted_area}
                # 不在已知区域列表中，转为 no_action
                self._logger.info(
                    LogCategory.MAIN, "VLM 决策点击任务追踪文字（非按钮且非已知区域），转为 no_action",
                    task=task_name, raw_text=click_text_value,
                    extracted_area=extracted_area,
                )
                return {"action": "no_action"}
        return decision

    # SceneEnterWorld* 节点名 → 中文区域名映射（用于从 teleport 节点名推导 VLM 传送目标）。
    # 通过解析节点名（去掉 SceneEnterWorld 前缀和尾部数字）匹配区域名。
    _TELEPORT_NODE_AREA_MAP: Dict[str, str] = {
        "ValleyIVTheHub": "枢纽区",
        "ValleyIVPowerPlateau": "供能高地",
        "ValleyIVOriginLodespring": "源矿源区",
        "ValleyIVOriginiumSciencePark": "源石科学园",
        "ValleyIVValleyPass": "谷地通道",
        "ValleyIVAburreyQuarry": "阿伯莉采石场",
        "ValleyIVTestArea": "试炼区",
        "WulingWulingCity": "武陵城",
        "WulingQingboStockade": "清波寨",
        "WulingJingyuValley": "景玉谷",
        "WulingMarkerStone": "界碑",
        "WulingTestArea": "试炼区",
        "WulingSwordVaultDale": "藏剑谷",
    }

    def _teleport_node_to_area(self, teleport_node: str) -> str:
        """从 SceneEnterWorld* 节点名提取中文区域名。

        例如 SceneEnterWorldValleyIVPowerPlateau3 → 供能高地
             SceneEnterWorldWulingWulingCity5 → 武陵城
        """
        import re
        if not teleport_node:
            return ""
        # 去掉前缀 SceneEnterWorld 和尾部数字
        m = re.match(r"SceneEnterWorld(.+?)(\d*)$", teleport_node)
        if not m:
            return ""
        area_key = m.group(1)
        return self._TELEPORT_NODE_AREA_MAP.get(area_key, "")

    # VLM 驱动传送：进入目标区域地图视图后，VLM 识别传送点并点击。
    # 由于 MaaFW 的 [JumpBack][Anchor] bug 导致 SceneEnterWorld* 失效，
    # 改用 SceneEnterMap* 进入地图视图（不依赖 anchor），再由 VLM 在
    # 地图视图中点击传送点 → 确认传送 → 等待加载完成。
    _VLM_TELEPORT_SYSTEM = (
        "你是一个游戏地图传送助手。给定当前游戏截图，"
        "你的工作是决定下一步操作以传送到目标区域。"
        "只输出一个 JSON 对象，不要输出任何其他内容。"
    )
    _VLM_TELEPORT_PROMPT = (
        "目标区域：{area}\n\n"
        "请分析截图，决定下一步操作以传送到目标区域。可选动作（输出 JSON）：\n"
        '{{"action": "click_teleport", "x": 0-100, "y": 0-100}} - '
        "点击地图上的传送点图标（x/y 是 0-100 的百分比坐标，左上角为0,0）\n"
        '{{"action": "click_confirm"}} - 点击传送确认按钮（看到『传送』确认对话框时）\n'
        '{{"action": "wait"}} - 等待加载/动画/传送过渡\n'
        '{{"action": "back"}} - 按返回键（不在地图视图或需要回退）\n'
        '{{"action": "done"}} - 已传送到大世界（看到角色、HUD、任务追踪等大世界元素）\n\n'
        "判断规则：\n"
        "1. 如果在地图视图（看到地图+传送点图标）→ click_teleport 点击任意一个传送点\n"
        "2. 如果点击传送点后弹出确认对话框（有『传送』按钮）→ click_confirm\n"
        "3. 如果在传送加载中（黑屏/转圈/进度条）→ wait\n"
        "4. 如果已到达大世界（看到角色、HUD）→ done\n"
        "5. 如果不在地图视图且无法操作 → back\n\n"
        "坐标说明：x/y 都是 0-100 的百分比，例如中心是 50,50。只输出 JSON。"
    )

    def _verify_in_target_area(
        self, serial: Optional[str], target_area: str,
    ) -> bool:
        """验证当前大世界是否在目标区域。

        通过 OCR 检测大世界画面中是否包含目标区域的特征关键词。
        用于检测 SceneEnterWorld* 假阳性（pipeline 返回 True 但实际未切换区域）。
        同时验证当前确实在大世界（非地图视图/区域总览），避免在总览视图中误判。
        """
        keywords = self._TASK_AREA_VERIFY_KEYWORDS.get(target_area)
        if not keywords:
            # 无关键词定义，无法验证，假定成功
            return True
        try:
            ocr_result = self.execute(
                "scene.elements",
                {"serial": serial, "enable_ocr": True,
                 "enable_template": False, "enable_color": False},
            )
        except Exception:
            return True  # OCR 失败，不阻塞流程
        if not isinstance(ocr_result, dict) or ocr_result.get("status") != "success":
            return True
        elements = ocr_result.get("elements", [])
        labels = [str(e.get("label", "")) for e in elements if isinstance(e, dict)]
        # 先确认在大世界（非地图视图/区域总览）
        _MAP_VIEW_KEYWORDS = (
            "//四号谷地", "//武陵", "// 武陵", "标记显示管理", "取消追踪", "地区总览",
            "地区建设等级", "O.M.V.帝江号",
        )
        if any(any(kw in label for label in labels) for kw in _MAP_VIEW_KEYWORDS):
            return False  # 在地图视图/总览，不是大世界
        # 大世界特征
        # 注意：不能用简单的 "m" in label，否则 "1ms"（延迟指示）会误判为距离。
        # 使用正则要求数字与 m 之间有空格，且 m 后为词边界（排除 "1ms"/"m/s"）。
        import re
        _DISTANCE_RE = re.compile(r'\d+\s+m\b')
        has_distance = any(_DISTANCE_RE.search(label) for label in labels)
        has_task = any("·" in label for label in labels)
        has_explore = any("探索" in label for label in labels)
        has_talk = any("交谈" in label for label in labels)
        if not (has_distance or has_task or has_explore or has_talk):
            return False  # 无大世界特征
        # 任一目标区域关键词出现在标签中即视为验证通过
        for kw in keywords:
            if any(kw in label for label in labels):
                return True
        return False

    def _wuling_overview_select_subarea(
        self,
        android: Any,
        serial: Optional[str],
        target_area: str,
    ) -> bool:
        """在武陵区域总览视图，点击目标子区域并等待地图切换。

        当 SceneEnterMapWuling* 的 TemplateMatch (MapOverviewWulingChoose.png) 识别失败时，
        通过 android.tap() 直接点击目标子区域坐标切换地图。

        Returns:
            bool: 是否成功切换到目标子区域地图视图（或已在目标子区域）
        """
        tap_coords = self._WULING_OVERVIEW_TAP_COORDS.get(target_area)
        if not tap_coords:
            return False

        def _ocr_labels() -> List[str]:
            try:
                ocr_result = self.execute(
                    "scene.elements",
                    {"serial": serial, "enable_ocr": True,
                     "enable_template": False, "enable_color": False},
                )
            except Exception:
                return []
            if not isinstance(ocr_result, dict) or ocr_result.get("status") != "success":
                return []
            elements = ocr_result.get("elements", [])
            return [str(e.get("label", "")) for e in elements if isinstance(e, dict)]

        labels = _ocr_labels()
        # 武陵总览特征词（区别于大世界 HUD 和子区域地图视图）
        has_overview = (
            any("地区建设等级" in l for l in labels)
            or any("O.M.V.帝江号" in l for l in labels)
        )
        if not has_overview:
            return False  # 不在武陵总览，不处理

        # 如果当前已选中目标子区域（地图标题包含目标名），无需切换
        # 检查所有标签（地图标题 "//武陵/清波寨" 可能在任意位置）
        if any(target_area in l for l in labels):
            self._logger.info(
                LogCategory.MAIN, "武陵总览：已选中目标子区域，无需切换",
                area=target_area,
            )
            return True

        # 按屏幕尺寸缩放点击坐标（pipeline 坐标基于 1280x720）
        screen_size = self._get_screen_size(serial)
        base_w, base_h = 1280, 720
        cx = int(tap_coords[0] * screen_size[0] / base_w)
        cy = int(tap_coords[1] * screen_size[1] / base_h)
        self._logger.info(
            LogCategory.MAIN, "武陵总览：点击子区域切换",
            area=target_area, cx=cx, cy=cy,
            screen=screen_size, base=(base_w, base_h),
        )
        try:
            android.tap(cx, cy)
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "武陵总览点击异常", error=str(exc))
            return False
        time.sleep(2.5)

        # 验证已切换到目标子区域（地图标题应包含目标名，检查所有标签）
        labels = _ocr_labels()
        if any(target_area in l for l in labels):
            self._logger.info(
                LogCategory.MAIN, "武陵总览：子区域切换成功",
                area=target_area,
            )
            return True
        self._logger.warning(
            LogCategory.MAIN, "武陵总览：子区域切换后未检测到目标名",
            area=target_area, top_labels=labels[:10],
        )
        return False

    def _vlm_find_teleport_point(
        self,
        serial: Optional[str],
        target_area: str,
    ) -> Optional[Tuple[int, int]]:
        """用 VLM 识别地图视图中的传送点图标，返回屏幕坐标。

        当 MapTeleport.png 模板匹配失败时，使用 VLM 视觉识别传送点。
        VLM 返回 0-100 百分比坐标，转换为屏幕像素坐标。

        Returns:
            (x, y) 屏幕像素坐标，或 None（未找到/VLM 失败）
        """
        import base64
        import json as _json
        import re as _re

        try:
            png_data = self.execute("screenshot", {"serial": serial})
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "VLM 传送点识别截图失败", error=str(exc))
            return None
        if not png_data:
            return None

        img_b64 = base64.b64encode(png_data).decode("ascii")
        # 获取屏幕分辨率，提供给 VLM 作为坐标参考
        screen_w, screen_h = self._get_screen_size(serial)
        system = (
            "你是一个游戏地图传送助手。给定当前游戏地图截图，"
            "你的工作是找到地图上的传送点图标并返回其位置。"
            "只输出一个 JSON 对象，不要输出任何其他内容。"
        )
        prompt = (
            f"目标区域：{target_area}\n"
            f"截图分辨率：{screen_w}x{screen_h}（宽x高，像素）\n\n"
            "请分析截图，找到地图上的传送点图标（通常是蓝色/青色的图标，带有传送标识，"
            "类似传送门或锚点的图标，不是文字标记，也不是任务追踪箭头）。\n"
            f"返回传送点图标的中心像素坐标。\n\n"
            f'输出格式：{{"x": {screen_w // 2}, "y": {screen_h // 2}}}（示例为中心点）\n'
            '如果找不到传送点图标，返回：{"x": -1, "y": -1}\n'
            "只输出 JSON，不要输出其他内容。"
        )

        try:
            client = self._llm_client_instance
            reply = client.chat(
                prompt,
                system=system,
                image=img_b64,
                image_mime_type="image/png",
                max_tokens=100,
                temperature=0.1,
                timeout=60.0,
                chat_template_kwargs={"enable_thinking": False},
            )
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "VLM 传送点识别失败", error=str(exc))
            return None

        # 解析 JSON
        text = reply.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [ln for ln in lines if not ln.startswith("```")]
            text = "\n".join(lines).strip()
        m_start = text.find("{")
        m_end = text.rfind("}")
        if m_start < 0 or m_end <= m_start:
            self._logger.warning(LogCategory.MAIN, "VLM 传送点识别回复非 JSON", reply=reply[:200])
            return None
        # 容错解析：VLM 偶尔返回位置参数格式如 {"x": 126, 240}（缺 "y" 键），
        # 先尝试标准 JSON 解析；失败时用正则按位置提取所有数字作为 [x, y]。
        result: Any = None
        try:
            result = _json.loads(text[m_start:m_end + 1])
        except Exception as exc:
            self._logger.info(
                LogCategory.MAIN, "VLM 传送点识别 JSON 标准解析失败，尝试位置参数兜底",
                error=str(exc), raw=text[:200],
            )
            # 位置参数兜底：从 JSON 文本中按出现顺序提取所有整数/浮点数
            nums = _re.findall(r"-?\d+(?:\.\d+)?", text[m_start:m_end + 1])
            if len(nums) >= 2:
                try:
                    x_val = float(nums[0])
                    y_val = float(nums[1])
                except (TypeError, ValueError):
                    self._logger.warning(
                        LogCategory.MAIN, "VLM 传送点识别位置参数兜底失败",
                        raw=text[:200], nums=nums,
                    )
                    return None
                result = {"x": x_val, "y": y_val}
                self._logger.info(
                    LogCategory.MAIN, "VLM 传送点识别位置参数兜底成功",
                    x=x_val, y=y_val, raw=text[:200],
                )
            else:
                self._logger.warning(
                    LogCategory.MAIN, "VLM 传送点识别 JSON 解析失败且无法兜底",
                    error=str(exc), raw=text[:200], nums=nums,
                )
                return None

        if isinstance(result, dict):
            x_raw = result.get("x", -1)
            y_raw = result.get("y", -1)
        else:
            return None
        try:
            x_raw = float(x_raw)
            y_raw = float(y_raw)
        except (TypeError, ValueError):
            return None
        if x_raw < 0 or y_raw < 0:
            self._logger.info(LogCategory.MAIN, "VLM 未找到传送点", area=target_area)
            return None

        # 转换为屏幕坐标（复用前面已获取的 screen_w, screen_h）
        # VLM 可能返回 0-100 百分比或原始像素坐标，需自动识别：
        # - 若 x/y 都在 0-100 范围内 → 视为百分比
        # - 若 x/y 超过 100 但在屏幕分辨率内 → 视为像素坐标
        if 0 <= x_raw <= 100 and 0 <= y_raw <= 100:
            cx = int(x_raw / 100.0 * screen_w)
            cy = int(y_raw / 100.0 * screen_h)
        elif 0 <= x_raw <= screen_w and 0 <= y_raw <= screen_h:
            # VLM 返回的是像素坐标
            cx = int(x_raw)
            cy = int(y_raw)
        else:
            # 超出范围，可能是 VLM 误解了坐标系统，跳过
            self._logger.warning(
                LogCategory.MAIN, "VLM 传送点坐标超出范围",
                area=target_area, x_raw=x_raw, y_raw=y_raw,
                screen_w=screen_w, screen_h=screen_h,
            )
            return None
        self._logger.info(
            LogCategory.MAIN, "VLM 识别到传送点",
            area=target_area, x_raw=x_raw, y_raw=y_raw, cx=cx, cy=cy,
            screen_size=(screen_w, screen_h),
        )
        return (cx, cy)

    def _run_pipeline_with_timeout(
        self,
        runtime: Any,
        entry: str,
        pipeline_override: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> bool:
        """在子线程中运行 pipeline，超时返回 False。

        MaaFW 的 job.wait() 会无限阻塞，某些 pipeline 节点（如 SceneEnterWorld*
        从非目标区域调用时）可能因 UI 状态不匹配而长时间挂起。
        本方法在子线程中调用 run_pipeline，主线程等待 timeout 秒后放弃。

        超时后会调用 runtime.post_stop() 中止 MaaFW 当前任务，避免后续 pipeline
        与 OCR 因 MaaFW 忙而级联超时（旧版仅返回 False，但底层 job 仍在运行，
        下一个 post_task 会无限等待，导致 OCR 也 10s 超时）。
        """
        import threading

        result = {"ok": False}
        def _run():
            try:
                result["ok"] = runtime.run_pipeline(entry, pipeline_override or {})
            except Exception as exc:
                self._logger.warning(
                    LogCategory.MAIN, "pipeline 执行异常（子线程）",
                    entry=entry, error=str(exc),
                )
                result["ok"] = False

        thread = threading.Thread(target=_run, daemon=True, name=f"pipeline-{entry}")
        thread.start()
        thread.join(timeout=timeout)
        if thread.is_alive():
            self._logger.warning(
                LogCategory.MAIN, "pipeline 执行超时，跳过",
                entry=entry, timeout=timeout,
            )
            # 关键：超时后必须显式中止 MaaFW 任务，否则下一个 post_task 会
            # 因 MaaFW 单任务限制而无限等待，导致级联超时（OCR 也会 10s 超时）
            try:
                if hasattr(runtime, "post_stop"):
                    runtime.post_stop()
            except Exception as exc:
                self._logger.warning(
                    LogCategory.MAIN, "post_stop 调用异常",
                    entry=entry, error=str(exc),
                )
            # 给 MaaFW 一点时间处理中止信号
            time.sleep(1.5)
            return False
        return result["ok"]

    def _vlm_teleport_to_area(
        self,
        android: Any,
        serial: Optional[str],
        target_area: str,
        runtime: Any = None,
        max_steps: int = 15,
    ) -> Dict[str, Any]:
        """传送到目标区域（专用 SceneEnterWorld* 节点优先 + OCR 兜底）。

        流程：
        1. **优先**：通过 `_TASK_AREA_WORLD_NODE` 查找专用 `SceneEnterWorld*` 节点
           （无数字后缀，不依赖 anchor，有专用 EnterTeleport 节点：
           TemplateMatch MapTeleport.png + OCR 区域名匹配）
           直接运行该节点 → 进入地图视图 → 点击传送点 → 确认传送 → 等待加载
        2. **兜底1**：若专用节点失败，使用 `_TASK_AREA_MAP_NODE` 进入地图视图，
           再尝试 `__ScenePrivateMapEnterTeleport` 通用传送节点
        3. **兜底2**：若通用传送也失败，OCR 检测传送点名称 → 点击 → 检测"传送"确认按钮 → 点击
        4. 验证到达大世界（OCR 检测大世界特征）

        Returns:
            {"ok": bool, "area": str, "steps": [...], "reason": str}
        """
        steps: List[Dict[str, Any]] = []

        # ===== Step 0: 检查是否已在目标区域大世界（避免不必要的传送） =====
        # 如果已在目标区域，直接返回成功，避免 pipeline 在错误状态下挂起
        if self._is_in_big_world(serial) and self._verify_in_target_area(serial, target_area):
            self._logger.info(
                LogCategory.MAIN, "传送：已在目标区域大世界，无需传送",
                area=target_area,
            )
            steps.append({"step": 0, "action": "already_in_target", "verified": True})
            return {"ok": True, "area": target_area,
                    "reason": "already_in_target", "steps": steps}

        # ===== Step 1: 优先尝试专用 SceneEnterWorld* 节点 =====
        world_node = self._TASK_AREA_WORLD_NODE.get(target_area)
        if world_node and runtime:
            self._logger.info(
                LogCategory.MAIN, "传送：尝试专用 SceneEnterWorld* 节点",
                area=target_area, world_node=world_node,
            )
            try:
                ok = self._run_pipeline_with_timeout(runtime, world_node, {}, timeout=30.0)
            except Exception as exc:
                self._logger.warning(
                    LogCategory.MAIN, "专用传送节点异常", error=str(exc), node=world_node,
                )
                ok = False
            steps.append({"step": 0, "action": "world_node", "node": world_node, "ok": ok})
            time.sleep(3.5)  # 等待传送加载完成

            if ok and self._is_in_big_world(serial):
                # 验证是否在正确的目标区域（防止假阳性：pipeline 返回 True
                # 但实际未切换区域，例如武陵节点从四号谷地大世界调用时）
                if self._verify_in_target_area(serial, target_area):
                    self._logger.info(
                        LogCategory.MAIN, "传送成功（专用节点+区域验证）",
                        area=target_area, node=world_node,
                    )
                    steps.append({"step": 1, "action": "in_big_world",
                                  "method": "world_node", "verified": True})
                    return {"ok": True, "area": target_area,
                            "reason": "world_node_teleported", "steps": steps}
                else:
                    self._logger.warning(
                        LogCategory.MAIN, "专用节点返回成功但区域验证失败（假阳性），尝试兜底",
                        area=target_area, node=world_node,
                    )
                    steps.append({"step": 1, "action": "world_node_false_positive",
                                  "verified": False})
            else:
                self._logger.info(
                    LogCategory.MAIN, "专用节点未到达大世界，尝试兜底",
                    area=target_area, ok=ok,
                )

        # ===== Step 2: 兜底1 - SceneEnterMap* + 专用/通用 EnterTeleport =====
        map_node = self._TASK_AREA_MAP_NODE.get(target_area)
        if not map_node:
            return {"ok": False, "area": target_area, "reason": "no_map_node",
                    "steps": steps, "available": list(self._TASK_AREA_MAP_NODE.keys())}

        self._logger.info(
            LogCategory.MAIN, "传送：进入地图视图（兜底）",
            area=target_area, map_node=map_node,
        )
        try:
            ok = self._run_pipeline_with_timeout(runtime, map_node, {}, timeout=30.0) if runtime else False
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "传送进入地图视图异常", error=str(exc))
            ok = False
        steps.append({"step": 2, "action": "enter_map_view", "node": map_node, "ok": ok})
        time.sleep(2.5)  # 等待地图加载

        # 尝试专用 EnterTeleport 节点（优先）或通用传送节点
        dedicated_teleport = self._TASK_AREA_ENTER_TELEPORT_NODE.get(target_area)
        teleport_node = dedicated_teleport or "__ScenePrivateMapEnterTeleport"
        self._logger.info(
            LogCategory.MAIN, "传送：尝试 EnterTeleport 节点",
            area=target_area, teleport_node=teleport_node,
            dedicated=bool(dedicated_teleport),
        )
        try:
            ok = self._run_pipeline_with_timeout(runtime, teleport_node, {}, timeout=30.0) if runtime else False
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "pipeline 传送异常", error=str(exc))
            ok = False
        steps.append({"step": 3, "action": "pipeline_enter_teleport",
                      "node": teleport_node, "ok": ok})
        time.sleep(2.0)

        # 如果 pipeline 传送成功，验证是否到达大世界
        if ok:
            # 尝试点击传送确认按钮（某些情况下需要）
            try:
                self._run_pipeline_with_timeout(runtime, "__ScenePrivateMapTeleportConfirm", {}, timeout=15.0) if runtime else None
            except Exception:
                pass
            time.sleep(3.0)
            if self._is_in_big_world(serial) and self._verify_in_target_area(serial, target_area):
                self._logger.info(
                    LogCategory.MAIN, "传送成功（pipeline+区域验证）",
                    area=target_area,
                )
                steps.append({"step": 4, "action": "in_big_world",
                              "method": "pipeline", "verified": True})
                return {"ok": True, "area": target_area,
                        "reason": "pipeline_teleported", "steps": steps}

        # ===== Step 2.5: 武陵总览子区域切换重试 =====
        # 当 SceneEnterMapWuling* 的 TemplateMatch (MapOverviewWulingChoose.png) 识别失败时，
        # pipeline 可能进入武陵总览但未切换到目标子区域（停留在默认的景玉谷）。
        # 此时专用 EnterTeleport 会因 OCR 检测不到目标子区域名而失败。
        # 通过 _wuling_overview_select_subarea 直接点击目标子区域坐标，再重试 EnterTeleport。
        if dedicated_teleport and target_area in self._WULING_OVERVIEW_TAP_COORDS:
            self._logger.info(
                LogCategory.MAIN, "传送：武陵总览子区域切换重试",
                area=target_area,
            )
            switched = self._wuling_overview_select_subarea(android, serial, target_area)
            steps.append({"step": 4, "action": "wuling_overview_switch",
                          "area": target_area, "switched": switched})
            if switched and runtime:
                self._logger.info(
                    LogCategory.MAIN, "传送：重试专用 EnterTeleport 节点",
                    area=target_area, teleport_node=dedicated_teleport,
                )
                try:
                    ok = self._run_pipeline_with_timeout(runtime, dedicated_teleport, {}, timeout=30.0)
                except Exception as exc:
                    self._logger.warning(
                        LogCategory.MAIN, "重试专用 EnterTeleport 异常", error=str(exc),
                    )
                    ok = False
                steps.append({"step": 5, "action": "retry_enter_teleport",
                              "node": dedicated_teleport, "ok": ok})
                time.sleep(2.0)
                if ok:
                    try:
                        self._run_pipeline_with_timeout(runtime, "__ScenePrivateMapTeleportConfirm", {}, timeout=15.0)
                    except Exception:
                        pass
                    time.sleep(3.5)
                    if self._is_in_big_world(serial) and self._verify_in_target_area(serial, target_area):
                        self._logger.info(
                            LogCategory.MAIN, "传送成功（武陵总览切换+重试）",
                            area=target_area,
                        )
                        steps.append({"step": 6, "action": "in_big_world",
                                      "method": "wuling_overview_retry", "verified": True})
                        return {"ok": True, "area": target_area,
                                "reason": "wuling_overview_retry_teleported", "steps": steps}

        # ===== Step 2.6: 确保进入地图视图（手动打开地图） =====
        # 当 SceneEnterMap* 和 EnterTeleport pipeline 都失败时，可能从未进入
        # 地图视图。VLM 视觉识别传送点必须在地图视图中进行，否则 VLM 看到的
        # 是大世界 HUD 而非地图，必然返回"未找到传送点"。
        # 通过 OCR 检测当前是否在地图视图，若否则手动打开地图：
        # 1. 先尝试点击地图按钮（屏幕左上角，约 (141, 125)）
        # 2. 再尝试按 M 键（部分版本支持）
        # 3. 再尝试点击任务追踪栏右侧的地图图标
        def _is_in_map_view_now() -> bool:
            """检测当前是否在地图视图（含区域总览）。"""
            try:
                ocr_result = self.execute(
                    "scene.elements",
                    {"serial": serial, "enable_ocr": True,
                     "enable_template": False, "enable_color": False},
                )
            except Exception:
                return False
            if not isinstance(ocr_result, dict) or ocr_result.get("status") != "success":
                return False
            labels = [
                str(e.get("label", "")).strip()
                for e in ocr_result.get("elements", [])
                if isinstance(e, dict)
            ]
            # 地图视图特征词：地区总览、标记显示管理、//区域名 等
            map_kws = (
                "地区总览", "标记显示管理", "//四号谷地", "//武陵",
                "取消追踪", "地区建设等级", "其他地图追踪中",
            )
            return any(any(kw in l for l in labels) for kw in map_kws)

        if not _is_in_map_view_now():
            self._logger.info(
                LogCategory.MAIN, "传送：不在地图视图，手动打开地图",
                area=target_area,
            )
            # 尝试 1：点击地图按钮（屏幕左上角）
            map_button_taps = [(141, 125), (165, 110), (120, 140)]
            for mx, my in map_button_taps:
                try:
                    android.tap(mx, my)
                except Exception as exc:
                    self._logger.warning(LogCategory.MAIN, "点击地图按钮异常", error=str(exc))
                time.sleep(2.0)
                if _is_in_map_view_now():
                    self._logger.info(
                        LogCategory.MAIN, "传送：地图按钮点击成功，已进入地图视图",
                        area=target_area, button=(mx, my),
                    )
                    steps.append({"step": 5, "action": "manual_open_map",
                                  "method": "map_button", "coord": (mx, my), "ok": True})
                    break
            # 尝试 2：按 M 键
            if not _is_in_map_view_now():
                try:
                    android.keyevent("KEYCODE_M")
                except Exception as exc:
                    self._logger.warning(LogCategory.MAIN, "M 键异常", error=str(exc))
                time.sleep(2.0)
                if _is_in_map_view_now():
                    self._logger.info(
                        LogCategory.MAIN, "传送：M 键打开地图成功",
                        area=target_area,
                    )
                    steps.append({"step": 5, "action": "manual_open_map",
                                  "method": "m_key", "ok": True})
            if not _is_in_map_view_now():
                self._logger.warning(
                    LogCategory.MAIN, "传送：手动打开地图失败，继续尝试 VLM 视觉识别",
                    area=target_area,
                )
                steps.append({"step": 5, "action": "manual_open_map", "ok": False})
        else:
            self._logger.info(
                LogCategory.MAIN, "传送：已在地图视图，跳过手动打开",
                area=target_area,
            )

        # ===== Step 2.7: VLM 识别传送点（MapTeleport.png 模板失效时的视觉兜底） =====
        # 当专用 EnterTeleport 节点失败（MapTeleport.png 模板不匹配新版游戏 UI），
        # 且已在正确地图视图中时，使用 VLM 视觉识别传送点图标并点击。
        # VLM 能区分传送点图标和标记名称，避免 OCR 误点标记进入标记管理模式。
        # VLM 可能误点非传送点元素（如资源点/标记），此时会弹出信息面板而无"传送"按钮，
        # 需按 BACK 关闭面板后重试 VLM。
        screen_size = self._get_screen_size(serial)
        _MAX_VLM_RETRIES = 3
        vlm_succeeded = False
        for vlm_attempt in range(1, _MAX_VLM_RETRIES + 1):
            self._logger.info(
                LogCategory.MAIN, "传送：VLM 视觉识别传送点",
                area=target_area, attempt=vlm_attempt,
            )
            vlm_point = self._vlm_find_teleport_point(serial, target_area)
            steps.append({"step": 6, "action": "vlm_find_teleport",
                          "attempt": vlm_attempt,
                          "found": vlm_point is not None,
                          "coord": vlm_point})
            if not vlm_point:
                break  # VLM 未找到传送点，不再重试

            cx, cy = vlm_point
            self._logger.info(
                LogCategory.MAIN, "传送：VLM 点击传送点",
                area=target_area, cx=cx, cy=cy, attempt=vlm_attempt,
            )
            try:
                android.tap(cx, cy)
            except Exception as exc:
                self._logger.warning(LogCategory.MAIN, "VLM 传送点点击异常", error=str(exc))
            time.sleep(2.5)

            # 检测"传送"确认按钮并点击
            try:
                ocr_result = self.execute(
                    "scene.elements",
                    {"serial": serial, "enable_ocr": True,
                     "enable_template": False, "enable_color": False},
                )
            except Exception:
                ocr_result = {}
            confirm_btn = None
            after_labels: List[str] = []
            if isinstance(ocr_result, dict) and ocr_result.get("status") == "success":
                elems = ocr_result.get("elements", [])
                for elem in elems:
                    if not isinstance(elem, dict):
                        continue
                    label = str(elem.get("label", "")).strip()
                    after_labels.append(label)
                    if label == "传送":
                        confirm_btn = elem
                        break

            if confirm_btn:
                ccx, ccy = self._norm_to_screen(
                    confirm_btn.get("center", [0.5, 0.65]), screen_size
                )
                self._logger.info(
                    LogCategory.MAIN, "传送：VLM 后点击确认按钮",
                    area=target_area, cx=ccx, cy=ccy,
                )
                steps.append({"step": 7, "action": "vlm_click_confirm",
                              "cx": ccx, "cy": ccy, "attempt": vlm_attempt})
                try:
                    android.tap(ccx, ccy)
                except Exception as exc:
                    self._logger.warning(LogCategory.MAIN, "确认点击异常", error=str(exc))
                # 等待传送加载完成（最长 20 秒，每 2 秒检查一次）
                # 加载期间会出现 "NOW LOADING" 等加载画面，需等待其消失
                teleport_done = False
                for wait_i in range(10):
                    time.sleep(2.0)
                    if self._is_in_big_world(serial) and self._verify_in_target_area(serial, target_area):
                        teleport_done = True
                        break
                    # 检测是否仍在加载（有 "LOADING" 字样）
                    try:
                        loading_ocr = self.execute(
                            "scene.elements",
                            {"serial": serial, "enable_ocr": True,
                             "enable_template": False, "enable_color": False},
                        )
                    except Exception:
                        loading_ocr = {}
                    loading_labels = []
                    if isinstance(loading_ocr, dict) and loading_ocr.get("status") == "success":
                        loading_labels = [
                            str(e.get("label", "")) for e in loading_ocr.get("elements", [])
                            if isinstance(e, dict)
                        ]
                    is_loading = any("LOADING" in l.upper() for l in loading_labels)
                    self._logger.info(
                        LogCategory.MAIN, "传送：等待加载",
                        area=target_area, wait=wait_i + 1, is_loading=is_loading,
                        labels_preview=loading_labels[:5],
                    )
                    if not is_loading and not teleport_done:
                        # 加载已结束但仍未到大世界，可能传送失败，退出等待
                        # 再等 2 秒确认
                        time.sleep(2.0)
                        if self._is_in_big_world(serial) and self._verify_in_target_area(serial, target_area):
                            teleport_done = True
                        break
                if teleport_done:
                    self._logger.info(
                        LogCategory.MAIN, "传送成功（VLM 视觉识别+区域验证）",
                        area=target_area,
                    )
                    steps.append({"step": 8, "action": "in_big_world",
                                  "method": "vlm_visual", "verified": True})
                    vlm_succeeded = True
                    return {"ok": True, "area": target_area,
                            "reason": "vlm_visual_teleported", "steps": steps}
                # 传送按钮点击后未到达大世界，可能需要再次重试
                self._logger.info(
                    LogCategory.MAIN, "VLM 点击确认后未到达大世界，重试",
                    area=target_area, attempt=vlm_attempt,
                )
                # 关闭可能残留的对话框，回到地图视图
                try:
                    android.keyevent("KEYCODE_BACK")
                except Exception:
                    pass
                time.sleep(1.5)
                continue
            else:
                # 未出现"传送"按钮，可能 VLM 点击的不是传送点（如资源点/标记）
                # 检测是否在信息面板（有"追踪"/"收纳"等按钮）
                in_info_panel = any(
                    kw in l for l in after_labels
                    for kw in ("追踪", "收纳", "前往传送")
                )
                self._logger.info(
                    LogCategory.MAIN, "VLM 点击后未出现传送确认按钮",
                    area=target_area, attempt=vlm_attempt,
                    in_info_panel=in_info_panel,
                    labels_preview=after_labels[:8],
                )
                if in_info_panel:
                    # 按 BACK 关闭信息面板，回到地图视图后重试 VLM
                    try:
                        android.keyevent("KEYCODE_BACK")
                    except Exception:
                        pass
                    time.sleep(2.0)
                    continue
                else:
                    # 既没有"传送"按钮也不在信息面板，可能画面状态异常，退出重试
                    break

        if not vlm_succeeded:
            self._logger.info(
                LogCategory.MAIN, "VLM 视觉识别传送点未成功，进入 OCR 兜底",
                area=target_area,
            )

        # ===== Step 3: 兜底2 - OCR 检测传送点 =====
        self._logger.info(
            LogCategory.MAIN, "传送：OCR 兜底",
            area=target_area,
        )
        _UI_NOISE_LABELS = {
            "前往传送", "取消追踪", "标记显示管理", "事务提醒", "任务完成奖励",
            "地区总览", "自定义标记点上限", "其他地图追踪中...",
            "X", "EXD", "UID", "探索", "确认", "取消", "创建",
        }
        # 地图视图/区域总览特征词（出现任一即视为非大世界）
        _MAP_VIEW_KEYWORDS = (
            "//四号谷地", "//武陵", "// 武陵", "标记显示管理", "取消追踪", "地区总览",
            # 区域总览特有
            "地区建设等级", "O.M.V.帝江号",
        )
        # 标记管理模式特征词（点击标记名称误入时出现）
        # 检测到任一即判定为误入标记管理模式，需按 BACK 退出
        _MARKER_MODE_KEYWORDS = (
            "自定义标记点上限", "标记1", "标记2", "标记3",
        )
        # 信息面板特征词（点击非传送点元素弹出，无"传送"按钮）
        # 检测到任一且无"传送"按钮时，按 BACK 关闭面板回到地图视图
        _INFO_PANEL_KEYWORDS = (
            "追踪", "收纳",
        )
        # 已点击但导致误入标记模式的标签黑名单（避免重复点击同一坏标签）
        _tried_labels_blacklist: set = set()
        # 最近一次点击的传送点候选标签（用于误入标记模式时加入黑名单）
        _last_clicked_label: str = ""
        # BACK 退出标记模式后重试计数
        _marker_mode_recover_count = 0
        _MAX_MARKER_MODE_RECOVERIES = 3
        # BACK 退出信息面板后重试计数
        _info_panel_recover_count = 0
        _MAX_INFO_PANEL_RECOVERIES = 3

        teleport_clicked = False
        for step_idx in range(5, max_steps + 1):
            # OCR 检测当前画面
            try:
                ocr_result = self.execute(
                    "scene.elements",
                    {"serial": serial, "enable_ocr": True,
                     "enable_template": False, "enable_color": False},
                )
            except Exception:
                ocr_result = {}
            elements = []
            if isinstance(ocr_result, dict) and ocr_result.get("status") == "success":
                elements = ocr_result.get("elements", [])

            ocr_labels = [
                str(e.get("label", "")).strip()
                for e in elements if isinstance(e, dict)
            ]

            # 检测是否已到达大世界
            if self._is_in_big_world_by_elements(ocr_labels, _MAP_VIEW_KEYWORDS):
                # 同样进行区域验证
                if self._verify_in_target_area(serial, target_area):
                    self._logger.info(
                        LogCategory.MAIN, "传送到达目标区域大世界（OCR 兜底+区域验证）",
                        area=target_area, step=step_idx,
                    )
                    steps.append({"step": step_idx, "action": "in_big_world",
                                  "method": "ocr_fallback", "verified": True})
                    return {"ok": True, "area": target_area,
                            "reason": "ocr_teleported", "steps": steps}
                else:
                    self._logger.info(
                        LogCategory.MAIN, "OCR 兜底到达大世界但区域不符，继续",
                        area=target_area, step=step_idx,
                    )

            # 检测标记管理模式（点击标记名称误入）
            # 特征词：自定义标记点上限 / 标记1 / 标记2 / 标记3
            in_marker_mode = any(
                any(kw in label for label in ocr_labels)
                for kw in _MARKER_MODE_KEYWORDS
            )
            if in_marker_mode and _marker_mode_recover_count < _MAX_MARKER_MODE_RECOVERIES:
                _marker_mode_recover_count += 1
                # 把导致误入的标签加入黑名单，避免下次再点
                if _last_clicked_label:
                    _tried_labels_blacklist.add(_last_clicked_label)
                    self._logger.warning(
                        LogCategory.MAIN, "传送：黑名单误入标记模式的标签",
                        area=target_area, label=_last_clicked_label,
                    )
                    _last_clicked_label = ""
                self._logger.warning(
                    LogCategory.MAIN, "传送：OCR 兜底误入标记管理模式，按 BACK 退出",
                    area=target_area, step=step_idx, recovery=_marker_mode_recover_count,
                )
                steps.append({"step": step_idx, "action": "marker_mode_recover",
                              "recovery": _marker_mode_recover_count})
                try:
                    android.keyevent("KEYCODE_BACK")
                except Exception as exc:
                    self._logger.warning(LogCategory.MAIN, "BACK 键异常", error=str(exc))
                time.sleep(2.0)
                # 重置 teleport_clicked 以便重新尝试其他传送点候选
                teleport_clicked = False
                continue

            # 检测信息面板（点击非传送点元素弹出，无"传送"按钮）
            # 特征词：追踪 / 收纳 （且没有"传送"按钮）
            has_confirm_btn = any(l == "传送" for l in ocr_labels)
            in_info_panel = (
                not has_confirm_btn
                and any(kw in l for l in ocr_labels for kw in _INFO_PANEL_KEYWORDS)
                and not any(any(kw in l for l in ocr_labels) for kw in _MAP_VIEW_KEYWORDS)
            )
            if in_info_panel and _info_panel_recover_count < _MAX_INFO_PANEL_RECOVERIES:
                _info_panel_recover_count += 1
                # 把导致误入信息面板的标签加入黑名单
                if _last_clicked_label:
                    _tried_labels_blacklist.add(_last_clicked_label)
                    self._logger.warning(
                        LogCategory.MAIN, "传送：黑名单误入信息面板的标签",
                        area=target_area, label=_last_clicked_label,
                    )
                    _last_clicked_label = ""
                self._logger.warning(
                    LogCategory.MAIN, "传送：OCR 兜底误入信息面板，按 BACK 退出",
                    area=target_area, step=step_idx, recovery=_info_panel_recover_count,
                )
                steps.append({"step": step_idx, "action": "info_panel_recover",
                              "recovery": _info_panel_recover_count})
                try:
                    android.keyevent("KEYCODE_BACK")
                except Exception as exc:
                    self._logger.warning(LogCategory.MAIN, "BACK 键异常", error=str(exc))
                time.sleep(2.0)
                teleport_clicked = False
                continue

            # 检测"传送"确认按钮
            confirm_btn = None
            for elem in elements:
                if not isinstance(elem, dict):
                    continue
                if str(elem.get("label", "")).strip() == "传送":
                    confirm_btn = elem
                    break

            if teleport_clicked and confirm_btn:
                cx, cy = self._norm_to_screen(
                    confirm_btn.get("center", [0.5, 0.65]), screen_size
                )
                self._logger.info(
                    LogCategory.MAIN, "传送点击确认按钮",
                    area=target_area, cx=cx, cy=cy, step=step_idx,
                )
                steps.append({"step": step_idx, "action": "click_confirm",
                              "cx": cx, "cy": cy})
                try:
                    android.tap(cx, cy)
                except Exception as exc:
                    self._logger.warning(LogCategory.MAIN, "传送点击确认异常", error=str(exc))
                time.sleep(4.0)
                if self._is_in_big_world(serial) and self._verify_in_target_area(serial, target_area):
                    return {"ok": True, "area": target_area,
                            "reason": "ocr_teleported", "steps": steps}
                continue

            if not teleport_clicked:
                # 找传送点名称（3-8 字中文，非 UI 噪声，非黑名单）
                # 两轮筛选：优先选择匹配目标区域名的标签，避免误点其他区域传送点
                def _is_valid_teleport_label(label: str) -> bool:
                    if not label or label in _UI_NOISE_LABELS:
                        return False
                    if label in _tried_labels_blacklist:
                        return False
                    if len(label) < 3 or len(label) > 8:
                        return False
                    if any(c.isdigit() for c in label):
                        return False
                    if "·" in label or "/" in label or ":" in label or "!" in label:
                        return False
                    if any(kw in label for kw in _MAP_VIEW_KEYWORDS):
                        return False
                    if label in ("破碎边界", "塔卫二常识", "ARKNIGHT", "O.M.V.帝江号"):
                        return False
                    if "。" in label or "." in label:
                        return False
                    task_desc_kws = ("确认", "前往", "寻找", "交谈", "与终", "应弭弗",
                                     "需要", "协助", "查看", "调查", "完成",
                                     "解锁", "追踪", "停止", "开始", "领取")
                    if any(kw in label for kw in task_desc_kws):
                        return False
                    if not any('\u4e00' <= c <= '\u9fff' for c in label):
                        return False
                    return True

                # 第 1 轮：优先匹配目标区域名或其验证关键词
                # 例如 target_area="枢纽区" → 匹配 "枢纽区" 或 keywords=["四号谷地", "枢纽区"]
                target_keywords = self._TASK_AREA_VERIFY_KEYWORDS.get(target_area, [])
                teleport_point = None
                for elem in elements:
                    if not isinstance(elem, dict):
                        continue
                    label = str(elem.get("label", "")).strip()
                    if not _is_valid_teleport_label(label):
                        continue
                    # 严格匹配：标签等于目标区域名，或标签包含目标区域名，
                    # 或目标区域名包含标签（如 "四号谷地" 匹配 "//四号谷地/枢纽区"）
                    if (
                        label == target_area
                        or target_area in label
                        or any(kw == label or kw in label for kw in target_keywords if kw != target_area)
                    ):
                        teleport_point = elem
                        self._logger.info(
                            LogCategory.MAIN, "传送：OCR 匹配到目标区域传送点",
                            area=target_area, label=label,
                        )
                        break

                # 第 2 轮：无匹配时退回到首个有效传送点标签
                if teleport_point is None:
                    for elem in elements:
                        if not isinstance(elem, dict):
                            continue
                        label = str(elem.get("label", "")).strip()
                        if not _is_valid_teleport_label(label):
                            continue
                        teleport_point = elem
                        break

                if teleport_point:
                    cx, cy = self._norm_to_screen(
                        teleport_point.get("center", [0.5, 0.5]), screen_size
                    )
                    label = str(teleport_point.get("label", "")).strip()
                    self._logger.info(
                        LogCategory.MAIN, "传送点击传送点（OCR）",
                        area=target_area, label=label, cx=cx, cy=cy, step=step_idx,
                    )
                    steps.append({"step": step_idx, "action": "click_teleport_ocr",
                                  "label": label, "cx": cx, "cy": cy})
                    try:
                        android.tap(cx, cy)
                        teleport_clicked = True
                        _last_clicked_label = label
                    except Exception as exc:
                        self._logger.warning(LogCategory.MAIN, "传送点击异常", error=str(exc))
                    time.sleep(2.5)
                    continue

            # 无操作可做，等待
            time.sleep(1.0)

        return {"ok": False, "area": target_area, "reason": "max_steps",
                "steps": steps}

    def _is_in_big_world(self, serial: Optional[str]) -> bool:
        """通过 OCR 检测当前是否在大世界（非地图视图/区域总览）。"""
        try:
            ocr_result = self.execute(
                "scene.elements",
                {"serial": serial, "enable_ocr": True,
                 "enable_template": False, "enable_color": False},
            )
        except Exception:
            return False
        if not isinstance(ocr_result, dict) or ocr_result.get("status") != "success":
            return False
        elements = ocr_result.get("elements", [])
        labels = [str(e.get("label", "")) for e in elements if isinstance(e, dict)]
        # 地图视图/区域总览特征词（出现任一即视为非大世界）
        _MAP_VIEW_KEYWORDS = (
            "//四号谷地", "//武陵", "// 武陵", "标记显示管理", "取消追踪", "地区总览",
            # 区域总览特有（区别于大世界 HUD）
            "地区建设等级", "O.M.V.帝江号",
        )
        return self._is_in_big_world_by_elements(labels, _MAP_VIEW_KEYWORDS)

    @staticmethod
    def _is_in_big_world_by_elements(labels: List[str], map_view_keywords: tuple) -> bool:
        """根据 OCR 标签列表判断是否在大世界。"""
        # 地图视图特征
        has_map = any(any(kw in label for label in labels) for kw in map_view_keywords)
        if has_map:
            return False
        # 大世界特征：距离指示（数字+空格+m，如"738 m"）、任务追踪（·）、探索、交谈
        # 注意：不能用简单的 "m" in label，否则 "1ms"（延迟指示）会误判为距离。
        # 使用正则要求数字与 m 之间有空格，且 m 后为词边界（排除 "1ms"/"m/s"）。
        import re
        _DISTANCE_RE = re.compile(r'\d+\s+m\b')
        has_distance = any(_DISTANCE_RE.search(label) for label in labels)
        has_task = any("·" in label for label in labels)
        has_explore = any("探索" in label for label in labels)
        has_talk = any("交谈" in label for label in labels)
        return has_distance or has_task or has_explore or has_talk

    def _vlm_interact_for_task(
        self,
        android: Any,
        serial: Optional[str],
        task_name: str,
        max_iterations: int = 20,
        runtime: Any = None,
    ) -> Dict[str, Any]:
        """VLM 驱动的任务交互循环：截图→决策→执行→重复，直到完成或上限。

        替代之前的"盲按 F 13 次"策略。VLM 每步根据截图决定：
        - press_f: 按 F 推进对话/交互
        - click_text: 点击指定文字的 UI 按钮（OCR 定位）
        - wait: 等待
        - task_complete: 任务完成（看到结算/获得奖励）
        - no_action: 无可推进操作

        传送拦截：当 VLM 决策 click_text "前往传送"时，从任务名提取目标区域，
        通过 _TASK_AREA_TELEPORT_MAP 查找 pipeline 节点直接传送，避免在传送
        地图 UI 中反复点击无效文字。需要传入 runtime（MaaEndRuntime）。

        防循环保护：
        - 相同 click_text 文字连续 3 次 → 中断（点击未起作用）
        - 连续 press_f 5 次无变化 → 中断
        - 连续 no_action 3 次 → 中断

        Returns:
            {"status": "complete"/"exhausted"/"error", "iterations": N,
             "actions": [...], "last_decision": {...}}
        """
        actions: List[Dict[str, Any]] = []
        last_decision: Dict[str, Any] = {"action": "start"}
        screen_size = self._get_screen_size(serial)

        def _consecutive_count(act_key: str, attr: Optional[str] = None) -> int:
            """统计 actions 末尾连续相同动作（可带属性匹配）的次数。"""
            n = 0
            for prev in reversed(actions):
                if prev.get("action") != act_key:
                    break
                if attr is not None and prev.get(attr) != actions[-1].get(attr):
                    break
                n += 1
            return n

        for it_idx in range(1, max_iterations + 1):
            # TELEPORT-SKIP-BREAK: 当 TELEPORT-FAIL-LIMIT 触发后，VLM 仍可能反复
            # 决策 click_text 区域名（如"阿伯莉采石场"），每次都被传送地名拦截
            # 跳过。若不退出，会浪费 max_iterations 次迭代（每次 ~7s）。
            # 连续 3 次 vlm_teleport_skipped 直接退出循环，让上层判定任务失败。
            consecutive_skips = 0
            for prev in reversed(actions):
                if prev.get("action") == "vlm_teleport_skipped":
                    consecutive_skips += 1
                else:
                    break
            if consecutive_skips >= 3:
                self._logger.warning(
                    LogCategory.MAIN, "VLM 交互连续传送跳过 3+ 次，退出（传送失败且 VLM 无法自主推进）",
                    task=task_name, iteration=it_idx, consecutive_skips=consecutive_skips,
                )
                return {"status": "exhausted", "iterations": it_idx - 1, "actions": actions,
                        "last_decision": last_decision, "reason": "teleport_skips_exhausted"}

            decision = self._vlm_decide_interaction(serial, task_name)
            action = str(decision.get("action", "no_action"))
            last_decision = decision
            self._logger.info(
                LogCategory.MAIN, "VLM 任务交互决策",
                task=task_name, iteration=it_idx, action=action, decision=decision,
            )

            if action == "task_complete":
                actions.append({"iteration": it_idx, "action": "task_complete"})
                self._logger.info(LogCategory.MAIN, "VLM 交互判定任务完成", task=task_name, iteration=it_idx)
                return {"status": "complete", "iterations": it_idx, "actions": actions, "last_decision": decision}

            if action == "no_action":
                actions.append({"iteration": it_idx, "action": "no_action"})
                consecutive_no_action = _consecutive_count("no_action")
                if consecutive_no_action >= 2:
                    # no_action 表示大世界无交互按钮可见，说明角色未到达 NPC 面前。
                    # 不再按 F 兜底（手机端 F 无效且无交互按钮），直接触发重新导航。
                    # REWALK-LIMIT: 最多 2 次重新导航（每次 60 步），超过则放弃。
                    # 之前是 4 次（240 步），实测每次 rewalk 都走完 60 步并报 arrived
                    # 但 OCR 验证仍无交互关键词，说明角色真的没到 NPC 面前。
                    # 4 次 rewalk 浪费 20+ 分钟，2 次足够（结合 walk_to_tracking
                    # 内置的 OCR 验证，已能过滤大部分误报）。
                    rewalk_count = sum(1 for a in actions if a.get("action") == "rewalk_navigation")
                    if rewalk_count < 2:
                        self._logger.info(
                            LogCategory.MAIN, "VLM 交互连续 no_action，触发重新导航（角色未到达 NPC）",
                            task=task_name, iteration=it_idx, rewalk_count=rewalk_count + 1,
                        )
                        actions.append({"iteration": it_idx, "action": "rewalk_navigation", "rewalk_count": rewalk_count + 1, "trigger": "no_action"})
                        try:
                            rewalk_result = self.execute(
                                "nav3.walk_tracking",
                                {
                                    "max_steps": 30,
                                    "step_timeout": 30.0,
                                    "serial": serial,
                                },
                            )
                            self._logger.info(
                                LogCategory.MAIN, "重新导航结束（no_action 触发）",
                                task=task_name, status=rewalk_result.get("status") if isinstance(rewalk_result, dict) else "invalid",
                                rewalk_count=rewalk_count + 1,
                            )
                        except Exception as exc:
                            self._logger.warning(LogCategory.MAIN, "重新导航异常", task=task_name, error=str(exc))
                        time.sleep(2.0)
                        continue
                    self._logger.warning(
                        LogCategory.MAIN, "VLM 交互连续 no_action 且重新导航已用尽，退出",
                        task=task_name, iteration=it_idx, rewalk_count=rewalk_count,
                    )
                    return {"status": "exhausted", "iterations": it_idx, "actions": actions, "last_decision": decision, "reason": "no_action_exhausted"}
                # 首次 no_action 时短暂等待再重试（可能是动画过渡）
                time.sleep(2.0)
                continue

            if action == "press_f":
                actions.append({"iteration": it_idx, "action": "press_f"})
                consecutive_f = _consecutive_count("press_f")
                if consecutive_f > 5:
                    # 连续 press_f 5+ 次无变化，说明 VLM 到达位置后无法推进。
                    # 触发一次重新导航（30 步），让 VLM 追踪标识走到正确位置。
                    # 每次重新导航计入 rewalk_count，最多重试 2 次，超过则退出。
                    # （之前 4 次太浪费，结合 walk_to_tracking 内置 OCR 验证已足够）
                    rewalk_count = sum(1 for a in actions if a.get("action") == "rewalk_navigation")
                    if rewalk_count < 2:
                        self._logger.info(
                            LogCategory.MAIN, "VLM 交互连续 press_f 5+ 次，触发重新导航",
                            task=task_name, iteration=it_idx, rewalk_count=rewalk_count + 1,
                        )
                        actions.append({"iteration": it_idx, "action": "rewalk_navigation", "rewalk_count": rewalk_count + 1})
                        try:
                            rewalk_result = self.execute(
                                "nav3.walk_tracking",
                                {
                                    "max_steps": 60,
                                    "step_timeout": 30.0,
                                    "serial": serial,
                                },
                            )
                            self._logger.info(
                                LogCategory.MAIN, "重新导航结束",
                                task=task_name, status=rewalk_result.get("status") if isinstance(rewalk_result, dict) else "invalid",
                                rewalk_count=rewalk_count + 1,
                            )
                        except Exception as exc:
                            self._logger.warning(LogCategory.MAIN, "重新导航异常", task=task_name, error=str(exc))
                        time.sleep(2.0)
                        continue
                    self._logger.warning(
                        LogCategory.MAIN, "VLM 交互连续 press_f 5+ 次且重新导航已用尽，退出",
                        task=task_name, iteration=it_idx, rewalk_count=rewalk_count,
                    )
                    return {"status": "exhausted", "iterations": it_idx, "actions": actions, "last_decision": decision, "reason": "press_f_exhausted"}
                # press_f: tap 屏幕交互按钮位置（手机端 keyevent F 无效）
                self._vlm_press_interact(android, serial)
                time.sleep(2.0)
                continue

            if action == "click_text":
                target_text = str(decision.get("text", "")).strip()
                if not target_text:
                    actions.append({"iteration": it_idx, "action": "click_text_empty"})
                    time.sleep(1.0)
                    continue

                # === 传送拦截 ===
                # 当 VLM 决策点击 "前往传送" 时，说明任务需要传送到其他区域。
                # 由于 MaaFW anchor bug，SceneEnterWorld* pipeline 节点失效，
                # 改用 _vlm_teleport_to_area：SceneEnterMap* 进入地图视图 +
                # VLM 识别并点击传送点完成实际传送。
                if target_text == "前往传送" and runtime is not None:
                    # TELEPORT-FAIL-LIMIT: 本任务传送失败次数已达上限时，
                    # 跳过传送拦截，让 VLM 决策下一个动作（避免反复触发
                    # 90s 的 pipeline 超时浪费）。
                    if getattr(self, "_task_teleport_failures", 0) >= getattr(self, "_task_teleport_failures_max", 2):
                        self._logger.warning(
                            LogCategory.MAIN, "VLM 交互传送拦截跳过：本任务传送失败次数已达上限",
                            task=task_name, target_area=task_name.rsplit("·", 1)[-1].strip(),
                            failures=self._task_teleport_failures,
                        )
                        actions.append({
                            "iteration": it_idx, "action": "vlm_teleport_skipped",
                            "reason": "teleport_failures_exhausted",
                            "failures": self._task_teleport_failures,
                        })
                        # 短暂等待后让 VLM 重新决策
                        time.sleep(2.0)
                        continue
                    # 从任务名提取目标区域
                    target_area = ""
                    for sep in ("·", "·", "·", "•", "・"):
                        if sep in task_name:
                            target_area = task_name.rsplit(sep, 1)[1].strip()
                            break
                    map_node = self._TASK_AREA_MAP_NODE.get(target_area) if target_area else None
                    self._logger.info(
                        LogCategory.MAIN, "VLM 交互传送拦截",
                        task=task_name, target_area=target_area,
                        map_node=map_node or "(无匹配)",
                    )
                    if map_node:
                        # VLM 驱动传送：进入地图视图 + VLM 点击传送点
                        actions.append({
                            "iteration": it_idx, "action": "vlm_teleport",
                            "target_area": target_area, "map_node": map_node,
                        })
                        tp_result = self._vlm_teleport_to_area(
                            android, serial, target_area, runtime=runtime,
                        )
                        actions[-1]["ok"] = tp_result.get("ok", False)
                        actions[-1]["reason"] = tp_result.get("reason")
                        # TELEPORT-FAIL-LIMIT: 计数失败次数
                        if not tp_result.get("ok") and tp_result.get("reason") != "already_in_target":
                            self._task_teleport_failures = getattr(self, "_task_teleport_failures", 0) + 1
                            self._logger.warning(
                                LogCategory.MAIN, "VLM 交互传送失败，计数器递增",
                                area=target_area, failures=self._task_teleport_failures,
                                max=getattr(self, "_task_teleport_failures_max", 2),
                                reason=tp_result.get("reason"),
                            )
                        self._logger.info(
                            LogCategory.MAIN, "VLM 传送结果",
                            area=target_area, ok=tp_result.get("ok"),
                            reason=tp_result.get("reason"),
                        )
                        # 如果已在目标区域，VLM 仍反复点"前往传送"说明角色离 NPC 还很远，
                        # 需要步行到 NPC。触发 rewalk（VLM 追踪标识导航）让角色走到 NPC。
                        if tp_result.get("reason") == "already_in_target":
                            already_tp_streak = 0
                            for a in reversed(actions):
                                if (
                                    a.get("action") == "vlm_teleport"
                                    and a.get("reason") == "already_in_target"
                                ):
                                    already_tp_streak += 1
                                else:
                                    break
                            if already_tp_streak >= 2:
                                rewalk_count = sum(1 for a in actions if a.get("action") == "rewalk_navigation")
                                if rewalk_count < 2:
                                    self._logger.info(
                                        LogCategory.MAIN, "VLM 交互已在目标区域但反复点前往传送，触发重新导航步行到 NPC",
                                        task=task_name, iteration=it_idx,
                                        already_tp_streak=already_tp_streak,
                                        rewalk_count=rewalk_count + 1,
                                    )
                                    actions.append({"iteration": it_idx, "action": "rewalk_navigation", "rewalk_count": rewalk_count + 1, "trigger": "goto_teleport_already_in_target"})
                                    try:
                                        rewalk_result = self.execute(
                                            "nav3.walk_tracking",
                                            {
                                                "max_steps": 60,
                                                "step_timeout": 30.0,
                                                "serial": serial,
                                            },
                                        )
                                        self._logger.info(
                                            LogCategory.MAIN, "重新导航（前往传送触发）结束",
                                            task=task_name, status=rewalk_result.get("status") if isinstance(rewalk_result, dict) else "invalid",
                                            rewalk_count=rewalk_count + 1,
                                        )
                                    except Exception as exc:
                                        self._logger.warning(LogCategory.MAIN, "重新导航异常", task=task_name, error=str(exc))
                                    time.sleep(2.0)
                                    continue
                                else:
                                    self._logger.warning(
                                        LogCategory.MAIN, "VLM 交互已在目标区域且重新导航已用尽，退出",
                                        task=task_name, iteration=it_idx, rewalk_count=rewalk_count,
                                    )
                                    return {"status": "exhausted", "iterations": it_idx, "actions": actions, "last_decision": decision, "reason": "goto_teleport_already_in_target_stuck"}
                        # 等待传送加载完成
                        time.sleep(3.0)
                        continue
                    else:
                        # 无匹配传送节点，回退到点击"前往传送"按钮（让 VLM 自行处理传送地图）
                        self._logger.info(
                            LogCategory.MAIN, "无匹配地图节点，回退到点击按钮",
                            task=task_name, target_area=target_area,
                        )

                # === 传送地名拦截 ===
                # VLM 在传送地图界面会决策 click_text 已知地名（如"枢纽区""供能高地"），
                # 但 OCR 点击地名条目不可靠。当目标文字命中 _TASK_AREA_MAP_NODE 的 key 时，
                # 直接通过 VLM 传送到该区域，跳过不可靠的地图 UI 点击流程。
                if runtime is not None and target_text in self._TASK_AREA_MAP_NODE:
                    # TELEPORT-FAIL-LIMIT: 本任务传送失败次数已达上限时，
                    # 跳过传送拦截，避免反复触发 90s pipeline 超时。
                    if getattr(self, "_task_teleport_failures", 0) >= getattr(self, "_task_teleport_failures_max", 2):
                        self._logger.warning(
                            LogCategory.MAIN, "VLM 交互传送地名拦截跳过：本任务传送失败次数已达上限",
                            task=task_name, target_area=target_text,
                            failures=self._task_teleport_failures,
                            iteration=it_idx,
                        )
                        actions.append({
                            "iteration": it_idx, "action": "vlm_teleport_skipped",
                            "reason": "teleport_failures_exhausted",
                            "target_area": target_text,
                            "failures": self._task_teleport_failures,
                        })
                        time.sleep(2.0)
                        continue
                    map_node = self._TASK_AREA_MAP_NODE[target_text]
                    self._logger.info(
                        LogCategory.MAIN, "VLM 交互传送地名拦截",
                        task=task_name, target_area=target_text,
                        map_node=map_node, iteration=it_idx,
                    )
                    # 防循环：统计末尾连续 vlm_teleport(already_in_target) 次数。
                    # 若 VLM 反复决策 click_text 同一区域名，但传送返回 already_in_target，
                    # 说明 VLM 误把屏幕上的区域名文字当成按钮，需要强制按 F 兜底交互。
                    # 注意：rewalk_navigation 不打断 streak（否则每次 rewalk 后 streak 归零，
                    # 导致 rewalk 循环永不退出）。
                    already_in_target_streak = 0
                    for a in reversed(actions):
                        action_label = a.get("action", "")
                        if action_label == "rewalk_navigation":
                            continue  # 不打断 streak
                        if action_label == "vlm_teleport" and a.get("reason") == "already_in_target":
                            already_in_target_streak += 1
                        else:
                            break
                    actions.append({
                        "iteration": it_idx, "action": "vlm_teleport",
                        "target_area": target_text, "map_node": map_node,
                    })
                    # 连续 2+ 次 already_in_target：角色已在目标区域但 VLM 反复点地名，
                    # 说明角色离 NPC 还很远，需要步行到 NPC。触发 rewalk 让角色走到 NPC。
                    if already_in_target_streak >= 2:
                        self._logger.warning(
                            LogCategory.MAIN, "VLM 交互连续 already_in_target 2+ 次，触发重新导航步行到 NPC",
                            task=task_name, target_area=target_text,
                            streak=already_in_target_streak, iteration=it_idx,
                        )
                        actions[-1]["ok"] = True
                        actions[-1]["reason"] = "already_in_target_skipped"
                        rewalk_count = sum(1 for a in actions if a.get("action") == "rewalk_navigation")
                        if rewalk_count < 2:
                            actions.append({"iteration": it_idx, "action": "rewalk_navigation", "rewalk_count": rewalk_count + 1, "trigger": "area_name_already_in_target"})
                            try:
                                rewalk_result = self.execute(
                                    "nav3.walk_tracking",
                                    {
                                        "max_steps": 60,
                                        "step_timeout": 30.0,
                                        "serial": serial,
                                    },
                                )
                                self._logger.info(
                                    LogCategory.MAIN, "重新导航（地名触发）结束",
                                    task=task_name, status=rewalk_result.get("status") if isinstance(rewalk_result, dict) else "invalid",
                                    rewalk_count=rewalk_count + 1,
                                )
                            except Exception as exc:
                                self._logger.warning(LogCategory.MAIN, "重新导航异常", task=task_name, error=str(exc))
                            time.sleep(2.0)
                            continue
                        else:
                            self._logger.warning(
                                LogCategory.MAIN, "VLM 交互连续 already_in_target 且重新导航已用尽，退出",
                                task=task_name, iteration=it_idx, rewalk_count=rewalk_count,
                            )
                            return {"status": "exhausted", "iterations": it_idx, "actions": actions, "last_decision": decision, "reason": "goto_x_already_in_target_stuck"}
                    tp_result = self._vlm_teleport_to_area(
                        android, serial, target_text, runtime=runtime,
                    )
                    actions[-1]["ok"] = tp_result.get("ok", False)
                    actions[-1]["reason"] = tp_result.get("reason")
                    # TELEPORT-FAIL-LIMIT: 计数失败次数
                    if not tp_result.get("ok") and tp_result.get("reason") != "already_in_target":
                        self._task_teleport_failures = getattr(self, "_task_teleport_failures", 0) + 1
                        self._logger.warning(
                            LogCategory.MAIN, "VLM 交互传送地名失败，计数器递增",
                            area=target_text, failures=self._task_teleport_failures,
                            max=getattr(self, "_task_teleport_failures_max", 2),
                            reason=tp_result.get("reason"),
                        )
                    self._logger.info(
                        LogCategory.MAIN, "VLM 传送地名结果",
                        area=target_text, ok=tp_result.get("ok"),
                        reason=tp_result.get("reason"),
                    )
                    # 等待传送加载完成
                    time.sleep(3.0)
                    continue

                # === 前往X 模式拦截 ===
                # 当 VLM 决策 click_text 形如 "前往清波寨完成" / "前往枢纽区" / "前往供能高地"
                # 等包含已知传送目标地名的按钮时，OCR 点击文本中心往往不触发实际传送。
                # 统计同一 target_text 已被点击次数，若 ≥2 次说明点击未起作用，直接通过
                # VLM 传送到该区域，避免反复点击同一无效按钮耗尽迭代。
                if runtime is not None:
                    prior_same_clicks = sum(
                        1 for a in actions
                        if a.get("action") == "click_text" and a.get("text") == target_text
                    )
                    if prior_same_clicks >= 2:
                        # 检测 target_text 是否包含已知传送地名
                        matched_area = None
                        for area_name in self._TASK_AREA_MAP_NODE:
                            if area_name in target_text:
                                matched_area = area_name
                                break
                        if matched_area:
                            map_node = self._TASK_AREA_MAP_NODE[matched_area]
                            # 防循环：统计末尾连续 vlm_teleport(already_in_target) 次数。
                            # 若 VLM 反复决策 click_text 同一前往X文本，但传送返回
                            # already_in_target，说明 VLM 误把屏幕上的任务目标描述文字
                            # （如"前往枢纽区""前往枢纽区，与希金斯交谈"）当成按钮，
                            # 需要强制按 F 兜底交互，避免无限循环触发传送拦截。
                            already_in_target_streak = 0
                            for a in reversed(actions):
                                if (
                                    a.get("action") == "vlm_teleport"
                                    and a.get("reason") == "already_in_target"
                                ):
                                    already_in_target_streak += 1
                                else:
                                    break
                            # 累计前往X触发次数（不论是否连续，用于检测 press_f/前往X 交替循环）
                            # 仅统计实际点击触发的传送（trigger == "repeat_click_pattern"），
                            # 不统计 rewalk 跳过的（trigger == "repeat_click_pattern_skipped"），
                            # 否则 rewalk 后立即达到阈值，rewalk 形同虚设。
                            total_goto_x_triggers = sum(
                                1 for a in actions
                                if a.get("action") == "vlm_teleport"
                                and a.get("trigger") == "repeat_click_pattern"
                            )
                            # 累计 8+ 次前往X触发（每次 rewalk 后允许 2 次新点击）：
                            # 认定 VLM 卡在远处（press_f/前往X 交替），角色还没到达 NPC 附近，
                            # 退出循环让上层重新触发追踪导航。
                            if total_goto_x_triggers >= 8:
                                self._logger.warning(
                                    LogCategory.MAIN, "VLM 交互前往X模式累计触发 4+ 次，退出循环",
                                    task=task_name, target_text=target_text, target_area=matched_area,
                                    total_triggers=total_goto_x_triggers, iteration=it_idx,
                                )
                                actions.append({
                                    "iteration": it_idx, "action": "vlm_teleport",
                                    "target_area": matched_area, "map_node": map_node,
                                    "ok": True, "reason": "already_in_target_exhausted",
                                    "trigger": "repeat_click_pattern_exhausted",
                                    "prior_clicks": prior_same_clicks,
                                })
                                return {
                                    "status": "exhausted",
                                    "iterations": it_idx,
                                    "actions": actions,
                                    "last_decision": decision,
                                    "reason": "goto_x_already_in_target_stuck",
                                }
                            # 连续 4+ 次 already_in_target：认定 VLM 卡死，退出循环
                            # 让上层验证/恢复逻辑接管（任务可能已完成或需要重新导航）。
                            if already_in_target_streak >= 4:
                                self._logger.warning(
                                    LogCategory.MAIN, "VLM 交互前往X模式连续 already_in_target 4+ 次，退出循环",
                                    task=task_name, target_text=target_text, target_area=matched_area,
                                    streak=already_in_target_streak, iteration=it_idx,
                                )
                                actions.append({
                                    "iteration": it_idx, "action": "vlm_teleport",
                                    "target_area": matched_area, "map_node": map_node,
                                    "ok": True, "reason": "already_in_target_exhausted",
                                    "trigger": "repeat_click_pattern_exhausted",
                                    "prior_clicks": prior_same_clicks,
                                })
                                return {
                                    "status": "exhausted",
                                    "iterations": it_idx,
                                    "actions": actions,
                                    "last_decision": decision,
                                    "reason": "goto_x_already_in_target_stuck",
                                }
                            # 连续 2-3 次 already_in_target：角色已在目标区域但 VLM 反复
                            # 点"前往X完成"任务追踪文字（非按钮），说明角色离 NPC 还很远，
                            # 需要步行到 NPC。触发 rewalk_navigation 让角色走到 NPC
                            # （与地名分支 already_in_target_streak >= 2 逻辑一致），
                            # 而非仅仅按 F 兜底（按 F 在远处无效，VLM 仍会重复点击）。
                            if already_in_target_streak >= 2:
                                self._logger.warning(
                                    LogCategory.MAIN, "VLM 交互前往X模式连续 already_in_target 2+ 次，触发重新导航步行到 NPC",
                                    task=task_name, target_text=target_text, target_area=matched_area,
                                    streak=already_in_target_streak, iteration=it_idx,
                                )
                                actions.append({
                                    "iteration": it_idx, "action": "vlm_teleport",
                                    "target_area": matched_area, "map_node": map_node,
                                    "ok": True, "reason": "already_in_target_skipped",
                                    "trigger": "repeat_click_pattern_skipped",
                                    "prior_clicks": prior_same_clicks,
                                })
                                rewalk_count = sum(1 for a in actions if a.get("action") == "rewalk_navigation")
                                # REWALK-LIMIT: 前往X already_in_target 触发的 rewalk 最多 2 次
                                # （每次 60 步约 6 分钟，2 次仍找不到 NPC 说明 VLM 看不见目标，
                                # 再多 rewalk 也是浪费，应退出循环让上层判定任务失败/跳过）
                                if rewalk_count < 2:
                                    actions.append({"iteration": it_idx, "action": "rewalk_navigation", "rewalk_count": rewalk_count + 1, "trigger": "goto_x_already_in_target"})
                                    try:
                                        rewalk_result = self.execute(
                                            "nav3.walk_tracking",
                                            {
                                                "max_steps": 60,
                                                "step_timeout": 30.0,
                                                "serial": serial,
                                            },
                                        )
                                        self._logger.info(
                                            LogCategory.MAIN, "重新导航（前往X触发）结束",
                                            task=task_name, status=rewalk_result.get("status") if isinstance(rewalk_result, dict) else "invalid",
                                            rewalk_count=rewalk_count + 1,
                                        )
                                    except Exception as exc:
                                        self._logger.warning(LogCategory.MAIN, "重新导航异常", task=task_name, error=str(exc))
                                    time.sleep(2.0)
                                    continue
                                else:
                                    self._logger.warning(
                                        LogCategory.MAIN, "VLM 交互前往X模式重新导航已用尽，退出",
                                        task=task_name, iteration=it_idx, rewalk_count=rewalk_count,
                                    )
                                    return {"status": "exhausted", "iterations": it_idx, "actions": actions, "last_decision": decision, "reason": "goto_x_already_in_target_stuck"}
                            self._logger.info(
                                LogCategory.MAIN, "VLM 交互前往X模式拦截（重复点击无效）",
                                task=task_name, target_text=target_text,
                                target_area=matched_area, map_node=map_node,
                                prior_clicks=prior_same_clicks, iteration=it_idx,
                            )
                            # TELEPORT-FAIL-LIMIT: 本任务传送失败次数已达上限时，
                            # 跳过传送，让 VLM 决策下一个动作。
                            if getattr(self, "_task_teleport_failures", 0) >= getattr(self, "_task_teleport_failures_max", 2):
                                self._logger.warning(
                                    LogCategory.MAIN, "VLM 交互前往X拦截跳过：本任务传送失败次数已达上限",
                                    task=task_name, target_area=matched_area,
                                    failures=self._task_teleport_failures,
                                    iteration=it_idx,
                                )
                                actions.append({
                                    "iteration": it_idx, "action": "vlm_teleport_skipped",
                                    "reason": "teleport_failures_exhausted",
                                    "target_area": matched_area,
                                    "failures": self._task_teleport_failures,
                                    "trigger": "repeat_click_pattern_skipped_by_failures",
                                })
                                time.sleep(2.0)
                                continue
                            actions.append({
                                "iteration": it_idx, "action": "vlm_teleport",
                                "target_area": matched_area, "map_node": map_node,
                                "trigger": "repeat_click_pattern",
                                "prior_clicks": prior_same_clicks,
                            })
                            tp_result = self._vlm_teleport_to_area(
                                android, serial, matched_area, runtime=runtime,
                            )
                            actions[-1]["ok"] = tp_result.get("ok", False)
                            actions[-1]["reason"] = tp_result.get("reason")
                            # TELEPORT-FAIL-LIMIT: 计数失败次数
                            if not tp_result.get("ok") and tp_result.get("reason") != "already_in_target":
                                self._task_teleport_failures = getattr(self, "_task_teleport_failures", 0) + 1
                                self._logger.warning(
                                    LogCategory.MAIN, "VLM 交互前往X传送失败，计数器递增",
                                    area=matched_area, failures=self._task_teleport_failures,
                                    max=getattr(self, "_task_teleport_failures_max", 2),
                                    reason=tp_result.get("reason"),
                                )
                            self._logger.info(
                                LogCategory.MAIN, "前往X VLM 传送结果",
                                area=matched_area, ok=tp_result.get("ok"),
                                reason=tp_result.get("reason"),
                            )
                            # 等待传送加载完成
                            time.sleep(3.0)
                            continue

                # 防循环：相同目标文字连续 3 次 → 中断
                actions.append({"iteration": it_idx, "action": "click_text", "text": target_text, "clicked": False})
                consecutive_same_click = _consecutive_count("click_text", attr="text")
                if consecutive_same_click > 3:
                    self._logger.warning(
                        LogCategory.MAIN, "VLM 交互连续点击相同文字 3+ 次，退出",
                        task=task_name, text=target_text, iteration=it_idx,
                    )
                    return {"status": "exhausted", "iterations": it_idx, "actions": actions, "last_decision": decision}
                # 安全护栏：超长文本（>10字符）通常是任务描述/系统提示而非 UI 按钮，
                # 点击其文字中心往往会误触任务追踪面板或打开不相关的系统界面
                # （如"查看源石副产物中心大楼内的情况"误入协议管理界面）。
                # 已知安全按钮白名单（短按钮文字）直接放行；超长文本跳过点击，
                # 改为按 F 尝试触发交互。
                _SAFE_CLICK_TEXTS = {
                    "前往传送", "传送", "确认", "取消", "关闭", "返回", "退出",
                    "开始追踪", "停止追踪", "任务奖励", "领取", "确定",
                }
                # 已知区域名/地名（非 UI 按钮）：这些是地图区域名称或协议系统物品名，
                # 在大世界或协议管理界面点击会打开协议管理弹出菜单，导致游戏卡死。
                # 仅在传送地图界面才可点击（由 _TASK_AREA_TELEPORT_MAP 拦截处理）。
                _BLOCKED_REGION_NAMES = {
                    "四号谷地", "阿伯莉采石场", "武陵", "清波寨", "景玉谷",
                    "藏剑谷", "枢纽区", "供能高地", "源矿源区", "源石科学园",
                    "界碑", "试炼区", "武陵城",
                }
                if len(target_text) > 10 and target_text not in _SAFE_CLICK_TEXTS:
                    self._logger.info(
                        LogCategory.MAIN, "VLM 交互跳过超长文本点击（避免误触）",
                        task=task_name, text=target_text, length=len(target_text),
                        iteration=it_idx,
                    )
                    actions[-1]["clicked"] = False
                    actions[-1]["skip_reason"] = "text_too_long"
                    # tap 交互按钮兜底尝试触发交互（手机端 keyevent F 无效）
                    self._vlm_press_interact(android, serial)
                    time.sleep(2.0)
                    continue
                # 区域名安全护栏：VLM 在大世界看到任务追踪文字中的区域名
                # （如"四号谷地""阿伯莉采石场"）会误以为是按钮去点击，
                # 实际这些文字在协议管理 UI 中是物品/区域标签，点击会打开
                # 协议管理弹出菜单导致游戏卡死。若 target_text 是已知区域名
                # 且不在传送拦截白名单中（即非传送地图界面），跳过点击按 F 兜底。
                # 注意：不按 BACK，因为 BACK 会触发"是否退出游戏？"对话框，
                # 反而让恢复流程更复杂。
                if (
                    target_text in _BLOCKED_REGION_NAMES
                    and target_text not in self._TASK_AREA_MAP_NODE
                ):
                    # 统计连续 blocked_region_name 次数
                    blocked_same_count = 0
                    for a in reversed(actions):
                        if a.get("skip_reason") == "blocked_region_name":
                            blocked_same_count += 1
                        else:
                            break
                    self._logger.info(
                        LogCategory.MAIN, "VLM 交互跳过区域名点击（避免误入协议管理）",
                        task=task_name, text=target_text, iteration=it_idx,
                        consecutive_blocked=blocked_same_count,
                    )
                    actions[-1]["clicked"] = False
                    actions[-1]["skip_reason"] = "blocked_region_name"
                    # tap 交互按钮兜底（手机端 keyevent F 无效）
                    self._vlm_press_interact(android, serial)
                    time.sleep(2.0)
                    # 连续 2 次以上 blocked_region_name 说明确实卡在协议管理类 UI，
                    # 提前退出循环让验证/恢复逻辑接管（_close_overlays_return_to_world
                    # 会点击 X 按钮关闭协议核心 UI）。
                    if blocked_same_count >= 1:
                        self._logger.warning(
                            LogCategory.MAIN,
                            "VLM 交互连续区域名点击被拦截 2+ 次，退出循环",
                            task=task_name, text=target_text, iteration=it_idx,
                        )
                        return {
                            "status": "exhausted",
                            "iterations": it_idx,
                            "actions": actions,
                            "last_decision": decision,
                            "reason": "blocked_region_name_stuck",
                        }
                    continue
                # OCR 定位目标文字
                try:
                    ocr_result = self.execute(
                        "scene.elements",
                        {"serial": serial, "enable_ocr": True, "enable_template": False, "enable_color": False},
                    )
                except Exception as exc:
                    self._logger.warning(LogCategory.MAIN, "点击文字 OCR 异常", error=str(exc))
                    ocr_result = {}
                elements = []
                if isinstance(ocr_result, dict) and ocr_result.get("status") == "success":
                    elements = ocr_result.get("elements", [])
                # 智能匹配：精确匹配 > 前缀匹配 > 子串匹配
                # 对多个匹配结果，优先选择屏幕下半部分（按钮通常在底部，标题在顶部）
                exact_matches = []
                prefix_matches = []
                substr_matches = []
                for elem in elements:
                    if not isinstance(elem, dict):
                        continue
                    label = str(elem.get("label", "")).strip()
                    if not label:
                        continue
                    if label == target_text:
                        exact_matches.append(elem)
                    elif label.startswith(target_text):
                        prefix_matches.append(elem)
                    elif target_text in label or label in target_text:
                        substr_matches.append(elem)
                # 选择最佳匹配：精确 > 前缀 > 子串
                # 多个匹配时优先选 y > 0.4 的（避免顶部标题）
                def _pick_best(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
                    if not candidates:
                        return None
                    # 优先选下半部分
                    lower = [e for e in candidates if float(e.get("center", [0, 0.5])[1]) > 0.4]
                    if lower:
                        return lower[0]
                    return candidates[0]
                target_elem = _pick_best(exact_matches) or _pick_best(prefix_matches) or _pick_best(substr_matches)
                clicked = False
                if target_elem is not None:
                    cx, cy = self._norm_to_screen(target_elem.get("center", [0.5, 0.5]), screen_size)
                    try:
                        android.tap(cx, cy)
                        clicked = True
                        self._logger.info(LogCategory.MAIN, "VLM 交互点击按钮", text=target_text, coord=(cx, cy),
                                          label=str(target_elem.get("label", "")))
                    except Exception as exc:
                        self._logger.warning(LogCategory.MAIN, "点击按钮异常", error=str(exc))
                # 更新 actions 末尾的 clicked 字段
                actions[-1]["clicked"] = clicked
                if not clicked:
                    # 未找到按钮，tap 交互按钮兜底（手机端 keyevent F 无效）
                    self._vlm_press_interact(android, serial)
                time.sleep(2.0)
                continue

            if action == "wait":
                actions.append({"iteration": it_idx, "action": "wait"})
                time.sleep(2.5)
                continue

            # 未知动作
            actions.append({"iteration": it_idx, "action": "unknown", "raw": action})
            time.sleep(1.0)

        self._logger.warning(LogCategory.MAIN, "VLM 交互达到上限", task=task_name, max_iterations=max_iterations)
        teleport_count = sum(1 for a in actions if a.get("action") == "teleport_pipeline")
        rewalk_count = sum(1 for a in actions if a.get("action") == "rewalk_navigation")
        return {
            "status": "exhausted", "iterations": max_iterations,
            "actions": actions, "last_decision": last_decision,
            "teleport_happened": teleport_count > 0,
            "teleport_count": teleport_count,
            "reason": "max_iterations_reached",
            "rewalk_count": rewalk_count,
        }

    def _vlm_read_all_task_names(
        self, android: Any, serial: Optional[str], category: str,
    ) -> List[Dict[str, Any]]:
        """滚动读取整个分类的任务列表，用 VLM 提取任务名 + OCR 定位点击坐标。

        流程：
        1. 滚动到列表顶端
        2. 逐屏截图 → VLM 提取任务名 → OCR 定位坐标
        3. 向下滚动，重复直到列表底部（连续2屏无新任务判定到底）
        4. 去重合并

        Returns:
            [{"name": str, "center": [x, y], "category": str}] 列表
        """
        all_tasks: List[Dict[str, Any]] = []
        seen_names: set = set()
        scroll_region = [80, 160, 420, 520]
        swipe_distance = 280

        # 滚动到顶端
        self._scroll_task_list_to_top(android, serial, scroll_region, swipe_distance)

        # 逐屏读取
        max_screens = 10
        no_new_count = 0
        for screen_idx in range(max_screens):
            # VLM 读取任务名
            vlm_names = self._vlm_read_task_names(serial)
            if not vlm_names:
                break

            # OCR 定位坐标
            try:
                ocr_result = self.execute(
                    "scene.elements",
                    {"serial": serial, "enable_ocr": True, "enable_template": False, "enable_color": False},
                )
            except Exception:
                ocr_result = {}
            elements: List[Any] = []
            if isinstance(ocr_result, dict) and ocr_result.get("status") == "success":
                elements = ocr_result.get("elements", [])

            new_count = 0
            for name in vlm_names:
                if name in seen_names:
                    continue
                # 在 OCR 元素中查找该任务名的坐标
                center = self._find_task_center_in_ocr(name, elements, (1280, 720))
                if center is None:
                    # OCR 未找到，用屏幕中部作为兜底
                    center = [0.3, 0.3 + 0.08 * len(all_tasks)]
                all_tasks.append({
                    "name": name,
                    "center": center,
                    "category": category,
                })
                seen_names.add(name)
                new_count += 1

            # 连续2屏无新任务 → 到底
            if new_count == 0:
                no_new_count += 1
                if no_new_count >= 2:
                    break
            else:
                no_new_count = 0

            # 向下滚动
            self._swipe_task_list(android, serial, scroll_region, swipe_distance, direction="down")
            time.sleep(0.5)

        self._logger.info(
            LogCategory.MAIN, "VLM 滚动读取分类任务完成",
            category=category, count=len(all_tasks),
            names=[t["name"] for t in all_tasks],
        )
        return all_tasks

    def _find_task_center_in_ocr(
        self, task_name: str, elements: List[Any], screen_size: Tuple[int, int],
    ) -> Optional[List[float]]:
        """在 OCR 元素中查找任务名对应的点击坐标。

        策略：在 OCR 元素中查找包含任务名关键词的元素，返回其归一化中心坐标。
        """
        # 任务名可能被 OCR 拆成多个片段，取任务名前 4 个字符作为匹配关键词
        keyword = task_name[:4] if len(task_name) >= 4 else task_name
        for elem in elements:
            if not isinstance(elem, dict):
                continue
            label = str(elem.get("label", "")).strip()
            if keyword in label:
                center = elem.get("center")
                if center and float(center[0]) > 0.1:  # 排除左侧分类标签
                    return [float(center[0]), float(center[1])]
        return None

    def _scroll_task_list_to_top(
        self, android: Any, serial: Optional[str],
        scroll_region: List[int], swipe_distance: int,
    ) -> None:
        """滚动任务列表到顶端（连续向上滑动若干次，确保到顶）。"""
        cx = (scroll_region[0] + scroll_region[2]) // 2
        y_bottom = scroll_region[3] - 20
        y_top = scroll_region[1] + 20
        for _ in range(8):
            try:
                android.swipe(cx, y_bottom, cx, y_bottom - swipe_distance, duration_ms=400)
            except Exception:
                pass
            time.sleep(0.5)

    def _swipe_task_list(
        self, android: Any, serial: Optional[str],
        scroll_region: List[int], swipe_distance: int, direction: str = "down",
    ) -> None:
        """在任务列表区域向指定方向滑动。"""
        cx = (scroll_region[0] + scroll_region[2]) // 2
        if direction == "down":
            y1 = scroll_region[3] - 20
            y2 = y1 - swipe_distance
        else:
            y1 = scroll_region[1] + 20
            y2 = y1 + swipe_distance
        try:
            android.swipe(cx, y1, cx, y2, duration_ms=400)
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "滑动任务列表异常", error=str(exc))

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
            vlm_max_steps = int(options.get("TaskExecuteVlmMaxStepsValue", options.get("BlueTaskVlmMaxStepsValue", 30)))
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
        try:
            target_count = int(options.get("TaskExecuteTargetCountValue", 10))
        except (TypeError, ValueError):
            target_count = 10

        self._logger.info(
            LogCategory.MAIN, "开始执行分类任务",
            category=category, selected=len(selected_tasks) if selected_tasks else 0,
            vlm_max_steps=vlm_max_steps, vlm_step_timeout=vlm_step_timeout,
            max_verification_checks=max_verification_checks, target_count=target_count,
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
            # 点击目标分类标签并用 VLM 读取该分类全部任务
            self._click_category_by_name(android, serial, category)
            time.sleep(1.5)
            tasks_to_run = self._vlm_read_all_task_names(android, serial, category)

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

        # 3. 逐一执行（最多执行 target_count 个成功任务）
        completed: List[str] = []
        failed: List[str] = []
        for idx, task in enumerate(tasks_to_run):
            if len(completed) >= target_count:
                self._logger.info(
                    LogCategory.MAIN, "已达到目标完成数量，停止执行",
                    completed=len(completed), target=target_count,
                )
                break
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
            category=category, completed=len(completed), failed=len(failed), target=target_count,
        )

        return {
            "status": "success" if not failed else "partial",
            "command": "readtask.run_category",
            "flow": "run_category_tasks",
            "options": options,
            "category": category,
            "target_count": target_count,
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

    # 已知的全屏 UI 界面标志文字：BACK 可能无法直接退出这些界面，
    # 需要点击界面右上角/左上角的关闭按钮（通常是"X"或"关闭"）。
    # 检测到这些文字时，优先点击关闭按钮而非按 BACK。
    _STUCK_UI_KEYWORDS: Tuple[str, ...] = (
        "协议管理",     # 协议管理界面（任务"职责所在"误入）
        "装备制造",     # 装备制造界面
        "工业",         # 工业相关界面
        "工具箱",       # 工具箱界面
        "取消工业",     # 工业取消按钮所在界面
    )

    def _close_overlays_return_to_world(
        self,
        android: Any,
        serial: Optional[str],
        max_back_presses: int = 10,
    ) -> bool:
        """通过反复按 BACK / 点击关闭按钮关闭弹窗/对话/地图等覆盖层，返回大世界。

        VLM 导航结束后角色可能触发了 NPC 对话、消息界面、地图、协议管理等覆盖层，
        导致任务列表入口坐标（大世界 UI）点击无效。本方法逐次按 BACK 或点击关闭按钮，
        每次后用 OCR 备用判据检测是否已回到大世界。

        特殊处理：
        1. 大世界中按 BACK 会弹出"是否退出游戏？"对话框，此时不能
           再按 BACK（会循环弹窗），而是点击"取消"按钮关闭对话框。
        2. 某些全屏 UI（协议管理/装备制造等）BACK 无法直接退出，
           需要点击界面右上角/左上角的关闭按钮。检测到这些界面的标志文字时，
           优先尝试点击"关闭"按钮或界面角落的关闭区域。

        Returns:
            True 表示已回到大世界；False 表示按完 max_back_presses 次仍未回到大世界。
        """
        screen_size = self._get_screen_size(serial)
        for attempt in range(1, max_back_presses + 1):
            # 先检测当前画面文字
            try:
                ocr_result = self.execute(
                    "scene.elements",
                    {"serial": serial, "enable_ocr": True, "enable_template": False, "enable_color": False},
                )
            except Exception as exc:
                self._logger.warning(LogCategory.MAIN, "覆盖层检测 OCR 异常", attempt=attempt, error=str(exc))
                ocr_result = {}
            elements: List[Any] = []
            if isinstance(ocr_result, dict) and ocr_result.get("status") == "success":
                elements = ocr_result.get("elements", [])
            text = "".join(e.get("label", "") for e in elements if isinstance(e, dict))

            # 检测"是否退出游戏"对话框：大世界中按 BACK 会弹出此框，
            # 说明角色已在大世界，点击"取消"关闭即可
            if "退出游戏" in text or "是否退出" in text:
                self._logger.info(
                    LogCategory.MAIN, "检测到退出游戏对话框，点击取消关闭",
                    attempt=attempt,
                )
                # 点击"取消"按钮（通过 OCR 定位）
                cancel_clicked = False
                for elem in elements:
                    label = str(elem.get("label", "")).strip()
                    if label == "取消":
                        cx, cy = self._norm_to_screen(elem.get("center", [0.5, 0.5]), screen_size)
                        try:
                            android.tap(cx, cy)
                            cancel_clicked = True
                        except Exception as exc:
                            self._logger.warning(LogCategory.MAIN, "点击取消按钮异常", error=str(exc))
                        break
                if not cancel_clicked:
                    # 兜底：取消按钮通常在对话框左侧（归一化 x ~0.4）
                    try:
                        sx, sy = self._norm_to_screen([0.4, 0.55], screen_size)
                        android.tap(sx, sy)
                    except Exception:
                        pass
                time.sleep(1.5)
                # 退出游戏对话框出现意味着角色已在大世界
                return True

            # 检测是否已在大世界
            matched = [kw for kw in self._IN_WORLD_OCR_KEYWORDS if kw in text]
            if matched:
                self._logger.info(
                    LogCategory.MAIN, "覆盖层关闭后已回到大世界",
                    attempt=attempt, matched=matched,
                )
                return True

            # 检测已知的全屏 UI（协议管理/装备制造等）：BACK 无法直接退出，
            # 优先尝试点击 OCR 检测到的"关闭"/"返回"按钮，或点击已知关闭按钮坐标。
            # 注意："取消"通常是 UI 内的操作按钮（如取消制造），不是关闭按钮，
            # 仅在点击"关闭"/"返回"无效后，才尝试 BACK + 角落点击混合策略。
            stuck_ui_matched = [kw for kw in self._STUCK_UI_KEYWORDS if kw in text]
            if stuck_ui_matched:
                self._logger.info(
                    LogCategory.MAIN, "检测到已知全屏 UI，尝试点击关闭按钮",
                    attempt=attempt, ui_keywords=stuck_ui_matched,
                )
                close_clicked = False
                # 优先 OCR 定位"关闭"/"返回"按钮（不含"取消"，因为"取消"通常是
                # UI 内的操作按钮而非关闭按钮）。OCR 可能将多个文字合并为一个 label，
                # 用子串匹配。
                _CLOSE_KEYWORDS_STRICT = ("关闭", "返回", "退出")
                for elem in elements:
                    label = str(elem.get("label", "")).strip()
                    if not label or len(label) > 6:
                        continue
                    if any(kw in label for kw in _CLOSE_KEYWORDS_STRICT):
                        cx, cy = self._norm_to_screen(elem.get("center", [0.5, 0.5]), screen_size)
                        try:
                            android.tap(cx, cy)
                            close_clicked = True
                            self._logger.info(
                                LogCategory.MAIN, "点击关闭类按钮",
                                label=label, coord=(cx, cy),
                            )
                        except Exception as exc:
                            self._logger.warning(LogCategory.MAIN, "点击关闭按钮异常", error=str(exc))
                        break
                if not close_clicked:
                    # 未找到"关闭/返回"按钮：前 3 次尝试点击已知关闭坐标（任务列表
                    # 关闭按钮位置 (1225, 35)，许多面板共享此位置），3 次后切换到
                    # BACK + 角落点击混合策略，避免反复点击无效坐标。
                    if attempt <= 3:
                        try:
                            android.tap(self._TASK_LIST_CLOSE_COORD[0], self._TASK_LIST_CLOSE_COORD[1])
                            close_clicked = True
                            self._logger.info(
                                LogCategory.MAIN, "点击任务列表关闭坐标",
                                coord=self._TASK_LIST_CLOSE_COORD, attempt=attempt,
                            )
                        except Exception:
                            pass
                    else:
                        # 3 次后混合策略：先 BACK 后角落点击
                        self._logger.info(
                            LogCategory.MAIN, "切换到 BACK + 角落点击混合策略",
                            attempt=attempt,
                        )
                        try:
                            android.keyevent("KEYCODE_BACK")
                        except Exception:
                            pass
                        time.sleep(1.0)
                        # BACK 后尝试右上角和左上角
                        for close_pos in ([0.95, 0.05], [0.05, 0.05]):
                            sx, sy = self._norm_to_screen(close_pos, screen_size)
                            try:
                                android.tap(int(sx), int(sy))
                                self._logger.info(
                                    LogCategory.MAIN, "混合策略点击角落",
                                    coord=(int(sx), int(sy)), attempt=attempt,
                                )
                            except Exception:
                                pass
                            time.sleep(0.8)
                            if self._verify_in_world_by_ocr(serial):
                                return True
                time.sleep(1.5)
                continue

            # 不在大世界也没有退出对话框/已知全屏 UI，按 BACK 关闭当前覆盖层
            try:
                android.keyevent("KEYCODE_BACK")
            except Exception as exc:
                self._logger.warning(
                    LogCategory.MAIN, "BACK 按键异常", attempt=attempt, error=str(exc),
                )
            time.sleep(1.2)

        # 最后再检测一次
        if self._verify_in_world_by_ocr(serial):
            return True
        self._logger.warning(
            LogCategory.MAIN, "反复按 BACK 仍未回到大世界",
            max_back_presses=max_back_presses,
        )
        return False

    def _force_restart_game(
        self,
        android: Any,
        serial: Optional[str],
        runtime: Any,
        client_version: str,
    ) -> bool:
        """强制关闭并重启游戏，作为卡死界面的最终兜底。

        当 _close_overlays_return_to_world 反复按 BACK / 点击关闭按钮均无法退出
        某些全屏 UI（如"协议管理"弹出菜单）时，游戏实际卡在一个无法通过常规
        手段退出的界面。此时唯一可靠的方式是 force-stop 游戏进程并重新启动，
        让游戏从大世界主城重新加载，彻底摆脱卡死的 UI。

        Returns:
            True 表示重启后已进入大世界；False 表示重启失败。
        """
        self._logger.warning(
            LogCategory.MAIN, "覆盖层无法关闭，强制重启游戏",
        )
        try:
            package = _get_game_package(self._config)
            android.shell(f"am force-stop {package}")
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "force-stop 异常", error=str(exc))
        time.sleep(3.0)
        # _ensure_game_in_world 检测到游戏未运行时会通过 AndroidOpenGame 重新启动
        return self._ensure_game_in_world(runtime, serial, client_version)

    def _open_task_list_if_needed(
        self,
        runtime: Any,
        serial: Optional[str],
        client_version: str,
    ) -> Dict[str, Any]:
        """若当前不在任务列表页，则返回大世界并点击任务列表入口。"""
        if self._is_task_list_page(serial):
            return {"status": "success", "step": "already_on_task_list"}

        android = self.android(serial)

        # VLM 导航/交互后可能停留在 NPC 对话、消息、地图等覆盖层上，
        # 直接点击任务图标坐标无效。先用 BACK 反复关闭覆盖层回到大世界。
        if not self._verify_in_world_by_ocr(serial):
            self._logger.info(LogCategory.MAIN, "检测到不在大世界，尝试关闭覆盖层")
            if not self._close_overlays_return_to_world(android, serial):
                # BACK 无法关闭时，强制重启游戏作为最终兜底
                if not self._force_restart_game(android, serial, runtime, client_version):
                    return {"status": "error", "message": "关闭覆盖层并返回大世界失败"}
            else:
                # _close_overlays_return_to_world 返回 True，但可能误判（如
                # 协议管理 UI 关闭后停留在地图界面，OCR 恰好匹配到"探索"等关键词）。
                # 二次验证：若仍不在大世界，强制重启。
                if not self._verify_in_world_by_ocr(serial):
                    self._logger.warning(
                        LogCategory.MAIN,
                        "覆盖层关闭返回True但OCR仍检测不到大世界特征，强制重启",
                    )
                    if not self._force_restart_game(android, serial, runtime, client_version):
                        return {"status": "error", "message": "关闭覆盖层并返回大世界失败"}

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
            # 重试一次：先 pipeline，再手动 tap 兜底
            try:
                runtime.run_pipeline("ReadTaskListClickTaskIcon", {})
            except Exception:
                pass
            time.sleep(2.0)
            if not self._is_task_list_page(serial):
                # pipeline 点击可能模板匹配到错误位置，手动 tap 任务列表图标坐标
                self._logger.info(LogCategory.MAIN, "pipeline 点击未打开任务列表，手动 tap 兜底")
                try:
                    android.tap(self._TASK_LIST_ICON_COORD[0], self._TASK_LIST_ICON_COORD[1])
                except Exception as exc:
                    self._logger.warning(LogCategory.MAIN, "手动 tap 任务图标异常", error=str(exc))
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

    def _get_screen_size(self, serial: Optional[str] = None) -> Tuple[int, int]:
        """获取设备屏幕分辨率，失败时默认 1280x720。

        ``serial`` 默认值为 ``None``，避免调用方遗漏时传入字符串 ``"None"``。
        """
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

    # 屏幕分辨率缓存：VLM keyevent 高频调用，每次截屏获取分辨率开销过大。
    # 以 serial 为 key 缓存，同一设备分辨率不变，切换设备时自然刷新。
    _SCREEN_SIZE_CACHE: Dict[Optional[str], Tuple[int, int]] = {}

    def _get_screen_size_cached(self, serial: Optional[str] = None) -> Tuple[int, int]:
        """带缓存的屏幕分辨率获取。

        首次调用同 _get_screen_size（截屏），后续直接返回缓存。
        """
        if serial not in self._SCREEN_SIZE_CACHE:
            self._SCREEN_SIZE_CACHE[serial] = self._get_screen_size(serial)
        return self._SCREEN_SIZE_CACHE[serial]

    def _norm_to_screen(
        self,
        center: Optional[List[float]],
        screen_size: Tuple[int, int],
    ) -> Tuple[int, int]:
        """将归一化 OCR 中心坐标转换为屏幕坐标。None/空时返回屏幕中心。"""
        w, h = screen_size
        if not center:
            return w // 2, h // 2
        try:
            cx = float(center[0]) if len(center) > 0 else 0.5
            cy = float(center[1]) if len(center) > 1 else 0.5
        except (TypeError, ValueError, IndexError):
            return w // 2, h // 2
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

        # TELEPORT-FAIL-LIMIT: 每任务传送失败计数器。
        # 某些任务（如"风雨欲来·阿伯莉采石场"）的传送 pipeline 节点全部失效
        # （SceneEnterWorld* 假阳性 / SceneEnterMap* 超时 / EnterTeleport 超时）。
        # 若不限制，VLM 交互循环会反复触发 _vlm_teleport_to_area，每次 90s
        # （3 pipeline × 30s timeout）的浪费，且最终进程会因 maaend.screenshot()
        # 在 pipeline 孤儿线程下挂起而僵死。
        # 策略：每任务最多 2 次 _vlm_teleport_to_area 失败（ok=False 且
        # reason != "already_in_target"），超过则跳过预传送 + 跳过交互循环中的
        # 传送拦截，直接让 VLM 追踪导航在本地图内尝试（即使可能失败）。
        self._task_teleport_failures = 0
        self._task_teleport_failures_max = 2

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
                # 仅当按钮文字是"开始追踪"时才点击。
                # 注意：不要用"追踪"作为判据——"停止追踪"也包含"追踪"二字，
                # 若任务已被追踪（按钮显示"停止追踪"），误点击会关闭追踪，
                # 导致大世界无追踪标识，VLM 导航完全失效。
                if label == "开始追踪" or (("开始" in label) and ("追踪" in label) and ("停止" not in label)):
                    ecx, ecy = self._norm_to_screen(elem.get("center", [0.5, 0.5]), screen_size)
                    self._logger.info(LogCategory.MAIN, "点击追踪按钮", task=task_name, label=label, coord=(ecx, ecy))
                    try:
                        android.tap(ecx, ecy)
                    except Exception as exc:
                        self._logger.warning(LogCategory.MAIN, "点击追踪按钮异常", error=str(exc))
                    time.sleep(2.0)
                    break
                # 如果按钮已经是"停止追踪"，说明任务已在追踪中，无需点击
                if label == "停止追踪" or (("停止" in label) and ("追踪" in label)):
                    self._logger.info(LogCategory.MAIN, "任务已在追踪中，跳过点击追踪按钮", task=task_name, label=label)
                    break

        # 3. 关闭任务列表，进入大世界
        self._close_task_list(android)
        time.sleep(1.5)
        # 3.1 确保已回到 3D 大世界：关闭任务列表后游戏可能停留在地图/传送界面
        # （尤其当任务条目点击触发了传送地图时）。此时直接开始 VLM 追踪导航会
        # 完全失效（所有 step stuck），且 VLM 交互循环会在地图上反复点击地名。
        # 用 _close_overlays_return_to_world 通过 BACK 反复关闭覆盖层直到回到大世界。
        # 注意：必须用 _is_in_big_world（严格判定：3D 大世界特征），不能用
        # _verify_in_world_by_ocr（宽松判定：主菜单"干员"等关键词），否则任务列表
        # 未完全关闭时 "干员" 仍在底层主菜单可见，会误判已到大世界，导致后续
        # Step 0 区域验证失败、触发不必要的传送。
        if not self._is_in_big_world(serial):
            self._logger.info(
                LogCategory.MAIN, "关闭任务列表后不在大世界，尝试关闭覆盖层",
                task=task_name,
            )
            self._close_overlays_return_to_world(android, serial)
            time.sleep(1.5)
            # 再次确认：若仍不在大世界，多等一会再检查一次
            if not self._is_in_big_world(serial):
                time.sleep(2.0)
                if not self._is_in_big_world(serial):
                    self._logger.warning(
                        LogCategory.MAIN, "关闭覆盖层后仍不在大世界，继续流程",
                        task=task_name,
                    )

        # 3.5 预传送：从任务名提取目标区域，若 _TASK_AREA_MAP_NODE 有匹配，
        # 通过 VLM 驱动传送（SceneEnterMap* 进入地图视图 + VLM 点击传送点）
        # 到目标区域附近。避免 VLM 追踪导航在地图界面迷失。
        # 这是传送拦截机制的延伸：与其让 VLM 在地图界面反复点击无效文字，
        # 不如在导航开始前就传送到目标区域，VLM 只需处理到达后的本地交互。
        target_area_pre = ""
        for sep in ("·", "·", "·", "•", "・"):
            if sep in task_name:
                target_area_pre = task_name.rsplit(sep, 1)[1].strip()
                break
        map_node_pre = self._TASK_AREA_MAP_NODE.get(target_area_pre) if target_area_pre else None
        if map_node_pre and self._task_teleport_failures < self._task_teleport_failures_max:
            self._logger.info(
                LogCategory.MAIN, "预传送至目标区域（VLM 驱动）",
                task=task_name, target_area=target_area_pre, map_node=map_node_pre,
            )
            tp_pre = self._vlm_teleport_to_area(
                android, serial, target_area_pre, runtime=runtime,
            )
            self._logger.info(
                LogCategory.MAIN, "预传送 VLM 结果",
                area=target_area_pre, ok=tp_pre.get("ok"),
                reason=tp_pre.get("reason"),
            )
            # TELEPORT-FAIL-LIMIT: 仅当 ok=False 且 reason != "already_in_target"
            # 才算失败（already_in_target 是角色已在目标区域的特殊情况，非失败）。
            if not tp_pre.get("ok") and tp_pre.get("reason") != "already_in_target":
                self._task_teleport_failures += 1
                self._logger.warning(
                    LogCategory.MAIN, "预传送失败，计数器递增",
                    area=target_area_pre, failures=self._task_teleport_failures,
                    max=self._task_teleport_failures_max,
                    reason=tp_pre.get("reason"),
                )
            # 等待传送加载完成
            time.sleep(3.0)
            # 传送后可能仍停留在地图视图，需关闭地图返回 3D 大世界，
            # 否则 VLM 追踪导航会在地图界面上迷失（屏幕上没有任务追踪标识）。
            # 按 BACK 关闭地图，最多尝试 3 次。
            for close_attempt in range(3):
                if self._is_in_big_world(serial):
                    break
                self._logger.info(
                    LogCategory.MAIN, "传送后不在大世界，按 BACK 关闭地图",
                    area=target_area_pre, attempt=close_attempt + 1,
                )
                try:
                    android.keyevent("KEYCODE_BACK")
                except Exception as exc:
                    self._logger.warning(LogCategory.MAIN, "BACK 键异常", error=str(exc))
                time.sleep(1.5)
            else:
                self._logger.warning(
                    LogCategory.MAIN, "传送后 3 次 BACK 仍不在大世界，继续流程",
                    area=target_area_pre,
                )
        elif map_node_pre and self._task_teleport_failures >= self._task_teleport_failures_max:
            self._logger.warning(
                LogCategory.MAIN, "预传送跳过：本任务传送失败次数已达上限",
                task=task_name, target_area=target_area_pre,
                failures=self._task_teleport_failures,
                max=self._task_teleport_failures_max,
            )

        # 4-5. VLM 追踪标识导航 + 交互循环（可重试）
        # 当交互循环因 already_in_target_stuck 退出时（角色还在远处，VLM 误点
        # 任务追踪文字），重新触发追踪导航让角色继续前进。最多重试 3 轮。
        max_nav_rounds = 3
        interact_result = {"status": "pending", "iterations": 0}
        for nav_round in range(max_nav_rounds):
            # 4. VLM 追踪标识导航
            self._logger.info(
                LogCategory.MAIN, "VLM 追踪标识导航开始",
                task=task_name, category=category, round=nav_round + 1,
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
                self._logger.info(
                    LogCategory.MAIN, "VLM 追踪标识导航结束",
                    task=task_name,
                    status=walk_result.get("status") if isinstance(walk_result, dict) else "invalid",
                    round=nav_round + 1,
                )
            except Exception as exc:
                self._logger.warning(LogCategory.MAIN, "VLM 追踪导航异常", task=task_name, error=str(exc))

            # 5. 到达后用 VLM 驱动交互循环：截图→VLM 决策→执行→重复
            # 替代之前的"盲按 F 13 次"策略。VLM 每步根据截图决定 press_f /
            # click_text / wait / task_complete / no_action，能识别对话/按钮/结算。
            # 传送拦截：当 VLM 决策点击"前往传送"时，通过 pipeline 直接传送。
            interact_result = self._vlm_interact_for_task(
                android, serial, task_name, max_iterations=30, runtime=runtime,
            )
            self._logger.info(
                LogCategory.MAIN, "VLM 交互循环结束",
                task=task_name, status=interact_result.get("status"),
                iterations=interact_result.get("iterations"),
                round=nav_round + 1,
            )
            # 判定是否需要重试追踪导航：
            # - 交互循环正常结束（task_complete/no_action）→ 不重试
            # - 交互循环因 already_in_target_stuck / press_f_exhausted / max_iterations_reached 退出
            #   → 角色还在远处，重试追踪导航
            # - no_action_exhausted 不重试：REWALK-LIMIT 已给 VLM 2 次机会（180 步），
            #   再重试（round 2/3 各 180 步）纯属浪费时间，VLM 仍找不到 NPC
            interact_status = interact_result.get("status", "")
            interact_reason = interact_result.get("reason", "")
            needs_retry = (
                interact_status == "exhausted"
                and interact_reason in (
                    "goto_x_already_in_target_stuck",
                    "goto_teleport_already_in_target_stuck",
                    "press_f_exhausted",
                    "max_iterations_reached",
                )
            )
            if needs_retry:
                if nav_round < max_nav_rounds - 1:
                    self._logger.warning(
                        LogCategory.MAIN, "VLM 交互因角色未到达目标退出，重新触发追踪导航",
                        task=task_name, round=nav_round + 1, next_round=nav_round + 2,
                        reason=interact_reason,
                    )
                    # 等待一下让角色稳定
                    time.sleep(2.0)
                    continue
                else:
                    self._logger.warning(
                        LogCategory.MAIN, "VLM 追踪+交互已重试上限，继续验证",
                        task=task_name, rounds=max_nav_rounds,
                    )
            break  # 其他状态不重试

        # 等待任务完成动画/奖励结算
        time.sleep(2.0)

        # 6. 频繁检查任务列表，确认任务完成（VLM 读取任务名，对比确认）
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

            # VLM 读取当前屏任务名，检查任务是否还在列表中
            # 最多检查3屏（滚动），若任务不在任何屏中则判定完成
            scroll_region = [80, 160, 420, 520]
            swipe_distance = 280
            self._scroll_task_list_to_top(android, serial, scroll_region, swipe_distance)
            task_still_in_list = False
            vlm_fail_count = 0
            vlm_success_count = 0
            for screen_idx in range(4):
                current_names = self._vlm_read_task_names(serial)
                # VLM 调用失败时返回空集合，不能据此判定任务已不在列表
                # 否则网络抖动会导致误判完成。失败时跳过此屏，不计入判定。
                if not current_names:
                    vlm_fail_count += 1
                    # 滚动到下一屏继续尝试
                    self._swipe_task_list(android, serial, scroll_region, swipe_distance, direction="down")
                    time.sleep(0.5)
                    continue
                vlm_success_count += 1
                # 精确匹配或前缀匹配（VLM 可能返回略微不同的名称）
                task_keyword = task_name[:6] if len(task_name) >= 6 else task_name
                if any(task_keyword in name or name in task_name for name in current_names):
                    task_still_in_list = True
                    break
                # 滚动到下一屏
                self._swipe_task_list(android, serial, scroll_region, swipe_distance, direction="down")
                time.sleep(0.5)

            self._logger.info(
                LogCategory.MAIN, "分类任务完成状态检查",
                task=task_name, category=category, attempt=check_idx + 1,
                still_in_list=task_still_in_list,
                vlm_success=vlm_success_count, vlm_fail=vlm_fail_count,
            )

            # 所有屏 VLM 都失败 → 无法判定，跳过此次检查并重试
            if vlm_success_count == 0:
                self._logger.warning(
                    LogCategory.MAIN, "验证时 VLM 全部失败，跳过此次检查",
                    task=task_name, attempt=check_idx + 1, fail_count=vlm_fail_count,
                )
                self._close_task_list(android)
                time.sleep(5.0)
                continue

            if not task_still_in_list:
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

        OCR 硬验证：VLM（qwen3.5-35b free）经常误报 arrived，必须用 OCR
        检查屏幕上是否真有交互关键词（交谈/拾取/互动/F）才接受 arrived。
        """
        nav = self.navigator()
        step_timeout = params.get("step_timeout")
        serial = params.get("serial")

        # 构造 OCR 验证函数：接收 PNG bytes，返回 OCR 标签列表。
        # 用 scene service 的 identify_from_bytes（与 scene.elements 命令同源，
        # 但直接对传入的 bytes 做 OCR，避免重新截图）。
        def _ocr_verify_fn(frame_bytes: bytes) -> List[str]:
            """对给定 PNG bytes 做 OCR，返回标签列表。"""
            try:
                svc = self.scene()
                page = svc.identify_from_bytes(frame_bytes)
                return [str(e.label) for e in page.elements if e.label]
            except Exception as exc:
                self._logger.warning(LogCategory.MAIN, "OCR 验证函数异常", error=str(exc))
                return []

        return nav.to_tracking_vlm(
            llm_client=self._llm_client_instance,
            max_steps=int(params.get("max_steps", 40)),
            keyevent_fn=self._vlm_keyevent,
            step_timeout=float(step_timeout) if step_timeout is not None else None,
            ocr_fn=_ocr_verify_fn,
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

        对于移动键（W/A/S/D），游戏是手机端触屏操作，keyevent 无效，
        改用 swipe 模拟左下角虚拟摇杆拖动：
        - W (forward): 摇杆从中心向上拖
        - S (backward): 摇杆从中心向下拖
        - A (left): 摇杆从中心向左拖
        - D (right): 摇杆从中心向右拖
        - Q (turn_left): 改用 swipe 屏幕右侧向左拖（相机左旋）
        - E (turn_right): 改用 swipe 屏幕右侧向右拖（相机右旋）
        - F (interact): 改用 tap 屏幕交互按钮位置（手机端 F keyevent 无效）

        坐标基于 1280x720 参考分辨率，通过 _scale_for_screen 按实际分辨率缩放。
        屏幕分辨率缓存于 _SCREEN_SIZE_CACHE，避免每次 keyevent 都截屏。
        """
        try:
            screen_size = self._get_screen_size_cached()
            # 移动键映射到 swipe 摇杆操作
            # 摇杆中心通过截屏重心分析确定为 (220, 560)，拖动距离 90px
            _JOYSTICK_CENTER_REF = (220, 560)
            _JOYSTICK_RADIUS_REF = 90
            jc_x, jc_y = self._scale_for_screen(_JOYSTICK_CENTER_REF, screen_size)
            jr = self._scale_radius(_JOYSTICK_RADIUS_REF, screen_size)
            _MOVE_KEY_SWIPE = {
                "KEYCODE_W": (jc_x, jc_y - jr),  # 上
                "KEYCODE_S": (jc_x, jc_y + jr),  # 下
                "KEYCODE_A": (jc_x - jr, jc_y),  # 左
                "KEYCODE_D": (jc_x + jr, jc_y),  # 右
            }
            # 相机旋转键映射到屏幕右侧 swipe（手机端相机旋转手势）
            _CAMERA_CENTER_REF = (960, 400)
            _CAMERA_SWIPE_DIST_REF = 300
            cc_x, cc_y = self._scale_for_screen(_CAMERA_CENTER_REF, screen_size)
            cd = self._scale_radius(_CAMERA_SWIPE_DIST_REF, screen_size)
            _TURN_KEY_SWIPE = {
                "KEYCODE_Q": (cc_x - cd, cc_y),  # 左旋
                "KEYCODE_E": (cc_x + cd, cc_y),  # 右旋
            }
            if key in _MOVE_KEY_SWIPE:
                if duration is not None:
                    dur_ms = max(800, min(int(duration * 1000), 5000))
                else:
                    dur_ms = 2000
                target_x, target_y = _MOVE_KEY_SWIPE[key]
                android.swipe(
                    jc_x, jc_y,
                    target_x, target_y,
                    duration_ms=dur_ms,
                )
            elif key in _TURN_KEY_SWIPE:
                if duration is not None:
                    dur_ms = max(300, min(int(duration * 1000), 1500))
                else:
                    dur_ms = 500
                target_x, target_y = _TURN_KEY_SWIPE[key]
                android.swipe(
                    cc_x, cc_y,
                    target_x, target_y,
                    duration_ms=dur_ms,
                )
            elif key == "KEYCODE_F":
                self._vlm_press_interact(android)
            else:
                if duration is not None and duration > 0.3:
                    repeats = max(1, int(duration / 0.15))
                    for _ in range(repeats):
                        android.keyevent(key)
                        time.sleep(0.12)
                else:
                    android.keyevent(key)
        except Exception as exc:
            self._logger.warning("VLM keyevent '%s' failed: %s", key, exc)

    @staticmethod
    def _scale_for_screen(ref_coord: Tuple[int, int], screen_size: Tuple[int, int]) -> Tuple[int, int]:
        """将基于 1280x720 的参考坐标按实际分辨率缩放。"""
        ref_w, ref_h = 1280, 720
        sw, sh = screen_size
        return int(round(ref_coord[0] * sw / ref_w)), int(round(ref_coord[1] * sh / ref_h))

    @staticmethod
    def _scale_radius(ref_r: int, screen_size: Tuple[int, int]) -> int:
        """将参考半径按实际分辨率等比缩放（取宽高缩放的平均值）。"""
        ref_w, ref_h = 1280, 720
        sw, sh = screen_size
        return int(round(ref_r * (sw / ref_w + sh / ref_h) / 2))

    def _vlm_press_interact(self, android: Any, serial: Optional[str] = None) -> None:
        """模拟 F 键交互：手机端 keyevent F 无效，改为 tap 屏幕交互按钮位置。

        坐标基于 1280x720 参考分辨率，通过 _scale_for_screen 按实际分辨率缩放。
        """
        screen_size = self._get_screen_size_cached()
        interact_btn = self._scale_for_screen((1100, 400), screen_size)
        dialog_area = self._scale_for_screen((640, 500), screen_size)
        try:
            android.tap(interact_btn[0], interact_btn[1], serial=serial)
            time.sleep(0.3)
            android.tap(dialog_area[0], dialog_area[1], serial=serial)
        except Exception as exc:
            self._logger.warning(LogCategory.MAIN, "vlm_press_interact 失败", error=str(exc))
            try:
                android.keyevent("KEYCODE_F")
            except Exception:
                pass
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
            # SCREENSHOT-PRIORITY: 优先使用 maaend.screenshot()（有 8s 硬超时保护），
            # 而非 android.screenshot()（scrcpy 未就绪时返回 None）。
            # 原因同 _screenshot 方法的修复：scrcpy 新进程启动需 10-15s 才能收到首帧，
            # 期间返回 None 导致 scene.elements 失败，进而导致 _is_in_big_world 等判定失效。
            image_bytes = None
            try:
                legacy = getattr(self, "_maaend", None)
                if legacy is not None and not self._maaend_clients:
                    image_bytes = legacy.screenshot()
                if image_bytes is None:
                    runtime = self.maaend(serial)
                    image_bytes = runtime.screenshot()
            except Exception as exc:
                self._logger.warning(LogCategory.MAIN, "_prepare_screen maaend.screenshot 异常", error=str(exc))
                image_bytes = None
            # maaend 失败时兜底用 AndroidRuntime (scrcpy)
            if image_bytes is None:
                try:
                    image_bytes = self.android(serial).screenshot(serial=serial)
                except Exception as exc:
                    self._logger.warning(LogCategory.MAIN, "_prepare_screen android.screenshot 异常", error=str(exc))
                    image_bytes = None
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
