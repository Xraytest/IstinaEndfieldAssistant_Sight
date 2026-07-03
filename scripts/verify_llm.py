"""验证 LLM 推理模块：启动 llama-server，发送测试请求，测量 TPS。"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.capability.llm.runtime import LlamaServerRuntime
from core.capability.llm.client import LlmClient
from core.foundation.paths import get_project_root


MODEL_PATH = r"models\LLM\Qwen3.5-4B-UD-Q4_K_XL.gguf"
EXE_PATH = get_project_root() / "3rd-part" / "llama-cpp" / "llama-server.exe"


def build_args(port: int, overrides: Dict[str, Any]) -> List[str]:
    args = [
        str(EXE_PATH),
        "-m",
        MODEL_PATH,
        "--port",
        str(port),
        "-c",
        "64000",
        "--threads",
        "8",
        "--temp",
        "0.3",
        "-ngl",
        "999",
        "--n-gpu-layers",
        "999",
        "-fa",
        "auto",
        "-ctk",
        "q8_0",
        "-ctv",
        "q8_0",
        "-cram",
        "0",
        "--perf",
    ]
    mapping = {
        "parallel": "--n-parallel",
        "ubatch": "--ubatch-size",
        "no_kv_offload": "--no-kv-offload",
        "no_repack": "--no-repack",
    }
    for key, value in overrides.items():
        if value is None:
            continue
        flag = mapping.get(key, key)
        if isinstance(value, bool):
            if value:
                args.append(str(flag))
        else:
            args.extend([str(flag), str(value)])
    return args


def measure(port: int, overrides: Dict[str, Any]) -> float:
    import subprocess, time, urllib.request, json

    proc = subprocess.Popen(
        build_args(port, overrides),
        cwd=str(get_project_root()),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        for _ in range(120):
            if proc.poll() is not None:
                out = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
                print("STARTERR:", out[:1000])
                return 0.0
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as resp:
                    if b"ready" in resp.read().lower():
                        break
            except Exception:
                pass
            time.sleep(1)
        else:
            print("健康检查超时")
            return 0.0

        client = LlmClient(base_url=f"http://127.0.0.1:{port}/v1")
        t0 = time.time()
        output = client.chat("Hello, reply with one short Chinese greeting.", max_tokens=32)
        t1 = time.time()
        tokens = max(len(output), 1)
        return tokens / max(t1 - t0, 1e-6)
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
    candidates = [
        {"np": 1, "ub": 256, "no_kv_offload": True, "no_repack": True, "perf": True},
        {"np": 1, "ub": 512, "no_kv_offload": True, "no_repack": True, "perf": True},
        {"np": 1, "ub": 256, "no_kv_offload": False, "no_repack": True, "perf": True},
        {"np": 2, "ub": 256, "no_kv_offload": True, "no_repack": True, "perf": True},
        {"np": 1, "ub": 256, "no_kv_offload": True, "no_repack": False, "perf": True},
    ]
    best = 0.0
    best_cfg = None
    for idx, cfg in enumerate(candidates, 1):
        port = 9998 + idx
        print(f"测试配置 {idx}: np={cfg.get('np')}, ub={cfg.get('ub')}, no_kv_offload={cfg.get('no_kv_offload')}, no_repack={cfg.get('no_repack')}, perf={cfg.get('perf')}")
        tps = measure(port, cfg)
        print(f" -> TPS={tps:.2f}")
        if tps > best:
            best = tps
            best_cfg = cfg
    print("最优配置:", best_cfg, "TPS:", best)
    return 0 if best > 100 else 3


if __name__ == "__main__":
    import sys
    sys.exit(main())
