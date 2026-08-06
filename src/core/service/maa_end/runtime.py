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
from queue import Empty, Queue

from core.foundation.constants import (
    ADB_PATH_DEFAULT,
    DEFAULT_DEVICE_ADDRESS,
    GAME_PACKAGE_ENDFIELD,
)
from core.foundation.logger import LogCategory, get_logger
from core.foundation.paths import get_project_root
from core.foundation.timeout_utils import run_with_timeout


def _strip_json_comments(text: str) -> str:
    """Remove // line comments and /* */ block comments from a JSON string.

    MaaFW's resource JSON (rapidjson) legitimately allows both comment styles,
    so upstream task/preset/interface files shipped under 3rd-part/maaend may
    contain them. Python's ``json`` rejects comments, so we strip them outside
    of string literals before parsing. String contents are preserved verbatim.

    Also strips a leading UTF-8 BOM (``\\ufeff``) if present, since some
    upstream pipeline JSONs are saved with BOM and ``json.loads`` rejects it
    with "Unexpected UTF-8 BOM (decode using utf-8-sig)".
    """
    if text and text[0] == "\ufeff":
        text = text[1:]
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

# Point maa library to the site-package bundled MaaFramework DLLs.
# After upgrading pip maafw to v5.12.2 (which fixes PPOCRv6 model loading
# and pipeline OCR node parsing), the project DLLs at 3rd-part/maaend/agent/maafw/
# are older v5.11.x and incompatible. We redirect MAAFW_BINARY_PATH to the
# bundled Python site-packages maa/bin where the upgraded DLLs live.
_PROJECT_ROOT = get_project_root()
_SITE_BIN_DIR = _PROJECT_ROOT / "3rd-part" / "python" / "Lib" / "site-packages" / "maa" / "bin"
_DEFAULT_DLL_DIR = _SITE_BIN_DIR if _SITE_BIN_DIR.is_dir() else None

# 方案 A1：在 import maa.* 之前注入 MAAFW_BINARY_PATH，确保主 Python 进程加载项目
# 自带的 OLDER 版本 MaaFramework.dll（与 3rd-part/maaend/resource 版本匹配），
# 避免加载用户 site-packages 中 NEWER 版本 DLL 触发 Resource.Loading.Failed。
# maa/__init__.py 在 import 时执行 Library.open(path)，path 取自该环境变量。
if _DEFAULT_DLL_DIR is not None and os.environ.get("MAAFW_BINARY_PATH") is None:
    os.environ["MAAFW_BINARY_PATH"] = str(_DEFAULT_DLL_DIR.resolve())

MAAFW_AVAILABLE = False
try:
    from maa.agent_client import AgentClient
    from maa.controller import AdbController, ControllerEventSink
    from maa.define import MaaAdbInputMethodEnum, MaaAdbScreencapMethodEnum, MaaLoggingLevel
    from maa.event_sink import NotificationType
    from maa.resource import Resource
    from maa.tasker import Tasker
    from maa.toolkit import Toolkit
    MAAFW_AVAILABLE = True
except ImportError:
    AgentClient = None  # type: ignore[misc,assignment]
    Resource = None  # type: ignore[misc,assignment]
    Tasker = None  # type: ignore[misc,assignment]
    AdbController = None  # type: ignore[misc,assignment]
    ControllerEventSink = None  # type: ignore[misc,assignment]
    NotificationType = None  # type: ignore[misc,assignment]
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


_INPUT_ACTIONS = frozenset({
    "Click", "Swipe", "Scroll", "ClickKey", "KeyDown", "KeyUp",
    "TouchDown", "TouchUp", "TouchMove", "LongPress", "LongPressKey",
    "InputText", "MultiSwipe",
})


class _InputObservationSink(ControllerEventSink if ControllerEventSink is not None else object):
    """Forward completed MaaFW controller actions to a non-blocking observer."""

    def __init__(self, runtime: "MaaEndRuntime") -> None:
        self._runtime = runtime

    def on_controller_action(self, controller: Any, noti_type: Any, detail: Any) -> None:
        if NotificationType is not None and noti_type != NotificationType.Succeeded:
            return
        action = str(getattr(detail, "action", "") or "")
        if action not in _INPUT_ACTIONS:
            return
        self._runtime._enqueue_input_observation(
            controller,
            action,
            getattr(detail, "param", {}) or {},
            getattr(detail, "info", {}) or {},
        )


