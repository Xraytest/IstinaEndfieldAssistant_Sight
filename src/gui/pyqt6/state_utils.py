"""共享的状态文件原子写入与损坏备份工具。

被 ``queue_state.py`` 与 ``scheduled_task_store.py`` 复用，
避免重复实现原子写入与备份逻辑。

QSettings 组织/应用名常量也集中在此处供全局复用。
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any


# QSettings 组织/应用名常量（main_window、i18n 等模块共享）
QSETTINGS_ORG = "ArkStudio"
QSETTINGS_APP = "IstinaEndfieldAssistant"


def atomic_write_json(path: Path, payload: Any, *, logger_name: str = __name__) -> bool:
    """将 ``payload`` 序列化为 JSON 并原子写入 ``path``。

    通过 ``.tmp`` 临时文件 + ``os.replace`` 实现原子替换，
    避免写入中途崩溃导致原文件损坏。任何异常都会被捕获并记录为 warning。
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp_path, path)
        return True
    except Exception as exc:
        logging.getLogger(logger_name).warning("atomic_write_json failed for %s: %s", path, exc)
        return False


def backup_corrupt_state(path: Path, *, logger_name: str = __name__) -> None:
    """将损坏的状态文件重命名为 ``.json.bak``（必要时带序号），避免每次启动都失败。"""
    try:
        backup = path.with_suffix(".json.bak")
        counter = 0
        while backup.exists():
            backup = path.with_suffix(f".json.bak.{counter}")
            counter += 1
        os.replace(path, backup)
    except Exception as exc:
        logging.getLogger(logger_name).warning("backup_corrupt_state failed for %s: %s", path, exc)
