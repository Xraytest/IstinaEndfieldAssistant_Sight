# 托盘期间运行状态保持（TRAY-01）

**时间**: 2026-07-13 04:50
**影响**: CLI 崩溃后预览永久显示"已断开"，需手动重新 connect
**严重度**: 中（功能可用但需人工干预，与"托盘期间保持运行状态"诉求冲突）

## 1. 根因分析

### 现象
用户反馈"不应该这么修改，而是设置为在托盘期间也保持与窗口相同的运行状态（scrcpy
持续传输且正在执行的任务不中断）"。此前 STALE-02（is_stale max_age 10→30s）和
CRASH-01（连接 processCrashed 信号）未能解决问题。

### 根因链
1. **CRASH-01 中断运行状态**：`_on_cli_crashed` handler 在 CLI 崩溃时执行三件事：
   - `set_connected(False)` — 标记设备断开
   - `_stop_frame_reader()` — 停止 reader
   - `_reader_retry_after = time.time() + 5.0` — 阻止 reader 5s 内重建

   这直接违反了"保持运行状态"的要求。CLIBridge 本身在 1s 后自动重启 CLI 进程
   （`_restart_process_only`），但 CRASH-01 确保了即使新 CLI 启动，设备也保持
   "断开"状态，用户必须手动重新 connect。

2. **CLIBridge 不会自动重连设备**：`_restart_process_only`（cli_bridge.py L272-277）
   仅重启 CLI 进程处理后续待执行命令，不重发 `system connect`。如果崩溃时无 pending
   命令，新 CLI 进程处于空闲状态，不会连接设备、不会启动 scrcpy daemon。

3. **STALE-02 是治标不治本**：将 `is_stale` 阈值从 10s 提高到 30s 只是延迟"已断开"
   显示，不解决根本问题——CLI 崩溃后没有自动恢复机制。

4. **托盘行为本身无问题**：`closeEvent` 在托盘可用时执行 `event.ignore() + self.hide()`，
   不停止任何定时器或进程。`hideEvent`/`changeEvent` 未被重写，默认行为不中断运行状态。
   用户的"托盘期间"观察实际是 CLI 崩溃 + CRASH-01 中断的组合表现。

### 时序图
```
t=0s    CLI 崩溃（如 STATUS_DLL_NOT_FOUND）
t=0s    processCrashed 信号 → _on_cli_crashed：
        - set_connected(False) ← 标记断开
        - _stop_frame_reader()  ← 停止 reader
t=1s    CLIBridge _restart_process_only：新 CLI 进程启动（空闲，无连接）
t=1.5s  （无自动重连 — 设备保持断开）
t=∞     用户手动 connect → 恢复
```

## 2. 修改方案

### 方案核心：自动重连 + reader 跟随 daemon 重启

#### main_window.py — 替换 `_on_cli_crashed`
- **不标记断开**：保持 `_connected = True`，用户不看到"已断开"
- **不停止 reader**：reader 继续读取旧 mmap（帧过期后由 is_stale 处理）
- **1.5s 后自动重连**：`QTimer.singleShot(1500, self._auto_reconnect_after_crash)`
  发起 `system connect`，使新 CLI 连接设备并启动 scrcpy daemon

#### main_window.py — `_refresh_preview` 中增加 `refresh()`
- `is_stale(max_age=10.0)` 返回 True 时，先尝试 `self._frame_reader.refresh()`
- `refresh()` 检测到新 daemon 的 mmap 后切换，下次 `read_frame()` 读到新帧恢复"实时"
- 仅当 `refresh()` 也失败（无新 daemon）时才显示"已断开"
- `max_age` 从 30s 恢复为 10s（不再需要 30s 阈值覆盖重建周期）

#### main_window.py — 新增 `hideEvent`/`showEvent`
- `hideEvent`：记录日志，明确声明运行状态保持不变
- `showEvent`：确保 preview_timer 运行（防御性检查）

#### scrcpy_frame_reader.py — 新增 `refresh()` 方法
- 重新读取 info 文件（按 serial 命名，daemon 重启后路径变化）
- 检测到新 mmap 路径时关闭旧 mmap、打开新 mmap、重置 `_last_frame_count`
- 返回 True 表示已切换到新 daemon；False 表示无新 daemon

#### scrcpy_frame_reader.py — 恢复 `is_stale` max_age
- 默认值从 30.0 恢复为 10.0
- 更新 docstring 说明 auto-reconnect 时序

### 修复后时序
```
t=0s    CLI 崩溃
t=0s    processCrashed → _on_cli_crashed：保持 _connected=True，不停止 reader
t=1s    CLIBridge _restart_process_only：新 CLI 进程启动
t=1.5s  _auto_reconnect_after_crash → execute("system connect")
t=3-4s  新 CLI 连接设备，启动 scrcpy daemon
t=5-8s  daemon 写入新 info 文件 + mmap，scrcpy 首帧
t=~8s   _refresh_preview: is_stale(True) → refresh() 检测到新 mmap → 切换
t=~8s   read_frame() 读到新帧 → "● 实时"
```

## 3. 影响面

| 组件 | 影响 |
|------|------|
| CLI 崩溃恢复 | 修复：自动重连设备，无需手动 connect |
| 预览状态 | 改善：崩溃后 ~8s 自动恢复"实时"，不永久显示"已断开" |
| is_stale 阈值 | 恢复为 10s（从 30s），更敏感的真实断连检测 |
| ScrcpyFrameReader | 新增 refresh() 方法，支持跟随 daemon 重启 |
| 托盘行为 | 新增 hideEvent/showEvent，显式保证运行状态不中断 |
| 日志 | 新增"CLI 崩溃后自动重连"和"frame reader 切换到新 daemon mmap"日志 |

## 4. 非期待变化

1. **CLI 连续崩溃（≥5次）时不自动重连**：CLIBridge 在 `crash_count >= max_crashes`
   时显示崩溃对话框且不再重启。此时 `_auto_reconnect_after_crash` 的 `execute` 调用
   会启动新进程，但如果再次崩溃，crash_count 继续递增。最终仍需用户干预。这是合理
   的安全边界。

2. **崩溃期间执行的任务丢失**：CLIBridge interactive 模式下 `_restart_process_only`
   不重试崩溃的命令（不同于非交互模式的 `_restart_last_command`）。如果 CLI 崩溃时
   正在执行 task/preset，该任务会失败。`_on_execution_finished` 会跳过自动重试
   （MAAEND-01 的 `_user_stopped` 机制）。这是已知限制，未来可通过重发任务命令改进。

3. **auto-reconnect 与用户操作竞争**：如果用户在 1.5s 窗口内手动操作（如执行任务），
   新命令会先于 `system connect` 被处理。任务可能因设备未连接而失败，随后
   `system connect` 恢复连接。这是可接受的边缘情况。

4. **refresh() 每 33ms 调用一次（is_stale 期间）**：在 is_stale 返回 True 的每个
   preview_timer 周期都会调用 `refresh()`，读取 info 文件。info 文件很小（<1KB），
   读取开销可忽略。一旦 refresh 成功切换到新 mmap，is_stale 不再返回 True（读到新帧
   后 `_last_new_frame_gui_ts` 更新），refresh 不再被调用。

5. **max_age 从 30s 恢复为 10s**：在 auto-reconnect 的 ~8s 恢复周期内，可能有 0-2s
   的"已断开"显示（10s 阈值 - 8s 恢复 = 2s）。这比之前 CRASH-01 的永久"已断开"
   显著改善。
