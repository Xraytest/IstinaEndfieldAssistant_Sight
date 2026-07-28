"""
本地质量检查脚本。

提交前必须运行,使用捆绑解释器依次运行 ruff 与 mypy,
记录退出码与输出。若 mypy strict 当前不可通过,输出失败清单,
不得放宽配置,只能逐文件修复或添加显式 # type: ignore 并记录理由。

Usage:
    3rd-part/python/python.exe scripts/run_quality_checks.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = REPO_ROOT / "3rd-part" / "python" / "python.exe"


def _run(cmd: list[str], label: str) -> tuple[int, str]:
    print(f"\n=== {label} ===")
    print(f"$ {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = (result.stdout or "") + (result.stderr or "")
        print(output)
        print(f"exit={result.returncode}")
        return result.returncode, output
    except FileNotFoundError as e:
        msg = f"{label}: 解释器或工具未找到 {e}"
        print(msg, file=sys.stderr)
        return 127, msg
    except subprocess.TimeoutExpired:
        msg = f"{label}: 超时(300s)"
        print(msg, file=sys.stderr)
        return 124, msg


def main() -> int:
    results: list[tuple[str, int]] = []

    rc, _ = _run(
        [str(PYTHON), "-m", "ruff", "check", "."],
        "ruff check .",
    )
    results.append(("ruff", rc))

    rc, _ = _run(
        [str(PYTHON), "-m", "mypy", "src"],
        "mypy src (strict)",
    )
    results.append(("mypy", rc))

    rc, _ = _run(
        [str(PYTHON), "-m", "pytest", "--collect-only", "-q"],
        "pytest --collect-only",
    )
    results.append(("pytest-collect", rc))

    print("\n=== Summary ===")
    overall = 0
    for name, rc in results:
        status = "PASS" if rc == 0 else f"FAIL(rc={rc})"
        print(f"  {name}: {status}")
        if rc != 0:
            overall = max(overall, rc)

    if overall != 0:
        print(
            "\n[!] Some checks failed. Do NOT relax ruff/mypy config; "
            "fix files one by one or add explicit '# type: ignore' with rationale."
        )
    return overall


if __name__ == "__main__":
    sys.exit(main())
