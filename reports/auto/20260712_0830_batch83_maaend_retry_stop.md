# 审计批次 83 — 队列执行手动停止后自动重连触发 / `_ensure_maaend_ready` 二次连接无防护 + 审计批次 82

**生成时间**: 2026-07-12 08:30
**覆盖文件**: `maaend_control_page.py`, `runtime.py`
**审计方法**: 静态代码逻辑分析，无测试执行
**前置去重**: 已读取 `reports/CODE_REVIEW_WARNS.md`，新发现跳过 FP-01~08、FX-01~10、DUP-A~J、O-01~O-24

---

## 新增发现（2 项）

### MAAEND-01 — 手动停止队列执行后自动重试仍会触发

**等级**: BUG / 中
**位置**: `maaend_control_page.py:1852-1861`（`_on_execution_finished`）+ `1827-1836`（`_retry_failed`）

**问题代码**:

```python
# maaend_control_page.py:1852-1861
def _on_execution_finished(self, success: bool):
    self._is_executing = False                      # ← 先设为 False
    ...
    if not success and self._failed_indices and self._auto_retry_enabled and self._retry_count < self._max_retries:
        QTimer.singleShot(self._retry_delay_ms, self._retry_failed)  # ← 然后安排自动重试
    ...

# maaend_control_page.py:1847-1850
def _stop_execution(self):
    if self._worker:
        self._worker.stop()    # ← 仅设置 _stopped = True，不取消自动重试定时器
    self._append_log("系统", locale.tr("execution_stop_requested", "Stop requested"))

# maaend_control_page.py:1827-1836
def _retry_failed(self) -> None:
    with self._failed_indices_lock:
        failed = list(self._failed_indices)
    if self._is_executing or not failed:   # ← _is_executing 已是 False
        return
    ...
    self._start_execution(lambda: self._runtime_queue_runner(retry_indices=failed))
```

**根因分析**:

用户点击"停止"时调用链：

1. `_stop_execution()` → `self._worker.stop()` → `self._worker._stopped = True`
2. `_runtime_queue_runner` 在循环顶部检查 `_stopped`（line 922），检测到后 break
3. `_runtime_queue_runner` 返回 `False`（有 failed 项）
4. `TaskRunWorker.run()` → `self.finished.emit(False)`
5. `_on_execution_finished(False)` 执行：
   - `self._is_executing = False`（line 1853）
   - 自动重试条件检查：`not success`=True, `self._failed_indices` 非空, `self._auto_retry_enabled`=True, `self._retry_count < self._max_retries`=True
   - → **`QTimer.singleShot` 安排自动重试**（line 1861）
6. `_retry_failed()` 在延迟后触发：
   - `self._is_executing` 为 `False`（line 1863 条件不成立）
   - `failed` 非空 → **继续执行** → `_start_execution` 启动新 Worker

**核心问题**：`_stop_execution` 不取消已安排的自动重试定时器，`_on_execution_finished` 在设置 `_is_executing = False` 后立即安排重试，`_retry_failed` 的 `_is_executing` 守卫在手动停止场景下完全失效。

**触发场景**:
- 队列执行中用户点击"停止"，队列中存在至少一个 failed 项
- 自动重试延迟（`_retry_delay_ms`）后，队列自动重新开始执行
- 用户以为已停止，实际任务悄悄恢复

**与 FX-05 的区别**: FX-05 覆盖 `player.py` 的 stop 后双发信号（`playback_finished` + `playback_stopped`）。MAAEND-01 是**不同问题**：关注队列执行的自动重试机制在手动停止后的错误触发，与脚本播放器的信号双发无关。

**与 O-05 的区别**: O-05 也是关于 stop 后的信号问题（player.py）。MAAEND-01 在 `maaend_control_page.py` 的队列执行层，关注的是自动重试逻辑而非信号双发。

**影响面**:
- **中**：用户明确要求停止时，应用应完全停止。自动重试导致任务在用户无感知的情况下恢复，违反用户意图。

**修复建议**:

方案 A（推荐）：在 `_stop_execution` 中设置停止标记，`_on_execution_finished` 检查后跳过自动重试：

```python
def _stop_execution(self):
    if self._worker:
        self._worker.stop()
    self._stop_requested = True  # 新增：标记手动停止
    self._append_log("系统", locale.tr("execution_stop_requested", "Stop requested"))

def _on_execution_finished(self, success: bool):
    self._is_executing = False
    if self._stop_requested:
        self._stop_requested = False
        self._append_log("系统", locale.tr("execution_stopped", "Execution stopped by user"))
        return  # 跳过自动重试
    ...
```

