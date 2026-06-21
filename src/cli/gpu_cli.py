"""
GPU CLI 模块 — GPU 检测、CUDA 诊断、显存监控、推荐模型

用法（通过 istina.py）:
  istina.py gpu status          # GPU 完整检测
  istina.py gpu monitor         # 显存实时监控
  istina.py gpu recommend       # 推荐最佳模型
  istina.py gpu cuda-check      # CUDA 环境检测

独立运行:
  python -m src.cli.gpu_cli status
  python -m src.cli.gpu_cli monitor --interval 2
"""

import sys, os, json, time, argparse
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from utils.paths import ensure_src_path, get_project_root

# ── 项目路径 ──────────────────────────────────────────────────
ensure_src_path(__file__)
PROJECT_ROOT = get_project_root(__file__)


# ── 依赖的本地模块 ──────────────────────────────────────────
def _get_gpu_checker():
    from core.local_inference.gpu_checker import GPUChecker, check_gpu
    return GPUChecker(), check_gpu


def _get_model_manager():
    from core.local_inference.model_manager import ModelManager
    return ModelManager(models_dir=os.path.join(PROJECT_ROOT, "models"))


# ── CLI 处理函数 ─────────────────────────────────────────────

def cmd_status(args) -> int:
    """完整 GPU 检测"""
    checker, check_fn = _get_gpu_checker()
    model_mgr = _get_model_manager()

    result = check_fn()

    print("=" * 55)
    print("GPU 检测报告")
    print("=" * 55)

    print(f"\nCUDA 可用:    {result.get('cuda_available', False)}")
    print(f"CUDA 版本:    {result.get('cuda_version', 'N/A')}")
    print(f"驱动版本:     {result.get('driver_version', 'N/A')}")
    print(f"GPU 数量:     {result.get('gpu_count', 0)}")
    print(f"满足推理要求: {result.get('meets_requirements', False)}")
    print(f"推荐模型:     {result.get('recommended_model', 'N/A')}")

    gpus = result.get('gpus', [])
    if gpus:
        print(f"\nGPU 详情 ({len(gpus)} 张):")
        for i, gpu in enumerate(gpus):
            print(f"  [{i}] {gpu.get('name', 'Unknown')}")
            print(f"      总显存: {gpu.get('total_memory_gb', 0):.2f} GB")
            print(f"      可用显存: {gpu.get('free_memory_gb', 0):.2f} GB")
            print(f"      计算能力: {gpu.get('compute_capability', 'N/A')}")

    # 下载模型推荐匹配
    if result.get('recommended_model'):
        info = model_mgr.get_model_info(result['recommended_model'])
        if info:
            status = "已下载" if info.is_downloaded else "未下载"
            print(f"\n  推荐模型: {info.name} ({info.parameters}, {info.quantization}) [{status}]")

    if result.get('error'):
        print(f"\n检测错误: {result['error']}")

    # JSON 输出
    if args.json:
        print(f"\n--- JSON ---")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


def cmd_monitor(args) -> int:
    """显存实时监控"""
    interval = args.interval or 2

    print("GPU 显存监控 (Ctrl+C 退出)")
    print(f"{'时间':<20} {'GPU':<30} {'总显存(GB)':<15} {'已用(GB)':<15} {'可用(GB)':<15} {'利用率':<10}")
    print("-" * 105)

    try:
        while True:
            ts = time.strftime("%H:%M:%S")
            checker, _ = _get_gpu_checker()
            result = checker.check_gpu_availability()
            gpus = result.get('gpus', [])

            if not gpus:
                print(f"{ts:<20} {'[无 GPU]'}")
            else:
                for gpu in gpus:
                    total = gpu.get('total_memory_gb', 0)
                    free = gpu.get('free_memory_gb', 0)
                    used = total - free
                    pct = (used / total * 100) if total > 0 else 0
                    name_short = gpu.get('name', 'Unknown')[:28]
                    print(f"{ts:<20} {name_short:<30} {total:<15.2f} {used:<15.2f} {free:<15.2f} {pct:<10.1f}%")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n监控已停止")
    return 0


