"""路径管理模块

提供项目根目录的解析，以及自动将 src/ 加入 sys.path 的工具函数。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def get_project_root() -> Path:
    """获取项目根目录

    以当前文件所在位置向上推断到项目根目录。
    paths.py 位于 src/core/foundation/，向上 2 层到达 src/，再向上 1 层到达项目根。

    Returns:
        项目根目录 Path 对象
    """
    return Path(__file__).resolve().parent.parent.parent.parent


def ensure_src_path(path: Optional[str] = None) -> None:
    """确保 src/ 在 sys.path 中

    如果 src/ 不在 sys.path 中，则将其插入到最前面。
    这样可以保证 `from core.xxx import ...` 正常工作。

    Args:
        path: 可选的参考文件路径，用于计算项目根目录。
              如果为 None，则使用当前文件位置计算。
    """
    if path is not None:
        # 使用提供的路径计算项目根目录
        source = Path(path).resolve()
        project_root = source.parent.parent.parent.parent
    else:
        project_root = get_project_root()

    src_dir = project_root / "src"
    src_str = str(src_dir)

    if src_str not in sys.path:
        sys.path.insert(0, src_str)
