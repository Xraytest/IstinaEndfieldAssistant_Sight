# 问题分析：GUI 队列执行无效果 + 停止按钮无效（CLIIBRIDGE-02）

**日期**: 2026-07-12
**触发**: 用户反馈 GUI 启动队列执行后设备无变化，点击停止无法终止队列
**上一轮修复**: commit 2b2b415（_sync_execute 连接 commandError + _user_stopped + stop_check_timer）—— 无效

## 1. 根因分析

### 证据来源
`logs/main.log` 尾部记录了最近一次队列执行的完整轨迹：

```
[14:59:33] CLI 交互循环: 收到命令 command=task run VisitFriends --options {...}
[14:59:33] [MAIN] 开始执行任务 task=VisitFriends ...
[15:00:37] scrcpy socket EOF（通道关闭），重建会话 server_alive=False
[15:00:38] [GUI] CLI 进程崩溃 exit_code=-1073741510 crash_count=1
```

task run 从 14:59:33 开始，65 秒后 CLI 子进程崩溃（exit_code=-1073741510 = 0xC000013A）。崩溃发生在 scrcpy 重建会话期间。

### 问题1根因：CLI 崩溃后静默重启，_sync_execute 等满超时

`cli_bridge.py` `_on_finished` 在 interactive 模式下，崩溃次数未达上限（5次）时的处理：

```python
# 旧代码（已修复）
if crashed:
    if self._crash_count < self._max_crashes and not self._restart_pending:
        self._restart_pending = True
        if self._current_command:
            self._pending_commands.insert(0, list(self._current_command))  # 重排队崩溃命令
        QTimer.singleShot(1000, self._restart_last_command)  # 1s 后重启重试
    else:
        self.commandError.emit(...)  # 仅达上限才 emit
```

**缺陷**：崩溃未达上限时，既不 emit `commandError` 也不 emit `commandFinished`，只安排 1s 后重启重试。

`_sync_execute` 等待 `commandFinished` 或 `commandError` 信号（上一轮已连接两者），但崩溃路径两者都不 emit。结果 `_sync_execute` 的 `loop.exec()` 等满 300s 超时才返回。期间 task run 未完成，**设备无变化**。

上一轮修复（连接 `commandError`）无效的原因：崩溃路径根本不 emit `commandError`。

### 问题2根因：停止不清空命令队列，崩溃重排队命令仍执行

`_stop_execution` 设置 `_worker.stop()` + `_user_stopped`，但不清空 `_pending_commands`。旧代码崩溃时 `self._pending_commands.insert(0, list(self._current_command))` 把崩溃命令重新排队。即使用户点停止：
1. `stop_check_timer` 中断 `_sync_execute` 返回 None
2. 但 CLI 进程重启后仍执行 `_pending_commands` 中重新排队的崩溃命令
3. **停止后队列恢复执行**

### CLI 崩溃根因（runtime 层，本次不修）
exit_code=-1073741510 (0xC000013A) 发生在 scrcpy 重建会话期间。project_memory 已记录"scrcpy + MaaEnd screencap 并发竞争是本项目独有问题"。CLI 崩溃根因需单独分析，本次修复确保 GUI 正确处理崩溃（不卡死、可停止）。

## 2. 修改方案

### 修改1: cli_bridge.py — 崩溃立即通知 + 不重排队崩溃命令
`_on_finished` interactive 崩溃路径：崩溃时立即 emit `commandError`，改用 `_restart_process_only` 只重启进程处理后续命令（不重试崩溃的命令）。

### 修改2: cli_bridge.py — 新增 _restart_process_only 方法
重启 CLI 进程处理 `_pending_commands` 中的后续命令，不重排队崩溃的命令。

### 修改3: cli_bridge.py — 新增 clear_pending 方法
清空待执行命令队列，供 `_stop_execution` 调用。

### 修改4: maaend_control_page.py — _stop_execution 清空队列
调用 `self._bridge.clear_pending()` 清空待执行命令，确保停止后 CLI 不执行后续任务。

### 修改5: maaend_control_page.py — _sync_execute 诊断日志
在 `_on_error`、`_check_stop`、结束点加 info 级别日志，记录退出原因（error/stop/timeout/finished），便于运行时验证。

## 3. 影响面

| 文件 | 影响 |
|------|------|
| cli_bridge.py | 崩溃处理逻辑变更：崩溃不再静默重启重试，改为立即通知失败 + 仅重启进程处理后续命令。影响所有 CLI 命令的崩溃恢复行为。 |
| maaend_control_page.py | _stop_execution 新增清空队列；_sync_execute 加诊断日志（不改逻辑）。 |

崩溃重试职责转移：旧实现由 CLIBridge 内部重试崩溃命令；新实现由 GUI 的自动重试机制（`_on_execution_finished` → `_retry_failed`）决定是否重试整个队列的失败项。这更合理：CLIBridge 只负责执行和报告，重试策略由调用方决定。

## 4. 非期待变化

- **崩溃不再自动重试**：CLI 偶发崩溃（非命令本身问题）时，旧代码会自动重试恢复，新代码通知失败。但 GUI 有自动重试机制（`_retry_failed`），会重新执行失败项，行为更可控。若不希望自动重试，用户可在设置中关闭。
- **_restart_process_only 仅在有 pending 命令时启动新进程**：崩溃时若无后续命令，不重启进程。下次 `execute` 时会自动启动新进程（`_send_next_if_idle` → `_start_interactive_process`），行为正确。
- **诊断日志增加**：`_sync_execute` 每次调用多 1-2 条 info 日志，对性能无可测影响。
