#!/usr/bin/env python3
"""
IstinaEndfieldAssistant — 统一 CLI 入口 v3

薄路由层，将各子命令委托给领域专用的 CLI 模块 (src/cli/)。
同时保持对 scripts/ 下独立脚本的直接调用。

用法:
  python istina.py daily                     # 每日签到+任务分析
  python istina.py harvest                   # 实体图像采集
  python istina.py analyze                   # 分析当前画面
  python istina.py task-analysis             # 任务分析
  python istina.py explore [--depth N]       # UI探索

  # 模块子命令 (委托 src/cli/)
  python istina.py gpu status                # GPU 完整检测
  python istina.py gpu monitor               # 显存实时监控
  python istina.py gpu recommend             # 推荐最佳模型
  python istina.py gpu cuda-check            # CUDA 环境检测

  python istina.py system doctor             # 全面系统诊断
  python istina.py system env                # 环境变量检查
  python istina.py system disk               # 磁盘使用情况
  python istina.py system perf               # 性能测试

  python istina.py device status             # 设备连接状态
  python istina.py device screenshot         # 截图保存
  python istina.py device info               # 设备详细信息
  python istina.py device tap <x> <y>        # 点击坐标
  python istina.py device swipe <x1> <y1> <x2> <y2> [dur]
  python istina.py device keyevent <code>    # 按键事件
  python istina.py device wake [--device D]  # 设备唤醒 (keyevent 26)
  python istina.py device monitor            # 设备实时监控

  python istina.py scene capture [--count N] # 轻量场景采集
  python istina.py scene nav <page>          # 导航到页面
  python istina.py scene analyze             # VLM 分析画面
  python istina.py scene ocr                 # OCR 检测画面
  python istina.py scene explore             # UI 探索

  python istina.py config [key] [value]      # 配置查看/修改
  python istina.py auth <status|login|logout> # 认证管理
  python istina.py model <list|info|download|disk>  # 模型管理
"""

import sys, os, json, argparse, subprocess, time, base64
from pathlib import Path
from typing import Optional, Dict, Any, List

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

SCRIPTS_DIR = PROJECT_ROOT / "scripts"


# ── 工具函数 ──────────────────────────────────────────────────
def run_script(script_name: str, args: List[str] = None,
               capture: bool = True, timeout: int = 300) -> subprocess.CompletedProcess:
    """运行 scripts/ 下的子脚本"""
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        msg = f"脚本未找到: {script_path}"
        print(f"[istina] 错误: {msg}", file=sys.stderr)
        return subprocess.CompletedProcess([], 1, b"", msg.encode())
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    if capture:
        return subprocess.run(cmd, capture_output=True, timeout=timeout)
    return subprocess.run(cmd, timeout=timeout)


def print_json(data: Any):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _delegate_to_cli_module(module_name: str, args_list: List[str]) -> int:
    """委托给 src/cli/ 下的领域模块执行

    Args:
        module_name: 模块名 (如 gpu_cli, device_cli)
        args_list: 命令行参数列表 (不含模块名)
    """
    module_path = SRC_DIR / "cli" / f"{module_name}.py"
    cmd = [sys.executable, str(module_path)] + args_list
    try:
        result = subprocess.run(cmd, timeout=args_list[-1] if any(a.isdigit() and int(a) > 60 for a in args_list) else 300)
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"[istina] 模块 {module_name} 超时")
        return 1


def _import_cli(module_name: str):
    """动态导入 CLI 模块（用于直接调用而非 subprocess）"""
    import importlib
    try:
        mod = importlib.import_module(f"cli.{module_name}")
        return mod
    except ImportError:
        return None


def ensure_session() -> tuple:
    """创建服务器连接，返回 (communicator, session_id)"""
    from core.logger import init_logger
    init_logger()
    from core.communication.communicator import ClientCommunicator
    comm = ClientCommunicator(
        host="127.0.0.1", port=9999,
        password="default_password", timeout=120
    )
    r = comm.send_request("login", {
        "user_id": "cli_user",
        "key": "aa7d3551ab7fdb975c2eed5251df53ade38aa12cd6161475221d774f27026763"
    })
    sid = r.get("session_id", "") if r else ""
    comm.set_logged_in(True)
    return comm, sid


# ── 子命令 ────────────────────────────────────────────────────

