"""Llama server runtime management."""

from __future__ import annotations

import atexit
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

from core.foundation.logger import get_logger
from core.foundation.paths import get_project_root


class LlamaServerRuntimeError(Exception):
    """Raised when the local llama server cannot be managed."""


class LlamaServerRuntime:
    """Manage a local llama-server process."""

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
        LlamaServerRuntime.kill_all_on_ports([9998])

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
            return dict(self._config.get("llm", {}) or {})
        return {}

    def start(self) -> bool:
        if self._process and self._process.poll() is None:
            return self.health_check()

        if self.health_check():
            self._ready = True
            self._logger.info("llama-server already running on port %s", self._default_port)
            return True

        llm_cfg = self._get_llm_config()
        if not llm_cfg.get("enabled", True):
            self._logger.info("LLM disabled, skipping llama-server startup")
            return False

        model_path = llm_cfg.get("model_path")
        if not model_path:
            self._logger.warning("LLM model_path is not configured")
            return False

        exe = self._resolve_exe()
        if exe is None:
            self._logger.error("llama-server.exe not found")
            return False

        model_path = self._resolve_model_path(str(model_path))
        if not Path(model_path).exists():
            self._logger.error("model file not found: %s", model_path)
            return False

        ok = self._try_start(exe, model_path, llm_cfg)
        if not ok and not self._cuda_failed:
            self._cuda_failed = True
            return self._try_start(exe, model_path, llm_cfg, force_cpu=True)
        return ok

    def stop(self) -> None:
        self._ready = False
        self._http_shutdown()
        self._kill_tracked_process()
        self._kill_processes_on_port()

    def health_check(self) -> bool:
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
        if self._process is not None and self._process.poll() is None:
            return False
        self._ready = False
        return False

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
            self._logger.warning("failed to stop llama-server PID %s: %s", proc.pid, exc)

    def _kill_processes_on_port(self) -> None:
        pids = self._find_pids_on_port(self._default_port)
        if not pids:
            return
        tracked_pid = self._process.pid if self._process and self._process.poll() is None else None
        for pid in pids:
            if tracked_pid is not None and pid == tracked_pid:
                continue
            try:
                p = subprocess.Popen(["taskkill", "/F", "/PID", str(pid)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                p.wait(timeout=5)
            except Exception:
                pass

    @staticmethod
    def _find_pids_on_port(port: int) -> set[int]:
        try:
            output = subprocess.check_output(["netstat", "-ano"], timeout=5, text=True)
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
        for port in ports:
            for pid in cls._find_pids_on_port(port):
                try:
                    p = subprocess.Popen(["taskkill", "/F", "/PID", str(pid)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
        args = [str(exe), "-m", model_path]

        mmproj_path = llm_cfg.get("mmproj_path")
        if mmproj_path:
            args.extend(["--mmproj", str(self._resolve_model_path(str(mmproj_path)))])

        args.extend(
            [
                "--port",
                str(self._default_port),
                "-c",
                str(int(llm_cfg.get("context_size", 2048))),
                "--threads",
                str(int(llm_cfg.get("threads", os.cpu_count() or 8))),
                "--temp",
                str(float(llm_cfg.get("temperature", 0.3))),
            ]
        )

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

        parallel = llm_cfg.get("parallel")
        if parallel is not None and int(parallel) > 0:
            args.extend(["-np", str(int(parallel))])

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
        if cache_ram is not None and int(cache_ram) > 0:
            args.extend(["-cram", str(int(cache_ram))])

        if llm_cfg.get("disable_kv_offload", False):
            args.append("--no-kv-offload")

        return args

    def _try_start(self, exe: Path, model_path: str, llm_cfg: Dict[str, Any], force_cpu: bool = False) -> bool:
        args = self._build_args(exe, model_path, llm_cfg, force_cpu=force_cpu)
        for idx, value in enumerate(args):
            if value == model_path:
                args[idx] = str(Path(model_path).resolve())
                break
        try:
            self._process = subprocess.Popen(args, cwd=str(get_project_root()), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as exc:
            self._logger.error("failed to start llama-server: %s", exc)
            return False

        for _ in range(60):
            if self._process.poll() is not None:
                return False
            if self.health_check():
                self._ready = True
                return True
            time.sleep(1)
        return False

