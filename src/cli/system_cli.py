"""
System CLI 模块 — 系统诊断、环境检查、性能测试

用法（通过 istina.py）:
  istina.py system doctor        # 全面系统诊断
  istina.py system env           # 环境变量检查
  istina.py system disk          # 磁盘使用情况
  istina.py system perf          # 性能测试

独立运行:
  python -m src.cli.system_cli doctor
"""

import sys, os, json, time, platform, subprocess, argparse
from typing import Dict, Any, Optional
from pathlib import Path
from utils.paths import ensure_src_path, get_project_root

ensure_src_path(__file__)
PROJECT_ROOT = get_project_root(__file__)


def _check_adb():
    """ADB 检测"""
    adb_path = os.path.join(PROJECT_ROOT, "3rd-party", "adb", "adb.exe")
    info = {"path": adb_path, "exists": os.path.exists(adb_path), "devices": []}
    if info["exists"]:
        try:
            r = subprocess.run([adb_path, "devices"], capture_output=True, text=True, timeout=10)
            lines = r.stdout.strip().split("\n")[1:]
            info["devices"] = [
                l.split("\t")[0] for l in lines
                if l.strip() and "device" in l
            ]
        except Exception as e:
            info["error"] = str(e)
    return info


def _check_server():
    """本地推理状态检测"""
    try:
        from core.local_inference.inference_manager import InferenceManager
        from core.logger import init_logger
        init_logger()
        
        # 检查本地推理是否可用
        return {"alive": True, "mode": "local", "note": "纯本地推理模式"}
    except Exception as e:
        return {"alive": False, "error": str(e)}


def _check_gpu():
    """GPU 概要检测"""
    try:
        from core.local_inference.gpu_checker import check_gpu
        result = check_gpu()
        return {
            "available": result.get("available", False),
            "cuda": result.get("cuda_available", False),
            "gpu_count": result.get("gpu_count", 0),
            "meets_requirements": result.get("meets_requirements", False),
        }
    except Exception as e:
        return {"error": str(e)}


def _check_models():
    """模型概要检测"""
    try:
        from core.local_inference.model_manager import ModelManager
        mm = ModelManager(models_dir=os.path.join(PROJECT_ROOT, "models"))
        usage = mm.get_disk_usage()
        return {
            "total_size_gb": usage.get("total_size_gb", 0),
            "model_count": usage.get("model_count", 0),
            "models": usage.get("models", {}),
        }
    except Exception as e:
        return {"error": str(e)}