def cmd_daily(args):
    """每日签到+任务分析流程"""
    params = []
    if args.model:
        params.extend(["--model", args.model])
    if args.dry_run:
        params.append("--dry-run")
    if args.delay:
        params.extend(["--delay", str(args.delay)])
    if args.timeout:
        params.extend(["--timeout", str(args.timeout)])

    print(f"[istina] 运行每日流水线 (model={args.model or 'exploration_deep'})")
    result = run_script("daily_pipeline.py", params, timeout=args.timeout or 300)
    out = result.stdout.decode("utf-8", errors="replace")
    if out:
        print(out)
    if result.stderr:
        print(result.stderr.decode("utf-8", errors="replace"), file=sys.stderr)
    if result.returncode != 0:
        print(f"[istina] 每日流程异常退出 (code={result.returncode})")
    return result.returncode


def cmd_harvest(args):
    """实体图像采集管线"""
    params = []
    if args.count:
        params.extend(["--count", str(args.count)])
    if args.model:
        params.extend(["--model", args.model])
    if args.interval:
        params.extend(["--interval", str(args.interval)])

    print(f"[istina] 启动实体采集管线 (target={args.count or 200} 张, model={args.model or 'auto'})")
    result = run_script("entity_harvest_pipeline.py", params, capture=False,
                        timeout=args.timeout or 7200)
    return result.returncode if hasattr(result, 'returncode') else 0


def cmd_analyze(args):
    """分析当前画面（VLM）"""
    from core.adb_utils import ADB, vlm_analyze, VLMOptions

    adb = ADB()
    img = adb.screencap(dedup=False)
    if img is None:
        print('{"error":"截图失败"}')
        return 1

    instruction = args.instruction or "识别当前游戏画面中的所有UI元素。JSON输出"
    opts = VLMOptions(
        model_tag=args.model or "exploration_deep",
        timeout=args.timeout or 120,
        system_prompt=args.system_prompt or "你是终末地UI分析器。逐一列出每个按钮。",
    )

    resp = vlm_analyze(img, instruction=instruction, opts=opts)
    if resp:
        reply = resp.get("reply", "")
        print(reply)
    else:
        print('{"error":"VLM 无响应"}')
        return 1
    return 0


def cmd_task_analysis(args):
    """任务分析（复用 analyze_tasks.py）"""
    params = []
    if args.model:
        params.extend(["--model", args.model])

    print(f"[istina] 运行任务分析")
    result = run_script("analyze_tasks.py", params, timeout=args.timeout or 300)
    out = result.stdout.decode("utf-8", errors="replace")
    if out:
        print(out)
    return result.returncode


def cmd_explore(args):
    """UI 探索"""
    params = []
    if args.depth:
        params.extend(["--depth", str(args.depth)])
    if args.model:
        params.extend(["--model", args.model])

    print(f"[istina] 启动 UI 探索 (depth={args.depth or 3})")
    result = run_script("explore_game.py", params, capture=False,
                        timeout=args.timeout or 1800)
    return 0


def cmd_scene(args):
    """场景探索采集（轻量采集，不启动完整管线）"""
    from core.adb_utils import ADB, vlm_analyze, VLMOptions
    from core.game_coords import Coords
    import hashlib

    adb = ADB()
    count = args.count or 10
    model_tag = args.model or "exploration_deep"
    session_dir = str(PROJECT_ROOT / "cache" / f"scene_{int(time.time())}")
    os.makedirs(session_dir, exist_ok=True)

    print(f"[istina] 场景采集启动 → {session_dir}")
    print(f"[istina] 目标: {count} 张, 模型: {model_tag}")

    last_hash = None
    for i in range(count):
        # 截图
        img = adb.screencap()
        if img is None:
            print(f"  [{i+1}/{count}] 画面无变化，跳过")
            adb.wait(2)
            continue

        h = hashlib.md5(img).hexdigest()[:8]
        path = os.path.join(session_dir, f"scene_{i:03d}_{h}.png")
        with open(path, "wb") as f:
            f.write(img)
        print(f"  [{i+1}/{count}] 截图已保存 ({len(img)//1024}KB) hash={h}")

        # 随机探索动作
        import random
        action = random.choice(["tap", "swipe_left", "swipe_right", "wait"])
        if action == "tap":
            x = random.randint(100, 1100)
            y = random.randint(100, 600)
            adb.tap(x, y)
            print(f"    → tap ({x}, {y})")
        elif action == "swipe_left":
            adb.swipe(900, 360, 300, 360, 600)
            print(f"    → swipe left")
        elif action == "swipe_right":
            adb.swipe(300, 360, 900, 360, 600)
            print(f"    → swipe right")
        else:
            adb.wait(random.uniform(1, 3))
            print(f"    → wait")

        adb.wait(2)

    print(f"[istina] 场景采集完成，共 {count} 张截图")
    return 0


