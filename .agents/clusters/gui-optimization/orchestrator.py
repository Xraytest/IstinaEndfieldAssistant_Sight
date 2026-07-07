"""Orchestrator for the GUI optimization sub-agent cluster."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
QUEUE_FILE = REPO_ROOT / ".agents" / "clusters" / "gui-optimization" / "optimization_queue.md"
ROLES_DIR = REPO_ROOT / ".agents" / "clusters" / "gui-optimization" / "roles"


@dataclass
class Task:
    id: str
    type: str
    description: str
    priority: int = 2
    status: str = "pending"
    dependencies: List[str] = field(default_factory=list)


def _parse_queue() -> List[Task]:
    if not QUEUE_FILE.exists():
        return []
    text = QUEUE_FILE.read_text(encoding="utf-8")
    tasks: List[Task] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("- `"):
            continue
        # Extract task id
        m = re.match(r"^- `([^`]+)`:", line)
        if not m:
            continue
        task_id = m.group(1)
        # Extract description between first `:` and `[priority=`
        desc_m = re.search(r":\s*(.*?)\s*\[priority=", line, re.DOTALL)
        desc = desc_m.group(1).strip().strip('"') if desc_m else ""
        # Extract priority
        prio_m = re.search(r"priority=(\d+)", line)
        prio = int(prio_m.group(1)) if prio_m else 2
        # Extract status
        status_m = re.search(r"status=([^,\]]+)", line)
        status = status_m.group(1).strip() if status_m else "pending"
        # Extract deps
        deps: List[str] = []
        deps_m = re.search(r"deps=([^\]]+)", line)
        if deps_m:
            deps = [d.strip() for d in deps_m.group(1).split(",") if d.strip()]
        tasks.append(
            Task(
                id=task_id,
                type=task_id.split("-", 1)[0],
                description=desc,
                priority=prio,
                status=status,
                dependencies=deps,
            )
        )
    return tasks


def _write_queue(tasks: List[Task]) -> None:
    lines = ["# Optimization Queue", ""]
    for task in tasks:
        deps = f", deps={', '.join(task.dependencies)}" if task.dependencies else ""
        lines.append(
            f"- `{task.id}`: \"{task.description}\" [priority={task.priority}, status={task.status}{deps}]"
        )
    QUEUE_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_task_status(task_id: str, status: str) -> None:
    tasks = _parse_queue()
    for task in tasks:
        if task.id == task_id:
            task.status = status
            break
    _write_queue(tasks)


def _next_pending(tasks: List[Task]) -> Optional[Task]:
    ready = [t for t in tasks if t.status == "pending" and all(d in [x.id for x in tasks if x.status == "done"] for d in t.dependencies)]
    if not ready:
        return None
    return sorted(ready, key=lambda t: t.priority)[0]


def _build_prompt(task: Task) -> str:
    role_file = ROLES_DIR / f"{task.type}.md"
    if role_file.exists():
        role_text = role_file.read_text(encoding="utf-8")
    else:
        role_text = "You are a helpful assistant working on GUI optimization."

    extra = ""
    if task.type == "research":
        extra = "\n\nSearch the internet for the latest Arknights / Hypergryph / Endfield UI design references. Save findings to docs/design/research/."
    elif task.type == "audit":
        extra = "\n\nAudit the current GUI code under src/gui/pyqt6/ and write findings to docs/design/audits/."
    elif task.type == "implement":
        extra = "\n\nImplement the smallest possible change to improve GUI/theme/style/interaction. Do NOT touch core logic."

    return f"""{role_text}

## Current Task
- ID: {task.id}
- Description: {task.description}
- Constraints:
  - Only modify GUI/theme/style/interaction code under src/gui/pyqt6/
  - Do NOT modify core logic in src/core/, src/cli/, 3rd-part/
  - After changes: git add -A && git commit -m "feat(gui): ..." && git push
  - Update docs/TASK_LOG.md with the change
{extra}"""


def _spawn_agent(prompt: str) -> None:
    print(f"Spawning sub-agent with prompt length={len(prompt)}")
    print("--- PROMPT START ---")
    print(prompt)
    print("--- PROMPT END ---")


def cmd_status(args: List[str]) -> int:
    tasks = _parse_queue()
    if not tasks:
        print("Queue is empty.")
        return 0
    print(f"{'ID':<20} {'Status':<10} {'Priority':<8} Description")
    print("-" * 80)
    for task in tasks:
        print(f"{task.id:<20} {task.status:<10} {task.priority:<8} {task.description}")
    return 0


def cmd_enqueue(args: List[str]) -> int:
    if len(args) < 2:
        print("Usage: orchestrator.py enqueue <type> <description> [priority]")
        return 1
    task_type = args[0]
    description = args[1]
    priority = int(args[2]) if len(args) > 2 else 2
    existing = _parse_queue()
    idx = len(existing) + 1
    task_id = f"{task_type}-{idx:03d}"
    existing.append(Task(id=task_id, type=task_type, description=description, priority=priority))
    _write_queue(existing)
    print(f"Enqueued: {task_id}")
    return 0


def cmd_reserve(args: List[str]) -> int:
    tasks = _parse_queue()
    task = _next_pending(tasks)
    if task is None:
        print("No pending tasks ready for execution.")
        return 0
    _update_task_status(task.id, "in_progress")
    print(f"Reserved: {task.id}")
    prompt = _build_prompt(task)
    _spawn_agent(prompt)
    return 0


def cmd_done(args: List[str]) -> int:
    if not args:
        print("Usage: orchestrator.py done <task_id>")
        return 1
    task_id = args[0]
    _update_task_status(task_id, "done")
    print(f"Marked done: {task_id}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print("Usage: orchestrator.py <status|enqueue|reserve|done> ...")
        return 1
    cmd = argv[0]
    rest = argv[1:]
    if cmd == "status":
        return cmd_status(rest)
    if cmd == "enqueue":
        return cmd_enqueue(rest)
    if cmd == "reserve":
        return cmd_reserve(rest)
    if cmd == "done":
        return cmd_done(rest)
    print(f"Unknown command: {cmd}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