def cmd_doctor(args) -> int:
    """全面系统诊断"""
    print("=" * 55)
    print("IEA 本地版系统全面诊断")
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"时间：{ts}")
    print("=" * 55)

    # 1. 系统信息
    print(f"\n[系统]")
    print(f"  OS: {platform.system()} {platform.release()}")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  项目路径：{PROJECT_ROOT}")

    # 2. ADB
    print(f"\n[ADB]")
    adb = _check_adb()
    print(f"  ADB: {'存在' if adb.get('exists') else '不存在'}")
    print(f"  设备：{adb.get('devices', [])}")

    # 3. 推理模式
    print(f"\n[推理模式]")
    srv = _check_server()
    if srv.get("alive"):
        print(f"  模式：{srv.get('mode', 'local')}")
        print(f"  说明：{srv.get('note', 'N/A')}")
    else:
        print(f"  状态：错误 ({srv.get('error', '')})")

    # 4. GPU
    print(f"\n[GPU]")
    gpu = _check_gpu()
    if "error" in gpu:
        print(f"  {gpu['error']}")
    else:
        print(f"  CUDA: {'可用' if gpu.get('cuda') else '不可用'}")
        print(f"  GPU 数：{gpu.get('gpu_count', 0)}")
        print(f"  满足推理：{gpu.get('meets_requirements', False)}")

    # 5. 模型
    print(f"\n[模型]")
    models = _check_models()
    if "error" in models:
        print(f"  {models['error']}")
    else:
        print(f"  总大小：{models.get('total_size_gb', 0):.1f} GB")
        print(f"  已下载：{models.get('model_count', 0)} 个")
        for name, size in models.get("models", {}).items():
            print(f"    {name}: {size:.1f}GB")

    # 6. 配置
    print(f"\n[配置]")
    cfg_path = os.path.join(PROJECT_ROOT, "config", "client_config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            cfg = json.load(f)
        print(f"  推理模式：{cfg.get('inference', {}).get('mode', 'local')}")
        print(f"  本地模型：{cfg.get('inference', {}).get('model_name', 'N/A')}")
    else:
        print(f"  未找到配置文件")

    # 7. 新模块
    print(f"\n[模块]")
    for mod_name in ["core.game_coords", "core.adb_utils", "cli.gpu_cli", "cli.system_cli"]:
        try:
            __import__(mod_name)
            print(f"  {mod_name}: OK")
        except Exception as e:
            print(f"  {mod_name}: FAIL ({e})")

    return 0


def cmd_env(args) -> int:
    """环境变量检查"""
    keys = [
        "CUDA_PATH", "CUDA_HOME", "PATH",
        "PYTHONPATH", "CONDA_PREFIX",
        "HUGGINGFACE_HUB_CACHE", "HF_HOME",
    ]
    print("=" * 55)
    print("环境变量检查")
    print("=" * 55)
    for k in keys:
        v = os.environ.get(k, "")
        if v:
            print(f"  {k} = {v[:120]}")
        else:
            print(f"  {k} = [未设置]")
    return 0


def cmd_disk(args) -> int:
    """磁盘使用情况"""
    print("=" * 55)
    print("磁盘使用情况")
    print("=" * 55)

    import shutil

    # 项目目录
    total, used, free = shutil.disk_usage(PROJECT_ROOT)
    print(f"\n项目磁盘：{PROJECT_ROOT}")
    print(f"  总空间：{total // (2**30)} GB")
    print(f"  已用：   {used // (2**30)} GB")
    print(f"  可用：   {free // (2**30)} GB")

    # 模型目录
    models_dir = os.path.join(PROJECT_ROOT, "models")
    if os.path.exists(models_dir):
        from core.local_inference.model_manager import ModelManager
        mm = ModelManager(models_dir=models_dir)
        usage = mm.get_disk_usage()
        print(f"\n模型存储:")
        print(f"  总大小：{usage.get('total_size_gb', 0):.2f} GB")
        for name, size in usage.get("models", {}).items():
            print(f"    {name}: {size:.2f} GB")

    # 缓存目录
    cache_dir = os.path.join(PROJECT_ROOT, "cache")
    if os.path.exists(cache_dir):
        cache_size = sum(f.stat().st_size for f in Path(cache_dir).rglob("*") if f.is_file())
        print(f"\n缓存：{cache_dir}")
        print(f"  大小：{cache_size / (1024**3):.2f} GB")

    # 日志目录
    logs_dir = os.path.join(PROJECT_ROOT, "logs")
    if os.path.exists(logs_dir):
        log_size = sum(f.stat().st_size for f in Path(logs_dir).rglob("*") if f.is_file())
        print(f"\n日志：{logs_dir}")
        print(f"  大小：{log_size / (1024**2):.2f} MB")

    return 0


def cmd_perf(args) -> int:
    """简单性能测试"""
    print("=" * 55)
    print("性能测试")
    print("=" * 55)

    # 1. 截图速度
    print(f"\n[1] 截图速度:")
    try:
        from core.adb_utils import ADB
        adb = ADB()
        t0 = time.time()
        img = adb.screencap(dedup=False)
        t1 = time.time()
        if img:
            print(f"  耗时：{(t1-t0)*1000:.0f}ms")
            print(f"  大小：{len(img)//1024}KB")
        else:
            print(f"  失败")
    except Exception as e:
        print(f"  错误：{e}")

    # 2. ADB 响应延迟
    print(f"\n[2] ADB 延迟:")
    try:
        import subprocess
        adb_path = os.path.join(PROJECT_ROOT, "3rd-party", "adb", "adb.exe")
        t0 = time.time()
        for _ in range(5):
            subprocess.run([adb_path, "-s", "localhost:16512", "shell", "echo", "ping"],
                          capture_output=True, timeout=5)
        t1 = time.time()
        print(f"  平均：{(t1-t0)/5*1000:.0f}ms/次")
    except Exception as e:
        print(f"  错误：{e}")

    # 3. Python 基础性能
    print(f"\n[3] Python 运算:")
    t0 = time.time()
    count = 0
    for i in range(5_000_000):
        count += i * i
    t1 = time.time()
    print(f"  5M 次循环：{(t1-t0)*1000:.0f}ms")

    return 0


# ── 独立入口 ─────────────────────────────────────────────────
def main(args_list: list = None):
    parser = argparse.ArgumentParser(description="System CLI 模块")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("doctor", help="全面系统诊断")
    sub.add_parser("env", help="环境变量检查")
    sub.add_parser("disk", help="磁盘使用情况")
    sub.add_parser("perf", help="性能测试")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    cmds = {
        "doctor": cmd_doctor,
        "env": cmd_env,
        "disk": cmd_disk,
        "perf": cmd_perf,
    }
    return cmds[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