def cmd_nav(args):
    """导航到指定页面"""
    from core.adb_utils import ADB
    from core.game_coords import Coords, NAVIGATION_MAP, PAGE_TYPE_KEYWORDS

    adb = ADB()
    target = args.target

    nav_info = NAVIGATION_MAP.get(target)
    if nav_info:
        action = nav_info.get("action")
        if action == "click":
            coords = nav_info.get("coords", Coords.title_click)
            print(f"[istina] 导航: {nav_info['desc']} → 点击 {coords}")
            adb.tap(*coords)
        elif action == "wait":
            dur = nav_info.get("duration", 5)
            print(f"[istina] 导航: {nav_info['desc']} → 等待 {dur}s")
            adb.wait(dur)
        elif action == "claim":
            for cx, cy in nav_info.get("claim_coords", []):
                print(f"  尝试点击 ({cx}, {cy})")
                adb.tap(cx, cy)
                adb.wait(1)
        return 0

    # 关键词匹配
    matched = False
    for page_type, keywords in PAGE_TYPE_KEYWORDS.items():
        if any(kw in target for kw in keywords):
            print(f"[istina] 页面类型 '{target}' → 匹配 '{page_type}'")
            matched = True
            break
    if not matched:
        print(f"[istina] 未知导航目标: {target}")
        print(f"  可用目标: {list(NAVIGATION_MAP.keys())}")

    # 回退：执行探索脚本的导航功能
    print(f"[istina] 回退到探索引擎导航")
    result = run_script("navigate_to_game.py", capture=False, timeout=60)
    return 0


def cmd_config(args):
    """配置查看/修改"""
    config_path = PROJECT_ROOT / "config" / "client_config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if args.key:
        keys = args.key.split(".")
        val = config
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k, "<not found>")
            else:
                val = "<not found>"
                break
        if args.value is not None:
            parent = config
            for k in keys[:-1]:
                parent = parent.get(k, {})
            parent[keys[-1]] = args.value
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"已设置 {args.key} = {args.value}")
        else:
            print(f"{args.key} = {val}")
    else:
        print_json(config)
    return 0


def cmd_auth(args):
    """认证管理"""
    from core.cloud.managers.auth_manager import AuthManager
    auth = AuthManager()

    if args.action == "status":
        info = auth.get_auth_info()
        print_json(info)
    elif args.action == "login":
        if args.token:
            result = auth.login_with_token(args.token)
        else:
            result = auth.login()
        print_json(result if result else {"error": "登录失败"})
    elif args.action == "logout":
        auth.logout()
        print('{"status":"logged_out"}')
    return 0


def cmd_model(args):
    """模型管理"""
    from core.local_inference.model_manager import ModelManager

    manager = ModelManager(
        models_dir=str(PROJECT_ROOT / "models")
    )

    if args.action == "list":
        models = manager.get_all_models()
        data = []
        for m in models:
            data.append({
                "name": m.name,
                "description": m.description,
                "size_gb": m.size_gb,
                "downloaded": m.is_downloaded,
                "parameters": m.parameters,
                "quantization": m.quantization,
            })
        print_json(data)

    elif args.action == "info":
        if not args.model_name:
            print('{"error":"需要模型名称"}')
            return 1
        info = manager.get_model_info(args.model_name)
        if info:
            print_json({
                "name": info.name,
                "description": info.description,
                "size_gb": info.size_gb,
                "parameters": info.parameters,
                "quantization": info.quantization,
                "downloaded": info.is_downloaded,
                "local_path": str(info.local_path) if info.local_path else None,
                "recommended_gpu_memory_gb": info.recommended_gpu_memory_gb,
            })
        else:
            print(f'{{"error":"未找到模型: {args.model_name}"}}')
            return 1

    elif args.action == "download":
        if not args.model_name:
            print('{"error":"需要模型名称"}')
            return 1
        print(f"[istina] 下载模型: {args.model_name}")
        path = manager.download_model(args.model_name)
        if path:
            print(f"  完成: {path}")
        else:
            print(f"  失败")
            return 1

    elif args.action == "disk":
        usage = manager.get_disk_usage()
        print_json(usage)

    return 0


