"""元素知识持久化存储仓库

提供 data/elements/, data/tasks/, data/events/ 的读写操作。
"""

import os
import json
import time
from typing import Dict, Any, List, Optional, Set

from .models import (
    ElementKnowledge, ElementVerification, PageKnowledge,
    TaskDefinition, TaskInstance, TaskStatus, TaskCycle,
    EventActivity, AnalysisResult,
)


# 数据存储根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_ROOT = os.path.join(PROJECT_ROOT, "data")


def _ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def _data_path(subdir: str, filename: str) -> str:
    return os.path.join(DATA_ROOT, subdir, filename)


class ElementRepository:
    """元素知识持久化仓库
    
    - data/elements/   -> 页面元素知识（PageKnowledge + ElementKnowledge）
    - data/tasks/      -> 任务定义与实例（TaskDefinition + TaskInstance）
    - data/events/     -> 活动信息（EventActivity）
    - data/analysis/   -> 分析会话记录（AnalysisResult + AnalysisSession）
    """

    def __init__(self):
        self._base_dir = DATA_ROOT
        _ensure_dir(os.path.join(DATA_ROOT, "elements"))
        _ensure_dir(os.path.join(DATA_ROOT, "tasks"))
        _ensure_dir(os.path.join(DATA_ROOT, "events"))
        _ensure_dir(os.path.join(DATA_ROOT, "analysis"))

    # ==================== 页面元素 ====================

    def save_page_elements(self, page_knowledge: PageKnowledge) -> str:
        """持久化页面元素知识"""
        page_name_safe = page_knowledge.page_name.replace(" ", "_").replace("/", "_")
        path = _data_path("elements", f"{page_name_safe}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(page_knowledge.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def load_page_elements(self, page_name: str) -> Optional[PageKnowledge]:
        """加载页面元素知识"""
        page_name_safe = page_name.replace(" ", "_").replace("/", "_")
        path = _data_path("elements", f"{page_name_safe}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return PageKnowledge.from_dict(json.load(f))

    def list_known_pages(self) -> List[str]:
        """列出已知页面名称"""
        elements_dir = os.path.join(DATA_ROOT, "elements")
        if not os.path.exists(elements_dir):
            return []
        pages = []
        for fname in sorted(os.listdir(elements_dir)):
            if fname.endswith(".json"):
                pages.append(fname[:-5])
        return pages

    def delete_page_elements(self, page_name: str) -> bool:
        """删除页面元素知识"""
        page_name_safe = page_name.replace(" ", "_").replace("/", "_")
        path = _data_path("elements", f"{page_name_safe}.json")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    # ==================== 任务 ====================

    def save_tasks(self, tasks: List[TaskDefinition], cycle: str = "all") -> str:
        """持久化任务定义"""
        path = _data_path("tasks", f"tasks_{cycle}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump([t.to_dict() for t in tasks], f, ensure_ascii=False, indent=2)
        return path

    def load_tasks(self, cycle: str = "all") -> List[TaskDefinition]:
        """加载任务定义"""
        path = _data_path("tasks", f"tasks_{cycle}.json")
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [TaskDefinition.from_dict(d) for d in data]

    def save_task_instance(self, instance: TaskInstance) -> str:
        """保存单个任务实例快照"""
        path = _data_path("tasks", f"instance_{instance.task_id}_{int(instance.timestamp)}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(instance.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def load_task_instances(self, task_id: str) -> List[TaskInstance]:
        """加载某个任务的所有历史实例"""
        tasks_dir = os.path.join(DATA_ROOT, "tasks")
        instances = []
        if not os.path.exists(tasks_dir):
            return instances
        for fname in sorted(os.listdir(tasks_dir)):
            if fname.startswith(f"instance_{task_id}_") and fname.endswith(".json"):
                with open(os.path.join(tasks_dir, fname), "r", encoding="utf-8") as f:
                    instances.append(TaskInstance.from_dict(json.load(f)))
        return instances

    def list_known_tasks(self) -> List[str]:
        """列出已知任务ID"""
        tasks_dir = os.path.join(DATA_ROOT, "tasks")
        if not os.path.exists(tasks_dir):
            return []
        task_ids: Set[str] = set()
        for fname in os.listdir(tasks_dir):
            if fname.startswith("instance_") and fname.endswith(".json"):
                parts = fname.split("_")
                if len(parts) >= 2:
                    task_ids.add(parts[1])
        return sorted(task_ids)

    # ==================== 活动 ====================

    def save_event(self, event: EventActivity) -> str:
        """持久化活动信息"""
        path = _data_path("events", f"{event.event_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(event.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def load_event(self, event_id: str) -> Optional[EventActivity]:
        """加载活动信息"""
        path = _data_path("events", f"{event_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return EventActivity.from_dict(json.load(f))

    def list_events(self) -> List[str]:
        """列出已知活动ID"""
        events_dir = os.path.join(DATA_ROOT, "events")
        if not os.path.exists(events_dir):
            return []
        return [f[:-5] for f in sorted(os.listdir(events_dir)) if f.endswith(".json")]

    # ==================== 分析会话 ====================

    def save_analysis_result(self, result: AnalysisResult) -> str:
        """持久化单次分析结果"""
        ts = int(result.timestamp or time.time())
        path = _data_path("analysis", f"analysis_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def load_analysis_results(self, limit: int = 20) -> List[AnalysisResult]:
        """加载最近的分析结果"""
        analysis_dir = os.path.join(DATA_ROOT, "analysis")
        if not os.path.exists(analysis_dir):
            return []
        files = sorted(
            [f for f in os.listdir(analysis_dir) if f.endswith(".json")],
            reverse=True
        )[:limit]
        results = []
        for fname in files:
            with open(os.path.join(analysis_dir, fname), "r", encoding="utf-8") as f:
                results.append(AnalysisResult.from_dict(json.load(f)))
        return results


class AnalysisSession:
    """单次分析会话追踪
    
    记录一次完整的分析过程中所有分析操作。
    """

    def __init__(self, session_id: str = "", device_serial: str = "localhost:16512"):
        import uuid
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.device_serial = device_serial
        self.start_time = time.time()
        self.end_time: float = 0.0
        self.results: List[AnalysisResult] = []
        self.pages_visited: List[str] = []
        self.tasks_found: List[TaskDefinition] = []
        self.events_found: List[EventActivity] = []
        self.repo = ElementRepository()

    def add_result(self, result: AnalysisResult) -> None:
        self.results.append(result)
        self.repo.save_analysis_result(result)
        if result.page_name and result.page_name not in self.pages_visited:
            self.pages_visited.append(result.page_name)

    def add_task(self, task: TaskDefinition) -> None:
        self.tasks_found.append(task)

    def add_event(self, event: EventActivity) -> None:
        self.events_found.append(event)
        self.repo.save_event(event)

    def finalize(self) -> Dict[str, Any]:
        self.end_time = time.time()
        self.repo.save_tasks(self.tasks_found, "session")
        return {
            "session_id": self.session_id,
            "device_serial": self.device_serial,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": round(self.end_time - self.start_time, 1),
            "pages_visited": self.pages_visited,
            "analysis_count": len(self.results),
            "tasks_found": len(self.tasks_found),
            "events_found": len(self.events_found),
        }

    def summary(self) -> str:
        info = self.finalize()
        lines = [
            f"分析会话: {info['session_id']}",
            f"设备: {info['device_serial']}",
            f"时长: {info['duration_seconds']}秒",
            f"访问页面: {len(info['pages_visited'])}",
            f"分析次数: {info['analysis_count']}",
            f"发现任务: {info['tasks_found']}",
            f"发现活动: {info['events_found']}",
        ]
        for p in info['pages_visited']:
            lines.append(f"  - {p}")
        return "\n".join(lines)
