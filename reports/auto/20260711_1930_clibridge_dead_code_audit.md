# 批次 66：CLIBridge 交互模式死代码 + 崩溃计数恢复后不重置 + 历史报告审计

> **生成时间**: 2026-07-11 19:30
> **审查范围**: `src/gui/pyqt6/cli_bridge.py` (291 行)
> **审计范围**: 批次 65（`20260711_1910_prts_worker_race.md`）、批次 2345（`20260710_2345.md` U10）
> **方法**: 静态代码分析 + 调用链追踪 + Qt 信号语义推演
> **发现总计**: 2 新发现 + 2 审计验证
> **严重度分布**: 0 High / 0 Medium / 0 Low / 2 Info

---

## 项目边界回顾

- IEA 是《明日方舟：终末地》的 MaaEnd/MaaFramework 自动化助手。本仓库为**非第三方**源码，`MaaEnd/` 与 `3rd-part/` 不在审查范围。
- 审查仅限本仓库 Python 源码；历史累计 260+ 条发现，本批严格避免重复提交。

---

## §1 新发现

### [NEW-INFO] `cli_bridge.py:76,148` — `_interactive` 恒为 True，非交互模式死代码

```python
# line 76
self._interactive = True

# line 148
_start_next_process = _start_interactive_process
```

`_interactive` 在 `__init__` 中硬编码为 `True`，全文件无任何赋值修改。这导致：

**1. `_start_next_process` 为死别名**（line 148）：
```python
_start_next_process = _start_interactive_process
```
该赋值使两个名称指向同一函数对象，但 `_start_next_process` 在全文件中**仅被 `_on_finished` 调用**（line 257）。而 `_on_finished` 中的调用位于非交互模式分支（line 233-257），该分支**永远不会执行**（因为 `_interactive` 恒为 True，line 216-232 的交互模式分支总是先返回）。

**2. `execute()` 中的 else 分支不可达**（line 88）：
```python
def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> None:
    ...
    if self._interactive:
        self._send_next_if_idle()
    else:
        self._start_next_process()  # ← 不可达
```

**3. `_on_finished` 中的非交互分支不可达**（line 233-257）：
```python
if self._interactive:
    if crashed:
        ...
    else:
        self._logger.info(...)
    self._finalize_current_process()
    return  # ← 交互模式在此返回，非交互分支永不执行
if crashed:  # ← 不可达
    ...
self._start_next_process()  # ← 不可达
```

**影响面**：
- **维护混淆**：非交互模式的代码路径（崩溃重启、队列顺序执行）虽不可达，但占据约 30 行逻辑，增加维护者理解成本。
- **删除风险**：若未来开发者删除"不可达"的非交互分支代码（如 `_start_next_process` 调用），可能无意中破坏 `_restart_last_command` 的调用链（该函数内部调用 `_start_next_process`）。
- **设计意图丢失**：原始设计意图（支持交互/非交互双模式）已丢失，但代码残留了双模式的痕迹。

**建议**：

方案 1（最小修改）：删除非交互模式残留代码，统一为交互模式：

```python
# 删除 _interactive 字段
# 删除 _start_next_process 别名
# execute() 简化为：
def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> None:
    params = params or {}
    args = self._build_args(command, params)
    self._pending_commands.append(args)
    self._send_next_if_idle()

# _on_finished 简化为：
def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
    if self._restart_pending:
        self._finalize_current_process()
        return
    crashed = exit_status == QProcess.ExitStatus.CrashExit
    if crashed:
        self._crash_count += 1
        self._logger.error(...)
        self.processCrashed.emit(self._crash_count)
        if self._crash_count < self._max_crashes and not self._restart_pending:
            self._restart_pending = True
            if self._current_command:
                self._pending_commands.insert(0, list(self._current_command))
            QTimer.singleShot(1000, self._restart_last_command)
        else:
            self.commandError.emit(...)
            self._show_crash_dialog()
    else:
        self._crash_count = 0
    self._finalize_current_process()
```

