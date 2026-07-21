"""实例管理器与实例上下文。

主要组件：
    - :class:`InstanceContext` : 单实例运行时上下文（聚合 bridge / queue_state /
      scheduler / frame worker 等实例私有资源）
    - :class:`InstanceManager` : 全局单例，管理实例注册表 + 活动实例切换 +
      实例 CRUD（create / delete / clone）

线程模型：
    - GUI 主线程操作实例切换、创建、删除
    - 每个实例的 CLIBridge 持有独立 QProcess（驻主线程）
    - 实例上下文通过 :func:`set_thread_instance_id` 在主线程切换

LLM 共享：
    - 本地 llama-server 进程内单例（按 port）
    - 云端 API 通过全局 .env 共享凭据
    - 所有 InstanceContext 调 ``LlamaServerRuntime.get_instance(config)`` 拿到同一对象
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from core.foundation.instance import (
    DEFAULT_INSTANCE_ID,
    get_instance_root,
    get_instances_root,
    is_valid_instance_id,
    set_thread_instance_id,
)
from core.foundation.logger import LogCategory, get_logger
from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.queue_state import QueueState
from gui.pyqt6.scheduled_task_scheduler import ScheduledTaskScheduler
from gui.pyqt6.scheduled_task_store import ScheduledTaskStore
from .registry import InstanceMeta, InstanceRegistry, PRESET_COLORS


class InstanceContext(QObject):
    """单个实例的运行时上下文。

    聚合该实例所有私有资源：
        - :class:`CLIBridge` : 独占的 CLI 子进程（通过 ``--instance <id>`` 路由）
        - :class:`QueueState` : 该实例的队列状态
        - :class:`ScheduledTaskStore` : 该实例的定时任务列表
        - :class:`ScheduledTaskScheduler` : 该实例的定时任务调度器

    每个 InstanceContext 在创建时即设置 thread-local 实例上下文，使后续
    构造的组件（IstinaRuntime 等）自动读取该实例的配置路径。
    """

    # 任务运行状态变化信号（用于 sidebar 蓝点指示）
    task_running_changed = pyqtSignal(str, bool)  # instance_id, running
    # 设备连接状态变化信号
    connection_changed = pyqtSignal(str, bool)    # instance_id, connected
    # 完成且未读状态变化信号（用于 sidebar 绿点指示）
    completed_unread_changed = pyqtSignal(str, bool)  # instance_id, unread

    def __init__(self, meta: InstanceMeta, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._meta = meta
        self._logger = get_logger(f"instance.{meta.id}")

        # 在当前线程临时切换实例上下文，构造实例私有组件
        prev_iid = self._set_thread_context()
        try:
            self._bridge = CLIBridge(parent=self, instance_id=meta.id)
            self._queue_state = QueueState(instance_id=meta.id)
            self._task_store = ScheduledTaskStore(instance_id=meta.id)
            self._scheduler = ScheduledTaskScheduler(
                self._task_store, self._bridge, parent=self,
            )
        finally:
            set_thread_instance_id(prev_iid)

        # 运行时状态
        self._task_running: bool = False
        self._connected: bool = False
        self._started: bool = False
        self._completed_unread: bool = False

    # ------------------------------------------------------------------
    # 实例上下文切换
    # ------------------------------------------------------------------
    def _set_thread_context(self) -> str:
        """将当前线程的实例上下文切换到本实例，返回之前的实例 id。"""
        from core.foundation.instance import get_instance_id
        prev = get_instance_id()
        set_thread_instance_id(self._meta.id)
        return prev

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------
    @property
    def id(self) -> str:
        return self._meta.id

    @property
    def meta(self) -> InstanceMeta:
        return self._meta

    @property
    def is_default(self) -> bool:
        return self._meta.is_default

    @property
    def bridge(self) -> CLIBridge:
        return self._bridge

    @property
    def queue_state(self) -> QueueState:
        return self._queue_state

    @property
    def task_store(self) -> ScheduledTaskStore:
        return self._task_store

    @property
    def scheduler(self) -> ScheduledTaskScheduler:
        return self._scheduler

    @property
    def is_task_running(self) -> bool:
        return self._task_running

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_completed_unread(self) -> bool:
        return self._completed_unread

    @property
    def instance_root(self) -> Path:
        return get_instance_root(self._meta.id)

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def start(self) -> None:
        """启动实例（启动定时任务调度器）。

        CLIBridge 在首次 execute 时自动拉起 CLI 子进程，无需显式启动。
        """
        if self._started:
            return
        try:
            self._scheduler.start()
            self._started = True
            self._logger.info(LogCategory.GUI, "实例已启动", instance=self._meta.id)
        except Exception as exc:
            self._logger.error(LogCategory.GUI, "实例启动失败", instance=self._meta.id, error=str(exc))

    def stop(self) -> None:
        """停止实例（停止调度器，但保留 CLI 子进程以便快速恢复）。"""
        if not self._started:
            return
        try:
            self._scheduler.stop()
            self._started = False
            self._logger.info(LogCategory.GUI, "实例已停止", instance=self._meta.id)
        except Exception as exc:
            self._logger.error(LogCategory.GUI, "实例停止失败", instance=self._meta.id, error=str(exc))

    def destroy(self) -> None:
        """彻底销毁实例（停止一切，断开设备，杀 CLI 子进程）。"""
        try:
            self.stop()
        except Exception:
            pass
        try:
            # 尝试断开设备
            if self._connected:
                self._bridge.execute("system disconnect", {})
        except Exception:
            pass
        # 终止 CLI 子进程
        proc = getattr(self._bridge, "_process", None)
        if proc is not None:
            try:
                proc.kill()
                proc.waitForFinished(2000)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 状态更新
    # ------------------------------------------------------------------
    def set_task_running(self, running: bool) -> None:
        if self._task_running == running:
            return
        self._task_running = running
        self.task_running_changed.emit(self._meta.id, running)

    def set_connected(self, connected: bool) -> None:
        if self._connected == connected:
            return
        self._connected = connected
        self.connection_changed.emit(self._meta.id, connected)

    def set_completed_unread(self, unread: bool) -> None:
        """设置"完成且未读"状态。

        当非活动实例的任务完成时设为 True（显示绿点）；
        用户切换到该实例时设为 False（清除绿点）。
        """
        if self._completed_unread == unread:
            return
        self._completed_unread = unread
        self.completed_unread_changed.emit(self._meta.id, unread)

    # ------------------------------------------------------------------
    # 激活/失活
    # ------------------------------------------------------------------
    def activate(self) -> None:
        """切换到此实例时调用：设置 thread-local + 启动调度器（若未启动）。"""
        set_thread_instance_id(self._meta.id)
        if not self._started:
            self.start()

    def deactivate(self) -> None:
        """从此实例切走时调用：可选地停止调度器以节省资源。

        当前实现：保持调度器运行，让非 active 实例的定时任务也能触发。
        """
        # 不停 scheduler：让定时任务在后台继续工作
        pass


class InstanceManager(QObject):
    """实例注册表与活动实例管理（全局单例）。

    信号：
        - :attr:`instance_changed` : 活动实例切换后发射
        - :attr:`instance_created` : 新实例创建后发射
        - :attr:`instance_deleted` : 实例删除后发射
        - :attr:`instance_meta_changed` : 实例元数据更新后发射（重命名/改色）
    """

    instance_changed = pyqtSignal(str)              # new_instance_id
    instance_created = pyqtSignal(str)              # new_instance_id
    instance_deleted = pyqtSignal(str)              # deleted_instance_id
    instance_meta_changed = pyqtSignal(str)         # instance_id
    instances_reloaded = pyqtSignal()               # 列表整体刷新

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._logger = get_logger("instance.manager")
        self._registry = InstanceRegistry()
        self._contexts: Dict[str, InstanceContext] = {}
        self._active_id: str = self._registry.active_id

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------
    @property
    def registry(self) -> InstanceRegistry:
        return self._registry

    @property
    def active_id(self) -> str:
        return self._active_id

    def list_metas(self) -> List[InstanceMeta]:
        return self._registry.list_metas()

    # ------------------------------------------------------------------
    # 上下文访问
    # ------------------------------------------------------------------
    def get_context(self, instance_id: str) -> InstanceContext:
        """获取或懒加载实例上下文。"""
        if instance_id in self._contexts:
            return self._contexts[instance_id]
        meta = self._registry.get_meta(instance_id)
        if meta is None:
            raise KeyError(f"实例不存在: {instance_id!r}")
        ctx = InstanceContext(meta, parent=self)
        self._contexts[instance_id] = ctx
        return ctx

    def get_active_context(self) -> InstanceContext:
        return self.get_context(self._active_id)

    def has_context(self, instance_id: str) -> bool:
        return instance_id in self._contexts

    # ------------------------------------------------------------------
    # 切换活动实例
    # ------------------------------------------------------------------
    def set_active(self, instance_id: str) -> bool:
        """切换活动实例。

        Returns:
            True 若切换成功，False 若实例不存在或已是活动实例
        """
        if instance_id == self._active_id:
            return False
        if self._registry.get_meta(instance_id) is None:
            self._logger.warning(LogCategory.GUI, "切换失败：实例不存在", instance=instance_id)
            return False

        # 通知旧实例失活
        prev_ctx = self._contexts.get(self._active_id)
        if prev_ctx is not None:
            prev_ctx.deactivate()

        # 加载并激活新实例
        new_ctx = self.get_context(instance_id)
        new_ctx.activate()

        # 更新注册表 active
        try:
            self._registry.set_active(instance_id)
        except Exception as exc:
            self._logger.warning(LogCategory.GUI, "更新注册表 active 失败", error=str(exc))

        self._active_id = instance_id
        self.instance_changed.emit(instance_id)
        self._logger.info(LogCategory.GUI, "活动实例已切换", instance=instance_id)
        return True

    # ------------------------------------------------------------------
    # 实例 CRUD
    # ------------------------------------------------------------------
    def create(
        self,
        display_name: str,
        color: str = "#3B82F6",
        clone_from: Optional[str] = None,
    ) -> str:
        """创建新实例。

        Args:
            display_name: 实例显示名（用于侧栏 + 标题栏）
            color: 实例主题色（HEX 格式，如 "#3B82F6"）
            clone_from: 可选，从指定实例克隆配置（client_config.json +
                maaend_task_state.json + scheduled_tasks.json）。None 则
                从 client_config.example.json 创建空配置。

        Returns:
            新实例的 id
        """
        instance_id = self._generate_instance_id(display_name)
        if instance_id == DEFAULT_INSTANCE_ID:
            # display_name 生成 id 与 default 冲突，重新生成
            instance_id = self._generate_instance_id(f"{display_name}_2")

        # 创建实例目录
        instance_root = get_instances_root() / instance_id
        instance_root.mkdir(parents=True, exist_ok=True)
        (instance_root / "config").mkdir(exist_ok=True)
        (instance_root / "cache").mkdir(exist_ok=True)
        (instance_root / "logs").mkdir(exist_ok=True)
        (instance_root / "scripts" / "recorded").mkdir(parents=True, exist_ok=True)

        # 拷贝配置
        config_dst = instance_root / "config" / "client_config.json"
        if clone_from is not None:
            clone_root = get_instance_root(clone_from)
            for fname in ("client_config.json", "maaend_task_state.json", "scheduled_tasks.json"):
                src = clone_root / "config" / fname
                if src.exists():
                    shutil.copy2(src, instance_root / "config" / fname)
        else:
            # 从 example 创建
            project_root = get_instance_root(DEFAULT_INSTANCE_ID)
            example = project_root / "config" / "client_config.example.json"
            if example.exists():
                shutil.copy2(example, config_dst)
            else:
                # example 不存在，写一个最小配置
                config_dst.write_text(
                    '{"device": {"serial": "", "emulator_path": ""}, "llm": {}}',
                    encoding="utf-8",
                )

        # 注册元数据
        sort_order = max((m.sort_order for m in self._registry.list_metas()), default=-1) + 1
        meta = InstanceMeta(
            instance_id=instance_id,
            display_name=display_name,
            color=color,
            sort_order=sort_order,
        )
        self._registry.upsert_meta(meta)
        self.instance_created.emit(instance_id)
        self._logger.info(LogCategory.GUI, "实例已创建", instance=instance_id, display_name=display_name)
        return instance_id

    def delete(self, instance_id: str) -> bool:
        """删除实例。

        - ``default`` 实例不可删除
        - 若删除的是当前活动实例，自动切换回 default
        - 同时删除 instances/<id>/ 目录

        Returns:
            True 若删除成功
        """
        if instance_id == DEFAULT_INSTANCE_ID:
            self._logger.warning(LogCategory.GUI, "禁止删除 default 实例")
            return False
        if self._registry.get_meta(instance_id) is None:
            return False

        # 若是当前活动实例，先切换回 default
        if instance_id == self._active_id:
            self.set_active(DEFAULT_INSTANCE_ID)

        # 销毁上下文
        ctx = self._contexts.pop(instance_id, None)
        if ctx is not None:
            ctx.destroy()

        # 删除实例目录
        instance_root = get_instances_root() / instance_id
        try:
            shutil.rmtree(instance_root, ignore_errors=True)
        except Exception as exc:
            self._logger.warning(LogCategory.GUI, "删除实例目录失败", instance=instance_id, error=str(exc))

        # 从注册表移除
        self._registry.remove_meta(instance_id)
        self.instance_deleted.emit(instance_id)
        self._logger.info(LogCategory.GUI, "实例已删除", instance=instance_id)
        return True

    def update_meta(
        self,
        instance_id: str,
        display_name: Optional[str] = None,
        color: Optional[str] = None,
    ) -> bool:
        """更新实例元数据（重命名/改色）。"""
        meta = self._registry.get_meta(instance_id)
        if meta is None:
            return False
        if display_name is not None and display_name.strip():
            meta.display_name = display_name.strip()
        if color is not None and color.strip():
            meta.color = color.strip()
        self._registry.upsert_meta(meta)
        # 若上下文已加载，更新其 meta 引用
        ctx = self._contexts.get(instance_id)
        if ctx is not None:
            ctx._meta = meta
        self.instance_meta_changed.emit(instance_id)
        return True

    # ------------------------------------------------------------------
    # 启动初始化
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        """启动时调用：加载注册表 + 初始化活动实例。"""
        # 懒加载活动实例（构造 bridge、scheduler 等）
        try:
            active_ctx = self.get_context(self._active_id)
            active_ctx.activate()
        except Exception as exc:
            self._logger.error(LogCategory.GUI, "活动实例初始化失败", instance=self._active_id, error=str(exc))
            # 回退到 default
            if self._active_id != DEFAULT_INSTANCE_ID:
                self._active_id = DEFAULT_INSTANCE_ID
                try:
                    self.get_context(DEFAULT_INSTANCE_ID).activate()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------
    def _generate_instance_id(self, display_name: str) -> str:
        """根据 display_name 生成合法且唯一的 instance_id。

        规则：
            - 中文转拼音首字母（简化处理：保留 ASCII，过滤其它）
            - 转小写，空格替换为下划线
            - 保留 a-z 0-9 _ -
            - 与已有 id 冲突时追加 _2 / _3 ...
            - 长度限制 32 字符
        """
        import re
        # 简化：保留 ASCII 字母/数字，空格转下划线，其它过滤
        raw = display_name.strip().lower()
        raw = re.sub(r"\s+", "_", raw)
        raw = re.sub(r"[^a-z0-9_-]", "", raw)
        if not raw:
            raw = "instance"
        # 截断到 28 字符，留 4 字符给 _N 后缀
        raw = raw[:28]
        candidate = raw
        n = 2
        existing_ids = {m.id for m in self._registry.list_metas()}
        while candidate in existing_ids:
            suffix = f"_{n}"
            candidate = raw[: 32 - len(suffix)] + suffix
            n += 1
        return candidate


__all__ = [
    "InstanceContext",
    "InstanceManager",
    "InstanceMeta",
    "PRESET_COLORS",
]