方案 B：在 `_stop_execution` 中取消已安排的自动重试定时器：

```python
def _stop_execution(self):
    if self._worker:
        self._worker.stop()
    if hasattr(self, '_retry_timer'):
        self._retry_timer.stop()  # 取消自动重试
    ...
```

---

### RUNTIME-02 — `_ensure_maaend_ready` 仅检查 `connected` 标志，不验证实际连接活性

**等级**: 代码质量 / 低
**位置**: `runtime.py:256-265`

**问题代码**:

```python
# runtime.py:256-265
def _ensure_maaend_ready(self, runtime: Any) -> bool:
    if runtime.connected:     # ← 仅检查标志位，不验证实际连接
        return True
    if not runtime.connect():
        self._logger.error(LogCategory.MAIN, "MaaEnd runtime 连接失败")
        return False
    if not runtime.load_resource():
        self._logger.error(LogCategory.MAIN, "MaaEnd runtime 资源加载失败")
        return False
    return True
```

**根因分析**:

`runtime.connected` 是一个布尔标志位（在 `MaaEndRuntime` 中设置），不反映 ADB 设备或 MaaFW 的实际连接状态。如果设备在连接后断开（如 ADB 超时、USB 断开、模拟器崩溃），`runtime.connected` 仍为 `True`，`_ensure_maaend_ready` 直接返回 `True`，后续 `runtime.run_task()` 会因连接失效而失败。

这与 `main_window.py:336-342` 的 `_preview_fail_count` 逻辑形成对比：GUI 层通过连续截图失败检测连接失效并更新状态，但服务层的 `_ensure_maaend_ready` 缺乏类似机制。

**影响面**:
- **低**：`_ensure_maaend_ready` 的调用方（`_run_task`、`_run_preset`、`_run_queue`）在运行时如果连接失效，`run_task` 本身会返回 `False`。但 `_ensure_maaend_ready` 的"ready"承诺与实际状态不符，调用方可能基于错误的 `True` 返回值做出乐观假设。

**修复建议**:

在 `_ensure_maaend_ready` 中增加连接活性验证：

```python
def _ensure_maaend_ready(self, runtime: Any) -> bool:
    if runtime.connected:
        # 验证连接活性：尝试轻量级操作（如 screenshot 或 health check）
        try:
            if hasattr(runtime, 'screenshot'):
                data = runtime.screenshot()
                if data is None:
                    self._logger.warning("MaaEnd runtime 连接已失效，尝试重连")
                    runtime._connected = False  # 强制标记为断开
                    return self._ensure_maaend_ready(runtime)  # 递归重连
        except Exception as exc:
            self._logger.warning("MaaEnd runtime 连接验证失败: %s", exc)
            return False
    ...
```

---

## 审计结论（批次 82）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 82 | TOUCH-01 (`back()` 无异常处理) | **结论正确**。当前代码仍为 `subprocess.check_output(args, timeout=10)` 无 try/except，与 `tap()`/`swipe()`/`long_press()` 的异常处理模式不一致。 |
| 批次 82 | REC-01 (`_clear_canvas` 3x `except Exception: pass`) | **结论正确**。三个 ADB 命令的失败完全不可见，恢复步骤完整性无法评估。 |
| 批次 82 | CLI-01 (`health_check()` 吞掉所有异常) | **结论正确**。`client.py:79` 的 `except Exception: return False` 确实使启动轮询失败原因不可区分。 |
| 批次 82 | SET-01 (`_read_config` 仅捕获 `JSONDecodeError`) | **结论正确**。`settings_page.py:226-228` 仅捕获 `json.JSONDecodeError`，`PermissionError`/`OSError` 未处理。 |
| 批次 82 | RUNTIME-01 (`stop_scrcpy` 清理异常静默) | **结论正确**。`runtime.py:241-252` 的 `except Exception: pass` 确实吞掉了 scrcpy 清理失败。 |

**批次 82 全部 5 项结论经本批次逐项源码复核确认准确，无需修正。**

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| BUG（中） | 1 | MAAEND-01 (手动停止后自动重试仍触发) |
| 代码质量（低） | 1 | RUNTIME-02 (`_ensure_maaend_ready` 不验证连接活性) |
| 高风险 | 0 | — |
| 低风险 | 0 | — |

---

*批次 83 报告 | 仅分析，无文件修改*