方案 2（保留设计意图）：如果未来可能需要非交互模式，应：
1. 添加 `_interactive` 的 setter 或参数化构造函数
2. 在 `__init__` 中根据参数决定模式
3. 确保双模式代码路径均可达且经过测试

---

### [NEW-INFO] `cli_bridge.py:207-257` — `_on_finished` 崩溃恢复成功后不重置 `_crash_count`

```python
def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
    ...
    if self._interactive:
        if crashed:
            self._crash_count += 1
            ...
            if self._crash_count < self._max_crashes and not self._restart_pending:
                self._restart_pending = True
                ...
                QTimer.singleShot(1000, self._restart_last_command)
            else:
                self.commandError.emit(...)
                self._show_crash_dialog()
        else:
            self._logger.info(...)
        self._finalize_current_process()
        return  # ← 提前返回，不执行 line 255 的 _crash_count = 0
    ...
    # line 255（仅非交互模式可达）
    self._crash_count = 0
```

**问题**：`_crash_count = 0`（line 255）仅位于**非交互模式分支**，而 `_interactive` 恒为 True，该分支不可达。这意味着：

**崩溃恢复序列中的计数偏差**：

```
场景：CLI 子进程崩溃 → 自动重启 → 重启成功 → 再次崩溃
```

| 步骤 | 事件 | `_crash_count` |
|------|------|----------------|
| 1 | 第 1 次崩溃 | 1 |
| 2 | `_restart_last_command` 启动新进程 | 1（未重置） |
| 3 | 新进程正常退出 | **1**（应重置为 0） |
| 4 | 第 2 次崩溃 | 2 |
| 5 | 用户判断：已连续崩溃 2 次 | 实际为 2 次独立事件 |

**后果**：`_crash_count` 在崩溃恢复后不重置，导致后续崩溃的"连续次数"被**高估**。例如：
- 实际场景：崩溃 → 恢复成功 → 崩溃 → 恢复成功 → 崩溃（3 次独立事件）
- `_crash_count` 序列：1 → 1 → 2 → 2 → 3
- `_max_crashes = 5` 时，第 5 次独立崩溃时 `_crash_count = 5`，触发弹窗告警

**与设计意图的偏差**：
- `_max_crashes = 5` 的设计意图是"连续崩溃 5 次后告警"
- 但恢复成功后不重置计数，实际语义变为"累计崩溃（含恢复后）5 次后告警"
- 恢复成功后的新崩溃被视为"连续"，与用户理解不符

**建议**：在 `_on_finished` 的交互模式分支中，正常退出时重置 `_crash_count`：

```python
if self._interactive:
    if crashed:
        self._crash_count += 1
        ...
    else:
        self._crash_count = 0  # 新增：正常退出时重置崩溃计数
        self._logger.info(...)
    self._finalize_current_process()
    return
```

或更精确地在 `_restart_last_command` 启动进程成功后重置（通过 `_on_finished` 的下一次调用）：

```python
def _restart_last_command(self) -> None:
    self._restart_pending = False
    # _crash_count 在 _on_finished 的下一次调用中重置（正常退出路径）
    ...
```

---

## §2 历史报告审计

### [AUDIT-1] 批次 65 `20260711_1910_prts_worker_race.md` — 审计确认无误

**NEW-MEDIUM**（`LlmChatWorker.run()` 竞态发送虚假"Error: empty"）：

审计结论：**合理，维持 Medium**。

`CLIBridge.execute()` 为异步方法（fire-and-forget），返回 `None`。`LlmChatWorker.run()` 在 worker 线程中调用 `execute()` 后，`result` 始终为 `None`，因此 `self.finished.emit(result or {"status": "error", "message": "empty"})` 无条件发送虚假错误。Qt 信号在主线程事件循环中串行处理，虚假错误先于真实结果到达，用户看到 "Error: empty" 后才是正确回复。

分析正确，无自我矛盾。

