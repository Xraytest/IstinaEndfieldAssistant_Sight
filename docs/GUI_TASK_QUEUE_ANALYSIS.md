# GUI 任务队列执行失败分析

## 1. 委托链执行路径

```
GUI (MaaEndControlPage)
├── _run_queue()                    # 点击"运行"按钮
│   └── _start_execution()
│       └── TaskRunWorker (QThread)
│           └── _runtime_queue_runner()
│               ├── for entry in self._queue_items:
│               │   ├── _sync_execute("preset run {name}")  或
│               │   └── _sync_execute("task run {name} --options {payload}")
│               │       └── QEventLoop 等待 commandFinished 信号
│               └── 返回 True/False
└── _on_execution_finished(success)
    └── _update_execution_ui()
```

`_sync_execute()` 的工作流程：
1. 创建 `QEventLoop`
2. 连接 `commandFinished` 信号到 `_on_finished`
3. 调用 `self._bridge.execute(command, params)` → 启动 CLI 子进程
4. `QTimer.singleShot(timeout_ms, loop.quit)` 启动超时定时器
5. `loop.exec()` 阻塞等待
6. 收到信号或超时后，断开连接，返回结果

---

## 2. 发现的 5 个关键错误

### 错误 1：默认超时 1200ms（P0 — 直接导致任务全部失败）

**位置**：`_sync_execute()` 默认参数 `timeout_ms: int = 1200`

**现象**：
```python
def _sync_execute(self, command, params=None, timeout_ms=1200):
    ...
    QTimer.singleShot(timeout_ms, loop.quit)  # 1.2 秒后强制退出
    loop.exec()
```

**根本原因**：
- 任务执行（`task run` / `preset run`）通常需要 **数秒到数分钟**
- 1.2 秒超时远远不够，导致 `loop.exec()` 在任务完成前就超时退出
- 返回 `None`，`_runtime_queue_runner` 判定为失败：
  ```python
  ok = bool(result and result.get("status") == "success")  # result 是 None → False
  ```
- 队列中第一个任务失败后立即 `return False`，后续任务全部跳过

**影响**：GUI 中所有任务队列执行都会在 1.2 秒后超时失败，无论任务实际是否成功。

---

### 错误 2：预览定时器干扰任务执行（P1 — 导致间歇性失败）

**位置**：`_preview_timer` 每 1500ms 触发 `_refresh_preview()`

**现象**：
```python
self._preview_timer = QTimer(self)
self._preview_timer.setInterval(1500)  # 1.5 秒
self._preview_timer.timeout.connect(self._refresh_preview)

def _refresh_preview(self):
    result = self._sync_execute("screenshot")  # 也会走 _sync_execute
    ...
```

**根本原因**：
- 任务执行期间，预览定时器仍在运行（`showEvent` 启动，`hideEvent` 停止）
- 每次定时器触发都会调用 `_sync_execute("screenshot")`，发送 `screenshot` 命令到同一个 CLI 进程
- CLI 进程是单进程的，`_pending_commands` 队列中的命令会排队
- 如果 `screenshot` 命令插队到正在执行的任务命令之前，或者与任务命令竞争，会导致：
  - 任务命令被延迟
  - `_sync_execute` 的信号匹配混乱（`cmd == expected`）
  - 任务超时或返回错误的结果

**影响**：任务执行期间，每 1.5 秒就会有一次截图请求插入队列，干扰任务执行。

---

### 错误 3：`_run_preset` 不自动执行队列（P2 — 行为不符合注释）

**位置**：`_run_preset()` 方法

**现象**：
```python
def _run_preset(self):
    ...
    # 队列覆盖完成后自动开始执行；外层已挡住执行中状态...
    return  # ← 只是返回，没有调用 _run_queue()
```

注释写着"队列覆盖完成后自动开始执行"，但实际代码只是清空队列、填充预设任务，然后直接返回。用户需要手动点击"运行"按钮才能执行。

**影响**：用户点击"应用预设"后，预期会自动执行，但实际上没有。

---

### 错误 4：预设任务在队列中 type 标记错误（P2 — 逻辑死代码）

**位置**：`_add_to_queue()` 方法

**现象**：
```python
# 当添加预设时
for task_entry in task_list:
    name = task_entry.get("name")
    ...
    entry = {"name": name, "display_name": name, "type": "task", ...}
    #                                                      ^^^^^^^^
    #                                                      硬编码为 "task"

# 在 _runtime_queue_runner 中
if item_type == "preset":  # ← 永远不会为 True
    result = self._sync_execute(f"preset run {name}")
else:
    result = self._sync_execute(f"task run {clean_name} --options {payload}")
```

