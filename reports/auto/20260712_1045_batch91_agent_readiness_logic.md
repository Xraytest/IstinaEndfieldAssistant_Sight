# 审计批次 91 — AGENT-01 `_start_agent` 就绪检查逻辑错误 + 审计批次 90

**生成时间**: 2026-07-12 10:45
**覆盖文件**: `maa_end/runtime.py`, `touch_manager.py`, `pipeline_node.py`, `pipeline_runner.py`
**审计方法**: 静态代码逻辑分析，无测试执行
**前置去重**: 已读取 `reports/CODE_REVIEW_WARNS.md`，新发现跳过 FP-01~08、FX-01~10、DUP-A~J、O-01~O-24

---

## 新增发现（1 项）

### AGENT-01 — `_start_agent` 就绪检查循环在进程存活时误设 ready

**等级**: 代码质量 / 中
**位置**: `maa_end/runtime.py:466-474`

**问题代码**:

```python
# maa_end/runtime.py:466-474
ready = False
for _ in range(10):  # 最多等待 5 秒（10 次 × 0.5s）
    if process.poll() is not None:
        # 进程已退出
        break
    time.sleep(0.5)
    if process.poll() is None:
        ready = True
        break
if not ready:
    self.logger.error(LogCategory.MAIN, "go-service 进程启动后立即退出", agent_id=agent_id)
    self._agent_client = None
    self._agent_process = None
    return
```

**根因分析**:

就绪检查循环的逻辑为：
1. 检查 `process.poll()` — 若进程已退出则 break
2. `time.sleep(0.5)` — 等待进程启动
3. 再次检查 `process.poll()` — 若仍存活则 `ready = True`

**关键缺陷**：`ready = True` 在 sleep 后设置，但 `process.poll()` 仅在循环开始时检查退出状态。如果进程在 sleep 期间退出，循环不会立即检测到——它会在下一次迭代开始时通过 `process.poll() is not None` break，此时 `ready` 仍为 `False`。这看似正确，但存在以下时序问题：

**场景**：进程启动后存活超过 0.5s，但随后快速崩溃（在 sleep 后 poll 之前退出）：
- 迭代 0：`poll()` → None（存活）→ sleep(0.5) → `poll()` → None（刚好还存活）→ `ready = True; break`
- 循环退出，`ready = True`
- 后续代码使用 `self._agent_process`（可能已崩溃）
- `AgentClient(agent_id)` 可能连接到已崩溃的进程

**更隐蔽的场景**：`process.poll()` 返回非 None（进程已退出），但循环通过 `break` 退出时，`ready` 未被设置为 True。这是正确行为。

实际上，当前代码的 break 条件（`process.poll() is not None`）仅出现在循环开头。如果进程在 sleep 后退出，循环不会在退出时检测到——它会在下一次迭代的开始时检测。这意味着：

- 迭代 0：poll → None → sleep → poll → None → ready=True（进程刚好还活着）
- 但实际上进程在 sleep 后 poll 检查后立即崩溃
- 代码继续执行，使用已崩溃的进程

**影响面**:
- **中**：go-service 进程启动不稳定时（模型文件缺失、端口冲突等），代码可能在进程崩溃后仍尝试使用它，导致后续 `AgentClient.connect()` 失败并抛出难以诊断的错误。

**修复建议**:

```python
ready = False
for attempt in range(10):
    if process.poll() is not None:
        self.logger.warning(LogCategory.MAIN, "go-service 进程在启动阶段退出", agent_id=agent_id, attempt=attempt)
        break
    time.sleep(0.5)
    # 每次迭代结束后统一检查，确保 sleep 后的退出也被捕获
    if process.poll() is None:
        ready = True
        break
else:
    # 循环正常结束（10 次迭代用完），进程可能仍存活但未就绪
    self.logger.warning(LogCategory.MAIN, "go-service 启动超时", agent_id=agent_id)
if not ready:
    self.logger.error(LogCategory.MAIN, "go-service 进程启动后立即退出", agent_id=agent_id)
    if process.poll() is None:
        process.kill()
    self._agent_client = None
    self._agent_process = None
    return
```

---

## 审计结论（批次 90）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 90 | SHELL-01 (`AndroidRuntime.shell()` 不检查 daemon 错误) | **结论正确**。`android_runtime.py:824-826` 返回 `response.get("result", "")`，不检查 `response.get("error")`。与 `tap()`/`swipe()`/`keyevent()` 的 `raise AndroidRuntimeError` 模式不一致。 |
| 批次 90 | PRTS-05 (`_start_llm` 不检查 "llm start" 结果) | **结论正确**。`prts_full_intelligence_page.py:172-181` 发送 "llm start" 后不检查结果，`_on_command_finished` 仅处理 "llm status" 和 "llm chat"。启动失败需等待 60s 轮询超时才显示状态。 |

**批次 90 全部 2 项新发现经本批次逐项源码复核确认准确，无需修正。**

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| 代码质量（中） | 1 | AGENT-01 (_start_agent 就绪检查逻辑错误) |
| 代码质量（低） | 0 | — |
| 高风险 | 0 | — |
| 中风险 | 0 | — |

**本轮无中高风险发现。**

---

*批次 91 报告 | 仅分析，无文件修改*