class MaaEndRuntime:
    """Thin wrapper around MaaFramework that behaves like MaaEnd's runner."""

    def __init__(
        self,
        maaend_root: Optional[str] = None,
        device_address: str = DEFAULT_DEVICE_ADDRESS,
        adb_path: str = ADB_PATH_DEFAULT,
        adb_restart_on_timeout: bool = True,
        game_package: str = GAME_PACKAGE_ENDFIELD,
        client_version: str = "CN",
    ):
        self.logger = get_logger()
        self._maaend_root = Path(maaend_root) if maaend_root else self._default_maaend_root()
        self._device_address = device_address
        self._adb_path = str(get_project_root() / adb_path)
        self._adb_restart_on_timeout = bool(adb_restart_on_timeout)
        self._game_package = (game_package or "").strip() or GAME_PACKAGE_ENDFIELD
        self._client_version = (client_version or "CN").strip() or "CN"
        self._resource_profile = self._resource_profile_for_version(self._client_version)
        self._resource: Optional[Any] = None
        self._tasker: Optional[Any] = None
        self._controller: Optional[Any] = None
        self._input_sink: Optional[Any] = None
        self._input_sink_id: Optional[int] = None
        self._input_observation_queue: Queue[tuple[Any, str, Dict[str, Any], Dict[str, Any]]] = Queue(maxsize=128)
        self._input_observation_stop = threading.Event()
        self._input_observation_thread: Optional[threading.Thread] = None
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
        # 用户主动停止事件：由 request_stop() 设置，_run_task_with_retry/_recover_and_retry/
        # _post_game_restart_cleanup 在关键节点检查，避免停止后仍执行 RecoverGame 流程。
        # 当前 CLI 子进程模式下，GUI 通过 kill QProcess 直接终止子进程即可生效；
        # 此 event 作为防御性设计，便于将来 CLI 改为长驻/RPC 模式时通过命令设置。
        self._user_stop_event: threading.Event = threading.Event()
        # 多实例隔离：agent_id 含 instance_tag，避免跨实例同时启动 go-service 时碰撞
        try:
            from core.foundation.instance import get_instance_id
            self._instance_tag = get_instance_id()
        except Exception:
            self._instance_tag = "default"


    def _default_maaend_root(self) -> Path:
        return get_project_root() / "3rd-part" / "maaend"

    @staticmethod
    def _resource_profile_for_version(client_version: str) -> str:
        return "cloud" if str(client_version).strip().lower() == "cloudcn" else "default"

    def set_client_version(self, client_version: str) -> None:
        """Select the primary MaaEnd resource bundle before loading it."""
        normalized = (client_version or "CN").strip() or "CN"
        profile = self._resource_profile_for_version(normalized)
        if profile != self._resource_profile and self._connected:
            raise RuntimeError("不能在已连接的 MaaEnd runtime 上切换客户端资源版本")
        self._client_version = normalized
        self._resource_profile = profile

    @property
    def client_version(self) -> str:
        return self._client_version

    def _primary_resource_name(self) -> str:
        return "resource_cloud" if self._resource_profile == "cloud" else "resource"

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
    _SCREENCAP_TIMEOUT_S = 10
    _MAX_TASK_RETRIES = 1

    # 不需要「先回到主世界」前置的任务：自身负责启动游戏/恢复，或本身就是进入主世界。
    # 其他任务（VisitFriends/SellProduct/DijiangRewards/DailyRewards/CreditShoppingN2 等）
    # 假设从主世界开始，若前一任务留下非主世界页面状态会导致 InWorld 误匹配。
    _TASKS_SKIP_ENTER_WORLD = frozenset({
        "AndroidOpenGame", "PCOpenGame", "OpenGame",
        "RecoverGame", "StopApp", "StartApp",
    })

    # 目标即「进入游戏/处于主世界」的启动类任务。其 pipeline 在云冷启动时可能因
    # 加载闪屏/首页未被 OpenGame 链覆盖而报失败（假阴性），但游戏实际已加载或可由
    # 通用 SceneAnyEnterWorld 推进到主世界。run_task 对此类任务的失败做有界纠正，
    # 与 _run_task_once 的 False-Success（假阳性）纠正对称，避免队列首项误报失败。
    _TASKS_OPEN_GAME = frozenset({
        "AndroidOpenGame", "PCOpenGame", "OpenGame", "RecoverGame",
    })

    # 长时间运行任务：好友拜访（53 个好友 × 加载+操作+退出 ≈ 15-25 分钟）、
    # 信用商店批量购买等。300s 看门狗会误杀，需更长超时。
    # DijiangRewards：多子任务（接待室/制造舱/培育舱/线索/情绪恢复/种子提取）串联，实测 8-15 分钟
    # AutoCollect：22 条路线 × (传送+VLM 导航+采集+OCR 验证+重试)，实测 20-40 分钟
    # AutoStockpile/AutoSell/DailyRewards：含 SubTask 串联（物资调度/自动售卖/每日奖励领取），
    # 实测 5-15 分钟，300s 看门狗在云游戏高延迟环境下会误杀
    _TASKS_LONG_RUNNING = frozenset({
        "VisitFriends",
        "DijiangRewards",
        "AutoCollect",
        "AutoStockpile",
        "AutoSell",
        "DailyRewards",
    })

    def _connect_once(self) -> bool:
        # ★ 强制横屏旋转：MuMu 等模拟器物理显示为竖屏(720x1280)，但云终末地等游戏
        # 以 ROTATION_90 横屏渲染(1280x720)。MaaFW 的 screencap 返回原始物理帧，
        # 导致 pipeline JSON 中按横屏设计的 ROI 坐标全部越界。通过 ADB 设置
        # user_rotation=1 强制系统横屏，使 screencap 输出与 pipeline 预期一致。
        self._force_landscape_rotation()
        self._resource = Resource()
        # ★ 触控通道：优先 Maatouch（高速 socket 协议），回退到 Minitouch/AdbShell。
        # 在云终末地等精简 Android 环境中 Maatouch 二进制可能无法部署，此时 MaaFW
        # 自动按优先级（Maatouch > MinitouchAndAdbKey > AdbShell）选择可用方案。
        # AdbShell (input keyevent/tap) 延迟较高但可用，比完全无触控好。
        input_methods = int(
            MaaAdbInputMethodEnum.Default
            if MaaAdbInputMethodEnum
            else (4 | 2 | 1)  # Maatouch | Minitouch | AdbShell
        )
        # ★ 截图通道：EncodeToFileAndPull(1) = screencap -p >文件后拉取。
        # MuMu 等精简 Android 模拟器上 exec-out(RawWithGzip/Encode) 返回 0 字节，
        # 只有 EncodeToFileAndPull 可用。Default(-57)仅保留 EmulatorExtras(64)，
        # 在云终末地等模拟器上不可用。
        screencap_methods = int(MaaAdbScreencapMethodEnum.EncodeToFileAndPull if MaaAdbScreencapMethodEnum else 1)
        self._controller = AdbController(
            adb_path=Path(self._adb_path),
            address=self._device_address,
            screencap_methods=screencap_methods,
            input_methods=input_methods,
            config={},
        )
        job = self._controller.post_connection()
        conn_ok = self._wait_job(job, timeout_s=float(self._CONNECTION_TIMEOUT_S))
        if not conn_ok:
            # MaaFW v5.12.2: 在云终末地等精简 Android 环境中，输入方法初始化
            # (Maatouch) 可能失败（No available input method），但控制器仍有
            # 截图能力。尝试截一帧验证，若能获取图像则视为降级连接成功。
            self.logger.warning(LogCategory.MAIN, "ADB 控制器连接报告失败（输入通道不可用），尝试降级连接", address=self._device_address)
            try:
                probe_job = self._controller.post_screencap()
                probe_ok = self._wait_job(probe_job, timeout_s=float(self._SCREENCAP_TIMEOUT_S))
                if probe_ok:
                    self.logger.warning(LogCategory.MAIN, "控制器降级连接成功（仅截图，无触控）", address=self._device_address)
                else:
                    self.logger.error(LogCategory.MAIN, "ADB 控制器连接失败且截图不可用", address=self._device_address)
                    self._cleanup_partial()
                    return False
            except Exception as probe_err:
                self.logger.error(LogCategory.MAIN, "ADB 控制器连接失败", address=self._device_address, error=str(probe_err))
                self._cleanup_partial()
                return False
        # 首轮截图失败不应让整个连接失败：screencap 通道可能在游戏加载未完成时
        # 暂时返回空帧。只要 ADB 控制器本身已连上，就视为设备已连接，GUI 应显示
        # "已连接"。screencap 后续在任务执行时会自动重试。
        screencap_job = self._controller.post_screencap()
        if not self._wait_job(screencap_job, timeout_s=float(self._SCREENCAP_TIMEOUT_S)):
            self.logger.warning(LogCategory.MAIN, "首次截图失败或超时（不阻断连接）", address=self._device_address)
        self._tasker = Tasker()
        if not self._tasker.bind(self._resource, self._controller):
            self.logger.error(LogCategory.MAIN, "Tasker 绑定失败")
            self._cleanup_partial()
            return False
        # 输入观测只在 Tasker/Controller 已绑定后注册，回调本身不执行同步 OCR。
        self._start_input_observer()
        # ERRSCREEN-01: Enable on_error screenshot saving so failed recognition
        # nodes save a screenshot to config/debug/on_error/ for analysis.
        try:
            self._tasker.set_save_on_error(True)
        except Exception:
            pass
        # Start Agent after Tasker is ready so it can register sinks correctly.
        # Agent 是可选增强（go-service.exe 子进程），缺失不应阻断设备连接。
        # 实际场景中 go-service.exe 可能因路径/权限/DLL 缺失而启动失败，
        # 但 ADB 控制器与 Tasker 已就绪，基础任务仍可执行。
        self._start_agent()
        if self._agent_client is None or self._agent_process is None:
            self.logger.warning(LogCategory.MAIN, "Agent 未启动（client 或 process 缺失），跳过 Agent 高级功能，基础连接已建立")
        else:
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

    def _start_input_observer(self) -> None:
        if ControllerEventSink is None or self._controller is None:
            return
        try:
            self._input_observation_stop.clear()
            if self._input_observation_thread is None or not self._input_observation_thread.is_alive():
                self._input_observation_thread = threading.Thread(
                    target=self._input_observation_worker,
                    name="maa-input-ocr",
                    daemon=True,
                )
                self._input_observation_thread.start()
            self._input_sink = _InputObservationSink(self)
            self._input_sink_id = self._controller.add_sink(self._input_sink)
            if self._input_sink_id is None:
                self.logger.warning(LogCategory.MAIN, "MaaFW 输入观测 sink 注册失败")
            else:
                self.logger.info(LogCategory.MAIN, "MaaFW 输入观测 sink 已注册", sink_id=self._input_sink_id)
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "MaaFW 输入观测 sink 初始化异常", error=str(exc))
            self._input_sink = None
            self._input_sink_id = None

    def _stop_input_observer(self) -> None:
        self._input_observation_stop.set()
        try:
            if self._input_sink_id is not None and self._controller is not None:
                self._controller.remove_sink(self._input_sink_id)
        except Exception as exc:
            self.logger.debug(LogCategory.MAIN, "移除输入观测 sink 失败", error=str(exc))
        self._input_sink_id = None
        self._input_sink = None
        thread = self._input_observation_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._input_observation_thread = None
        while True:
            try:
                self._input_observation_queue.get_nowait()
            except Empty:
                break

    def _enqueue_input_observation(
        self,
        controller: Any,
        action: str,
        param: Dict[str, Any],
        info: Dict[str, Any],
    ) -> None:
        try:
            self._input_observation_queue.put_nowait((controller, action, param, info))
        except Exception:
            self.logger.warning(LogCategory.MAIN, "输入观测队列已满，丢弃动作", action=action)

    def _input_observation_worker(self) -> None:
        while not self._input_observation_stop.is_set():
            try:
                controller, action, param, info = self._input_observation_queue.get(timeout=0.2)
            except Empty:
                continue
            try:
                # 等待云游戏渲染一帧；不在 MaaFW sink 回调线程内重入。
                time.sleep(0.12)
                cap_job = controller.post_screencap()
                if not self._wait_job(cap_job, timeout_s=3.0):
                    self.logger.warning(LogCategory.MAIN, "输入后截图失败", action=action, param=param)
                    continue
                image = controller.cached_image
                if image is None or self._tasker is None:
                    self.logger.warning(LogCategory.MAIN, "输入后 OCR 无图像或 Tasker 不可用", action=action)
                    continue
                from maa.pipeline import JOCR, JRecognitionType
                ocr_param = JOCR(
                    expected=[".+"],
                    roi=[0, 0, int(image.shape[1]), int(image.shape[0])],
                    threshold=0.3,
                )
                ocr_job = self._tasker.post_recognition(JRecognitionType.OCR, ocr_param, image)
                detail = ocr_job.wait().get()
                labels: List[str] = []
                if detail:
                    for node in detail.nodes:
                        rec = getattr(node, "recognition", None)
                        for result in getattr(rec, "all_results", []) if rec else []:
                            text = str(getattr(result, "text", "") or "").strip()
                            if text:
                                labels.append(text)
                self.logger.info(
                    LogCategory.MAIN,
                    "输入后 OCR",
                    action=action,
                    param=param,
                    info=info,
                    ocr="".join(labels)[:500],
                    ocr_count=len(labels),
                )
            except Exception as exc:
                self.logger.warning(LogCategory.MAIN, "输入后 OCR 观测异常", action=action, error=str(exc))

    def _cleanup_partial(self) -> None:
        """Clean up partially-created resources after a failed connect()."""
        self._stop_input_observer()
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

    def request_stop(self) -> None:
        """标记用户主动停止：_run_task_with_retry/_recover_and_retry/_post_game_restart_cleanup
        在关键节点检查此事件，提前退出并跳过 RecoverGame 流程。

        与 post_stop 的区别：
          - post_stop 是 MaaFW 任务级中止，仅中断当前 pipeline job
          - request_stop 是 runtime 级中止，阻止后续重试与 RecoverGame（StopApp→StartApp→OpenGame）
        """
        self._user_stop_event.set()
        self.logger.info(LogCategory.MAIN, "已请求停止 runtime，后续重试与 RecoverGame 将被跳过")
        # 同时调用 post_stop 中止当前 MaaFW job，让 _wait_job 尽快返回
        try:
            self.post_stop()
        except Exception:
            pass

    def clear_stop_request(self) -> None:
        """清除停止标记，供下次任务执行前重置。"""
        self._user_stop_event.clear()

    def _start_agent(self) -> None:
        if self._agent_client is not None:
            return
        agent_root = self._resolve_agent_root()
        agent_exe = agent_root / "go-service.exe"
        if AgentClient is None or not agent_exe.exists():
            self.logger.warning(LogCategory.MAIN, "go-service.exe 不存在，跳过 Agent 启动", path=str(agent_exe))
            return
        agent_id = f"istina-maaend-{self._instance_tag}-{int(time.time() * 1000)}"
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
            resource_dir = self._resolve_asset_path(self._primary_resource_name())
            # nodes.json 是 IEA 把全部任务 pipeline 聚合后的冗余副本，与
            # resource*/pipeline 下分散的任务文件大量重名；MaaFW 会递归加载各 resource
            # 目录全部 JSON 并因 "key already exists" 整体失败。加载前将各 pipeline 目录
            # 中的聚合 nodes.json 统一移出。
            self._relocate_aggregate_nodes()
            # 方案 E：剥除 pipeline JSON 中的 // 和 /* */ 注释。MaaFW 的 C++ rapidjson
            # 不支持注释，含注释的 JSON 会触发 json::open failed → Resource.Loading.Failed。
            # 3rd-part/maaend/resource/pipeline 下有 5 个文件含注释，需在 post_bundle 前预处理。
            self._strip_comments_in_pipeline()
            job = self._resource.post_bundle(resource_dir)
            # BUNDLE-HARD-TIMEOUT: 资源加载若 MaaFW 内部死锁会无限阻塞
            if not self._wait_job(job, timeout_s=60.0):
                self.logger.error(LogCategory.MAIN, "Pipeline 资源加载失败或超时", path=str(resource_dir))
                # 方案 D：资源加载失败视为整体未连接，避免 _connected=True 与
                # IstinaRuntime.connect() 返回 False 的语义错配（导致 GUI 显示
                # connected=False 但日志显示"MaaEnd runtime 连接成功"）。
                self._connected = False
                return False
            self.logger.info(LogCategory.MAIN, "Pipeline 资源加载成功", path=str(resource_dir))
            adb_resource_dir = self._resolve_asset_path("resource_adb")
            if adb_resource_dir.exists():
                job_adb = self._resource.post_bundle(adb_resource_dir)
                if not self._wait_job(job_adb, timeout_s=60.0):
                    self.logger.error(LogCategory.MAIN, "ADB 资源加载失败或超时", path=str(adb_resource_dir))
                    self._connected = False  # 方案 D：同上，资源加载失败重置连接态
                    return False
                self.logger.info(LogCategory.MAIN, "ADB 资源加载成功", path=str(adb_resource_dir))
            return True
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "Pipeline 资源加载异常", error=str(e))
            self._connected = False  # 方案 D：异常路径同样重置连接态
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

    def _strip_comments_in_pipeline(self) -> None:
        """剥除 pipeline 目录下所有 JSON 文件的 // 和 /* */ 注释。

        MaaFW 的 Resource.post_bundle 用 C++ rapidjson 解析 JSON，不支持注释。
        3rd-part/maaend/resource/pipeline 下部分 JSON 含 // 行注释，导致
        json::open failed → Resource.Loading.Failed。此方法在 post_bundle 前扫描
        所有 pipeline JSON，对含注释的文件剥除注释后原地写回，使资源加载自愈。
        重新同步 3rd-part 资源后再次调用会自动修复。
        """
        pipeline_dir = self._resolve_asset_path(self._primary_resource_name(), "pipeline")
        if not pipeline_dir.is_dir():
            return
        for json_path in pipeline_dir.rglob("*.json"):
            try:
                text = json_path.read_text(encoding="utf-8")
                # 严格解析成功则无需处理
                json.loads(text)
                continue
            except json.JSONDecodeError:
                # 解析失败，可能含注释，尝试剥除
                pass
            except Exception:
                # 读取失败等其他异常，跳过
                continue
            try:
                stripped = _strip_json_comments(text)
                # 验证剥注释后能严格解析
                json.loads(stripped)
                json_path.write_text(stripped, encoding="utf-8")
                self.logger.info(LogCategory.MAIN, "已剥除 JSON 注释", path=str(json_path))
            except Exception as exc:
                self.logger.warning(
                    LogCategory.MAIN, "剥除 JSON 注释失败", path=str(json_path), error=str(exc)
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
            override.update(self._apply_option(opt_def, value, option_defs, options))
        base_override = task.get("pipeline_override") or {}
        merged = self._merge_overrides(base_override, override)
        return merged

    def _apply_option(self, opt_def: Dict[str, Any], value: Any,
                      option_defs: Optional[Dict[str, Any]] = None,
                      options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        opt_type = opt_def.get("type", "switch")
        cases = opt_def.get("cases", [])
        if opt_type == "switch":
            case_name = value if isinstance(value, str) else ("Yes" if value else "No")
            for case in cases:
                if case.get("name") == case_name:
                    result.update(case.get("pipeline_override") or {})
                    nested_options = case.get("option") or []
                    # 嵌套选项定义位于顶层 option_defs 中（与父选项同级），而非父选项的 "option" 字段内。
                    # 旧代码 nested_defs = opt_def.get("option", {}) 取的是父选项的 "option" 字段，
                    # 但任务定义中嵌套选项定义与父选项同级，必须用 option_defs 才能取到。
                    nested_defs = option_defs if isinstance(option_defs, dict) else {}
                    for nested_name in nested_options:
                        # 用户配置可能以两种格式存储嵌套选项值：
                        # 1. 字典格式：value = {"NestedOpt": "Yes", ...}（父选项值为 dict）
                        # 2. 扁平格式：options = {"ParentOpt": "Yes", "NestedOpt": "Yes", ...}（嵌套选项作为顶层 key）
                        # 旧代码仅支持格式 1，导致 GUI 以扁平格式保存的嵌套选项（如 SellProduct 的
                        # ValleyIVRefugeeCamp/ValleyIVInfraStation 等）被静默忽略，引发"没过说过"误判。
                        if isinstance(value, dict):
                            nested_value = value.get(nested_name)
                        elif isinstance(options, dict):
                            nested_value = options.get(nested_name)
                        else:
                            nested_value = None
                        if nested_value is None:
                            continue
                        result.update(self._apply_option(
                            nested_defs.get(nested_name, {}), nested_value, option_defs, options))
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
                    # 处理嵌套选项（与 switch 类型一致）。
                    # select 类型的 case 也可能携带 "option" 字段（如 DijiangRewards 的
                    # SelectToGrow=Any 携带 AutoExtractSeed/SortBy/SortOrder）。
                    # 旧代码直接 return，导致这些嵌套选项被静默忽略，引发"没过说过"误判。
                    nested_options = case.get("option") or []
                    nested_defs = option_defs if isinstance(option_defs, dict) else {}
                    for nested_name in nested_options:
                        if isinstance(value, dict):
                            nested_value = value.get(nested_name)
                        elif isinstance(options, dict):
                            nested_value = options.get(nested_name)
                        else:
                            nested_value = None
                        if nested_value is None:
                            continue
                        result.update(self._apply_option(
                            nested_defs.get(nested_name, {}), nested_value, option_defs, options))
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
                replaced = self._replace_tokens(val, value)
                # 模板替换后，纯数字字符串需转为 int/float，否则 MaaFW pipeline
                # 解析器会对 max_hit/timeout/threshold 等字段报 type error。
                # 例如 "{MaxClueSend}" → "3"（string）→ 3（int）
                resolved[key] = self._coerce_numeric(replaced)
            elif isinstance(val, dict):
                resolved[key] = self._resolve_input_tokens(val, value)
        return resolved

    def _coerce_numeric(self, text: str) -> Any:
        """将纯数字字符串转为 int/float，非数字字符串原样返回。

        MaaFW pipeline 字段如 max_hit/timeout/threshold 期望数值类型，
        但模板替换（{MaxClueSend} → "3"）总产生字符串。此方法将 "3" → 3(int)、
        "3.5" → 3.5(float)，同时保留 "Yes"/"全部售出" 等非数字字符串。
        """
        stripped = text.strip()
        if not stripped:
            return text
        try:
            return int(stripped)
        except ValueError:
            pass
        try:
            return float(stripped)
        except ValueError:
            pass
        return text

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

    def _wait_for_tasker_ready(self, wait_s: float = 5.0, rebuild_on_stuck: bool = True) -> bool:
        """等待 Tasker 退出 stopping 状态，避免 post_task/post_recognition 在
        stopping 状态下立即失败（"runner id not found [task_id=0]"）。

        MaaFW Tasker 在以下情况会进入 stopping 状态：
        - run_pipeline 超时调用 post_stop() 释放 MaaFW
        - 看门狗 _connection_watchdog 检测到卡死调用 post_stop()
        - 任务异常被外部 post_stop() 中断

        Tasker 不会自动从 stopping 状态恢复，必须等待内部 runner 释放或重建
        Tasker 实例。本方法提供两个层次：
        1. 轮询 self._tasker.stopping，最多等待 wait_s 秒
        2. 若超时仍 stopping 且 rebuild_on_stuck=True，重建 Tasker（重新创建
           实例并 bind resource/controller）

        Returns:
            True 若 Tasker 已就绪（不在 stopping 状态），False 若无法恢复
        """
        if not self._tasker:
            return False
        try:
            if not getattr(self._tasker, "stopping", False):
                return True
        except Exception:
            return True  # 属性不可访问时假设就绪，避免阻塞
        self.logger.warning(LogCategory.MAIN, "Tasker 处于 stopping 状态，等待恢复", wait_s=wait_s)
        deadline = time.monotonic() + wait_s
        while time.monotonic() < deadline:
            try:
                if not getattr(self._tasker, "stopping", False):
                    self.logger.info(LogCategory.MAIN, "Tasker 已退出 stopping 状态")
                    return True
            except Exception:
                return True
            time.sleep(0.2)
        if not rebuild_on_stuck:
            self.logger.warning(LogCategory.MAIN, "Tasker 仍在 stopping 状态（不重建）")
            return False
        # 重建 Tasker：post_stop 后 Tasker 内部 runner 可能未释放，
        # 必须新建 Tasker 实例并重新 bind resource/controller 才能恢复
        self.logger.warning(LogCategory.MAIN, "Tasker 仍卡在 stopping 状态，重建 Tasker 实例")
        try:
            old_tasker = self._tasker
            try:
                # 旧的 Tasker 不需要 destroy，Python GC 会处理
                pass
            except Exception:
                pass
            if Tasker is None:
                return False
            new_tasker = Tasker()
            if not new_tasker.bind(self._resource, self._controller):
                self.logger.error(LogCategory.MAIN, "重建 Tasker bind 失败")
                return False
            try:
                new_tasker.set_save_on_error(True)
            except Exception:
                pass
            # 重新注册 AgentClient sink（若存在）
            if self._agent_client is not None:
                try:
                    self._agent_client.register_sink(self._resource, self._controller, new_tasker)
                except Exception as exc:
                    self.logger.warning(LogCategory.MAIN, "重建 Tasker 后 AgentClient sink 注册失败", error=str(exc))
            self._tasker = new_tasker
            self.logger.info(LogCategory.MAIN, "Tasker 重建成功")
            return True
        except Exception as exc:
            self.logger.error(LogCategory.MAIN, "Tasker 重建失败", error=str(exc))
            return False

    def _wait_job(self, job: Any, timeout_s: Optional[float] = None) -> bool:
        """等待任务完成。

        注意：job.wait() 返回 Job 对象自身（truthy），不是任务成功与否的布尔值。
        必须用 job.succeeded 检查任务的真实状态。

        如果指定 timeout_s，使用 run_with_timeout 包装，避免 MaaFramework
        并发限制导致 job.wait() 无限阻塞。超时返回 False。
        """
        if timeout_s is None:
            job.wait()
            return job.succeeded

        def _do_wait() -> bool:
            job.wait()
            return bool(job.succeeded)

        result = run_with_timeout(
            _do_wait,
            timeout=timeout_s,
            name="maafw-wait-job",
            thread_name="maafw-wait-job",
            on_timeout=lambda n, t: self.logger.warning(
                LogCategory.MAIN, "job.wait() 超时，放弃等待",
                timeout_s=timeout_s,
            ),
        )
        if result.is_timeout or result.is_error:
            return False
        return bool(result.data)

    # SceneAnyEnterWorld 等导航类管道的正常执行耗时上限（秒）。
    # 实测：从主世界到主世界 ≈3s，从登录页/弹窗后回主世界 ≤30s。
    # 云终末地从启动器首页点击「开始游戏」到进入主世界 ≈39s（含加载+logo+点击继续），
    # 网络波动时可能超过 60s。设为 90s 给云终末地足够加载时间，避免间歇性超时。
    # 超过 90s 通常是 InWorld 模板在非主世界页面误匹配导致 MaaFW next 列表
    # 死循环（PostStop / DoNothing 节点 loop back）。看门狗会 post_stop 释放 MaaFW。
    _PIPELINE_NAV_TIMEOUT_S = 90

    def run_pipeline(self, entry: str, pipeline_override: Dict[str, Any], timeout_s: Optional[float] = None) -> bool:
        if not self._connected or self._tasker is None:
            self.logger.error(LogCategory.MAIN, "runtime 未连接，无法执行管道")
            return False
        # 超时兜底：默认使用 _PIPELINE_NAV_TIMEOUT_S（60s），调用方可传入更短的超时
        # （如 __ScenePrivateAnyEnterWorldSuccess 判定节点用 5s，避免 60s 等待阻塞队列）
        effective_timeout = timeout_s if timeout_s is not None else self._PIPELINE_NAV_TIMEOUT_S
        self.logger.info(LogCategory.MAIN, "开始执行自定义管道", entry=entry, timeout_s=effective_timeout)
        # TASKER-READY-FIX: post_stop 后 Tasker 会进入 stopping 状态，必须等待恢复
        # 否则 post_task/post_recognition 立即返回 task_id=0 报 "runner id not found"。
        # 必须在 _dismiss_cloud_idle_popup 之前调用，因为后者使用 post_recognition
        if not self._wait_for_tasker_ready(wait_s=5.0, rebuild_on_stuck=True):
            self.logger.error(LogCategory.MAIN, "Tasker 未就绪，无法执行管道", entry=entry)
            return False
        # 管道执行前检测并关闭云游戏空闲断连弹窗
        self._dismiss_cloud_idle_popup()
        try:
            # NODE-REG-FIX: 同 _run_task_once，用 resource.override_pipeline 注册再执行
            if pipeline_override:
                try:
                    self._resource.override_pipeline(pipeline_override)
                except Exception as reg_err:
                    self.logger.warning(LogCategory.MAIN, "注册 pipeline override 失败", error=str(reg_err))
            job = self._tasker.post_task(entry, {})
            # 超时兜底：避免 SceneAnyEnterWorld 在 InWorld 误匹配时陷入 MaaFW
            # next 列表死循环（实测 4 分钟仍未退出）。超时后 post_stop 释放 MaaFW，
            # 让上层（_ensure_in_world_before_task / _ensure_game_is_alive）走重启路径。
            succeeded = self._wait_job(job, timeout_s=effective_timeout)
            if not succeeded and job is not None:
                self.logger.warning(
                    LogCategory.MAIN,
                    "管道执行超时，发送 post_stop 释放 MaaFW",
                    entry=entry,
                    timeout_s=effective_timeout,
                )
                try:
                    self._tasker.post_stop()
                except Exception:
                    pass
                # POST-STOP-WAIT: 等待 Tasker 退出 stopping 状态，避免后续调用
                # 立即失败。run_pipeline 通常被串联调用（如 _open_game_false_negative_recover
                # 先 SceneAnyEnterWorld 再 __ScenePrivateAnyEnterWorldSuccess），
                # 上层调用方不会感知 stopping 状态，需要在此主动恢复。
                self._wait_for_tasker_ready(wait_s=3.0, rebuild_on_stuck=False)
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
        if task_name not in self._TASKS_SKIP_ENTER_WORLD:
            if not self._ensure_in_world_before_task(task_name):
                self.logger.error(LogCategory.MAIN, "任务前未确认主世界", task=task_name)
                return False
        ok = self._run_task_with_retry(task_name, options, entry, override)
        if ok and task_name not in self._TASKS_SKIP_ENTER_WORLD:
            ok = self._verify_in_world_by_ocr()
            if not ok:
                self.logger.error(LogCategory.MAIN, "任务返回成功但后置 OCR 未确认主世界", task=task_name)
        if (
            not ok
            and task_name in self._TASKS_OPEN_GAME
            and not self._user_stop_event.is_set()
            and self._connected
        ):
            # 假阴性纠正：启动类任务 pipeline 报失败，但通用 SceneAnyEnterWorld
            # 能把游戏推进到主世界（云冷启动加载闪屏/首页未被 OpenGame 链覆盖时常见）。
            if self._open_game_false_negative_recover(task_name):
                return True
        return ok

    def _open_game_false_negative_recover(self, task_name: str) -> bool:
        """启动类任务假阴性纠正：有界地用 SceneAnyEnterWorld 推进到主世界。

        云终末地冷启动/空闲断连恢复时，OpenGame 通用登录链的等待节点不覆盖
        『正在加载资源』闪屏，导致 AndroidOpenGame 在加载未完成时即报失败，但游戏
        随后加载完成并可由 SceneAnyEnterWorld（含已验证的云首页/点击继续节点）推进到
        主世界。此处做有界纠正：成功进入主世界则视为误判纠正返回 True；若确有异常
        （登录失败/断网）则 SceneAnyEnterWorld 亦无法进入主世界，仍返回 False，不会
        掩盖真实失败。仅作为 pipeline 自身驱动失败时的保底，正常路径不触发。

        CLOUD-LOAD-RETRY: 云版本游戏冷启动加载可达 60-120s，单次 SceneAnyEnterWorld
        （90s 超时）可能在加载未完成时即报失败。增加最多 3 次重试，每次间隔 10s，
        给游戏足够的加载时间。重试期间不发送 post_stop（由 run_pipeline 内部处理）。
        """
        try:
            self.logger.info(
                LogCategory.MAIN,
                "启动类任务报失败，尝试有界进入主世界纠正误判",
                task=task_name,
            )
            # CLOUD-LOAD-RETRY: 云版本游戏加载慢，单次 SceneAnyEnterWorld 可能失败
            # 增加重试机制，最多 3 次，每次间隔 10s
            max_retries = 3
            retry_interval = 10.0
            for attempt in range(1, max_retries + 1):
                if self._user_stop_event.is_set():
                    return False
                if attempt > 1:
                    self.logger.info(
                        LogCategory.MAIN,
                        "误判纠正：等待游戏加载后重试",
                        task=task_name,
                        attempt=attempt,
                        max_retries=max_retries,
                        wait_s=retry_interval,
                    )
                    time.sleep(retry_interval)
                if not self.run_pipeline("SceneAnyEnterWorld", {}):
                    self.logger.warning(
                        LogCategory.MAIN,
                        "误判纠正：SceneAnyEnterWorld 未进入主世界",
                        task=task_name,
                        attempt=attempt,
                    )
                    continue
                # 验证是否确实在主世界（严格判定）
                in_world = self.run_pipeline("__ScenePrivateAnyEnterWorldSuccess", {}, timeout_s=5.0)
                if in_world:
                    self.logger.info(
                        LogCategory.MAIN,
                        "启动类任务误判纠正成功：pipeline 报失败但已进入主世界",
                        task=task_name,
                        attempt=attempt,
                    )
                    return True
                self.logger.warning(
                    LogCategory.MAIN,
                    "误判纠正：严格判定未通过",
                    task=task_name,
                    attempt=attempt,
                )
            self.logger.warning(
                LogCategory.MAIN,
                "误判纠正：重试耗尽仍未能进入主世界（视为真实失败）",
                task=task_name,
                max_retries=max_retries,
            )
            return False
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "启动类任务误判纠正异常", task=task_name, error=str(exc))
            return False

    def _run_task_with_retry(self, task_name: str, options: Dict[str, Any], entry: str, override: Dict[str, Any]) -> bool:
        for attempt in range(1 + self._MAX_TASK_RETRIES):
            # 用户主动停止：跳过重试与恢复，立即返回失败
            if self._user_stop_event.is_set():
                self.logger.warning(LogCategory.MAIN, "检测到停止请求，跳过任务重试", task=task_name, attempt=attempt)
                return False
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
            # result is False：MaaFW 穷举 entry.next 后仍未命中（OCR/TemplateMatch
            # 未命中、菜单未渲染好、UI 变化等"正常失败"）。对齐 project_memory 约束：
            # 不得触发 _recover_and_retry/RecoverGame，否则会导致"任务刚启动就被
            # 强制关游戏"（如 VisitFriends 22s 内 OCR 未命中 → 整任务判定失败 →
            # 直接 StopApp 关游戏的严重 bug）。仅做轻量 BACK 关弹窗后重试一次。
            if self._recovering or attempt >= self._MAX_TASK_RETRIES:
                break
            # 用户主动停止：跳过轻量恢复，避免触发不必要的 BACK 操作
            if self._user_stop_event.is_set():
                self.logger.warning(LogCategory.MAIN, "检测到停止请求，跳过异常恢复", task=task_name)
                return False
            if self._connected and self._lightweight_recover_ui():
                self.logger.info(LogCategory.MAIN, "轻量恢复完成，重试任务", task=task_name)
                retry_result = self._run_task_once(task_name, options, entry, override)
                if retry_result is True:
                    return True
            # 轻量恢复后仍失败：视为正常失败，返回 False 让上层决定是否继续下一个任务。
            # 不再触发 _recover_and_retry（RecoverGame: StopApp → StartApp → OpenGame），
            # 该恢复只能由用户手动触发，或上层逻辑在显式检测到自动登出弹窗/
            # 连接断开等真正崩溃场景时调用。
            self.logger.warning(LogCategory.MAIN, "任务执行失败（轻量恢复后仍失败，视为正常失败）", task=task_name)
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
            # TASKER-READY-FIX: 前一任务看门狗可能调用 post_stop 让 Tasker 进入
            # stopping 状态，必须等待恢复才能 post_task
            if not self._wait_for_tasker_ready(wait_s=5.0, rebuild_on_stuck=True):
                self.logger.error(LogCategory.MAIN, "Tasker 未就绪，无法执行任务", task=task_name, entry=entry)
                return None
            # NODE-REG-FIX: MaaFW v5.12.x 的 MaaTaskerPostTask 对 override 中新节点
            # (不在 resource 中预先注册的节点) 无法正确解析执行，导致 Node: name="",
            # completed=False, succeeded=False。
            # 改用 resource.override_pipeline() 先将 override 注册到 resource 中，
            # 再以空 override 执行 post_task，确保 OCR 等新节点能被正确加载。
            # 该方法也修复了 MaaFW pipeline OCR 报 ocrer_ is null 的根本原因：
            # 旧版 v5.11.x DLL 不支持 PPOCRv6 模型格式。
            if override:
                try:
                    self._resource.override_pipeline(override)
                except Exception as reg_err:
                    self.logger.warning(LogCategory.MAIN, "注册 pipeline override 失败（仍尝试原方式）", error=str(reg_err))
            job = self._tasker.post_task(entry, {})
            succeeded = self._wait_job(job)
        except Exception as e:
            self._connected = False
            self.logger.exception(LogCategory.MAIN, "任务执行异常", task=task_name, error=str(e))
            return None
        finally:
            watchdog_stop.set()
            # WATCHDOG-POST-STOP-WAIT: 看门狗可能在 _wait_job 期间触发 post_stop
            # 让 Tasker 进入 stopping 状态，需要主动等待恢复，避免下一任务立即失败
            try:
                if self._tasker is not None and getattr(self._tasker, "stopping", False):
                    self.logger.info(LogCategory.MAIN, "任务结束检测到 Tasker stopping，等待恢复", task=task_name)
                    self._wait_for_tasker_ready(wait_s=3.0, rebuild_on_stuck=False)
            except Exception:
                pass
        if succeeded:
            if self._detect_task_skipped(job, task_name, entry):
                self.logger.warning(LogCategory.MAIN, "任务被跳过（未满足执行条件，如未到计划周期）", task=task_name)
                return False

            detail = job.get()
            if detail:
                # 记录识别过程日志（DEBUG 级别）
                self._log_recognition_detail(task_name, entry, detail)

                # False Success 检测（多策略）：
                # FS-1: 所有识别节点均未命中（OCR/TemplateMatch 全失败但 MaaFW 报成功）
                # FS-2: 任务轨迹含 PostStop/AbortPipeline 节点（被中止但 MaaFW 仍报 Succeeded）
                # FS-3: 节点数为 0 或所有节点 completed=False（MaaFW override 注册失败的典型症状）
                # FS-4: 任务经 FakeTrue 空节点回落完成（无识别命中的空转成功，典型"没过说过"误判）
                has_recognition = False
                has_any_hit = False
                has_post_stop = False
                has_faketrue_completed = False
                completed_node_count = 0
                hit_node_names: List[str] = []
                all_node_names: List[str] = []
                for node in detail.nodes:
                    node_name = getattr(node, "name", "") or ""
                    all_node_names.append(node_name)
                    if getattr(node, "completed", False):
                        completed_node_count += 1
                    node_name_lower = node_name.lower()
                    # PostStop 中止：action 类型为 PostStop 或节点名含 Abort/Stop
                    if "abort" in node_name_lower or "poststop" in node_name_lower or "stop" in node_name_lower:
                        has_post_stop = True
                    # FakeTrue 空节点：无识别无动作的总为真节点，常作为 next 末尾的软失败回落
                    if "faketrue" in node_name_lower and getattr(node, "completed", False):
                        has_faketrue_completed = True
                    if node.recognition:
                        has_recognition = True
                        if node.recognition.hit:
                            has_any_hit = True
                            hit_node_names.append(node_name)

                # 节点轨迹 INFO 级日志（成功路径），便于排查"没过说过"误判
                self.logger.info(
                    LogCategory.MAIN,
                    "任务节点轨迹",
                    task=task_name,
                    nodes=all_node_names,
                    hit_nodes=hit_node_names,
                    has_any_hit=has_any_hit,
                )

                false_success_reason = None
                if has_recognition and not has_any_hit:
                    false_success_reason = "所有识别节点均未命中但 MaaFW 报告成功"
                elif has_post_stop and not has_any_hit:
                    false_success_reason = "任务被 PostStop/Abort 中止但 MaaFW 报告成功"
                elif completed_node_count == 0 and len(detail.nodes) > 0:
                    false_success_reason = "所有节点均未完成（MaaFW override 注册失败或 pipeline 解析错误）"
                elif has_faketrue_completed and not has_any_hit:
                    false_success_reason = "任务经 FakeTrue 空节点回落完成（无识别命中的空转成功）"

                if false_success_reason:
                    self.logger.warning(
                        LogCategory.MAIN,
                        f"任务执行结果误判纠正：{false_success_reason} (False Success)",
                        task=task_name,
                        entry=entry,
                        node_count=len(detail.nodes),
                        completed_nodes=completed_node_count,
                        has_recognition=has_recognition,
                        has_any_hit=has_any_hit,
                        has_post_stop=has_post_stop,
                        has_faketrue_completed=has_faketrue_completed,
                    )
                    return False

            self.logger.info(LogCategory.MAIN, "任务执行成功", task=task_name)
            return True
        if not self._connected:
            return None
        self.logger.warning(LogCategory.MAIN, "任务执行失败", task=task_name)
        # 任务失败也尝试记录识别详情，便于分析失败原因
        try:
            detail_fail = job.get()
            if detail_fail:
                self._log_recognition_detail(task_name, entry, detail_fail)
                # 失败路径同样记录节点轨迹 INFO 日志，便于定位失败节点
                fail_node_names = [getattr(n, "name", "") or "" for n in detail_fail.nodes]
                fail_hit_names = [
                    getattr(n, "name", "") or ""
                    for n in detail_fail.nodes
                    if n.recognition and n.recognition.hit
                ]
                self.logger.info(
                    LogCategory.MAIN,
                    "任务节点轨迹",
                    task=task_name,
                    nodes=fail_node_names,
                    hit_nodes=fail_hit_names,
                    has_any_hit=bool(fail_hit_names),
                )
        except Exception:
            pass
        return False

    def _connection_watchdog(self, task_name: str, stop_event: threading.Event) -> None:
        # 游戏启动/恢复类任务耗时较长（加载、登录流程），使用更长的卡死超时。
        # 300s 对 OpenGame 太短：游戏冷启动 + 加载 + 登录流程可达 5-8 分钟，
        # 看门狗在 300s 触发 post_stop 会与任务完成产生竞态，导致：
        # job.succeeded=False（post_stop 赢了竞态）→ _connected=False →
        # _run_task_once 返回 None → 触发连接恢复 → 重新执行 AndroidOpenGame → 无限循环。
        _WATCHDOG_TIMEOUT_GAME = 900  # 15 min for OpenGame/RecoverGame/StartApp/StopApp
        _WATCHDOG_TIMEOUT_LONG = 1800  # 30 min for long-running tasks (VisitFriends etc.)
        _WATCHDOG_TIMEOUT_NORMAL = 300  # 5 min for other tasks
        if task_name in self._TASKS_SKIP_ENTER_WORLD:
            stuck_timeout = _WATCHDOG_TIMEOUT_GAME
        elif task_name in self._TASKS_LONG_RUNNING:
            stuck_timeout = _WATCHDOG_TIMEOUT_LONG
        else:
            stuck_timeout = _WATCHDOG_TIMEOUT_NORMAL
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
            if elapsed > stuck_timeout:
                self.logger.warning(LogCategory.MAIN, "看门狗：任务疑似卡死，发送中断信号", task=task_name, elapsed_s=int(elapsed), stuck_timeout=stuck_timeout)
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
            # 用户主动停止：中止队列
            if self._user_stop_event.is_set():
                self.logger.warning(LogCategory.MAIN, "检测到停止请求，中止队列执行", remaining=total - idx)
                failures.append(name)
                break
            if not self._ensure_queue_connection(name, idx, total):
                failures.append(name)
                break
            # run_task() 统一负责任务前主世界 guard，避免队列路径和直跑路径行为不一致。
            self.logger.info(LogCategory.MAIN, "队列进度", current=idx + 1, total=total, task=name)
            task_ok = self.run_task(name, options)
            if not task_ok:
                failures.append(name)
                self.logger.warning(LogCategory.MAIN, "队列任务失败，继续后续", failed_task=name, failed_index=idx + 1)
                # 用户主动停止：中止队列（不再继续后续任务）
                if self._user_stop_event.is_set():
                    self.logger.warning(LogCategory.MAIN, "检测到停止请求，中止队列执行", failed_task=name)
                    break
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
            # 任务前尝试关闭云游戏空闲断连弹窗。
            # 弹窗关闭后还需验证游戏是否仍在运行。
            self._dismiss_cloud_idle_popup()
            # 游戏活跃度检查：若弹窗刚关闭，游戏可能在退出过程中，
            # 需要确保回到主世界后再开始任务。
            # 仅对非 OpenGame/RecoverGame 任务做此检查，避免
            # 启动类任务自身流程被打断。
            if task_name not in self._TASKS_SKIP_ENTER_WORLD:
                self._ensure_game_is_alive()
            # ADB 健康即视为连接可用。
            # 旧实现额外调用 _verify_connection_alive()（post_screencap + _wait_job 10s），
            # 但 screencap 通道可能在游戏加载/过场时短暂延迟，导致 10s 超时误判为"控制器失效"，
            # 进而触发 _rebuild_controller/_quick_reconnect_adb，在队列中每个任务前增加 10-60s 开销。
            # 若控制器实际失效，_run_task_once 的 post_task 会抛出异常并设置 _connected=False，
            # 随后 _run_task_with_retry 会通过 _try_recover_connection 恢复，无需在此预检。
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

    _WORLD_REQUIRED_OCR = frozenset({"探索", "UID"})
    _WORLD_BLOCKING_OCR = frozenset({
        "事务总览", "据点", "联络干员", "物资调度", "仓储节点",
        "自动结束", "知道了", "6095",
    })

    def _verify_in_world_by_ocr(self) -> bool:
        """Use a lightweight Controller screenshot + OCR world-state guard."""
        if not self._connected or self._controller is None or self._tasker is None:
            return False
        try:
            cap_job = self._controller.post_screencap()
            if not self._wait_job(cap_job, timeout_s=4.0):
                return False
            image = self._controller.cached_image
            if image is None:
                return False
            from maa.pipeline import JOCR, JRecognitionType
            ocr_param = JOCR(
                expected=[".+"],
                roi=[0, 0, int(image.shape[1]), int(image.shape[0])],
                threshold=0.3,
            )
            detail = self._tasker.post_recognition(JRecognitionType.OCR, ocr_param, image).wait().get()
            text_parts: List[str] = []
            if detail:
                for node in detail.nodes:
                    rec = getattr(node, "recognition", None)
                    for result in getattr(rec, "all_results", []) if rec else []:
                        value = str(getattr(result, "text", "") or "").strip()
                        if value:
                            text_parts.append(value)
            text = "".join(text_parts)
            required_hit = "探索" in text and ("UID" in text or "1439188325" in text)
            blocked = [word for word in self._WORLD_BLOCKING_OCR if word in text]
            ok = required_hit and not blocked
            self.logger.info(
                LogCategory.MAIN,
                "任务边界主世界 OCR",
                ok=ok,
                required_hit=required_hit,
                blocked=blocked,
                ocr=text[:300],
            )
            return ok
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "任务边界主世界 OCR 异常", error=str(exc))
            return False

    def _ensure_in_world_before_task(self, task_name: str) -> bool:
        """Close overlays, then require an explicit main-world OCR confirmation."""
        if not self._connected or self._tasker is None:
            return False
        self.logger.info(LogCategory.MAIN, "任务间清理：先验证当前 UI", before_task=task_name)
        try:
            # 已在主世界时不发送 BACK，避免把云游戏从主世界退出。
            if self._verify_in_world_by_ocr():
                return True
            self.logger.info(LogCategory.MAIN, "任务间清理：关闭覆盖层后重试", before_task=task_name)
            if not self._lightweight_recover_ui():
                return False
            return self._verify_in_world_by_ocr()
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "任务间清理异常", before_task=task_name, error=str(exc))
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

    def _send_key_back(self) -> bool:
        """关闭当前弹窗/对话框（替代 ADB BACK 键）。

        重要约束（见 project_memory）：
        - 禁止使用 adb input（tap/swipe/keyevent）进行游戏交互，
          com.hypergryph.endfield 会忽略 adb shell input 命令。
        - 改用 MaaTouch（self._controller.post_click）点击屏幕右上角
          关闭按钮区域 [1190, 20, 20, 20]（实测中心 (1200, 30) 有效），
          该位置在好友列表/任务详情/菜单子页面/设置弹窗等绝大多数模态页面
          均为关闭按钮，与 pipeline 中的 __ScenePrivateCloudFriendsListExit
          /__ScenePrivateCloudMenuSubPageExit/__ScenePrivateCloudMissionPageExit
          节点使用的 target 一致。
        - 若 _controller 不可用（未连接），降级为 ADB keyevent 4 仅用于
          系统级弹窗（非游戏内交互），作为最后兜底。
        """
        try:
            if self._connected and self._controller is not None:
                # MaaTouch 点击右上角关闭按钮区域
                click_job = self._controller.post_click(1200, 30)
                click_job.wait()
                time.sleep(0.8)
                self.logger.info(LogCategory.MAIN, "已点击右上角关闭按钮（MaaTouch 替代 BACK 键）")
                return True
            # 兜底：仅当 MaaTouch 不可用时使用 ADB keyevent（系统级弹窗）
            self.logger.warning(LogCategory.MAIN, "MaaTouch 不可用，降级使用 ADB BACK 键")
            subprocess.run(
                [self._adb_path, "-s", self._device_address, "shell", "input", "keyevent", "4"],
                text=True, timeout=5, capture_output=True,
            )
            time.sleep(0.8)
            return True
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "发送 BACK 键失败", error=str(exc))
            return False

    def _force_landscape_rotation(self) -> None:
        """强制设备横屏旋转，解决模拟器竖屏物理显示与游戏横屏渲染的不匹配。

        MuMu 等模拟器物理显示为竖屏(720x1280)，但云终末地等游戏以 ROTATION_90
        横屏渲染(1280x720)。MaaFW 的 screencap 返回原始物理帧(竖屏)，导致
        pipeline JSON 中按横屏设计的 ROI 坐标全部越界。通过 ADB 设置
        user_rotation=1 强制系统横屏，使 screencap 输出与 pipeline 预期一致。
        """
        try:
            # 检查当前旋转状态
            result = subprocess.run(
                [self._adb_path, "-s", self._device_address, "shell",
                 "settings", "get", "system", "user_rotation"],
                text=True, timeout=5, capture_output=True,
            )
            current = result.stdout.strip()
            if current == "1":
                self.logger.debug(LogCategory.MAIN, "设备已处于横屏模式，无需调整")
                return
            # 设置横屏 (1 = ROTATION_90)
            subprocess.run(
                [self._adb_path, "-s", self._device_address, "shell",
                 "settings", "put", "system", "user_rotation", "1"],
                text=True, timeout=5, capture_output=True,
            )
            # 验证设置成功
            verify = subprocess.run(
                [self._adb_path, "-s", self._device_address, "shell",
                 "settings", "get", "system", "user_rotation"],
                text=True, timeout=5, capture_output=True,
            )
            if verify.stdout.strip() == "1":
                self.logger.info(LogCategory.MAIN, "已强制设备横屏旋转 (user_rotation=1)")
            else:
                self.logger.warning(
                    LogCategory.MAIN, "设置横屏旋转后验证失败",
                    expected="1", actual=verify.stdout.strip(),
                )
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "强制横屏旋转失败（不阻断连接）", error=str(exc))

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
                    screencap_ok = self._wait_job(job, timeout_s=float(self._SCREENCAP_TIMEOUT_S))
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

    # ──────────────────────────────────────────────
    # 云游戏空闲断连弹窗处理
    # ──────────────────────────────────────────────
    # 云终末地长时间无操作后会弹出提示框：
    #   "由于长时间未操作，游戏将自动结束"
    #   按钮："知道了" 或 "点击任意位置继续"
    # 此弹窗会阻止所有后续 pipeline 操作，必须在任务间逐一检测并关闭。
    # 注意：弹窗关闭后游戏可能仍在运行，也可能已自动退出。
    # 需在关闭后检查游戏状态并重新启动。
    # 重要：云游戏空闲断连弹窗会忽略 MaaTouch 触控（与"自动登出"弹窗一样，
    # 截图完全无变化）。当检测到点击"知道了"后弹窗仍在，必须直接 force-stop
    # 重启游戏（adb am force-stop + monkey 启动），不可反复尝试点击。
    _CLOUD_IDLE_TIMEOUT_KEYWORDS = frozenset({
        "长时间未操作", "自动结束", "点击任意位置继续",
        "知道了", "提示",
        "将自动结束",
    })
    _CLOUD_IDLE_TIMEOUT_DISMISS_BUTTON_TEXT = "知道了"
    _CLOUD_IDLE_DISMISS_RETRY_COUNT = 3

    def _lightweight_recover_ui(self) -> bool:
        """轻量恢复：当任务失败时，尝试关闭弹窗后重试。

        先检测并关闭云游戏空闲断连弹窗，再发送 3 次 BACK 关闭
        其他可能存在的弹窗/对话框，最后验证连接是否正常。
        """
        if not self._connected:
            return False
        self._dismiss_cloud_idle_popup()
        self.logger.info(LogCategory.MAIN, "轻量恢复：多次 BACK 关闭弹窗/对话框")
        for _ in range(3):
            if not self._send_key_back():
                return False
        if not self._verify_connection_alive():
            return False
        time.sleep(1.5)
        return True

    def _dismiss_cloud_idle_popup(self) -> bool:
        """检测并关闭云游戏空闲断连弹窗，并推进到主世界。

        云终末地空闲断连后游戏会重启到 启动页/logo 页（含"开始游戏"/"点击任意位置继续"），
        而不是主世界。旧实现只点击"知道了"按钮就返回，导致后续 InWorld 因 logo 页的
        "设置/修复"按钮误判为主世界（已修复：InWorld 移除了设置/修复 OCR），任务因
        __ScenePrivateWorldEnterMenuList 在 logo 页无菜单按钮而全部失败。

        现关闭弹窗后继续推进：检测并点击"开始游戏"/"点击任意位置继续"，等待加载完成，
        确保返回 True 时游戏已在主世界或正在加载中。

        Returns:
            True 若弹窗已检测并关闭（并已推进到主世界/加载中），False 若无弹窗。
        """
        if not self._connected or self._tasker is None or self._controller is None:
            return False
        # TASKER-READY-FIX: post_recognition 在 stopping 状态下也会失败，
        # 需先等待 Tasker 就绪。rebuild_on_stuck=False 避免在弹窗检测路径上重建 Tasker
        # （重建逻辑由 run_pipeline/run_task 调用方负责）
        if not self._wait_for_tasker_ready(wait_s=3.0, rebuild_on_stuck=False):
            return False
        try:
            # 截图
            job = self._controller.post_screencap()
            if not self._wait_job(job, timeout_s=float(self._SCREENCAP_TIMEOUT_S)):
                return False
            img = self._controller.cached_image
            if img is None:
                return False

            from maa.pipeline import JOCR, JRecognitionType

            # OCR 全屏搜索"知道了"按钮
            ocr_param = JOCR(
                expected=[self._CLOUD_IDLE_TIMEOUT_DISMISS_BUTTON_TEXT],
                roi=[0, 0, img.shape[1], img.shape[0]],
                threshold=0.3,
            )
            ocr_job = self._tasker.post_recognition(JRecognitionType.OCR, ocr_param, img)
            detail = ocr_job.wait().get()

            # 检查是否找到"知道了"按钮
            if not detail:
                return False
            popup_hit = False
            for node in detail.nodes:
                if node.recognition and node.recognition.hit:
                    best = node.recognition.best_result
                    if best:
                        bx = best.box
                        if hasattr(bx, 'x'):
                            cx = bx.x + bx.w // 2
                            cy = bx.y + bx.h // 2
                        else:
                            cx = bx[0] + bx[2] // 2
                            cy = bx[1] + bx[3] // 2
                        self.logger.warning(
                            LogCategory.MAIN,
                            "检测到云游戏空闲断连弹窗，点击关闭",
                            button_text=self._CLOUD_IDLE_TIMEOUT_DISMISS_BUTTON_TEXT,
                            target=(cx, cy),
                        )
                        click_job = self._controller.post_click(cx, cy)
                        click_job.wait()
                        time.sleep(2.0)
                        # 弹出可能还残留二次确认或其他弹窗，再做 BACK 清理
                        for _ in range(2):
                            self._send_key_back()
                        popup_hit = True
                        break
            if not popup_hit:
                return False

            # 验证弹窗是否已关闭：云游戏空闲断连弹窗可能忽略 MaaTouch 触控
            # （与"自动登出"弹窗一样，截图完全无变化）。
            # 若点击后弹窗仍在，必须 force-stop 重启游戏。
            verify_deadline = time.time() + 6.0
            dialog_persisted = False
            while time.time() < verify_deadline:
                verify_job = self._controller.post_screencap()
                if not self._wait_job(verify_job, timeout_s=float(self._SCREENCAP_TIMEOUT_S)):
                    time.sleep(1.0)
                    continue
                verify_img = self._controller.cached_image
                if verify_img is None:
                    time.sleep(1.0)
                    continue
                verify_param = JOCR(
                    expected=["知道了", "长时间未操作", "自动结束", "自动结"],
                    roi=[0, 0, verify_img.shape[1], verify_img.shape[0]],
                    threshold=0.3,
                )
                verify_detail = self._tasker.post_recognition(
                    JRecognitionType.OCR, verify_param, verify_img
                ).wait().get()
                still_visible = False
                if verify_detail:
                    for vnode in verify_detail.nodes:
                        if vnode.recognition and vnode.recognition.hit:
                            still_visible = True
                            break
                if not still_visible:
                    break
                dialog_persisted = True
                time.sleep(1.0)

            if dialog_persisted:
                self.logger.warning(
                    LogCategory.MAIN,
                    "云弹窗点击无效（MaaTouch 被忽略），执行 force-stop 重启游戏",
                )
                try:
                    subprocess.run(
                        [self._adb_path, "-s", self._device_address, "shell",
                         "am", "force-stop", self._game_package],
                        text=True, timeout=10, capture_output=True,
                    )
                    time.sleep(3.0)
                    subprocess.run(
                        [self._adb_path, "-s", self._device_address, "shell",
                         "monkey", "-p", self._game_package, "-c",
                         "android.intent.category.LAUNCHER", "1"],
                        text=True, timeout=10, capture_output=True,
                    )
                    self.logger.info(LogCategory.MAIN, "force-stop 重启已完成，等待游戏加载")
                    time.sleep(12.0)
                except Exception as exc:
                    self.logger.warning(LogCategory.MAIN, "force-stop 重启失败", error=str(exc))

            # 关闭弹窗后，游戏会重启到启动页/logo 页。需要推进到主世界，
            # 否则后续任务会因 InWorld 不匹配（已移除设置/修复 OCR）而失败。
            # 循环检测并点击"开始游戏"/"点击任意位置继续"，最多尝试 30s。
            self.logger.info(LogCategory.MAIN, "云弹窗已关闭，推进游戏到主世界")
            advance_deadline = time.time() + 30.0
            advanced = False
            while time.time() < advance_deadline:
                time.sleep(2.0)
                # 截图
                cap_job = self._controller.post_screencap()
                if not self._wait_job(cap_job, timeout_s=float(self._SCREENCAP_TIMEOUT_S)):
                    continue
                cur_img = self._controller.cached_image
                if cur_img is None:
                    continue

                # OCR 找"开始游戏"/"点击任意位置继续"/"点击"
                advance_param = JOCR(
                    expected=["开始游戏", "開始遊戲", "(?i)Start\\s*Game", "(?i)Start",
                              "点击任意位置继续", "點擊任意位置繼續", "点击", "點擊",
                              "(?i)Continue", "(?i)Tap", "(?i)Click"],
                    roi=[0, 0, cur_img.shape[1], cur_img.shape[0]],
                    threshold=0.5,
                )
                adv_job = self._tasker.post_recognition(JRecognitionType.OCR, advance_param, cur_img)
                adv_detail = adv_job.wait().get()
                if not adv_detail:
                    continue
                advance_target = None
                for node in adv_detail.nodes:
                    if node.recognition and node.recognition.hit:
                        best = node.recognition.best_result
                        if best:
                            bx = best.box
                            if hasattr(bx, 'x'):
                                advance_target = (bx.x + bx.w // 2, bx.y + bx.h // 2)
                            else:
                                advance_target = (bx[0] + bx[2] // 2, bx[1] + bx[3] // 2)
                            break
                if advance_target:
                    self.logger.info(
                        LogCategory.MAIN,
                        "云弹窗恢复：点击推进按钮",
                        target=advance_target,
                    )
                    click_job = self._controller.post_click(*advance_target)
                    click_job.wait()
                    advanced = True
                    # 点击后等待加载，再循环检测是否需要再次点击
                    time.sleep(3.0)
                    continue
                else:
                    # 没有找到推进按钮，可能已在主世界或正在加载
                    if advanced:
                        # 已点击过推进按钮，再等一会确认
                        time.sleep(3.0)
                        break
                    # 未点击过，继续等待
                    continue

            if advanced:
                self.logger.info(LogCategory.MAIN, "云弹窗恢复：已推进到主世界/加载中")
            else:
                self.logger.warning(LogCategory.MAIN, "云弹窗恢复：未找到推进按钮（可能已在主世界）")
            return True
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "云游戏空闲弹窗检测异常", error=str(exc))
            return False

    def _ensure_game_is_alive(self) -> bool:
        """检查游戏是否仍在运行，必要时尝试回到主世界。

        在队列任务间调用，确保游戏进程在继续执行任务前处于活跃状态。
        检查链：
        1. ADB 健康检查
        2. 截图验证
        3. 尝试 SceneAnyEnterWorld 回到主世界
        4. 验证是否确实在主世界（严格判定，避免子页面误匹配）

        重要约束（见 project_memory）：
        - SceneAnyEnterWorld 返回 False 是"正常失败"（OCR/TemplateMatch 未命中、UI 变化等），
          不得触发 RecoverGame/AndroidOpenGame 重启游戏。
        - 仅当截图失败（游戏进程可能已退出）时才视为真正异常。
        - 误触发重启会导致"任务刚启动就被强制关游戏"的严重 bug。

        Returns:
            True 若游戏已就绪（在主世界），False 若无法恢复（不重启游戏）
        """
        if not self._connected or self._tasker is None or self._controller is None:
            return False
        try:
            # 先尝试截图验证
            job = self._controller.post_screencap()
            if not self._wait_job(job, timeout_s=float(self._SCREENCAP_TIMEOUT_S)):
                self.logger.warning(LogCategory.MAIN, "游戏状态检查：截图失败，可能已退出")
                return False

            # 尝试 SceneAnyEnterWorld（已能正常工作且耗时约 40s）
            self.logger.info(LogCategory.MAIN, "游戏状态检查：尝试回到主世界")
            ok = self.run_pipeline("SceneAnyEnterWorld", {})
            if not ok:
                # SceneAnyEnterWorld 失败 = 正常失败（未命中识别节点），
                # 不重启游戏，让上层任务自行处理或失败
                self.logger.warning(LogCategory.MAIN, "游戏状态检查：SceneAnyEnterWorld 未命中（正常失败，不重启游戏）")
                return False

            # 验证是否确实在主世界（严格判定）
            # SceneAnyEnterWorld 可能因中间节点（如 __ScenePrivateCloudSplashContinue）
            # 匹配而返回 True，但实际未到达主世界（如仍在任务详情页）
            # 使用 5s 超时：判定节点无 next，节点级 timeout 不限制识别失败等待，需短超时兜底
            verify_ok = self.run_pipeline("__ScenePrivateAnyEnterWorldSuccess", {}, timeout_s=5.0)
            if verify_ok:
                self.logger.info(LogCategory.MAIN, "游戏状态检查：已在主世界（严格判定通过）")
                return True
            self.logger.warning(LogCategory.MAIN, "游戏状态检查：SceneAnyEnterWorld 返回成功但严格判定未通过（可能仍在子页面）")
            return False
        except Exception as exc:
            self.logger.warning(LogCategory.MAIN, "游戏状态检查异常", error=str(exc))
            return False

    # ──────────────────────────────────────────────
    # 任务识别过程日志记录
    # ──────────────────────────────────────────────
    def _log_recognition_detail(self, task_name: str, entry: str, job_result: Any) -> None:
        """记录任务执行过程中各识别节点的 OCR/TemplateMatch 结果。

        调用位置：_run_task_once（任务执行成功/失败后）。
        日志级别：DEBUG，仅在问题调试时查阅。

        注意：本方法只读不写，严禁包含任何 BACK/click/sleep 等副作用操作。
        历史曾因合并冲突残留了 _lightweight_recover_ui 的代码片段，导致每个
        任务执行后被无差别发送 3 次 BACK，触发云终末地游戏退出主世界 →
        _ensure_game_is_alive 重启游戏 → 单任务阻塞 4 分钟的级联故障。
        """
        if not job_result:
            return
        try:
            for node in job_result.nodes:
                if node.recognition:
                    rec = node.recognition
                    node_name = node.name or entry
                    result_texts = []
                    for r in rec.all_results[:5]:
                        if hasattr(r, 'text'):
                            result_texts.append(f'{r.text}({r.score:.2f})')
                        elif hasattr(r, 'box'):
                            result_texts.append(f'box=({r.box.x},{r.box.y},{r.box.w},{r.box.h}) score={r.score:.2f}')
                    self.logger.debug(
                        LogCategory.MAIN,
                        f"识别详情: node={node_name} algorithm={rec.algorithm} "
                        f"hit={rec.hit} results={len(rec.all_results)} "
                        f"top={result_texts[:3]}",
                        task=task_name,
                    )
        except Exception as exc:
            self.logger.debug(LogCategory.MAIN, "记录识别详情异常", task=task_name, error=str(exc))

    def _verify_connection_alive(self) -> bool:
        if not self._connected or self._controller is None:
            return False
        try:
            job = self._controller.post_screencap()
            ok = self._wait_job(job, timeout_s=float(self._SCREENCAP_TIMEOUT_S))
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

        关键：connect() 内部的 _connect_once() 只创建空的 Resource() 对象，
        不加载 pipeline 和 OCR 模型。若不调用 load_resource()，重连后所有
        OCR 任务都会因 'ocrer_ is null' 失败，pipeline 任务都会因
        'task not exist' 失败（见 queue_cli_run_20260726_155007.log 中
        DailyRewards 看门狗中断后的级联失败）。必须在 connect() 成功后
        显式调用 load_resource() 重建 pipeline 与 OCR 引擎。
        """
        self.logger.info(LogCategory.MAIN, "尝试重连 MaaEnd runtime")
        try:
            if not self.connect():
                return False
            if not self.load_resource():
                self.logger.error(LogCategory.MAIN, "重连后资源加载失败，连接不可用")
                self._connected = False
                return False
            self.logger.info(LogCategory.MAIN, "重连并加载资源成功")
            return True
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
        # 解决方案：把 post_screencap() + 轮询 job.done 全部放入 run_with_timeout
        # 的子线程，主线程用 join(timeout) 等待，超时即放弃。子线程为 daemon，自然消亡。
        if not self._connected or self._controller is None:
            return None

        def _do_screencap() -> Optional[bytes]:
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
                    return None
                time.sleep(0.05)
            if not job.succeeded:
                self.logger.warning(LogCategory.MAIN, "截图失败（screencap 未成功），但保持连接态")
                return None
            cached = self._controller.cached_image
            if cached is None:
                return None
            import cv2
            success, buf = cv2.imencode(".png", cached)
            if success:
                return buf.tobytes()
            return None

        result = run_with_timeout(
            _do_screencap,
            timeout=timeout_s + 2.0,  # 主线程给 2s 余量
            name="maaend-screenshot",
            thread_name="maaend-screenshot",
            on_timeout=lambda n, t: self.logger.warning(
                LogCategory.MAIN,
                "截图超时（post_screencap 阻塞或 job 不完成），放弃本次截图",
                timeout_s=timeout_s,
            ),
            on_error=lambda n, e: self.logger.warning(LogCategory.MAIN, "截图异常，保持连接态", error=str(e)),
        )
        if result.is_timeout or result.is_error:
            return None
        return result.data
