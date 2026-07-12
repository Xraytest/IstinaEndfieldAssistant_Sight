# 队列执行无效果 + 停止按钮无法终止执行 — 根因分析与修复

**日期**: 2026-07-12
**触发条件**: GUI 启动队列执行后设备未产生任何变化；点击停止按钮无法有效结束执行中的队列
**严重性**: High（核心功能不可用）

---

## 1. 根因分析

### 问题 1：启动队列执行后设备未产生任何变化

**直接原因**：`_sync_execute` 只连接 `commandFinished` 信号，不连接 `commandError` 信号。当 CLI 交互进程崩溃时（`cli_bridge.py:216-231` interactive 模式 `crashed=True` 分支），bridge emit `commandError` 但**不 emit `commandFinished`**，`_sync_execute` 的 `loop.exec()` 无法退出，等待 300s 超时。期间：

- `task run` 命令可能未真正执行（CLI 崩溃前未完成）
- 设备无任何变化
- UI 持续显示"运行中"
- 用户认为队列卡死

**代码位置**：
- `maaend_control_page.py:365-410`（修改前）：`_sync_execute` 仅 `commandFinished.connect`
- `cli_bridge.py:216-231`：interactive 模式崩溃分支只 emit `commandError`，不 emit `commandFinished`

**调用链**：
```
_run_queue → _start_execution → TaskRunWorker.run (子线程)
  → _runtime_queue_runner → _sync_execute("task run ...")
    → loop.exec() 等待 commandFinished
    ← CLI 崩溃 → _on_finished (cli_bridge) → emit commandError (非 commandFinished)
    → loop.exec() 永远不退出 → 等 300s 超时
```

**根本原因**：`_sync_execute` 缺少对 `commandError` 信号的处理，CLI 崩溃时无法及时退出等待。

### 问题 2：点击停止无法有效结束执行中的队列

#### 2A：自动重试定时器未被取消（MAAEND-01，批次83 已确认）

**直接原因**：`_on_execution_finished` 在执行失败时安排自动重试定时器（`QTimer.singleShot(self._retry_delay_ms, self._retry_failed)`），但 `_stop_execution` 不取消该定时器也不标记用户主动停止。

**执行序列**：
1. 用户点击停止 → `_stop_execution` → `_worker.stop()`（设置 `_stopped=True`）
2. 当前任务完成或超时 → `_runtime_queue_runner` break → 返回 False
3. `_on_execution_finished(False)` 被调用
4. 检查 `not success and self._failed_indices and self._auto_retry_enabled` → True
5. 安排 `QTimer.singleShot(2000ms, self._retry_failed)`
6. 2s 后 `_retry_failed` 触发 → `_start_execution` → 队列恢复执行
7. 用户看到"停止"后 2s 又开始执行，认为停止无效

**代码位置**：
- `maaend_control_page.py:1848-1852`（修改前）：`_stop_execution` 不设置任何停止标志
- `maaend_control_page.py:1860-1862`（修改前）：`_on_execution_finished` 无条件安排自动重试

#### 2B：`_sync_execute` 不响应停止标志

**直接原因**：`_stop_execution` 仅设置 `_worker._stopped = True` 标志，`_runtime_queue_runner` 只在每个任务**开始前**检查该标志（第 923 行）。如果当前任务正在 `_sync_execute` 的 `loop.exec()` 中阻塞，停止标志不会被检查，需要等当前任务完成或 300s 超时。

**代码位置**：
- `maaend_control_page.py:923`：`if self._worker and getattr(self._worker, '_stopped', False): break` — 仅在循环开始检查
- `maaend_control_page.py:406`（修改前）：`loop.exec()` 阻塞期间无停止检查

---

## 2. 修改方案

### 修改 1：`_sync_execute` 连接 `commandError` 信号（解决问题 1）

`maaend_control_page.py:391-396` 新增 `_on_error` 回调，CLI 崩溃或业务错误时立即退出 `loop.exec()`：

```python
def _on_error(cmd: str, msg: str):
    nonlocal result
    if cmd.split()[: len(expected)] == expected:
        result = {"status": "error", "message": msg}
        loop.quit()
```

并在 `try/finally` 中连接/断开 `commandError` 信号。

### 修改 2：`_sync_execute` 增加停止检查定时器（解决问题 2B）

`maaend_control_page.py:404-410` 新增 200ms 间隔的 `stop_check_timer`，检查 `_worker._stopped` 标志：

