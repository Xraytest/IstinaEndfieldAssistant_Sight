"""GPU check utility.

Detects NVIDIA GPU presence and VRAM at UI startup. Falls back gracefully on
non-NVIDIA or absent GPUs so the UI never hard-fails on environment issues.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional


VRAM_WARNING_THRESHOLD_BYTES = 7 * 1024 * 1024 * 1024  # 7 GiB


@dataclass(frozen=True)
class GPUCheckResult:
    is_nvidia: bool
    vram_bytes: Optional[int]
    gpu_name: Optional[str]
    raw_output: str


def check_gpu() -> GPUCheckResult:
    """Query nvidia-smi for NVIDIA GPU presence and total VRAM.

    Returns a GPUCheckResult. If nvidia-smi is missing or fails, returns an
    "unsupported" result (is_nvidia=False) so callers can warn the user.
    """
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        return GPUCheckResult(
            is_nvidia=False,
            vram_bytes=None,
            gpu_name=None,
            raw_output="",
        )

    try:
        proc = subprocess.run(
            [nvidia_smi, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return GPUCheckResult(
            is_nvidia=False,
            vram_bytes=None,
            gpu_name=None,
            raw_output="",
        )

    raw = (proc.stdout or "").strip()
    if proc.returncode != 0 or not raw:
        return GPUCheckResult(
            is_nvidia=False,
            vram_bytes=None,
            gpu_name=None,
            raw_output=raw,
        )

    # Parse the first GPU line: "NVIDIA GeForce RTX 5060 Laptop GPU, 8151"
    first_line = raw.splitlines()[0].strip()
    parts = [p.strip() for p in first_line.split(",")]
    if len(parts) < 2:
        return GPUCheckResult(
            is_nvidia=False,
            vram_bytes=None,
            gpu_name=first_line or None,
            raw_output=raw,
        )

    gpu_name = parts[0]
    vram_str = parts[1].split()[0] if parts[1] else "0"
    try:
        vram_mib = int(vram_str)
    except ValueError:
        vram_mib = 0

    vram_bytes = vram_mib * 1024 * 1024
    return GPUCheckResult(
        is_nvidia=True,
        vram_bytes=vram_bytes,
        gpu_name=gpu_name,
        raw_output=raw,
    )


def format_gpu_warning(result: GPUCheckResult) -> Optional[str]:
    """Map a GPUCheckResult to a user-facing warning message, or None if OK."""
    if not result.is_nvidia:
        return (
            "GPU不受支持，使用全智能相关功能可能导致严重卡顿。"
        )
    if result.vram_bytes is None or result.vram_bytes < VRAM_WARNING_THRESHOLD_BYTES:
        return (
            "GPU显存低，使用全智能相关功能可能产生卡顿。"
        )
    return None
