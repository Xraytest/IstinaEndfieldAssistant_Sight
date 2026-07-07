from __future__ import annotations

import os
from pathlib import Path

_tmp_root = Path(__file__).resolve().parent / ".tmp" / "python-temp"
_tmp_root.mkdir(parents=True, exist_ok=True)
os.environ["TMPDIR"] = str(_tmp_root)
os.environ["TEMP"] = str(_tmp_root)
os.environ["TMP"] = str(_tmp_root)

# Point maa library to MaaEnd maafw for matching AgentClient/Server versions
_maafw_dir = Path(__file__).resolve().parent / "3rd-part" / "maaend" / "agent" / "maafw"
if _maafw_dir.is_dir():
    os.environ["MAAFW_BINARY_PATH"] = str(_maafw_dir.resolve())
