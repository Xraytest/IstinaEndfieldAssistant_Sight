"""Instance context management (multi-instance support).

IEA supports running multiple independent instances in the same GUI process.
Each instance corresponds to an independent game device (emulator/real device)
and its complete settings. Configuration, queue, scheduled tasks, cache, logs,
script recordings, and window state are isolated between instances; LLM (local
llama-server / cloud API) is globally shared.

Instance id rules:
    - Must match ``^[a-zA-Z0-9_-]{1,32}$``
    - ``default`` is the reserved instance, using project root as its data root
      (backward compatibility)
    - Other instances' data root is ``<project_root>/instances/<id>/``

Threading model:
    - Instance context is propagated in-process via thread-local variable
    - GUI main thread switches instance via :class:`InstanceContextGuard`
    - CLI subprocess sets it early via ``--instance <id>`` argument
    - Default instance ``default`` is always available, no explicit setup needed
"""

from __future__ import annotations

import re
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from .paths import get_project_root


# Instance id validation: 1-32 letters/digits/underscores/hyphens
_INSTANCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")

# Reserved instance id
_DEFAULT_INSTANCE_ID = "default"
# Public alias (for external modules to import, avoiding private underscore prefix)
DEFAULT_INSTANCE_ID = _DEFAULT_INSTANCE_ID

# thread-local context: stores current thread's instance id
_context_local = threading.local()

# Process-level current instance id (fallback when thread-local not set)
_process_instance_id: str = _DEFAULT_INSTANCE_ID

# Instance context lock: protects _process_instance_id and set_instance_id calls
_instance_lock = threading.RLock()


def is_valid_instance_id(instance_id: str) -> bool:
    """Check if instance id is valid."""
    if not isinstance(instance_id, str):
        return False
    return bool(_INSTANCE_ID_PATTERN.match(instance_id))


def normalize_instance_id(instance_id: Optional[str]) -> str:
    """Normalize instance id: empty/None returns default, else validate and return."""
    if not instance_id or not instance_id.strip():
        return _DEFAULT_INSTANCE_ID
    iid = instance_id.strip()
    if not is_valid_instance_id(iid):
        raise ValueError(
            f"Invalid instance_id: {instance_id!r} (only 1-32 letters/digits/underscores/hyphens allowed)"
        )
    return iid


def set_instance_id(instance_id: Optional[str]) -> str:
    """Set **process-level** current instance id (also syncs to thread-local).

    Called once at GUI process startup or CLI subprocess entry. GUI instance
    switching uses :func:`set_thread_instance_id` to only modify thread-local,
    avoiding affecting other threads.

    Returns:
        Normalized instance id
    """
    iid = normalize_instance_id(instance_id)
    with _instance_lock:
        global _process_instance_id
        _process_instance_id = iid
    _context_local.instance_id = iid
    return iid


def set_thread_instance_id(instance_id: Optional[str]) -> str:
    """Set only the current thread's instance id (does not affect process-level default).

    Called by GUI main thread when switching instances, used with
    :class:`InstanceContextGuard`.
    """
    iid = normalize_instance_id(instance_id)
    _context_local.instance_id = iid
    return iid


def get_instance_id() -> str:
    """Get the currently active instance id.

    Returns thread-local context value first, otherwise falls back to
    process-level default.
    """
    iid = getattr(_context_local, "instance_id", None)
    if iid:
        return iid
    with _instance_lock:
        return _process_instance_id


def get_instance_root(instance_id: Optional[str] = None) -> Path:
    """Get instance private data root directory.

    - ``default`` instance returns project root (backward compat with old layout)
    - Other instances return ``<project_root>/instances/<id>/``

    Note: returned path may not exist, caller should
    ``mkdir(parents=True, exist_ok=True)`` as needed.
    """
    iid = instance_id or get_instance_id()
    if iid == _DEFAULT_INSTANCE_ID:
        return get_project_root()
    return get_project_root() / "instances" / iid


def get_instances_root() -> Path:
    """Get parent directory of all instances ``<project_root>/instances/``."""
    return get_project_root() / "instances"


def get_instance_subdir(name: str, instance_id: Optional[str] = None) -> Path:
    """Get instance private subdirectory (auto-created).

    Args:
        name: Subdirectory name, e.g. ``config``, ``cache``, ``logs``, ``scripts/recorded``
        instance_id: Optional instance id, defaults to current instance

    Returns:
        Path: ``<instance_root>/<name>`` directory (created)
    """
    # Path traversal defense
    if ".." in Path(name).parts:
        raise ValueError(f"Invalid instance subdirectory name (possible path traversal): {name!r}")
    p = get_instance_root(instance_id) / name
    resolved = p.resolve()
    instance_root = get_instance_root(instance_id).resolve()
    if not str(resolved).startswith(str(instance_root)):
        raise ValueError(f"Instance subdirectory out of bounds: {name!r}")
    p.mkdir(parents=True, exist_ok=True)
    return p


@contextmanager
def instance_context(instance_id: str):
    """Context manager: within the with block, all :func:`get_instance_id`
    returns this instance id.

    Usage::

        with instance_context("account_2"):
            runtime = IstinaRuntime()  # auto-reads account_2's config
    """
    prev = get_instance_id()
    set_thread_instance_id(instance_id)
    try:
        yield instance_id
    finally:
        set_thread_instance_id(prev)


class InstanceContextGuard:
    """RAII-style instance context guard.

    Equivalent to :func:`instance_context`, provides class form for scenarios
    needing explicit start/stop::

        guard = InstanceContextGuard("account_2")
        guard.__enter__()
        try:
            ...
        finally:
            guard.__exit__(None, None, None)
    """

    def __init__(self, instance_id: str) -> None:
        self._instance_id = normalize_instance_id(instance_id)
        self._prev: Optional[str] = None

    def __enter__(self) -> str:
        self._prev = get_instance_id()
        set_thread_instance_id(self._instance_id)
        return self._instance_id

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._prev is not None:
            set_thread_instance_id(self._prev)
        else:
            set_thread_instance_id(_DEFAULT_INSTANCE_ID)


__all__ = [
    "DEFAULT_INSTANCE_ID",
    "InstanceContextGuard",
    "get_instance_id",
    "get_instance_root",
    "get_instance_subdir",
    "get_instances_root",
    "instance_context",
    "is_valid_instance_id",
    "normalize_instance_id",
    "set_instance_id",
    "set_thread_instance_id",
]
