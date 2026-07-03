"""LLM 推理性能测试：全量参数扫描，寻找 >100 TPS 的最终可能"""
from __future__ import annotations

import json
import subprocess
import time
import urllib.request
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

MODEL_PATH = r"models\LLM\Qwen3.5-4B-UD-Q4_K_XL.gguf"
EXE_PATH = Path(__file__).resolve().parent.parent / "3rd-part" / "llama-cpp" / "llama-server.exe"


def read_nvidia_smi() -> str:
    try:
        out = subprocess.check_output(["nvidia-smi", "--query-gpu=index,name,memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"], stderr=subprocess.STDOUT, text=True, shell=True)
        return out.strip()
    except Exception as exc:
        return f"nvidia-smi failed: {exc}"


def build_args(port: int, *, context_size: int = 32768, batch_size: int = 2048, ubatch_size: int = 512, threads: int = 8, flash_attn: str = "auto", reasoning: str = "off", no_kv_offload: bool = False, no_repack: bool = False, no_cont_batching: bool = False, cache_prompt: bool = True, parallel: int = -1, warmup: bool = True, ctx_checkpoints: int = 0, checkpoint_min_step: int = 0, swa_full: bool = False, no_kv_unified: bool = False, disable_kv_offload: bool = False) -> List[str]:
    args = [
        str(EXE_PATH),
        "-m",
        str(Path(MODEL_PATH).resolve()),
        "--port",
        str(port),
        "-c",
        str(context_size),
        "-b",
        str(batch_size),
        "-ub",
        str(ubatch_size),
        "--threads",
        str(threads),
        "--temp",
        "0.3",
        "-ngl",
        "999",
        "--n-gpu-layers",
        "999",
        "-fa",
        flash_attn,
        "-ctk",
        "q8_0",
        "-ctv",
        "q8_0",
        "-cram",
        "0",
        "-rea",
        reasoning,
    ]
    if no_kv_offload or disable_kv_offload:
        args.append("--no-kv-offload")
    if no_repack:
        args.append("--no-repack")
    if no_cont_batching:
        args.append("--no-cont-batching")
    if not cache_prompt:
        args.append("--no-cache-prompt")
    if parallel > 0:
        args.extend(["-np", str(parallel)])
    if not warmup:
        args.append("--no-warmup")
    if ctx_checkpoints > 0:
        args.extend(["-ctxcp", str(ctx_checkpoints)])
    if checkpoint_min_step > 0:
        args.extend(["-cms", str(checkpoint_min_step)])
    if swa_full:
        args.append("--swa-full")
    if no_kv_unified:
        args.append("--no-kv-unified")
    return args


def measure_completion(port: int, *, context_size: int = 64000, prompt: str = "Hello", max_tokens: int = 64, **kwargs: Any) -> float:
    args = build_args(port, context_size=context_size, **kwargs)
    print("启动:", " ".join(args))
    proc = subprocess.Popen(
        args,
        cwd=str(Path(__file__).resolve().parent.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        for _ in range(240):
            if proc.poll() is not None:
                out = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
                print("STARTERR:", out[:4000])
                return 0.0
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/models", method="GET")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                pass
            time.sleep(1)
        else:
            print("健康检查超时")
            return 0.0

        print("nvidia-smi:", read_nvidia_smi())
        payload = {
            "model": "local",
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                choices = data.get("choices") or []
                if not choices:
                    print("COMPLETION_ERR: 空结果", data)
                    return 0.0
                text = choices[0].get("text") or ""
                usage = data.get("usage") or {}
                completion_tokens = int(usage.get("completion_tokens") or max_tokens)
        except Exception as exc:
            print("COMPLETION_ERR:", exc)
            return 0.0
        t1 = time.time()
        print("nvidia-smi:", read_nvidia_smi())
        print("completion:", text[:200])
        return completion_tokens / max(t1 - t0, 1e-6)
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def main() -> int:
    print("启动前 nvidia-smi:", read_nvidia_smi())
    candidates = [
        {"context_size": 32768, "batch_size": 2048, "ubatch_size": 1024, "threads": 24, "flash_attn": "on", "reasoning": "off", "no_kv_offload": True, "no_repack": True, "no_cont_batching": True, "cache_prompt": False, "parallel": 1, "warmup": False, "ctx_checkpoints": 0, "checkpoint_min_step": 0, "swa_full": False, "no_kv_unified": True},
        {"context_size": 32768, "batch_size": 2048, "ubatch_size": 1024, "threads": 24, "flash_attn": "on", "reasoning": "off", "no_kv_offload": True, "no_repack": True, "no_cont_batching": True, "cache_prompt": False, "parallel": 1, "warmup": False, "ctx_checkpoints": 0, "checkpoint_min_step": 0, "swa_full": True, "no_kv_unified": True},
        {"context_size": 32768, "batch_size": 4096, "ubatch_size": 2048, "threads": 24, "flash_attn": "on", "reasoning": "off", "no_kv_offload": True, "no_repack": True, "no_cont_batching": True, "cache_prompt": False, "parallel": 1, "warmup": False, "ctx_checkpoints": 0, "checkpoint_min_step": 0, "swa_full": False, "no_kv_unified": True},
        {"context_size": 32768, "batch_size": 8192, "ubatch_size": 4096, "threads": 24, "flash_attn": "on", "reasoning": "off", "no_kv_offload": True, "no_repack": True, "no_cont_batching": True, "cache_prompt": False, "parallel": 1, "warmup": False, "ctx_checkpoints": 0, "checkpoint_min_step": 0, "swa_full": False, "no_kv_unified": True},
        {"context_size": 32768, "batch_size": 16384, "ubatch_size": 8192, "threads": 24, "flash_attn": "on", "reasoning": "off", "no_kv_offload": True, "no_repack": True, "no_cont_batching": True, "cache_prompt": False, "parallel": 1, "warmup": False, "ctx_checkpoints": 0, "checkpoint_min_step": 0, "swa_full": False, "no_kv_unified": True},
        {"context_size": 32768, "batch_size": 32768, "ubatch_size": 16384, "threads": 24, "flash_attn": "on", "reasoning": "off", "no_kv_offload": True, "no_repack": True, "no_cont_batching": True, "cache_prompt": False, "parallel": 1, "warmup": False, "ctx_checkpoints": 0, "checkpoint_min_step": 0, "swa_full": False, "no_kv_unified": True},
    ]
    best = 0.0
    best_cfg = None
    for idx, cfg in enumerate(candidates, 1):
        port = 10260 + idx
        print(f"测试配置 {idx}: {cfg}")
        tps = measure_completion(port, **cfg, prompt="Hello", max_tokens=64)
        print(f" -> TPS={tps:.2f}")
        if tps > best:
            best = tps
            best_cfg = cfg
    print("最优配置:", best_cfg, "TPS:", best)
    print("结束 nvidia-smi:", read_nvidia_smi())
    return 0 if best > 100 else 3


if __name__ == "__main__":
    sys.exit(main())
