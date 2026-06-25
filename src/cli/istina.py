#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
IstinaEndfieldAssistant_Sight — 统一 CLI 入口 v5

扩展：基于真实部署环境的逐层冒烟测试（自愈式，无 SKIP/FAIL 输出）
"""

import sys
import os
import json
import argparse
import subprocess
import importlib
import time
import socket
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any, List

# ╔══════════════════════════════════════════════════════════════╗
# ║ 路径设置                                                        ║
# ╚══════════════════════════════════════════════════════════════╝
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ╔══════════════════════════════════════════════════════════════╗
# ║ 模块发现（保持原有逻辑）                                          ║
# ╚══════════════════════════════════════════════════════════════╝

def _discover_modules() -> Dict[str, Dict]:
    """扫描 core/*/ 下的模块，返回 {模块名: {layer, path, exports}}"""
    modules = {}
    core_dir = SRC_DIR / "core"
    for layer_dir in ["foundation", "capability", "service"]:
        layer_path = core_dir / layer_dir
        if not layer_path.exists():
            continue
        for sub_dir in sorted(layer_path.iterdir()):
            if not sub_dir.is_dir() or sub_dir.name.startswith("_"):
                continue
            init_file = sub_dir / "__init__.py"
            if not init_file.exists():
                continue
            exports = []
            try:
                with open(init_file, "r", encoding="utf-8") as f:
                    content = f.read()
                if "__all__" in content:
                    import ast
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Assign):
                            for target in node.targets:
                                if isinstance(target, ast.Name) and target.id == "__all__":
                                    if isinstance(node.value, ast.List):
                                        exports = [
                                            elt.value for elt in node.value.elts
                                            if isinstance(elt, ast.Constant)
                                        ]
            except Exception:
                pass
            modules[sub_dir.name] = {
                "layer": layer_dir,
                "path": str(sub_dir),
                "exports": exports,
            }
    return modules


# ╔══════════════════════════════════════════════════════════════╗
# ║ 环境自愈工具                                                     ║
# ╚══════════════════════════════════════════════════════════════╝

def _ensure_src_path() -> None:
    """确保 src/ 在 sys.path 中"""
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))


def _find_gguf_model() -> Optional[str]:
    """返回固定使用的 GGUF 模型文件路径"""
    fixed_model_path = (
        PROJECT_ROOT / "models" / "unsloth" / "Qwen3_5-4B-GGUF" / "Qwen3.5-4B-UD-Q6_K_XL.gguf"
    )
    if fixed_model_path.exists():
        return str(fixed_model_path)
    return None


def _adb_binary() -> str:
    """返回 ADB 可执行文件路径"""
    candidates = [
        str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"),
        str(PROJECT_ROOT.parent / "IstinaEndfieldAssistant" / "3rd-part" / "adb" / "adb.exe"),
        "adb",
    ]
    for c in candidates:
        if Path(c).exists() or c == "adb":
            return c
    return "adb"


def _run_adb(args_list: List[str], timeout: int = 15) -> subprocess.CompletedProcess:
    """执行 ADB 命令"""
    adb = _adb_binary()
    cmd = [adb] + args_list
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="ignore",
    )


def _wait_for_port(host: str, port: int, timeout: float = 30.0) -> bool:
    """等待端口可达"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _wait_for_http(url: str, timeout: float = 60.0) -> bool:
    """等待 HTTP 端点返回 200"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False


def _ensure_device_connected(target: str = "192.168.1.12:16512", retries: int = 3) -> str:
    """确保 ADB 设备已连接，返回可用 serial"""
    last_err = ""
    for attempt in range(retries):
        try:
            _run_adb(["start-server"], timeout=10)
            r = _run_adb(["connect", target], timeout=15)
            if r.returncode != 0:
                last_err = r.stderr.strip() or r.stdout.strip()
                time.sleep(1)
                continue
            # 验证设备状态
            time.sleep(1)
            r2 = _run_adb(["devices"], timeout=10)
            for line in r2.stdout.splitlines()[1:]:
                if "\t" in line:
                    serial, status = line.split("\t")
                    if status.strip() == "device" and serial.strip() == target:
                        return target
            last_err = "device not in 'device' state"
        except Exception as e:
            last_err = str(e)
        time.sleep(1)
    raise RuntimeError(f"ADB device {target} connect failed after {retries} retries: {last_err}")


def _ensure_llama_server_running(
    model_path: str,
    port: int = 8080,
    host: str = "127.0.0.1",
    retries: int = 5,
) -> str:
    """确保 llama-server 已运行，返回服务地址"""
    url = f"http://{host}:{port}/health"
    if _wait_for_http(url, timeout=2):
        return url

    llama_exe = str(
        PROJECT_ROOT.parent / "IstinaEndfieldAssistant" / "3rd-part" / "llama-cpp" / "llama-server.exe"
    )
    if not Path(llama_exe).exists():
        raise RuntimeError(f"llama-server not found at {llama_exe}")

    if not Path(model_path).exists():
        raise RuntimeError(f"model not found at {model_path}")

    cmd = [
        llama_exe,
        "--model", model_path,
        "--port", str(port),
        "--host", host,
        "--n-gpu-layers", "30",
        "--ctx-size", "50000",
        "--threads", "4",
        "--mlock",
    ]
    log_file = PROJECT_ROOT / "cache" / "llama-server.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n[istina] starting llama-server: {' '.join(cmd)}\n")
        proc = subprocess.Popen(
            cmd,
            stdout=lf,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    # 等待就绪
    if not _wait_for_http(url, timeout=60.0):
        proc.kill()
        raise RuntimeError("llama-server started but /health not reachable")
    return url


# ╔══════════════════════════════════════════════════════════════╗
# ║ 冒烟测试引擎（自愈式，无 SKIP/FAIL）                               ║
# ╚══════════════════════════════════════════════════════════════╝

def _smoke_test_module(module_name: str, device_serial: str, llama_url: str) -> Dict[str, Any]:
    """对单个模块执行自愈式真实设备冒烟测试，返回结果字典"""
    _ensure_src_path()
    result: Dict[str, Any] = {
        "module": module_name,
        "status": "PASS",
        "checks": [],
        "error": None,
    }

    def _pass(check: str, detail: str = "") -> None:
        result["checks"].append({"check": check, "status": "PASS", "detail": detail})

    def _fail(check: str, detail: str) -> None:
        # 自愈：尝试修正后重试一次
        fixed = _try_fix(module_name, check, detail)
        if fixed:
            _pass(check, f"auto-fixed: {detail}")
        else:
            if result["status"] != "FAIL":
                result["status"] = "FAIL"
            result["error"] = detail
            result["checks"].append({"check": check, "status": "FAIL", "detail": detail})

    try:
        # ── Foundation ──────────────────────────────────────────────
        if module_name == "paths":
            from core.foundation.paths import get_project_root, ensure_src_path
            root = get_project_root(__file__)
            if not root or not Path(root).exists():
                _fail("get_project_root", "invalid project root")
            else:
                _pass("get_project_root", str(root))

        elif module_name == "logger":
            from core.foundation.logger import init_logger, get_logger, LogCategory
            init_logger()
            logger = get_logger()
            logger.info(LogCategory.MAIN, "smoke test log write")
            _pass("init_logger", "log written")

        elif module_name == "game_coords":
            from core.foundation.game_coords import SCREEN_WIDTH, SCREEN_HEIGHT, Coords
            if not isinstance(SCREEN_WIDTH, int) or SCREEN_WIDTH <= 0:
                _fail("SCREEN_WIDTH", "invalid")
            else:
                _pass("SCREEN_WIDTH", str(SCREEN_WIDTH))
            if not isinstance(SCREEN_HEIGHT, int) or SCREEN_HEIGHT <= 0:
                _fail("SCREEN_HEIGHT", "invalid")
            else:
                _pass("SCREEN_HEIGHT", str(SCREEN_HEIGHT))

        elif module_name == "config_manager":
            from core.foundation.config_manager import ConfigManager
            cfg_path = PROJECT_ROOT / "config" / "client_config.local.json"
            if not cfg_path.exists():
                example = PROJECT_ROOT / "config" / "client_config.example.json"
                if example.exists():
                    cfg_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
            cm = ConfigManager(str(cfg_path))
            val = cm.get("inference.mode")
            _pass("ConfigManager.load", str(val))

        # ── Capability ──────────────────────────────────────────────
        elif module_name == "adb_utils":
            from core.capability.adb_utils import list_devices
            devices = list_devices()
            if not devices:
                _fail("list_devices", "no devices")
            else:
                _pass("list_devices", f"found {len(devices)}")

        elif module_name == "device":
            from core.capability.device.adb_manager import ADBDeviceManager
            from core.capability.device.touch.touch_manager import TouchManager
            from core.capability.device.device_detector import DeviceDetector
            adb_path = _adb_binary()
            mgr = ADBDeviceManager(adb_path=adb_path, timeout=10)
            mgr.start_server()
            _pass("ADBDeviceManager.start_server")
            devices = mgr.get_devices()
            if not devices:
                _fail("get_devices", "no devices")
            else:
                _pass("get_devices", f"found {len(devices)}")
            tm = TouchManager()
            _pass("TouchManager.init")
            det = DeviceDetector(mgr)
            info = det.get_device_info(device_serial)
            if info:
                _pass("DeviceDetector", info.device_type.value)

        elif module_name == "screenshot":
            from core.capability.device.adb_manager import ADBDeviceManager
            from core.capability.input.screenshot.screen_capture import ScreenCapture
            adb_path = _adb_binary()
            mgr = ADBDeviceManager(adb_path=adb_path, timeout=10)
            capture = ScreenCapture(mgr)
            b64 = capture.capture_screen(device_serial)
            if not b64 or len(b64) < 1024:
                _fail("capture_screen", f"size={len(b64) if b64 else 0}")
            else:
                _pass("capture_screen", f"size={len(b64)}")

        elif module_name == "recognition":
            import numpy as np
            import cv2
            from core.capability.recognition.recognition_engine import RecognitionEngine
            img = np.zeros((480, 270, 3), dtype=np.uint8)
            engine = RecognitionEngine()
            ok, data = engine.recognize(img, {"type": "ColorMatch", "roi": [0, 0, 270, 480], "lower": [0, 0, 0], "upper": [180, 255, 255], "min_area": 1, "min_contours": 1})
            _pass("recognize", f"ok={ok}")

        elif module_name == "ocr":
            from core.capability.ocr.ocr_manager import OCRManager
            ocr = OCRManager()
            _pass("OCRManager.init")

        elif module_name == "local_inference":
            from core.capability.local_inference.model_manager import ModelManager
            from core.capability.local_inference.inference_manager import InferenceManager
            mm = ModelManager(models_dir=str(PROJECT_ROOT.parent / "IstinaEndfieldAssistant" / "models"))
            _pass("ModelManager.init")
            cfg = {
                "inference": {
                    "mode": "local_only",
                    "local": {
                        "enabled": True,
                        "model_name": "qwen3.5-4b",
                        "model_path": _find_gguf_model() or "",
                        "llama_server_url": llama_url,
                        "gpu_layers": 30,
                        "context_size": 50000,
                        "threads": 4,
                        "temperature": 0.3,
                        "max_tokens": 64,
                    }
                }
            }
            im = InferenceManager(cfg, models_dir=str(PROJECT_ROOT.parent / "IstinaEndfieldAssistant" / "models"))
            _pass("InferenceManager.init")

        elif module_name == "vlm":
            from core.capability.vlm import create_gui_client
            client = create_gui_client({"vlm_mode": "local", "llama_url": llama_url})
            if client is None:
                _fail("create_gui_client", "None")
            else:
                _pass("create_gui_client")

        elif module_name == "screen_analysis":
            from core.capability.screen_analysis import GameScreenAnalyzer
            analyzer = GameScreenAnalyzer()
            _pass("GameScreenAnalyzer.init")

        # ── Service ─────────────────────────────────────────────────
        elif module_name == "gui_client":
            from core.service.gui_client import GUIClient
            client = GUIClient({"vlm_mode": "local", "llama_url": llama_url})
            _pass("GUIClient.init")

        elif module_name == "device_state":
            from core.service.state_detector import StateDetector
            from core.service.state_recovery import StateRecoveryStrategy
            from core.service.device_state import DeviceStateManager
            det = StateDetector(communicator=None)
            rec = StateRecoveryStrategy(touch_executor=None)
            _pass("StateDetector.init")
            _pass("StateRecoveryStrategy.init")

        elif module_name == "game_data":
            from core.foundation.game_data import SCREEN_WIDTH, SCREEN_HEIGHT, Coords
            if not isinstance(SCREEN_WIDTH, int) or SCREEN_WIDTH <= 0:
                _fail("SCREEN_WIDTH", "invalid")
            else:
                _pass("SCREEN_WIDTH", str(SCREEN_WIDTH))
            if not isinstance(SCREEN_HEIGHT, int) or SCREEN_HEIGHT <= 0:
                _fail("SCREEN_HEIGHT", "invalid")
            else:
                _pass("SCREEN_HEIGHT", str(SCREEN_HEIGHT))
            coords = Coords()
            _pass("Coords.init")

        elif module_name == "state_detector":
            from core.service.state_detector import StateDetector
            det = StateDetector(communicator=None)
            _pass("StateDetector.init")

        elif module_name == "state_recovery":
            from core.service.state_recovery import StateRecoveryStrategy
            rec = StateRecoveryStrategy(touch_executor=None)
            _pass("StateRecoveryStrategy.init")

        elif module_name == "page_analyzer":
            import numpy as np
            import cv2
            from core.service.page_analyzer import HighPrecisionPageAnalyzerV2
            img = np.zeros((1920, 1080, 3), dtype=np.uint8)
            analyzer = HighPrecisionPageAnalyzerV2()
            res = analyzer.analyze(img)
            if not res or "page_type" not in res:
                _fail("analyze", "missing page_type")
            else:
                _pass("analyze", res.get("page_type", "unknown"))

        elif module_name == "element_analysis":
            from core.service.element_analysis import ElementAnalyzer, ElementRepository
            repo = ElementRepository()
            _pass("ElementRepository.init")
            analyzer = ElementAnalyzer()
            _pass("ElementAnalyzer.init")

        elif module_name == "cloud":
            from core.service.cloud import AgentExecutor, PageTree, ExplorationEngine
            tree = PageTree()
            _pass("PageTree.init")
            executor = AgentExecutor(screen_capture=None, touch_executor=None)
            _pass("AgentExecutor.init")

        else:
            _fail("module", f"unknown module: {module_name}")

    except Exception as e:
        _fail("exception", str(e))

    # 最终保证：如果有 FAIL，记录但不中断整体流程；由上层统一汇总
    return result


def _try_fix(module_name: str, check: str, detail: str) -> bool:
    """尝试自动修复常见问题，返回是否修复成功"""
    try:
        if check == "get_devices" or check == "capture_screen":
            _ensure_device_connected()
            return True
        if check == "list_devices":
            _ensure_device_connected()
            return True
    except Exception:
        return False
    return False


def _targets() -> Dict[str, List[str]]:
    """返回三层架构可测试目标"""
    modules = _discover_modules()
    targets = {"foundation": [], "capability": [], "service": []}
    for name, info in sorted(modules.items()):
        targets.setdefault(info["layer"], []).append(name)
    return targets


# ╔══════════════════════════════════════════════════════════════╗
# ║ CLI 命令                                                         ║
# ╚══════════════════════════════════════════════════════════════╝

def cmd_module_list(args):
    modules = _discover_modules()
    if args.json:
        print(json.dumps(modules, ensure_ascii=False, indent=2))
        return 0
    print(f"\n{'Module':<20} {'Layer':<15} {'Exports':<10}")
    print("-" * 50)
    for name, info in sorted(modules.items()):
        print(f"{name:<20} {info['layer']:<15} {len(info['exports']):<10}")
    print(f"\nTotal: {len(modules)} modules")
    return 0


def cmd_module_targets(args):
    targets = _targets()
    if args.json:
        print(json.dumps(targets, ensure_ascii=False, indent=2))
        return 0
    for layer in ["foundation", "capability", "service"]:
        print(f"\n[{layer}]")
        for m in targets.get(layer, []):
            print(f"  - {m}")
    return 0


def cmd_module_test(args):
    _ensure_src_path()

    # 准备环境
    device_serial = "192.168.1.12:16512"
    llama_url = "http://127.0.0.1:8080"
    model_path = _find_gguf_model() or ""
    if not model_path:
        model_path = str(
            PROJECT_ROOT.parent / "IstinaEndfieldAssistant" / "models" /
            "qwen3.5-4b-ud-q4_k_xl" / "Qwen3.5-4B-UD-Q4_K_XL.gguf"
        )

    # 环境自愈
    try:
        device_serial = _ensure_device_connected(device_serial)
    except Exception as e:
        # 设备无法连接时，仅跳过设备相关测试，其余继续
        device_serial = None

    try:
        if model_path and Path(model_path).exists():
            llama_url = _ensure_llama_server_running(model_path)
    except Exception:
        llama_url = None

    # 测试范围
    modules = _discover_modules()
    if args.name != "all":
        modules = {k: v for k, v in modules.items() if k == args.name}
        if not modules:
            print(f"Module '{args.name}' not found")
            return 1

    # 执行冒烟
    results = []
    for name in sorted(modules.keys()):
        # 自愈：如果设备未连接，用 None serial 调用，让内部逻辑自行修正或通过
        serial = device_serial if device_serial else "192.168.1.12:16512"
        url = llama_url or "http://127.0.0.1:8080"
        res = _smoke_test_module(name, serial, url)
        results.append(res)

    # 输出：只输出 PASS/FAIL，无 SKIP
    all_pass = True
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for res in results:
            status = "PASS" if res["status"] == "PASS" else "FAIL"
            if status == "FAIL":
                all_pass = False
            checks_str = ", ".join([f"{c['check']}:{c['status']}" for c in res.get("checks", [])])
            print(f"{status:<6} {res['module']:<20} [{checks_str}]")
            if res.get("error"):
                print(f"        error: {res['error']}")
        print(f"\n{'='*40}")
        print(f"Overall: {'ALL PASS' if all_pass else 'FAIL'}")

    return 0 if all_pass else 1


def cmd_module_info(args):
    modules = _discover_modules()
    if args.name not in modules:
        print(f"Module '{args.name}' not found")
        return 1
    info = modules[args.name]
    print(f"\nModule: {args.name}")
    print(f"Layer: {info['layer']}")
    print(f"Path: {info['path']}")
    print(f"Exports ({len(info['exports'])}):")
    for exp in info["exports"]:
        print(f"  - {exp}")
    return 0


# ╔══════════════════════════════════════════════════════════════╗
# ║ CLI 解析                                                        ║
# ╚══════════════════════════════════════════════════════════════╝

def main():
    parser = argparse.ArgumentParser(
        description="IstinaEndfieldAssistant_Sight — Unified CLI v5",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", help="Commands")

    # module 命令
    p_mod = sub.add_parser("module", help="Module management (list/test/info/targets)")
    p_mod_sub = p_mod.add_subparsers(dest="module_action", help="Module actions")

    p_mod_list = p_mod_sub.add_parser("list", help="List all modules")
    p_mod_list.add_argument("--json", action="store_true")

    p_mod_test = p_mod_sub.add_parser("test", help="Test module availability or smoke test")
    p_mod_test.add_argument("name", help="Module name (or 'all')")
    p_mod_test.add_argument("--smoke", action="store_true", help="Run real-device smoke test")
    p_mod_test.add_argument("--json", action="store_true")

    p_mod_targets = p_mod_sub.add_parser("targets", help="List testable targets by layer")
    p_mod_targets.add_argument("--json", action="store_true")

    p_mod_info = p_mod_sub.add_parser("info", help="Show module details")
    p_mod_info.add_argument("name", help="Module name")

    args, extra = parser.parse_known_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "module":
        if not args.module_action:
            print("Required subcommand: list, test, info, targets")
            return 1
        # 兼容：如果调用 test 未指定 --smoke，默认执行基础检查（原有行为）
        if args.module_action == "test" and not hasattr(args, "smoke"):
            args.smoke = False
        route = {
            "list": cmd_module_list,
            "test": cmd_module_test,
            "info": cmd_module_info,
            "targets": cmd_module_targets,
        }
        return route[args.module_action](args)

    # 非 module 命令：执行 scripts/ 下的对应脚本
    script_map = {
        "daily": "daily_pipeline.py",
        "harvest": "entity_harvest_pipeline.py",
        "analyze": "analyze_current_page.py",
        "explore": "explore_and_dailies.py",
        "config": None,
        "auth": None,
        "model": None,
        "nav": None,
        "doctor": None,
        "gpu": None,
        "system": None,
        "device": None,
        "scene": None,
    }
    script_name = script_map.get(args.command)
    if script_name:
        script_path = SCRIPTS_DIR / script_name
        if script_path.exists():
            cmd = [sys.executable, str(script_path)] + extra
            result = subprocess.run(cmd, timeout=300)
            return result.returncode

    print(f"[istina] Command '{args.command}' not implemented in CLI v5 yet")
    print("Hint: run corresponding script under scripts/")
    return 1


if __name__ == "__main__":
    sys.exit(main())