**根本原因**：
- 预设被展平为多个任务 entry，但 `type` 被硬编码为 `"task"`
- `_runtime_queue_runner` 中的 `item_type == "preset"` 分支永远不会执行
- 如果将来需要支持队列中直接放预设（不展平），这个逻辑会有问题

**影响**：`preset run` 分支是死代码，虽然当前不影响功能（因为预设已经被展平）。

---

### 错误 5：`_sync_execute` 跨线程信号连接不安全（P3 — 边界条件）

**位置**：`_sync_execute()` 在 `TaskRunWorker` 线程中调用

**现象**：
```python
def _sync_execute(self, command, ...):
    loop = QEventLoop()
    def _on_finished(cmd, res):
        if cmd == expected:
            result = res
            loop.quit()
    self._bridge.commandFinished.connect(_on_finished)
    self._bridge.execute(expected, params or {})
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    self._bridge.commandFinished.disconnect(_on_finished)
```

**根本原因**：
- `_sync_execute` 在 worker 线程中调用，但 `commandFinished` 信号是在 GUI 主线程发射的（`QProcess` 在主线程）
- `connect` 和 `disconnect` 在不同线程中操作，虽然 Qt 支持线程安全的连接，但在 `loop.exec()` 启动之前，如果信号已经发射（极端情况），可能会丢失
- `QTimer.singleShot` 在当前线程（worker 线程）中触发，但 `loop.quit()` 需要在同一个线程中调用，这没有问题

**影响**：在极端情况下（CLI 进程极快完成），信号可能在 `loop.exec()` 启动前就已经发射并被排队，但由于 Qt 的事件队列机制，通常不会丢失。这是一个边界条件问题。

---

## 3. 修复方案

### P0 — 必须修复

**1. 为任务执行使用更长的超时时间**

```python
# 当前代码
result = self._sync_execute(f"task run {clean_name} --options {payload}")  # 1.2s 超时

# 修复后
result = self._sync_execute(f"task run {clean_name} --options {payload}", timeout_ms=300000)  # 5 分钟
```

或者更好的方式：区分"查询"和"执行"的超时：
```python
_EXECUTE_TIMEOUT_MS = 300000  # 5 分钟
_QUERY_TIMEOUT_MS = 5000      # 5 秒
_PREVIEW_TIMEOUT_MS = 3000    # 3 秒
```

**2. 任务执行期间禁用预览定时器**

```python
def _start_execution(self, target):
    self._is_executing = True
    self.stop_preview_timer()  # ← 添加
    self._update_execution_ui()
    ...

def _on_execution_finished(self, success):
    self._is_executing = False
    self.start_preview_timer()  # ← 添加
    self._update_execution_ui()
    ...
```

### P1 — 建议修复

**3. 修复 `_run_preset` 自动执行**

```python
def _run_preset(self):
    ...
    self._append_log("预设", f"已应用预设 '{_zh(self._selected_preset)}' ({len(task_list)} 个任务)")
    # 自动开始执行队列
    if self._queue_items and not self._is_executing:
        self._run_queue()
```

### P2 — 代码清理

**4. 移除死代码或修复 type 标记**

```python
# 在 _add_to_queue 中，预设展平为任务
entry = {"name": name, "display_name": name, "type": "task", ...}

# 由于 type 总是 "task"，移除 _runtime_queue_runner 中的 dead branch
# 或者保留但添加注释说明当前不会触发
```

**5. `_sync_execute` 线程安全改进**

```python
def _sync_execute(self, command, params=None, timeout_ms=1200):
    loop = QEventLoop()
    result = None
    expected = command

    def _on_finished(cmd, res):
        nonlocal result
        if cmd == expected:
            result = res
            if loop.isRunning():
                loop.quit()

    self._bridge.commandFinished.connect(_on_finished)
    self._bridge.execute(expected, params or {})
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    self._bridge.commandFinished.disconnect(_on_finished)
    return result
```

---

## 4. 根因总结

GUI 任务队列无法正确执行的**直接原因**是 `_sync_execute` 的默认超时时间（1200ms）远小于任务实际执行时间。这导致：
1. 每个任务都在 1.2 秒后超时
2. `_runtime_queue_runner` 判定为失败
3. 队列立即终止

**次要原因**是预览定时器（1.5 秒间隔）在任务执行期间持续发送 `screenshot` 命令，干扰 CLI 进程的命令队列。

这两者共同导致 GUI 中任务队列完全无法正常工作。
