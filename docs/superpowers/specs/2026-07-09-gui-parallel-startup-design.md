# GUI 启动并行加载设计：自动重连 + 列表加载

## 1. 问题

启动时，`MaaEndControlPage._delayed_init()` 串行执行两个阻塞操作：

1. `_try_auto_connect()` — 最长 15 秒
2. `refresh()` — 若缓存为空，需发起 `metadata list`，约数秒

用户在启动阶段看到空白界面约 15-20 秒，预览定时器也被停止。

## 2. 目标

- 列表渲染延迟降至 **零阻塞**
- 自动重连与列表加载并行执行，互不等待
- 预览定时器在合适时机自动恢复
- 保持 Qt 主线程响应，界面即时可见

## 3. 设计方案

### 3.1 整体架构

采用 **B + C 合并方案**：

- **B（QThread 并行 worker）**：自动重连和元数据加载各自放入 `QThread`，通过 Qt 信号-槽机制安全回调主线程
- **C（缓存优先渲染）**：启动时立即用本地缓存渲染任务/预设列表，不等待任何网络/子进程结果

```
_delayed_init()
    ├── 1. 停止预览定时器
    ├── 2. refresh()               ← 走缓存分支，立即渲染列表
    ├── 3. 启动 AutoConnectWorker  ← 后台线程
    └── 4. 启动 MetadataLoadWorker ← 后台线程
        └── 两者并行运行，完成后通过信号回调
```

### 3.2 新增组件

#### `AutoConnectWorker(QThread)`

```python
class AutoConnectWorker(QThread):
    finished = pyqtSignal(bool)  # success

    def __init__(self, sync_execute, params: dict):
        super().__init__()
        self._sync_execute = sync_execute
        self._params = params

    def run(self) -> None:
        result = self._sync_execute("system connect", self._params, timeout_ms=15000)
        self.finished.emit(bool(result and result.get("status") == "success"))
```

#### `MetadataLoadWorker(QThread)`

```python
class MetadataLoadWorker(QThread):
    finished = pyqtSignal(dict)  # raw result

    def __init__(self, sync_execute):
        super().__init__()
        self._sync_execute = sync_execute

    def run(self) -> None:
        result = self._sync_execute("metadata list", timeout_ms=10000)
        self.finished.emit(result or {})
```

### 3.3 修改点

#### `_delayed_init`（`maaend_control_page.py:1232`）

```python
def _delayed_init(self) -> None:
    """延迟初始化：立即渲染缓存列表，后台并行执行重连和元数据加载。"""
    preview_timer = getattr(self.window(), "_preview_timer", None)
    if preview_timer is not None:
        preview_timer.stop()

    # C: 立即用缓存渲染列表
    self.refresh()

    # B: 启动两个后台 worker
    self._auto_connect_worker = AutoConnectWorker(
        self._bridge, self._resolve_connect_params()
    )
    self._auto_connect_worker.finished.connect(self._on_auto_connect_finished)
    self._auto_connect_worker.start()

    self._metadata_worker = MetadataLoadWorker(self._bridge)
    self._metadata_worker.finished.connect(self._on_metadata_loaded)
    self._metadata_worker.start()
```

#### 新增回调方法

```python
def _on_auto_connect_finished(self, success: bool) -> None:
    if success:
        self._connected = True
        self._auto_connect_attempted = False
        self._append_log("系统", locale.tr("auto_connect_success", "Auto-connect succeeded at startup"))
    else:
        self._auto_connect_attempted = True
        self._append_log("系统", locale.tr("auto_connect_failed", "Auto-connect failed at startup, will not retry."))

    preview_timer = getattr(self.window(), "_preview_timer", None)
    if preview_timer is not None and self._connected:
        preview_timer.start()

def _on_metadata_loaded(self, result: dict) -> None:
    if result and result.get("status") == "success":
        self._tasks_cache = result.get("tasks") or {}
        self._task_option_defs = result.get("task_option_defs") or {}
        self._presets_cache = result.get("presets") or {}
        self._persist_metadata_cache()
    self.refresh()
```