def cmd_device(args):
    """设备管理"""
    from core.adb_utils import ADB

    adb = ADB()

    if args.action == "status":
        ok = adb.check_connection()
        print(f'{{"connected": {json.dumps(ok)}, "serial": "{adb.serial}"}}')

    elif args.action == "screenshot":
        path = adb.screenshot_path(str(PROJECT_ROOT / "cache"), tag="cli")
        if path:
            print(f'{{"path": "{path}", "size_bytes": {os.path.getsize(path)}}}')
        else:
            print('{"error":"截图失败"}')
            return 1

    elif args.action == "info":
        from core.adb_utils import list_devices, _adb_cmd
        devices = list_devices()
        try:
            r = _adb_cmd(["shell", "wm", "size"], timeout=5)
            resolution = r.stdout.decode().strip()
        except:
            resolution = "unknown"
        print_json({
            "devices": devices,
            "current_serial": adb.serial,
            "resolution": resolution,
            "adb_path": str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"),
        })

    return 0


def cmd_doctor(args):
    """全面诊断"""
    from core.adb_utils import ADB, list_devices, check_device

    print("=" * 50)
    print("IstinaEndfieldAssistant - 系统诊断")
    print("=" * 50)

    # ADB
    ADB_PATH = str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe")
    print(f"\n[ADB] Path: {ADB_PATH}")
    print(f"  Exists: {os.path.exists(ADB_PATH)}")
    ok = check_device()
    print(f"  Device connected: {ok}")
    if ok:
        devices = list_devices()
        print(f"  Devices: {devices}")

    # Server
    print(f"\n[Server] 127.0.0.1:9999")
    try:
        from core.logger import init_logger
        init_logger()
        from core.communication.communicator import ClientCommunicator
        comm = ClientCommunicator(
            host="127.0.0.1", port=9999,
            password="default_password", timeout=10
        )
        r = comm.send_request("ping", {})
        print(f"  Status: {'OK' if r else 'No response'}")
    except Exception as e:
        print(f"  Error: {e}")

    # Config
    config_path = PROJECT_ROOT / "config" / "client_config.json"
    print(f"\n[Config] {config_path}")
    print(f"  Exists: {config_path.exists()}")
    if config_path.exists():
        with open(config_path) as f:
            cfg = json.load(f)
        print(f"  Server: {cfg.get('server')}")
        print(f"  Inference mode: {cfg.get('inference', {}).get('mode')}")

    # Models
    from core.local_inference.model_manager import ModelManager
    manager = ModelManager(models_dir=str(PROJECT_ROOT / "models"))
    usage = manager.get_disk_usage()
    print(f"\n[Models]")
    print(f"  Disk usage: {usage.get('total_size_gb', 0):.1f}GB")
    for name, size in usage.get("models", {}).items():
        print(f"    {name}: {size:.1f}GB")

    # Coords module
    try:
        from core.game_coords import Coords
        print(f"\n[Coords] 模块已加载，{len([k for k in dir(Coords) if not k.startswith('_')])} 个坐标")
    except Exception as e:
        print(f"\n[Coords] 加载失败: {e}")

    # ADB Utils module
    try:
        from core.adb_utils import ADB
        print(f"[ADB Utils] 模块已加载")
    except Exception as e:
        print(f"[ADB Utils] 加载失败: {e}")

    # Python
    print(f"\n[Python] {sys.version}")
    return 0


# ── 领域模块委托 ─────────────────────────────────────────────
def _delegate_with_extra(module_name: str, extra_args: List[str]) -> int:
    """委托给领域模块，透传额外参数"""
    if not extra_args:
        print(f"[istina] {module_name}: 需要子命令 (如 status)")
        return 1
    mod = _import_cli(module_name)
    if mod and hasattr(mod, "main"):
        # 直接调用（进程内）
        import importlib
        importlib.reload(mod)
        sys.argv = ["", *extra_args]
        try:
            return mod.main()
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else 0
    # 子进程回退
    return _delegate_to_cli_module(module_name, extra_args)


def cmd_gpu(args, extra):
    """GPU 检测 → 委托 cli.gpu_cli"""
    return _delegate_with_extra("gpu_cli", extra)


def cmd_system(args, extra):
    """系统诊断 → 委托 cli.system_cli"""
    return _delegate_with_extra("system_cli", extra)


def cmd_device(args, extra):
    """设备管理 → 委托 cli.device_cli"""
    return _delegate_with_extra("device_cli", extra)


