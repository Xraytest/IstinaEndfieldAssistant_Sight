"""Shared path setup for scripts/ directory.

Usage from scripts/*.py:
    from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path

Usage from scripts/subdir/*.py:
    import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
"""
import sys
import os
from pathlib import Path

# 自举：先添加 src 路径才能导入 utils.paths
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from core.foundation.utils.paths import get_project_root, get_src_dir, ensure_src_path

PROJECT_ROOT = Path(get_project_root())
SRC_DIR = Path(get_src_dir())


def ensure_path():
    """确保 src 目录在 sys.path 中"""
    ensure_src_path(__file__)
