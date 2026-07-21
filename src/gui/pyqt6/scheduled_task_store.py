"""定时任务持久化与数据模型。

存储位置：config/scheduled_tasks.json
数据结构：
{
  "tasks": [<ScheduledTask 字典>]
}
"""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


WEEKDAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # 周一到周日


class ScheduledTask:
    """单个定时任务的数据载体。"""

    def __init__(
        self,
        name: str = "",
        target_type: str = "queue",  # "queue" | "preset"
        target_name: str = "",
        device_serial: str = "",
        trigger_time: str = "08:00",  # HH:MM 24h
        weekdays: Optional[List[int]] = None,  # [] = 每天; [0..6] = 周一..周日
        launch_emulator: bool = False,
        enabled: bool = True,
        task_id: Optional[str] = None,
        last_run_at: Optional[str] = None,
        last_run_status: str = "",  # "" | "success" | "failed" | "running"
        next_run_at: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> None:
        self.id = task_id or uuid.uuid4().hex
        self.name = name
        self.target_type = target_type
        self.target_name = target_name
        self.device_serial = device_serial
        self.trigger_time = trigger_time
        self.weekdays = list(weekdays) if weekdays is not None else []
        self.launch_emulator = launch_emulator
        self.enabled = enabled
        self.last_run_at = last_run_at
        self.last_run_status = last_run_status
        self.next_run_at = next_run_at
        self.created_at = created_at or datetime.now().isoformat(timespec="seconds")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "target_type": self.target_type,
            "target_name": self.target_name,
            "device_serial": self.device_serial,
            "trigger_time": self.trigger_time,
            "weekdays": list(self.weekdays),
            "launch_emulator": self.launch_emulator,
            "last_run_at": self.last_run_at,
            "last_run_status": self.last_run_status,
            "next_run_at": self.next_run_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduledTask":
        return cls(
            task_id=str(data.get("id") or "").strip() or None,
            name=str(data.get("name") or "").strip(),
            target_type=str(data.get("target_type") or "queue").strip(),
            target_name=str(data.get("target_name") or "").strip(),
            device_serial=str(data.get("device_serial") or "").strip(),
            trigger_time=str(data.get("trigger_time") or "08:00").strip(),
            weekdays=[int(d) for d in (data.get("weekdays") or []) if isinstance(d, int) and 0 <= d <= 6],
            launch_emulator=bool(data.get("launch_emulator", False)),
            enabled=bool(data.get("enabled", True)),
            last_run_at=data.get("last_run_at"),
            last_run_status=str(data.get("last_run_status") or ""),
            next_run_at=data.get("next_run_at"),
            created_at=data.get("created_at"),
        )


class ScheduledTaskStore:
    """定时任务列表的持久化管理器（线程安全）。"""

    def __init__(self, state_path: Optional[Path] = None) -> None:
        self._state_path = state_path or self._resolve_state_path()
        self._tasks: List[ScheduledTask] = []
        self._lock = threading.Lock()
        self.load()

    @staticmethod
    def _resolve_state_path() -> Path:
        try:
            from core.foundation.paths import get_project_root
            base = Path(get_project_root()) / "config"
        except Exception:
            base = Path(__file__).resolve().parent.parent.parent.parent / "config"
        base.mkdir(parents=True, exist_ok=True)
        return base / "scheduled_tasks.json"

    @property
    def state_path(self) -> Path:
        return self._state_path

    def list_tasks(self) -> List[ScheduledTask]:
        with self._lock:
            return list(self._tasks)

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        with self._lock:
            for t in self._tasks:
                if t.id == task_id:
                    return t
            return None

    def add_task(self, task: ScheduledTask) -> None:
        with self._lock:
            self._tasks.append(task)
        self.persist()

    def update_task(self, task: ScheduledTask) -> bool:
        with self._lock:
            for i, t in enumerate(self._tasks):
                if t.id == task.id:
                    self._tasks[i] = task
                    self.persist()
                    return True
            return False

    def delete_tasks(self, task_ids: List[str]) -> int:
        with self._lock:
            before = len(self._tasks)
            self._tasks = [t for t in self._tasks if t.id not in set(task_ids)]
            removed = before - len(self._tasks)
        if removed:
            self.persist()
        return removed

    def set_enabled(self, task_ids: List[str], enabled: bool) -> int:
        with self._lock:
            count = 0
            for t in self._tasks:
                if t.id in set(task_ids):
                    t.enabled = enabled
                    count += 1
        if count:
            self.persist()
        return count

    def update_run_state(
        self,
        task_id: str,
        last_run_at: Optional[str],
        last_run_status: str,
        next_run_at: Optional[str],
    ) -> None:
        with self._lock:
            for t in self._tasks:
                if t.id == task_id:
                    t.last_run_at = last_run_at
                    t.last_run_status = last_run_status
                    t.next_run_at = next_run_at
                    break
        self.persist()

    def load(self) -> None:
        with self._lock:
            if not self._state_path.exists():
                self._tasks = []
                return
            try:
                data = json.loads(self._state_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logging.getLogger(__name__).warning("ScheduledTaskStore load failed: %s", exc)
                self._backup_corrupt_state()
                self._tasks = []
                return
            tasks_data = data.get("tasks") if isinstance(data, dict) else None
            self._tasks = []
            if isinstance(tasks_data, list):
                for entry in tasks_data:
                    if not isinstance(entry, dict):
                        continue
                    self._tasks.append(ScheduledTask.from_dict(entry))

    def _backup_corrupt_state(self) -> None:
        try:
            backup = self._state_path.with_suffix(".json.bak")
            counter = 0
            while backup.exists():
                backup = self._state_path.with_suffix(f".json.bak.{counter}")
                counter += 1
            os.replace(self._state_path, backup)
        except Exception as exc:
            logging.getLogger(__name__).warning("ScheduledTaskStore backup corrupt file failed: %s", exc)

    def persist(self) -> bool:
        with self._lock:
            try:
                payload = {
                    "tasks": [t.to_dict() for t in self._tasks],
                }
                self._state_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = self._state_path.with_suffix(".tmp")
                tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(tmp_path, self._state_path)
                return True
            except Exception as exc:
                logging.getLogger(__name__).warning("ScheduledTaskStore persist failed: %s", exc)
                return False


def compute_next_run(
    trigger_time: str,
    weekdays: List[int],
    now: Optional[datetime] = None,
    last_run_at: Optional[str] = None,
) -> Optional[datetime]:
    """根据触发时间、星期几限制、上次运行时间，计算下一次触发的 datetime。

    - weekdays 为空：每天触发
    - weekdays 非空：仅在指定星期几触发
    - 如果今天还没到触发时间，下次就是今天；否则是下一个符合条件的日期
    - last_run_at 用于防止同一天重复触发（如果今天已运行过且触发时间已过，跳到下个符合日）
    """
    try:
        hh, mm = trigger_time.split(":")
        hour, minute = int(hh), int(mm)
    except Exception:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    now_dt = now or datetime.now()
    target_today = now_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # 解析 last_run_at
    last_run_dt: Optional[datetime] = None
    if last_run_at:
        try:
            last_run_dt = datetime.fromisoformat(last_run_at)
        except Exception:
            last_run_dt = None

    allowed_weekdays = set(weekdays) if weekdays else set(range(7))

    # 候选日：今天、今天+1..+7
    for delta in range(0, 8):
        candidate_date = (now_dt + timedelta(days=delta)).date()
        if candidate_date.weekday() not in allowed_weekdays:
            continue
        candidate_dt = datetime.combine(candidate_date, target_today.time())
        if candidate_dt <= now_dt:
            # 已过：除非今天且今天没运行过
            if delta == 0 and (last_run_dt is None or last_run_dt.date() < candidate_dt.date()):
                return candidate_dt
            continue
        return candidate_dt
    return None