def cmd_scene(args, extra):
    """场景采集 → 委托 cli.scenario_cli"""
    return _delegate_with_extra("scenario_cli", extra)


# ── CLI 解析 ──────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="IstinaEndfieldAssistant — 统一 CLI v3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # ── 业务命令 (直接处理) ──
    p_daily = sub.add_parser("daily", help="每日签到+任务分析")
    p_daily.add_argument("--model", help="模型标签")
    p_daily.add_argument("--dry-run", action="store_true", help="仅分析不点击")
    p_daily.add_argument("--delay", type=float, help="点击后等待秒数")
    p_daily.add_argument("--timeout", type=int, default=300, help="超时秒数 (默认 300)")

    p_harvest = sub.add_parser("harvest", help="实体图像采集管线")
    p_harvest.add_argument("--count", type=int, default=200, help="目标截图数")
    p_harvest.add_argument("--model", help="模型标签")
    p_harvest.add_argument("--interval", type=float, help="动作间隔秒数")
    p_harvest.add_argument("--timeout", type=int, default=7200, help="超时秒数 (默认 7200)")

    p_ana = sub.add_parser("analyze", help="VLM 分析当前画面")
    p_ana.add_argument("--model", help="模型标签")
    p_ana.add_argument("--instruction", "-i", default="", help="自定义指令")
    p_ana.add_argument("--system-prompt", help="系统提示词")
    p_ana.add_argument("--timeout", type=int, default=120)

    p_ta = sub.add_parser("task-analysis", help="任务分析")
    p_ta.add_argument("--model", help="模型标签")
    p_ta.add_argument("--timeout", type=int, default=300)

    p_exp = sub.add_parser("explore", help="UI 探索")
    p_exp.add_argument("--depth", type=int, default=3, help="探索深度")
    p_exp.add_argument("--model", help="模型标签")
    p_exp.add_argument("--timeout", type=int, default=1800)

    p_cfg = sub.add_parser("config", help="配置查看/修改")
    p_cfg.add_argument("key", nargs="?", help="配置键 (点号分隔)")
    p_cfg.add_argument("value", nargs="?", help="新值 (不提供则查看)")

    p_auth = sub.add_parser("auth", help="认证管理")
    p_auth.add_argument("action", choices=["status", "login", "logout"], help="操作")
    p_auth.add_argument("--token", help="登录令牌")

    p_mdl = sub.add_parser("model", help="模型管理")
    p_mdl.add_argument("action", choices=["list", "info", "download", "disk"], help="操作")
    p_mdl.add_argument("model_name", nargs="?", help="模型名称")

    # nav (保留直接处理)
    p_nav = sub.add_parser("nav", help="导航到页面")
    p_nav.add_argument("target", help="目标页面名")

    # ── 领域模块命令 (委托 src/cli/) ──
    # GPU (python istina.py gpu status|monitor|recommend|cuda-check)
    sub.add_parser("gpu", help="GPU 检测 (子命令: status/monitor/recommend/cuda-check)")

    # System (python istina.py system doctor|env|disk|perf)
    sub.add_parser("system", help="系统诊断 (子命令: doctor/env/disk/perf)")

    # Device (python istina.py device status|screenshot|info|tap|swipe|keyevent|monitor)
    sub.add_parser("device", help="设备管理 (子命令: status/screenshot/info/tap/swipe/keyevent/monitor)")

    # Scene (python istina.py scene capture|nav|analyze|ocr|explore)
    sub.add_parser("scene", help="场景采集 (子命令: capture/nav/analyze/ocr/explore)")

    args, extra = parser.parse_known_args()

    if not args.command:
        parser.print_help()
        return 1

    # ── 命令路由 ──
    # 直接处理的命令
    direct_commands = {
        "daily": cmd_daily,
        "harvest": cmd_harvest,
        "analyze": cmd_analyze,
        "task-analysis": cmd_task_analysis,
        "explore": cmd_explore,
        "config": cmd_config,
        "auth": cmd_auth,
        "model": cmd_model,
        "nav": cmd_nav,
        "doctor": cmd_doctor,
    }

    # 委托给领域模块的命令
    delegated_commands = {
        "gpu": cmd_gpu,
        "system": cmd_system,
        "device": cmd_device,
        "scene": cmd_scene,
    }

    target = args.command
    if target in direct_commands:
        return direct_commands[target](args)
    elif target in delegated_commands:
        return delegated_commands[target](args, extra)
    else:
        print(f"[istina] 未知命令: {target}")
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
