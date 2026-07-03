"""LlamaServerRuntime - 管理 llama-server.exe 常驻进程

负责启动、停止、健康检查，并在 CUDA 不可用时自动回退 CPU。
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

from core.foundation.logger import get_logger, LogCategory
from core.foundation.paths import get_project_root


class LlamaServerRuntimeError(Exception):
    """LlamaServerRuntime 基础异常"""


class LlamaServerRuntime:
    """llama-server.exe 常驻进程管理器

    默认行为：
    - 使用 3rd-part/llama-cpp/llama-server.exe
    - 优先启用 CUDA（-ngl 999 / --n-gpu-layers 999）
    - 监听 127.0.0.1:9998
    - 启动后等待 /health 返回 ready
    - 健康检查失败 2 次视为不可用
    """

    def __init__(self, config: Dict[str, Any]):
        self._config = config
        self._process: Optional[subprocess.Popen[bytes]] = None
        self._ready = False
        self._cuda_failed = False
        self._logger = get_logger(__name__)
        self._default_port = int(config.get("port", 9998))

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def port(self) -> int:
        return self._default_port

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._default_port}/v1"

    def _get_llm_config(self) -> Dict[str, Any]:
        if isinstance(self._config, dict):
            return self._config.get("llm", {})
        return {}

    def start(self) -> bool:
        if self._process and self._process.poll() is None:
            return self.health_check()

        llm_cfg = self._get_llm_config()
        if not llm_cfg.get("enabled", True):
            self._logger.info("LLM 已禁用，跳过 llama-server 启动")
            return False

        model_path = llm_cfg.get("model_path")
        if not model_path:
            self._logger.warning("LLM model_path 未配置")
            return False

        exe = self._resolve_exe()
        if exe is None:
            self._logger.error("未找到 llama-server.exe")
            return False

        model_path = self._resolve_model_path(str(model_path))
        if not Path(model_path).exists():
            self._logger.error("模型文件不存在: %s", model_path)
            return False

        ok = self._try_start(exe, model_path, llm_cfg)
        if not ok and not self._cuda_failed:
            self._logger.warning("CUDA 启动失败，回退 CPU 模式重试")
            self._cuda_failed = True
            return self._try_start(exe, model_path, llm_cfg, force_cpu=True)
        return ok

    def stop(self) -> None:
        self._ready = False
        if self._process is None:
            return
        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        except Exception as exc:
            self._logger.warning("关闭 llama-server 失败: %s", exc)
        finally:
            self._process = None

    def health_check(self) -> bool:
        if self._process is None or self._process.poll() is not None:
            self._ready = False
            return False
        try:
            import urllib.request
            url = f"http://127.0.0.1:{self._default_port}/health"
            with urllib.request.urlopen(url, timeout=2) as resp:
                data = resp.read().decode("utf-8", errors="replace")
                if "ready" in data.lower() or '"status"' in data.lower():
                    self._ready = True
                    return True
        except Exception:
            pass
        self._ready = False
        return False

    def _resolve_exe(self) -> Optional[Path]:
        candidates = [
            get_project_root() / "3rd-part" / "llama-cpp" / "llama-server.exe",
            Path("3rd-part/llama-cpp/llama-server.exe"),
            Path(r"3rd-part\llama-cpp\llama-server.exe"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _resolve_model_path(self, model_path: str) -> str:
        p = Path(model_path)
        if p.exists():
            return str(p)
        candidate = get_project_root() / model_path
        if candidate.exists():
            return str(candidate)
        return model_path

    def _build_args(self, exe: Path, model_path: str, llm_cfg: Dict[str, Any], force_cpu: bool) -> list[str]:
        args = [
            str(exe),
            "-m",
            model_path,
            "--port",
            str(self._default_port),
            "-c",
            str(int(llm_cfg.get("context_size", 2048))),
            "--threads",
            str(int(llm_cfg.get("threads", os.cpu_count() or 8))),
            "--temp",
            str(float(llm_cfg.get("temperature", 0.3))),
        ]

        if force_cpu:
            return args

        ngl = str(llm_cfg.get("n_gpu_layers", "999"))
        args.extend(["-ngl", ngl, "--n-gpu-layers", ngl])

        flash_attn = str(llm_cfg.get("flash_attention", "auto"))
        if flash_attn in {"on", "off", "auto"}:
            args.extend(["-fa", flash_attn])

        batch_size = llm_cfg.get("batch_size")
        if batch_size is not None:
            args.extend(["-b", str(int(batch_size))])

        ubatch_size = llm_cfg.get("ubatch_size")
        if ubatch_size is not None:
            args.extend(["-ub", str(int(ubatch_size))])

        if llm_cfg.get("no_repack", False):
            args.append("--no-repack")

        if llm_cfg.get("no_cont_batching", False):
            args.append("--no-cont-batching")

        reasoning = str(llm_cfg.get("reasoning", "off"))
        if reasoning in {"on", "off", "auto"}:
            args.extend(["-rea", reasoning])

        kv_type = str(llm_cfg.get("kv_cache_type", "q8_0"))
        if kv_type:
            args.extend(["-ctk", kv_type, "-ctv", kv_type])

        cache_ram = llm_cfg.get("cache_ram_mb")
        if cache_ram is not None and cache_ram > 0:
            args.extend(["-cram", str(int(cache_ram))])

        if llm_cfg.get("disable_kv_offload", False):
            args.append("--no-kv-offload")

        return args

    def _try_start(self, exe: Path, model_path: str, llm_cfg: Dict[str, Any], force_cpu: bool = False) -> bool:
        args = self._build_args(exe, model_path, llm_cfg, force_cpu=force_cpu)
        # 使用绝对路径，避免 llama-server 相对路径解析失败
        for idx, value in enumerate(args):
            if value == model_path:
                args[idx] = str(Path(model_path).resolve())
                break
        try:
            self._process = subprocess.Popen(
                args,
                cwd=str(get_project_root()),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as exc:
            self._logger.error("启动 llama-server 失败: %s", exc)
            return False

        for _ in range(60):
            if self._process.poll() is not None:
                out = self._safe_read(self._process.stderr)
                print("LLAMA_SERVER_STDERR:", out[:2000])
                self._logger.error("llama-server 退出: %s", out[:500])
                return False
            if self.health_check():
                mode = "cpu" if force_cpu else "cuda"
                self._logger.info("llama-server 就绪: mode=%s, port=%s", mode, self._default_port)
                return True
            time.sleep(1)
        return False

    @staticmethod
    def _safe_read(pipe: Optional[object]) -> str:
        if pipe is None:
            return ""
        try:
            data = pipe.read()
            if isinstance(data, bytes):
                return data.decode("utf-8", errors="replace")
            return str(data)
        except Exception:
            return ""