#### 删除 `_try_auto_connect`（`maaend_control_page.py:1246`）

原有方法被 `AutoConnectWorker` 替代，直接移除。

#### Worker 清理（`closeEvent` 或析构）

为避免页面销毁时 worker 仍在运行，在 `MaaEndControlPage` 的 `closeEvent` 中追加清理：

```python
def closeEvent(self, event: QCloseEvent) -> None:
    for worker in (self._auto_connect_worker, self._metadata_worker):
        if worker is not None and worker.isRunning():
            worker.quit()
            worker.wait(500)
    super().closeEvent(event)
```

### 3.4 缓存机制说明

`_refresh_task_list` 和 `_refresh_preset_list` 已包含缓存优先逻辑：

```python
def _refresh_task_list(self):
    if not self._tasks_cache:          # 缓存命中时，直接渲染，不发起 CLI 调用
        result = self._sync_execute("metadata list", timeout_ms=10000)
        ...
```

启动时调用 `refresh()` 会立即渲染列表（若缓存存在），否则显示空列表，等待后台 `MetadataLoadWorker` 完成后再填充。

## 4. 关键风险与缓解

| 风险 | 缓解 |
|------|------|
| `_sync_execute` 跨线程调用 | `commandFinished` 通过 Qt `AutoConnection` → `QueuedConnection`，`QEventLoop` 在 worker 线程中处理事件，无需同步锁 |
| 两个 worker 同时完成竞争回调 | Qt 单线程事件循环保证信号串行处理 |
| 缓存过期导致列表错误 | 连接成功后自动触发一次静默刷新；若手动刷新时仍无网络，用户可见空列表 |
| worker 未完成时页面销毁 | `closeEvent` 中调用 `worker.quit()` + `worker.wait(500)` 强制退出 |
| 重复启动 worker | 每次只有一个 `AutoConnectWorker`；连接成功后通过 `refresh()` 直接刷新，不再创建新 worker |

## 5. 影响面

- **修改**：`_delayed_init`、`closeEvent`、新增 `AutoConnectWorker`、`MetadataLoadWorker`、`_on_auto_connect_finished`、`_on_metadata_loaded`
- **删除**：`_try_auto_connect`
- **不变**：`_ensure_connected`、`refresh()`、`_refresh_task_list`、`_refresh_preset_list`、`MainWindow` 所有逻辑、`CLIBridge` 所有逻辑

## 6. 测试策略

1. **单元测试**：新增测试验证 `AutoConnectWorker` 和 `MetadataLoadWorker` 正确运行并发射信号
2. **现有测试**：`test_control_page_connect_uses_last_connected_device` 需适配（`_sync_execute` 不在主线程调用时行为一致）
3. **手动验证**：
   - 启动 GUI，观察列表是否立即可见（缓存路径）
   - 观察日志中 "Auto-connect succeeded/failed" 是否在后台输出
   - 观察预览定时器是否在连接成功后恢复
4. **性能对比**：记录启动到列表可见的时间，目标从 15s → <500ms

## 7. 与现有架构一致性

- 项目已有 `TaskRunWorker(QThread)` 先例（`maaend_control_page.py:1439`），风格一致
- `_sync_execute` 基于 `QEventLoop` + 信号，天然支持跨线程 queued connection
- 不改变任何公共 API，仅私有方法重构

## 8. 实施顺序

1. 新增两个 Worker 类（`maaend_control_page.py:1439` 后追加）
2. 修改 `_delayed_init`（`maaend_control_page.py:1232`）
3. 新增回调方法（`maaend_control_page.py:1258` 后追加）
4. 在 `closeEvent` 中追加 worker 清理逻辑
5. 删除 `_try_auto_connect`（`maaend_control_page.py:1246`）
6. 运行 `pytest` 验证
7. 手动启动 GUI 验证体验
