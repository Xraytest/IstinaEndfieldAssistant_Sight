"""IstinaAI CLI handlers

把 istina.py 的 main() 从“解析+处理”拆成“只解析路由，handler 负责执行”。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import platform
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from core.foundation.logger import get_logger
from core.foundation.paths import get_project_root
from core.service.runtime import IstinaRuntime


def _json_dumps(result: Any) -> str:
    try:
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False)


def _write_or_base64(data: bytes, out_path: Optional[str]) -> Dict[str, Any]:
    if data is None:
        return {"status": "error", "message": "screenshot returned None"}
    out = Path(out_path) if out_path else None
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        return {"status": "success", "path": str(out), "size": len(data)}
    return {"status": "success", "size": len(data), "base64": base64.b64encode(data).decode("ascii")}


class CLIDispatch:
    """istina.py 主函数只构造 args 和 runtime，然后把具体分支委托到这里。"""

    def __init__(self, runtime: IstinaRuntime):
        self._runtime = runtime
        self._logger = get_logger(__name__)

    def dispatch(self, args: argparse.Namespace) -> Dict[str, Any]:
        if args.command == "system":
            return self._handle_system(args)
        if args.command == "daily":
            return self._handle_daily(args)
        if args.command == "harvest":
            return self._handle_harvest(args)
        if args.command == "analyze":
            return self._handle_analyze(args)
        if args.command == "explore":
            return self._handle_explore(args)
        if args.command == "screenshot":
            return self._handle_screenshot(args)
        if args.command == "task":
            return self._handle_task(args)
        if args.command == "preset":
            return self._handle_preset(args)
        if args.command == "metadata":
            return self._handle_metadata(args)
        if args.command == "device":
            return self._handle_device(args)
        if args.command == "shell":
            return self._handle_shell(args)
        if args.command == "gpu":
            return self._handle_gpu(args)
        if args.command == "scene":
            return self._handle_scene(args)
        if args.command == "config":
            return self._handle_config(args)
        if args.command == "auth":
            return self._handle_auth(args)
        if args.command == "model":
            return self._handle_model(args)
        if args.command == "nav":
            return self._handle_nav(args)
        if args.command == "nav2":
            return self._handle_nav2(args)
        if args.command == "nav3":
            return self._handle_nav3(args)
        if args.command == "llm":
            return self._handle_llm(args)
        return {"status": "error", "message": "unknown command"}

    def _handle_system(self, args: argparse.Namespace) -> Dict[str, Any]:
        if args.action == "connect":
            ok = self._runtime.execute("system.connect", {"serial": args.serial})
            return {"status": "success" if ok else "error", "connected": self._runtime.connected}
        if args.action == "disconnect":
            self._runtime.execute("system.disconnect", {"serial": args.serial})
            return {"status": "success", "connected": self._runtime.connected}
        if args.action == "doctor":
            return _handle_system_doctor(self._runtime, args)
        if args.action == "env":
            return _handle_system_env(self._runtime, args)
        if args.action == "disk":
            return _handle_system_disk(self._runtime, args)
        if args.action == "perf":
            return _handle_system_perf(self._runtime, args)
        return {"status": "error", "message": "unknown system action"}

    def _handle_task(self, args: argparse.Namespace) -> Dict[str, Any]:
        if args.action == "run":
            return _handle_task_run(self._runtime, args)
        if args.action == "list":
            return _handle_task_list(self._runtime, args)
        return {"status": "error", "message": "unknown task action"}

    def _handle_preset(self, args: argparse.Namespace) -> Dict[str, Any]:
        if args.action == "run":
            return _handle_preset_run(self._runtime, args)
        if args.action == "list":
            return _handle_preset_list(self._runtime, args)
        return {"status": "error", "message": "unknown preset action"}

    def _handle_metadata(self, args: argparse.Namespace) -> Dict[str, Any]:
        if args.action == "list":
            return _handle_metadata_list(self._runtime, args)
        return {"status": "error", "message": "unknown metadata action"}

    def _handle_device(self, args: argparse.Namespace) -> Dict[str, Any]:
        if args.action == "status":
            return _handle_device_status(self._runtime, args)
        if args.action == "screenshot":
            return _handle_device_screenshot(self._runtime, args)
        if args.action == "info":
            return _handle_device_info(self._runtime, args)
        if args.action == "tap":
            return _handle_device_tap(self._runtime, args)
        if args.action == "swipe":
            return _handle_device_swipe(self._runtime, args)
        if args.action == "keyevent":
            return _handle_device_keyevent(self._runtime, args)
        if args.action == "monitor":
            return _handle_device_monitor(self._runtime, args)
        return {"status": "error", "message": "unknown device action"}

    def _handle_gpu(self, args: argparse.Namespace) -> Dict[str, Any]:
        if args.action == "status":
            return _handle_gpu_status(self._runtime, args)
        if args.action == "monitor":
            return _handle_gpu_monitor(self._runtime, args)
        if args.action == "recommend":
            return _handle_gpu_recommend(self._runtime, args)
        if args.action == "cuda-check":
            return _handle_gpu_cuda_check(self._runtime, args)
        return {"status": "error", "message": "unknown gpu action"}

    def _handle_scene(self, args: argparse.Namespace) -> Dict[str, Any]:
        if args.action == "capture":
            return _handle_scene_capture(self._runtime, args)
        if args.action == "nav":
            return _handle_scene_nav(self._runtime, args)
        if args.action == "analyze":
            return _handle_scene_analyze(self._runtime, args)
        if args.action == "ocr":
            return _handle_scene_ocr(self._runtime, args)
        if args.action == "explore":
            return _handle_scene_explore(self._runtime, args)
        if args.action == "identify":
            return _handle_scene_identify(self._runtime, args)
        if args.action == "verify":
            return _handle_scene_verify(self._runtime, args)
        if args.action == "elements":
            return _handle_scene_elements(self._runtime, args)
        if args.action == "context":
            return _handle_scene_context(self._runtime, args)
        return {"status": "error", "message": "unknown scene action"}

    def _handle_config(self, args: argparse.Namespace) -> Dict[str, Any]:
        if args.action == "get":
            return _handle_config_get(self._runtime, args)
        if args.action == "set":
            return _handle_config_set(self._runtime, args)
        return {"status": "error", "message": "unknown config action"}

    def _handle_auth(self, args: argparse.Namespace) -> Dict[str, Any]:
        if args.action == "status":
            return _handle_auth_status(self._runtime, args)
        if args.action == "login":
            return _handle_auth_login(self._runtime, args)
        if args.action == "logout":
            return _handle_auth_logout(self._runtime, args)
        return {"status": "error", "message": "unknown auth action"}

    def _handle_model(self, args: argparse.Namespace) -> Dict[str, Any]:
        if args.action == "list":
            return _handle_model_list(self._runtime, args)
        if args.action == "info":
            return _handle_model_info(self._runtime, args)
        if args.action == "disk":
            return _handle_model_disk(self._runtime, args)
        return {"status": "error", "message": "unknown model action"}

    def _handle_llm(self, args: argparse.Namespace) -> Dict[str, Any]:
        if args.action == "prompt":
            return _handle_llm_prompt(self._runtime, args)
        if args.action == "status":
            return _handle_llm_status(self._runtime, args)
        if args.action == "start":
            return {"status": "success" if self._runtime.warmup_llm() else "error", "command": "llm.start"}
        if args.action == "stop":
            self._runtime.cooldown_llm()
            return {"status": "success", "command": "llm.stop"}
        return {"status": "error", "message": "unknown llm action"}

    def _handle_daily(self, args: argparse.Namespace) -> Dict[str, Any]:
        return _handle_daily(self._runtime, args)

    def _handle_harvest(self, args: argparse.Namespace) -> Dict[str, Any]:
        return _handle_harvest(self._runtime, args)

    def _handle_analyze(self, args: argparse.Namespace) -> Dict[str, Any]:
        return _handle_analyze(self._runtime, args)

    def _handle_explore(self, args: argparse.Namespace) -> Dict[str, Any]:
        return _handle_explore(self._runtime, args)

    def _handle_screenshot(self, args: argparse.Namespace) -> Dict[str, Any]:
        return _handle_screenshot(self._runtime, args)

    def _handle_shell(self, args: argparse.Namespace) -> Dict[str, Any]:
        return _handle_shell(self._runtime, args)

    def _handle_nav(self, args: argparse.Namespace) -> Dict[str, Any]:
        return _handle_nav(self._runtime, args)

    def _handle_nav2(self, args: argparse.Namespace) -> Dict[str, Any]:
        return _handle_nav2(self._runtime, args)


    def _handle_nav3(self, args: argparse.Namespace) -> Dict[str, Any]:
        return _handle_nav3(self._runtime, args)
# -------------------------
# 具体处理函数
# -------------------------

def _handle_daily(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    try:
        options = json.loads(args.options)
    except json.JSONDecodeError as exc:
        return {"status": "error", "message": f"options JSON 解析失败: {exc}"}
    return runtime.execute("daily.run", {"options": options})


def _handle_harvest(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    try:
        options = json.loads(args.options)
    except json.JSONDecodeError as exc:
        return {"status": "error", "message": f"options JSON 解析失败: {exc}"}
    return runtime.execute("harvest.run", {"options": options})


def _handle_analyze(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    try:
        options = json.loads(args.options)
    except json.JSONDecodeError as exc:
        return {"status": "error", "message": f"options JSON 解析失败: {exc}"}
    return runtime.execute("analyze.run", {"options": options})


def _handle_explore(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    try:
        options = json.loads(args.options)
    except json.JSONDecodeError as exc:
        return {"status": "error", "message": f"options JSON 解析失败: {exc}"}
    return runtime.execute("explore.run", {"options": options})


def _handle_screenshot(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    _logger = get_logger(__name__)
    _logger.info("CLI handler: 开始 screenshot", out=getattr(args, "out", None))
    data = runtime.execute("screenshot", {})
    _logger.info("CLI handler: screenshot 完成", data_type=type(data).__name__, data_size=len(data) if isinstance(data, (bytes, bytearray)) else None)
    return _write_or_base64(data, getattr(args, "out", None))


def _handle_task_run(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    try:
        options = json.loads(args.options)
    except json.JSONDecodeError as exc:
        return {"status": "error", "message": f"options JSON 解析失败: {exc}"}
    params = {
        "name": args.name,
        "options": options,
        "serial": getattr(args, "serial", None),
    }
    if hasattr(args, "timeout") and args.timeout is not None:
        params["timeout"] = args.timeout
    ok = runtime.execute("task.run", params)
    return {"status": "success" if ok else "error", "task": args.name}


def _handle_task_list(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    tasks = runtime.execute("task.list", {"serial": getattr(args, "serial", None)})
    if not isinstance(tasks, dict):
        tasks = {}
    task_option_defs = {}
    try:
        task_option_defs = runtime.maaend(getattr(args, "serial", None)).task_option_defs()
    except Exception:
        task_option_defs = {}
    return {"status": "success", "tasks": tasks, "task_option_defs": task_option_defs}


def _handle_preset_run(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    ok = runtime.execute("preset.run", {"name": args.name, "serial": getattr(args, "serial", None)})
    return {"status": "success" if ok else "error", "preset": args.name}


def _handle_preset_list(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    presets = runtime.execute("preset.list", {"serial": getattr(args, "serial", None)})
    if not isinstance(presets, dict):
        presets = {}
    return {"status": "success", "presets": presets}


def _handle_metadata_list(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    metadata = runtime.execute("metadata.list", {"serial": getattr(args, "serial", None)})
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "status": "success",
        "tasks": metadata.get("tasks") or {},
        "presets": metadata.get("presets") or {},
        "task_option_defs": metadata.get("task_option_defs") or {},
    }


def _handle_device_info(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    android = runtime.android()
    devices = android.get_devices()
    return {
        "status": "success",
        "devices": [{"serial": d.serial, "state": d.state} for d in devices],
    }


def _handle_device_status(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    android = runtime.android()
    try:
        client = android.default_client
        server_version = client.version()
        devices = android.get_devices()
        return {
            "status": "success",
            "adb_server": {"version": server_version},
            "devices": [{"serial": d.serial, "state": d.state} for d in devices],
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _handle_device_screenshot(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    android = runtime.android()
    data = android.screenshot()
    return _write_or_base64(data, getattr(args, "out", None))


def _handle_device_tap(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    android = runtime.android()
    try:
        android.tap(int(args.x), int(args.y))
        return {"status": "success", "x": int(args.x), "y": int(args.y)}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _handle_device_swipe(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    android = runtime.android()
    try:
        android.swipe(
            int(args.x1),
            int(args.y1),
            int(args.x2),
            int(args.y2),
            duration_ms=int(args.duration),
        )
        return {
            "status": "success",
            "x1": int(args.x1),
            "y1": int(args.y1),
            "x2": int(args.x2),
            "y2": int(args.y2),
            "duration_ms": int(args.duration),
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _handle_device_keyevent(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    android = runtime.android()
    try:
        android.shell(f"input keyevent {args.key}")
        return {"status": "success", "key": args.key}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _handle_device_monitor(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    try:
        android = runtime.android()
        devices = android.get_devices()
        return {
            "status": "success",
            "device_count": len(devices),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _handle_shell(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    android = runtime.android()
    try:
        output = android.shell(args.cmd)
        return {"status": "success", "output": output}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _handle_scene_capture(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    data = runtime.android().screenshot()
    return _write_or_base64(data, getattr(args, "out", None))


def _handle_scene_nav(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    target = getattr(args, "target", None)
    return runtime.execute("nav.to", {"target": target})


def _handle_scene_analyze(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    try:
        options = json.loads(getattr(args, "options", "{}") or "{}")
    except json.JSONDecodeError as exc:
        return {"status": "error", "message": f"options JSON 解析失败: {exc}"}
    return runtime.execute("analyze.run", {"options": options})


def _handle_scene_ocr(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    return {"status": "not_implemented", "command": "scene ocr"}


def _handle_scene_explore(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    try:
        options = json.loads(getattr(args, "options", "{}") or "{}")
    except json.JSONDecodeError as exc:
        return {"status": "error", "message": f"options JSON 解析失败: {exc}"}
    return runtime.execute("explore.run", {"options": options})


def _handle_config_get(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    value = runtime.config.get(args.key)
    if value is None:
        return {"status": "error", "message": "config key not found", "key": args.key}
    return {"status": "success", "key": args.key, "value": value}


def _handle_config_set(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    runtime.config[args.key] = args.value
    runtime.save_config()
    return {"status": "success", "key": args.key, "value": args.value}


def _handle_auth_status(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    return {"status": "not_implemented", "auth": "no active session"}


def _handle_auth_login(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    return {"status": "not_implemented"}


def _handle_auth_logout(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    return {"status": "not_implemented"}


def _handle_model_list(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    root = get_project_root()
    models_dir = Path(root) / "models"
    files = []
    if models_dir.is_dir():
        for path in sorted(models_dir.rglob("*")):
            if path.is_file():
                files.append({
                    "name": str(path.relative_to(models_dir)),
                    "path": str(path),
                    "size_bytes": path.stat().st_size,
                })
    return {"status": "success", "models": files}


def _handle_model_info(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    root = get_project_root()
    models_dir = Path(root) / "models"
    try:
        root_resolved = models_dir.resolve()
        target = (models_dir / args.name).resolve()
        if not target.is_relative_to(root_resolved):
            target = None
    except Exception:
        target = None
    if target is None or not target.exists():
        return {"status": "error", "message": "model not found", "name": args.name}
    return {
        "status": "success",
        "name": args.name,
        "path": str(target),
        "size_bytes": target.stat().st_size if target.is_file() else None,
        "is_dir": target.is_dir(),
    }


def _handle_model_disk(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    root = get_project_root()
    models_dir = Path(root) / "models"
    if not models_dir.is_dir():
        return {"status": "success", "path": str(models_dir), "size_bytes": 0}
    total = 0
    for path in models_dir.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except Exception:
                pass
    return {"status": "success", "path": str(models_dir), "size_bytes": total}


def _handle_gpu_status(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    try:
        import pynvml
        pynvml.nvmlInit()
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            return {
                "status": "success",
                "gpus": [
                    {
                        "index": 0,
                        "name": name,
                        "total_memory_bytes": mem.total,
                        "free_memory_bytes": mem.free,
                        "used_memory_bytes": mem.used,
                    }
                ],
            }
        finally:
            pynvml.nvmlShutdown()
    except Exception:
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            return {
                "status": "success",
                "gpus": [
                    {
                        "index": i,
                        "name": gpu.name,
                        "total_memory_bytes": int(gpu.memoryTotal * 1024 * 1024),
                        "free_memory_bytes": int(gpu.memoryFree * 1024 * 1024),
                        "used_memory_bytes": int(gpu.memoryUsed * 1024 * 1024),
                    }
                    for i, gpu in enumerate(gpus)
                ],
            }
        except Exception:
            return {"status": "success", "gpus": [], "message": "no gpu libs"}


def _handle_gpu_monitor(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    try:
        import pynvml
        pynvml.nvmlInit()
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            return {
                "status": "success",
                "utilization": {
                    "gpu_percent": util.gpu,
                    "memory_percent": util.memory,
                },
                "memory": {
                    "total_bytes": mem.total,
                    "free_bytes": mem.free,
                    "used_bytes": mem.used,
                },
            }
        finally:
            pynvml.nvmlShutdown()
    except Exception:
        try:
            import GPUtil
            gpu = GPUtil.getGPUs()[0]
            return {
                "status": "success",
                "utilization": {
                    "gpu_percent": gpu.load * 100,
                    "memory_percent": (gpu.memoryUsed / gpu.memoryTotal) * 100 if gpu.memoryTotal else None,
                },
                "memory": {
                    "total_bytes": int(gpu.memoryTotal * 1024 * 1024),
                    "free_bytes": int(gpu.memoryFree * 1024 * 1024),
                    "used_bytes": int(gpu.memoryUsed * 1024 * 1024),
                },
            }
        except Exception:
            return {"status": "success", "message": "no gpu libs", "utilization": None, "memory": None}


def _handle_gpu_recommend(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    gpus = _handle_gpu_status(runtime, args).get("gpus", [])
    recommendation = "CPU"
    if gpus:
        mem = gpus[0].get("free_memory_bytes", 0)
        if mem and mem >= 4 * 1024 * 1024 * 1024 or mem and mem >= 2 * 1024 * 1024 * 1024:
            recommendation = "GPU"
    return {
        "status": "success",
        "gpu_count": len(gpus),
        "recommendation": recommendation,
        "primary": gpus[0] if gpus else None,
    }


def _handle_gpu_cuda_check(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    try:
        import torch
        return {
            "status": "success",
            "torch_available": True,
            "cuda_available": bool(torch.cuda.is_available()),
            "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        }
    except Exception as exc:
        return {
            "status": "success",
            "torch_available": False,
            "cuda_available": False,
            "device_count": 0,
            "error": str(exc),
        }


def _handle_system_doctor(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    try:
        cpu_count = os.cpu_count()
    except Exception:
        cpu_count = None
    result = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "cpu_count": cpu_count,
    }
    try:
        import psutil
        result["memory"] = {
            "total_bytes": psutil.virtual_memory().total,
            "available_bytes": psutil.virtual_memory().available,
        }
    except Exception:
        pass
    return {"status": "success", "doctor": result}


def _handle_system_env(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "status": "success",
        "env": {
            "python_version": platform.python_version(),
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "cwd": os.getcwd(),
        },
    }


def _handle_system_disk(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    path = str(get_project_root())
    usage = shutil.disk_usage(path)
    return {
        "status": "success",
        "path": path,
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
    }


def _handle_system_perf(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    result: Dict[str, Any] = {"status": "success", "perf": {"cpu_count": os.cpu_count()}}
    try:
        import psutil
        result["perf"]["cpu_percent"] = psutil.cpu_percent(interval=0)
        result["perf"]["memory"] = {
            "total_bytes": psutil.virtual_memory().total,
            "available_bytes": psutil.virtual_memory().available,
            "percent": psutil.virtual_memory().percent,
        }
    except Exception:
        pass
    return result


def _handle_scene_identify(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    image_data = getattr(args, "image", None)
    return runtime.execute("scene.identify", {"image": image_data})


def _handle_scene_verify(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    expected = getattr(args, "expected", None)
    image_data = getattr(args, "image", None)
    return runtime.execute("scene.verify", {"expected": expected, "image": image_data})


def _handle_scene_elements(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    image_data = getattr(args, "image", None)
    return runtime.execute("scene.elements", {"image": image_data})


def _handle_scene_context(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    return runtime.execute("scene.context", {})


def _handle_nav(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    return runtime.execute("nav.to", {"target": args.target})


def _handle_nav2(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    action = getattr(args, "action", None)
    if action == "to_coords":
        return runtime.execute("nav2.to_coords", {
            "map_name": args.map_name,
            "x": args.x,
            "y": args.y,
            "level_id": getattr(args, "level", None),
            "zone": getattr(args, "zone", None),
        })
    if action == "to_entity":
        return runtime.execute("nav2.to_entity", {
            "name": args.name,
            "limit": getattr(args, "limit", 10),
        })
    if action == "where":
        return runtime.execute("nav2.where", {})
    if action == "list_entities":
        return runtime.execute("nav2.list_entities", {
            "category": getattr(args, "category", None),
            "map_name": getattr(args, "map_name", None),
            "name": getattr(args, "name", None),
            "limit": getattr(args, "limit", 50),
        })
    if action == "list_maps":
        return runtime.execute("nav2.list_maps", {})
    return {"status": "error", "message": f"unknown nav2 action: {action}"}



def _handle_nav3(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    action = getattr(args, "action", None)
    if action == "walk":
        return runtime.execute("nav3.walk", {
            "map_name": args.map_name,
            "x": args.x,
            "y": args.y,
            "level_id": getattr(args, "level", None),
            "zone": getattr(args, "zone", None),
            "max_steps": getattr(args, "max_steps", 40),
        })
    if action == "to_entity":
        return runtime.execute("nav3.to_entity", {
            "name": args.name,
            "max_steps": getattr(args, "max_steps", 40),
            "limit": getattr(args, "limit", 10),
        })
    if action == "status":
        return runtime.execute("nav3.status", {})
    return {"status": "error", "message": f"unknown nav3 action: {action}"}


def _handle_llm_prompt(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    params: Dict[str, Any] = {"prompt": args.text}
    system = getattr(args, "system", None)
    temperature = getattr(args, "temperature", None)
    max_tokens = getattr(args, "max_tokens", None)
    image = getattr(args, "image", None)
    if system:
        params["system"] = system
    if temperature is not None:
        params["temperature"] = float(temperature)
    if max_tokens is not None:
        params["max_tokens"] = int(max_tokens)
    if image is not None:
        params["image"] = image
    return runtime.execute("llm.chat", params)


def _handle_llm_status(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    return runtime.execute("llm.status", {})