```python
stop_check_timer = QTimer()
stop_check_timer.setInterval(200)
def _check_stop():
    worker = self._worker
    if worker is not None and getattr(worker, '_stopped', False):
        loop.quit()
stop_check_timer.timeout.connect(_check_stop)
```

在 `loop.exec()` 期间 `start()`，退出后 `stop()`。

### 修改 3：`_stop_execution` 设置 `_user_stopped` 标志（解决问题 2A）

`maaend_control_page.py:1869-1870`：`_stop_execution` 设置 `self._user_stopped = True`。

`maaend_control_page.py:1878-1886`：`_on_execution_finished` 读取并重置 `_user_stopped`，若为 True 则跳过自动重试：

```python
user_stopped = self._user_stopped
self._user_stopped = False
...
if not success and not user_stopped and self._failed_indices and ...:
    # 安排自动重试
```

### 修改 4：`__init__` 初始化 `_user_stopped`

`maaend_control_page.py:311`：新增 `self._user_stopped = False`。

---

## 3. 影响面

### 修改涉及的函数

| 函数 | 修改内容 | 调用方 |
|------|----------|--------|
| `__init__` | 新增 `_user_stopped` 初始化 | 构造时 |
| `_sync_execute` | 连接 `commandError` + 停止检查定时器 | 预览、自动连接、队列执行、元数据加载等所有 CLI 调用 |
| `_stop_execution` | 设置 `_user_stopped = True` | 停止按钮 |
| `_on_execution_finished` | 检查 `_user_stopped` 跳过自动重试 | TaskRunWorker.finished 信号 |

### 信号连接变化

- `_sync_execute` 新增 `commandError` 信号连接（DirectConnection），在 finally 中 disconnect
- `_sync_execute` 新增 `stop_check_timer.timeout` 信号连接，在 finally 中 stop

### 调用点影响

- **预览 `_refresh_preview`**：`_sync_execute("screenshot")` 在主线程调用，`_worker` 为 None 时停止检查不触发，无影响
- **自动连接 `_do_auto_connect`**：`_sync_execute("system connect")` 在主线程调用，同上
- **队列执行 `_runtime_queue_runner`**：`_sync_execute("task run ...")` 在子线程调用，停止检查生效，`commandError` 崩溃时立即退出

---

## 4. 非期待变化与回退策略

### 非期待变化

1. **`_sync_execute` 返回值变化**：CLI 崩溃时返回 `{"status": "error", "message": "..."}` 而非 None。调用方 `ok = bool(result and result.get("status") == "success")` 仍判断为失败，行为一致。
2. **停止检查定时器开销**：每 200ms 一次检查，开销极小。`_worker` 为 None 时直接返回，无副作用。
3. **`_user_stopped` 重置时机**：`_on_execution_finished` 中重置，确保不影响后续手动执行。若 `_on_execution_finished` 未被调用（极端情况），`_user_stopped` 保持 True，但下次 `_run_queue` 会先检查 `_is_executing`（应为 False）再执行，且 `_user_stopped` 在 `_on_execution_finished` 之外不会被读取，无实际影响。
4. **`commandError` 信号匹配**：`_on_error` 使用 `cmd.split()[: len(expected)] == expected` 匹配，与 `_on_finished` 一致。若多个命令同名，可能误匹配，但这是 `_on_finished` 已有的行为，非新引入。

### 回退策略

- 若修改引入问题，可逐项回退：
  - 回退修改 1：移除 `commandError` 连接（`_sync_execute` 恢复等超时行为）
  - 回退修改 2：移除 `stop_check_timer`（停止恢复等任务完成行为）
  - 回退修改 3：移除 `_user_stopped` 逻辑（自动重试恢复无条件触发）
- 三项修改相互独立，可单独回退。

---

## 验证

- `py_compile` 通过
- 逻辑验证：
  - CLI 崩溃 → `commandError` emit → `_on_error` 匹配 → `loop.quit()` → `_sync_execute` 立即返回 `{"status": "error"}`（不再等 300s）
  - 用户点击停止 → `_user_stopped = True` + `_worker._stopped = True` → `stop_check_timer` 200ms 内检测到 → `loop.quit()` → `_sync_execute` 退出 → `_runtime_queue_runner` break → `_on_execution_finished(False)` → `user_stopped=True` 跳过自动重试
