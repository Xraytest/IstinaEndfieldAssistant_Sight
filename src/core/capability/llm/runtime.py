"""LlamaServerRuntime - 管理 llama-server.exe 常驻进程

负责启动、停止、健康检查，并在 CUDA 不可用时自动回退 CPU。
"""

from __future__ import annotations

import atexit
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
    - 退出时自动清理所有占用端口的残留进程
    """

    _atexit_registered = False

    def __init__(self, config: Dict[str, Any]):
        self._config = config
        self._process: Optional[subprocess.Popen[bytes]] = None
        self._ready = False
        self._cuda_failed = False
        self._logger = get_logger(__name__)
        self._default_port = int(config.get("port", 9998))
        self._register_atexit()

    def _register_atexit(self) -> None:
        if LlamaServerRuntime._atexit_registered:
            return
        LlamaServerRuntime._atexit_registered = True
        atexit.register(self._atexit_cleanup)

    @staticmethod
    def _atexit_cleanup() -> None:
        LlamaServerRuntime.kill_all_on_ports([9997, 9998])

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

        if self.health_check():
            self._ready = True
            self._logger.info("检测到已有 llama-server 运行在端口 %s", self._default_port)
            return True

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

        # 1. 优雅关闭：发送 /shutdown
        self._http_shutdown()

        # 2. 终止跟踪的子进程
        self._kill_tracked_process()

        # 3. 清理端口上所有残留进程
        self._kill_processes_on_port()

    def health_check(self) -> bool:
        # 优先 HTTP 检测，覆盖外部启动的服务
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
        # 无 HTTP 响应时才有进程检查
        if self._process is not None and self._process.poll() is None:
            return False
        self._ready = False
        return False

    # ------------------------------------------------------------------
    # 进程清理
    # ------------------------------------------------------------------

    def _http_shutdown(self) -> None:
        try:
            import urllib.request
            req = urllib.request.Request(
                f"http://127.0.0.1:{self._default_port}/shutdown",
                method="POST",
                data=b"",
            )
            urllib.request.urlopen(req, timeout=2)
        except Exception:
            pass

    def _kill_tracked_process(self) -> None:
        proc = self._process
        if proc is None:
            return
        self._process = None
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        except Exception as exc:
            self._logger.warning("终止 llama-server PID %s 失败: %s", proc.pid, exc)

    def _kill_processes_on_port(self) -> None:
        pids = self._find_pids_on_port(self._default_port)
        if not pids:
            return
        tracked_pid = self._process.pid if self._process and self._process.poll() is None else None
        for pid in pids:
            if tracked_pid is not None and pid == tracked_pid:
                continue
            try:
                p = subprocess.Popen(
                    ["taskkill", "/F", "/PID", str(pid)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                p.wait(timeout=5)
                self._logger.info("清理端口 %s 残留进程 PID %s", self._default_port, pid)
            except Exception as exc:
                self._logger.debug("清理 PID %s 失败: %s", pid, exc)

    @staticmethod
    def _find_pids_on_port(port: int) -> set[int]:
        try:
            output = subprocess.check_output(
                ["netstat", "-ano"],
                timeout=5,
                text=True,
            )
            pids: set[int] = set()
            for line in output.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    if parts:
                        try:
                            pids.add(int(parts[-1]))
                        except ValueError:
                            pass
            return pids
        except Exception:
            return set()

    @classmethod
    def kill_all_on_ports(cls, ports: list[int]) -> None:
        """静态方法：强制清理指定端口上所有进程（无实例依赖）"""
        for port in ports:
            pids = cls._find_pids_on_port(port)
            for pid in pids:
                try:
                    p = subprocess.Popen(
                        ["taskkill", "/F", "/PID", str(pid)],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    p.wait(timeout=5)
                except Exception:
                    pass

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