def cmd_recommend(args) -> int:
    """推荐最佳模型"""
    checker, _ = _get_gpu_checker()
    model_mgr = _get_model_manager()

    result = checker.check_gpu_availability()
    recommended = result.get('recommended_model')
    gpu_count = result.get('gpu_count', 0)
    vram = 0
    for gpu in result.get('gpus', []):
        vram = max(vram, gpu.get('total_memory_gb', 0))

    print("=" * 55)
    print("模型推荐")
    print("=" * 55)
    print(f"检测到 {gpu_count} 张 GPU, 最大显存 {vram:.1f}GB")

    # 列出所有匹配的模型
    print(f"\n可用模型 (从高到低):")
    models = model_mgr.get_all_models()
    for m in sorted(models, key=lambda x: x.recommended_gpu_memory_gb, reverse=True):
        enough = vram >= m.recommended_gpu_memory_gb
        marker = ">>" if m.name == recommended else "  "
        status = "已下载" if m.is_downloaded else "未下载"
        mem_text = f"需要 {m.recommended_gpu_memory_gb}GB 显存"
        print(f"  {marker} {m.name:<35} {m.parameters:<6} {m.quantization:<6} {mem_text:<20} [{status}] {'★' if enough and m.name == recommended else ''}")

    return 0


def cmd_cuda_check(args) -> int:
    """CUDA 环境专项检测"""
    print("=" * 55)
    print("CUDA 环境检测")
    print("=" * 55)

    # 1. nvidia-smi
    print("\n[1] nvidia-smi:")
    try:
        import subprocess
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version",
                           "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            for line in r.stdout.strip().split("\n"):
                print(f"  {line}")
        else:
            print("  [未找到]")
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug(f"nvidia-smi 执行失败：{e}")
        print("  [不可用]")

    # 2. CUDA_PATH
    print("\n[2] CUDA_PATH 环境变量:")
    cuda_path = os.environ.get("CUDA_PATH", "")
    if cuda_path:
        print(f"  {cuda_path}")
    else:
        print("  [未设置]")

    # 3. PyTorch CUDA
    print("\n[3] PyTorch CUDA:")
    try:
        import torch
        print(f"  torch.__version__: {torch.__version__}")
        print(f"  torch.cuda.is_available(): {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"  torch.cuda.device_count(): {torch.cuda.device_count()}")
            print(f"  torch.version.cuda: {torch.version.cuda}")
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                total_gb = props.total_memory / (1024**3)
                print(f"  [{i}] {props.name} ({total_gb:.1f}GB)")
    except ImportError:
        print("  [PyTorch 未安装]")
    except Exception as e:
        print(f"  [错误: {e}]")

    # 4. llama-cpp-python
    print("\n[4] llama-cpp-python (GPU 支持):")
    try:
        import llama_cpp
        print(f"  llama_cpp available (version: {getattr(llama_cpp, '__version__', 'unknown')})")
        # Check if compiled with CUDA
        try:
            from llama_cpp import Llama
            print(f"  Supports GPU: {hasattr(Llama, 'n_gpu_layers')}")
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"llama_cpp Llama 检查失败：{e}")
            pass
    except ImportError:
        print("  [llama-cpp-python 未安装]")

    # 5. 总体判断
    print("\n[5] 总体判断:")
    from core.local_inference.gpu_checker import is_gpu_sufficient, check_gpu
    result = check_gpu()
    if result.get("cuda_available"):
        print("  CUDA 可用 -> 支持 GPU 推理")
    else:
        print("  CUDA 不可用 -> 仅支持 CPU 推理 (速度较慢)")

    if is_gpu_sufficient():
        print("  硬件满足本地推理最低要求")
    else:
        print("  硬件不满足本地推理最低要求")

    return 0


# ── 独立入口 ─────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="GPU CLI 模块")
    sub = parser.add_subparsers(dest="command")

    p_status = sub.add_parser("status", help="GPU 完整检测")
    p_status.add_argument("--json", action="store_true", help="JSON 格式输出")

    p_mon = sub.add_parser("monitor", help="显存实时监控")
    p_mon.add_argument("--interval", "-i", type=float, default=2, help="刷新间隔(秒)")

    sub.add_parser("recommend", help="推荐最佳模型")

    p_cuda = sub.add_parser("cuda-check", help="CUDA 环境检测")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    cmds = {
        "status": cmd_status,
        "monitor": cmd_monitor,
        "recommend": cmd_recommend,
        "cuda-check": cmd_cuda_check,
    }
    return cmds[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
