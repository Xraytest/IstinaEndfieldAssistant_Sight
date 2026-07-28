"""ADB wrapper that logs all commands, then delegates to real adb.exe.

Use this to discover what screencap commands MaaFW actually sends.
Set adb_path to this script's output .exe (or use Python directly).
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

REAL_ADB = Path(__file__).resolve().parents[1] / "3rd-part" / "adb" / "adb.exe"
LOG_FILE = Path(__file__).resolve().parents[1] / "config" / "debug" / "adb_wrapper.log"


def main() -> int:
    args = sys.argv[1:]
    cmd_str = " ".join(args)

    # Log the command
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] adb {' '.join(args)}\n")

    # Special handling: if this is a screencap command, log extra info
    if "screencap" in cmd_str:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"  >>> SCREENCAP DETECTED: {cmd_str}\n")

    # Delegate to real adb
    result = subprocess.run(
        [str(REAL_ADB)] + args,
        capture_output=False,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
