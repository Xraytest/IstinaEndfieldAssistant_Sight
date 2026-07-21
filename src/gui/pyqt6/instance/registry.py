"""实例注册表持久化。

注册表文件位于 ``<project_root>/instances/registry.json``，记录所有实例的
元数据（不存配置本身，配置在各自 ``instances/<id>/`` 目录）。

注册表结构::

    {
      "version": "1.0",
      "active": "default",
      "instances": [
        {
          "id": "default",
          "display_name": "默认",
          "color": "#3B82F6",
          "created_at": "2026-07-21T10:00:00",
          "sort_order": 0
        }
      ]
    }
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.foundation.instance import (
    DEFAULT_INSTANCE_ID,
    get_instances_root,
    is_valid_instance_id,
)


# 预设颜色（用户可在新建实例对话框中选择）
PRESET_COLORS: List[str] = [
    "#3B82F6",  # 蓝
    "#10B981",  # 绿
    "#F59E0B",  # 橙
    "#EF4444",  # 红
    "#8B5CF6",  # 紫
    "#EC4899",  # 粉
    "#14B8A6",  # 青
    "#6B7280",  # 灰
]


class InstanceMeta:
    """单个实例的元数据载体。"""

    def __init__(
        self,
        instance_id: str,
        display_name: str = "",
        color: str = "#3B82F6",
        created_at: Optional[str] = None,
        sort_order: int = 0,
    ) -> None:
        if not is_valid_instance_id(instance_id):
            raise ValueError(f"非法 instance_id: {instance_id!r}")
        self.id = instance_id
        self.display_name = display_name or instance_id
        self.color = color
        self.created_at = created_at or datetime.now().isoformat(timespec="seconds")
        self.sort_order = sort_order

    @property
    def is_default(self) -> bool:
        return self.id == DEFAULT_INSTANCE_ID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "color": self.color,
            "created_at": self.created_at,
            "sort_order": self.sort_order,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InstanceMeta":
        # 注意：旧版 registry.json 可能含 "icon" 字段，此处显式忽略，
        # 不再读取（已移除 emoji 图标特性）。
        return cls(
            instance_id=str(data.get("id") or "").strip(),
            display_name=str(data.get("display_name") or "").strip(),
            color=str(data.get("color") or "#3B82F6").strip(),
            created_at=data.get("created_at"),
            sort_order=int(data.get("sort_order") or 0),
        )


class InstanceRegistry:
    """实例注册表持久化管理器（线程安全）。

    注册表文件位置固定为 ``<project_root>/instances/registry.json``（全局共享，
    不属于任何实例私有数据）。
    """

    def __init__(self, registry_path: Optional[Path] = None) -> None:
        self._registry_path = registry_path or self._resolve_registry_path()
        self._lock = threading.RLock()
        self._instances: List[InstanceMeta] = []
        self._active_id: str = DEFAULT_INSTANCE_ID
        self.load()

    @staticmethod
    def _resolve_registry_path() -> Path:
        path = get_instances_root() / "registry.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def registry_path(self) -> Path:
        return self._registry_path

    @property
    def active_id(self) -> str:
        with self._lock:
            return self._active_id

    def set_active(self, instance_id: str) -> None:
        with self._lock:
            if not any(m.id == instance_id for m in self._instances):
                raise ValueError(f"实例不存在: {instance_id!r}")
            self._active_id = instance_id
        self.persist()

    def list_metas(self) -> List[InstanceMeta]:
        with self._lock:
            return list(self._instances)

    def get_meta(self, instance_id: str) -> Optional[InstanceMeta]:
        with self._lock:
            for m in self._instances:
                if m.id == instance_id:
                    return m
            return None

    def upsert_meta(self, meta: InstanceMeta) -> None:
        """插入或更新实例元数据。"""
        with self._lock:
            for i, m in enumerate(self._instances):
                if m.id == meta.id:
                    self._instances[i] = meta
                    break
            else:
                self._instances.append(meta)
        self.persist()

    def remove_meta(self, instance_id: str) -> bool:
        """从注册表移除实例元数据（不删文件）。"""
        with self._lock:
            before = len(self._instances)
            self._instances = [m for m in self._instances if m.id != instance_id]
            removed = len(self._instances) < before
            if removed and self._active_id == instance_id:
                self._active_id = DEFAULT_INSTANCE_ID
        if removed:
            self.persist()
        return removed

    def load(self) -> None:
        with self._lock:
            if not self._registry_path.exists():
                # 首次启动：写入 default 实例
                self._instances = [InstanceMeta(
                    instance_id=DEFAULT_INSTANCE_ID,
                    display_name="默认",
                    color="#3B82F6",
                    sort_order=0,
                )]
                self._active_id = DEFAULT_INSTANCE_ID
                self.persist()
                return
            try:
                data = json.loads(self._registry_path.read_text(encoding="utf-8"))
            except Exception:
                # 注册表损坏：回退到 default
                self._instances = [InstanceMeta(
                    instance_id=DEFAULT_INSTANCE_ID,
                    display_name="默认",
                    sort_order=0,
                )]
                self._active_id = DEFAULT_INSTANCE_ID
                self.persist()
                return
            instances_data = data.get("instances") if isinstance(data, dict) else None
            self._instances = []
            if isinstance(instances_data, list):
                for entry in instances_data:
                    if not isinstance(entry, dict):
                        continue
                    try:
                        meta = InstanceMeta.from_dict(entry)
                    except ValueError:
                        continue
                    self._instances.append(meta)
            # 确保 default 始终存在
            if not any(m.id == DEFAULT_INSTANCE_ID for m in self._instances):
                self._instances.insert(0, InstanceMeta(
                    instance_id=DEFAULT_INSTANCE_ID,
                    display_name="默认",
                    sort_order=0,
                ))
            # 按 sort_order 排序
            self._instances.sort(key=lambda m: (m.sort_order, m.id))
            self._active_id = str(data.get("active") or DEFAULT_INSTANCE_ID) if isinstance(data, dict) else DEFAULT_INSTANCE_ID
            if not any(m.id == self._active_id for m in self._instances):
                self._active_id = DEFAULT_INSTANCE_ID

    def persist(self) -> bool:
        with self._lock:
            try:
                payload = {
                    "version": "1.0",
                    "active": self._active_id,
                    "instances": [m.to_dict() for m in self._instances],
                }
                self._registry_path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self._registry_path.with_suffix(".tmp")
                tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                import os as _os
                _os.replace(tmp, self._registry_path)
                return True
            except Exception:
                return False


__all__ = ["InstanceMeta", "InstanceRegistry", "PRESET_COLORS"]