**NEW-LOW**（`_attach_image` 异常时 `_pending_image_b64` 泄漏旧值）：

审计结论：**合理，维持 Low**。

`except Exception:` 捕获读取失败但未重置 `_pending_image_b64`，用户下次发送消息携带旧图片且无法感知。触发概率低但后果隐蔽。

分析正确，无自我矛盾。

**总体评价**：批次 65 报告逻辑自洽，两个发现均为历史未覆盖问题。

---

### [AUDIT-2] 批次 2345 `20260710_2345.md` U10 — `_restart_last_command` 不验证重启成功，与本批互补

**批次 2345 U10**（`cli_bridge.py` `_restart_last_command` 不验证重启成功）：

审计结论：**合理，与本批互补**。

U10 指出 `_restart_last_command` 调用 `_start_next_process` 后不检查返回值，重启失败时静默忽略。这与本批 NEW-INFO #2（崩溃恢复后不重置 `_crash_count`）为**不同根因**：

- U10：重启操作本身失败（进程无法启动），静默忽略导致用户不知情
- 本批：重启操作成功，但恢复成功后 `_crash_count` 不重置，导致后续崩溃计数被高估

两者独立，互补关系。U10 关注"重启失败"的静默性，本批关注"恢复成功后计数偏差"的语义错误。

**关于本批 NEW-INFO #1（`_interactive` 恒为 True 死代码）**：U10 的分析基于 `_start_next_process` 为有效调用。本批指出 `_start_next_process` 实际为死别名（`_interactive` 恒为 True），U10 的建议（"验证 `_start_next_process` 返回值"）在当前代码中**无法执行**（因为该路径不可达）。这不构成 U10 的错误，但说明 U10 的分析基于"非交互模式可达"的假设，与实际代码状态不符。

---

## §3 发现统计

| 类别 | 条目 | 严重度 | 状态 |
|------|------|--------|------|
| 新发现 | NEW-INFO #1（`_interactive` 恒为 True，非交互模式死代码） | Info | 历史未覆盖 |
| 新发现 | NEW-INFO #2（崩溃恢复成功后不重置 `_crash_count`） | Info | 历史未覆盖 |
| 审计验证 | AUDIT-1（批次 65 合理） | — | 确认无误 |
| 审计验证 | AUDIT-2（批次 2345 U10 与本批互补） | — | 确认无误 |
| **合计** | **2 新 + 2 审计** | **2I** | — |

---

## §4 跨批次一致性验证

- **批次 2345 U10**（`_restart_last_command` 不验证重启成功）→ 与本批 NEW-INFO #2 互补，不冲突
- **批次 2345 U10**（`_start_next_process` 返回值检查）→ 与本批 NEW-INFO #1 存在隐含矛盾（U10 假设非交互模式可达，本批指出不可达）
- **批次 65 NEW-MEDIUM**（`LlmChatWorker` 竞态）→ 与本批独立文件/路径，不冲突
- **批次 65 NEW-LOW**（`_attach_image` 状态泄漏）→ 与本批独立文件/路径，不冲突
- **批次 1730 SRV-01** → 批次 1745 A1 已推翻为假阳性，本批不重复
- **批次 1730 范围**（cli_bridge.py 285 行）→ 本批审查 291 行版本（新增 6 行），发现 2 条新 Info，与批次 1730 无矛盾

---

## §5 验证方法

- 全部发现基于对 `cli_bridge.py` 的**逐行静态阅读**与代码路径可达性分析。
- **未执行任何测试**，未修改任何业务代码。
- 审计部分基于对批次 65、批次 2345 报告的逐条代码复核。
- 关键推演依据：`_interactive` 在全文件无赋值修改，为恒定 True；`_crash_count = 0` 位于不可达分支，交互模式下崩溃恢复后计数不重置。
- 重复检测：交叉核对 19 份历史报告确认两个新发现均为全新。
- 本批严格遵循"避免重复提交历史已覆盖问题"原则。
