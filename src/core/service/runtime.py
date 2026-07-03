"""IstinaRuntime - 统一运行时入口

封装设备层与 MaaEndRuntime，提供 GUI/CLI 统一执行接口。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from core.capability.device.android_runtime import AndroidRuntime
from core.capability.device.adb_manager import ADBDeviceInfo
from core.capability.element_recognition import SceneUnderstandingService
from core.capability.llm.client import LlmClient
from core.capability.llm.runtime import LlamaServerRuntime
from core.foundation.logger import get_logger, LogCategory
from core.foundation.paths import get_project_root
from core.service.maa_end.runtime import MaaEndRuntime


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
        self._client = AndroidRuntime(serial=device_address or "default", adb_path=adb_path)

    @property
    def adb_manager(self):
        return self._client

    def get_devices(self) -> List[ADBDeviceInfo]:
        return self._client.get_devices()

    def screenshot(self, serial: Optional[str] = None) -> Optional[bytes]:
        return self._client.screenshot(serial=serial)

    def tap(self, x: int, y: int, serial: Optional[str] = None) -> None:
        self._client.tap(x, y, serial=serial)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300, serial: Optional[str] = None) -> None:
        self._client.swipe(x1, y1, x2, y2, duration_ms=duration_ms, serial=serial)

    def keyevent(self, key: str, serial: Optional[str] = None) -> str:
        return self._client.keyevent(key, serial=serial)

    def shell(self, cmd: str, serial: Optional[str] = None) -> str:
        return self._client.shell(cmd, serial=serial)

    def start_scrcpy(self, max_size: int = 1280, bit_rate: int = 8000000, serial: Optional[str] = None) -> Dict[str, Any]:
        return self._client.start_scrcpy(max_size=max_size, bit_rate=bit_rate, serial=serial)

    def stop_scrcpy(self, serial: Optional[str] = None) -> Dict[str, Any]:
        return self._client.stop_scrcpy(serial=serial)


class IstinaRuntime:
    """共享运行时 - GUI 和 CLI 的统一初始化入口"""

    def __init__(self, config_path: Optional[str] = None):
        self._config = self._load_config(config_path)
        self._android: Optional[AndroidRuntimeProxy] = None
        self._maaend: Optional[MaaEndRuntime] = None
        self._llm_runtime = LlamaServerRuntime(self._config)
        self._llm_client = LlmClient(base_url=self._llm_runtime.base_url)
        self._scene_svc: Optional[SceneUnderstandingService] = None
        self._logger = get_logger(__name__)

    @property
    def config(self) -> Dict[str, Any]:
        return self._config

    @property
    def connected(self) -> bool:
        return bool(self._maaend and self._maaend.connected)

    def android(self, serial: Optional[str] = None) -> AndroidRuntimeProxy:
        if self._android is None:
            self._android = AndroidRuntimeProxy(
                adb_path=self._config.get("adb_path", "3rd-part/adb/adb.exe"),
                device_address=self._config.get("device", {}).get("serial"),
            )
        return self._android

    def maaend(self, serial: Optional[str] = None) -> MaaEndRuntime:
        if self._maaend is None:
            self._maaend = MaaEndRuntime(
                maaend_root=self._config.get("maaend_root"),
                device_address=self._config.get("device", {}).get("serial", "localhost:16512"),
                adb_path=self._config.get("adb_path", "3rd-part/adb/adb.exe"),
            )
        return self._maaend

    def scene(self) -> SceneUnderstandingService:
        if self._scene_svc is None:
            self._scene_svc = SceneUnderstandingService(
                maaend_runtime=self.maaend(),
            )
        return self._scene_svc

    def connect(self, serial: Optional[str] = None) -> bool:
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
        self._logger.info(LogCategory.MAIN, "MaaEnd runtime 已就绪")
        return True

    def disconnect(self, serial: Optional[str] = None) -> None:
        if self._maaend is not None:
            try:
                self._maaend.disconnect()
            except Exception as e:
                self._logger.error(LogCategory.MAIN, "断开连接异常", error=str(e))

    def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> Any:
        params = params or {}
        parts = command.split(".")
        if len(parts) == 2:
            domain, action = parts
        else:
            domain, action = "unknown", command

        if domain == "task" and action == "run":
            return self._run_task(params)
        if domain == "task" and action == "list":
            return self._list_tasks(params)
        if domain == "preset" and action == "run":
            return self._run_preset(params)
        if domain == "preset" and action == "list":
            return self._list_presets(params)
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
        if domain == "scene" and action == "identify":
            return self._scene_identify(params)
        if domain == "scene" and action == "verify":
            return self._scene_verify(params)
        if domain == "scene" and action == "elements":
            return self._scene_analyze_elements(params)
        if domain == "scene" and action == "context":
            return self._scene_context(params)
        if domain == "llm":
            return self._llm_run(params)

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

    def _run_task(self, params: Dict[str, Any]) -> bool:
        name = params.get("name")
        options = params.get("options") or {}
        serial = params.get("serial")
        runtime = self.maaend(serial)
        return bool(runtime.run_task(name, options))

    def _run_preset(self, params: Dict[str, Any]) -> bool:
        name = params.get("name")
        serial = params.get("serial")
        runtime = self.maaend(serial)
        return bool(runtime.run_preset(name))

    def _screenshot(self, params: Dict[str, Any]) -> Optional[bytes]:
        serial = params.get("serial")
        runtime = self.maaend(serial)
        return runtime.screenshot()

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        candidates = []
        if config_path:
            candidates.append(Path(config_path))
        candidates.append(get_project_root() / "config" / "client_config.json")
        for path in candidates:
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    self._logger.warning(LogCategory.MAIN, "加载配置失败，使用默认值", error=str(e))
                    break
        return {}

    def _daily_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        options = params.get("options") or {}
        preset_name = options.get("preset", "DailyFull")
        if not self.connected:
            return {"status": "error", "message": "MaaEnd runtime 未连接", "flow": "daily_quest"}
        ok = self.execute("preset.run", {"name": preset_name})
        return {
            "status": "success" if ok else "error",
            "command": "daily.run",
            "flow": "daily_quest",
            "preset": preset_name,
            "options": options,
            "maaend_connected": self.connected,
        }

    def _harvest_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        options = params.get("options") or {}
        preset_name = options.get("preset", "AutoCollect")
        if not self.connected:
            return {"status": "error", "message": "MaaEnd runtime 未连接", "flow": "entity_harvest"}
        ok = self.execute("preset.run", {"name": preset_name})
        return {
            "status": "success" if ok else "error",
            "command": "harvest.run",
            "flow": "entity_harvest",
            "preset": preset_name,
            "options": options,
            "maaend_connected": self.connected,
        }

    def _analyze_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        mode = params.get("mode", "default")
        options = params.get("options") or {}
        task_name = options.get("task", "EnvironmentMonitoring")
        if not self.connected:
            return {"status": "error", "message": "MaaEnd runtime 未连接", "command": "analyze.run"}
        ok = self.execute("task.run", {"name": task_name, "options": options})
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
        if not self.connected:
            return {"status": "error", "message": "MaaEnd runtime 未连接", "command": "explore.run"}
        ok = self.execute("task.run", {"name": task_name, "options": options})
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
        if not self.connected:
            return {"status": "error", "message": "MaaEnd runtime 未连接", "command": "nav.to"}
        if not task_name:
            return {"status": "error", "message": "nav target 为空", "command": "nav.to"}
        ok = self.execute("task.run", {"name": task_name, "options": options})
        return {
            "status": "success" if ok else "error",
            "command": "nav.to",
            "target": target,
            "task": task_name,
            "options": options,
            "maaend_connected": self.connected,
        }

    # ------------------------------------------------------------------
    # Scene understanding commands
    # ------------------------------------------------------------------

    def _scene_identify(self, params: Dict[str, Any]) -> Dict[str, Any]:
        svc = self.scene()
        image_data = params.get("image")
        if image_data is not None:
            import base64
            try:
                image_bytes = base64.b64decode(image_data)
            except Exception:
                return {"status": "error", "message": "base64 解码失败"}
        else:
            runtime = self.maaend(params.get("serial"))
            image_bytes = runtime.screenshot()
        if image_bytes is None:
            return {"status": "error", "message": "无法获取截图"}
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        screen = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if screen is None:
            return {"status": "error", "message": "截图解码失败"}
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
        image_data = params.get("image")
        if image_data is not None:
            import base64
            try:
                image_bytes = base64.b64decode(image_data)
            except Exception:
                return {"status": "error", "message": "base64 解码失败"}
        else:
            runtime = self.maaend(params.get("serial"))
            image_bytes = runtime.screenshot()
        if image_bytes is None:
            return {"status": "error", "message": "无法获取截图"}
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        screen = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if screen is None:
            return {"status": "error", "message": "截图解码失败"}
        svc = self.scene()
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
        image_data = params.get("image")
        if image_data is not None:
            import base64
            try:
                image_bytes = base64.b64decode(image_data)
            except Exception:
                return {"status": "error", "message": "base64 解码失败"}
        else:
            runtime = self.maaend(params.get("serial"))
            image_bytes = runtime.screenshot()
        if image_bytes is None:
            return {"status": "error", "message": "无法获取截图"}
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        screen = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if screen is None:
            return {"status": "error", "message": "截图解码失败"}
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

    def _llm_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self._llm_runtime.ready:
            ok = self._llm_runtime.start()
            if not ok:
                return {"status": "error", "message": "llama-server 启动失败"}
        prompt = params.get("prompt") or params.get("text") or ""
        system = params.get("system")
        temperature = params.get("temperature")
        max_tokens = params.get("max_tokens")
        try:
            output = self._llm_client.chat(prompt, system=system, temperature=temperature, max_tokens=max_tokens)
            return {"status": "success", "command": "llm.chat", "output": output}
        except Exception as exc:
            return {"status": "error", "command": "llm.chat", "message": str(exc)}
