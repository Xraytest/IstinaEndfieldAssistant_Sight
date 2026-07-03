"""检查 LLM 推理是否真的在 CUDA 上执行"""
from __future__ import annotations

import subprocess
import time
import urllib.request
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

MODEL_PATH = r"models\LLM\Qwen3.5-4B-UD-Q4_K_XL.gguf"
EXE_PATH = Path(__file__).resolve().parent.parent / "3rd-part" / "llama-cpp" / "llama-server.exe"
PORT = 10270


def main() -> int:
    args = [
        str(EXE_PATH),
        "-m",
        str(Path(MODEL_PATH).resolve()),
        "--port",
        str(PORT),
        "-c",
        "32768",
        "-b",
        "2048",
        "-ub",
        "1024",
        "--threads",
        "24",
        "--temp",
        "0.3",
        "-ngl",
        "999",
        "--n-gpu-layers",
        "999",
        "-fa",
        "on",
        "-ctk",
        "q8_0",
        "-ctv",
        "q8_0",
        "-cram",
        "0",
        "-rea",
        "off",
        "--no-kv-offload",
        "--no-repack",
        "--no-cont-batching",
        "--no-cache-prompt",
        "-np",
        "1",
        "--no-warmup",
        "--no-kv-unified",
    ]
    print("启动命令:", " ".join(args))
    proc = subprocess.Popen(
        args,
        cwd=str(Path(__file__).resolve().parent.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        for _ in range(120):
            if proc.poll() is not None:
                out = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
                print("进程已退出，stderr:", out[:4000])
                return 1
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2) as resp:
                    data = resp.read().decode("utf-8", errors="replace")
                    if "ready" in data.lower() or '"status"' in data.lower():
                        print("服务就绪")
                        break
            except Exception:
                pass
            time.sleep(1)
        else:
            print("健康检查超时")
            return 1

        # 发送测试请求，同时监控stderr
        payload = {
            "model": "local",
            "prompt": "Hello",
            "max_tokens": 32,
            "temperature": 0.3,
        }
        import json
        req = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/v1/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            print("响应:", data.get("choices", [{}])[0].get("text", "")[:200])
        t1 = time.time()
        print(f"耗时: {t1-t0:.2f}s")

        # 读取剩余stderr
        time.sleep(1)
        out = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        print("=== 完整 stderr ===")
        print(out[-4000:])
        print("==================")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
