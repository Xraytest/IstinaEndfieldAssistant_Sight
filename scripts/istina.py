#!/usr/bin/env python3
"""
IstinaEndfieldAssistant_Sight — CLI 入口（薄包装）

委托给 src/cli/istina.py 执行。
"""
import sys
from pathlib import Path

_src_dir = Path(__file__).resolve().parent.parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from cli.istina import main

if __name__ == "__main__":
    sys.exit(main())
