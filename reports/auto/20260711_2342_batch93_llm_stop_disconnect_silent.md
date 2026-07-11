# 审计批次 93 — LLM-02 CLI llm start 无诊断信息 / LLM-03 CLI llm stop 总是成功 / SYS-01 CLI disconnect 总是成功 + 审计批次 92

**生成时间**: 2026-07-11 23:42
**覆盖文件**: `cli/handlers.py`, `core/service/runtime.py`, `core/service/maa_end/runtime.py`
**审计方法**: 静态代码逻辑分析，无测试执行
**前置去重**: 已读取 `reports/CODE_REVIEW_WARNS.md`，新发现跳过 FP-01~08、FX-01~10、DUP-A~J、O-01~O-24

---

## 审计结论（批次 92）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 92 | CACHE-01 (`_persist_metadata_cache` 非原子写入) | **结论正确**。`maaend_control_page.py:1575-1584` 直接 `write_text` 覆盖写入，异常时文件截断损坏。同文件内至少 3 处非原子写入（`_export_queue`、`_write_config`、`_persist_metadata_cache`），而 `settings_page.py` 和 `queue_state.py` 已使用原子写入（tempfile + os.replace）。 |
| 批次 92 | 批次 91 审计 + `_start_agent` except 块补充观察 | **结论正确**。`maa_end/runtime.py:483-495` 的 except 块仅清理 `_agent_client` 和 `_agent_process`，未重置 `_connected`。若 `AgentClient.bind()` 或 `AgentClient.connect()` 抛出异常（go-service 在 socket 建立前崩溃），异常被捕获后连接态保持 True，后续 `run_task`/`run_pipeline` 通过连接检查但实际无法操作。 |

**批次 92 全部新发现经本批次逐项源码复核确认准确，无需修正。**

---

## 新增发现（3 项）

### LLM-02 — CLI `llm start` handler 启动失败时返回无诊断信息的错误响应

**等级**: 用户体验 / 低
**位置**: `cli/handlers.py:239-240`

**问题代码**:

```python
# cli/handlers.py:239-240
if args.action == "start":
    return {"status": "success" if self._runtime.warmup_llm() else "error", "command": "llm.start"}
```

**根因分析**:

当 `warmup_llm()` 返回 False 时，handler 仅返回 `{"status": "error", "command": "llm.start"}`，不含任何诊断信息。但 `LlamaServerRuntime.start()` 内部已记录详细失败原因（模型文件缺失、可执行文件未找到、端口占用、CUDA 初始化失败等），这些信息仅存在于日志中，未传播到 CLI 响应。

**调用链**:

```
CLI: istina.py llm start
  → CLIDispatch._handle_llm("start")
    → runtime.warmup_llm()
      → LlamaServerRuntime.start()  # 内部记录失败原因
    → 返回 {"status": "error", "command": "llm.start"}  # 无 message 字段
  → CLI 输出: {"status": "error", "command": "llm.start"}
```

用户看到错误状态但不知道具体原因，需要额外查看日志才能诊断。

**影响面**:
- **低**：仅影响 CLI `llm start` 命令的错误响应。GUI 侧（PRTS 页面）有独立的启动流程和状态轮询。但 CLI 用户（脚本/自动化）无法从响应中获取失败原因。

**修复建议**:

```python
if args.action == "start":
    ok = self._runtime.warmup_llm()
    if ok:
        return {"status": "success", "command": "llm.start"}
    # 从 runtime 获取诊断信息
    llama = getattr(self._runtime, "_llm_runtime_instance", None)
    msg = "llama-server 启动失败"
    if llama is not None and not getattr(llama, "ready", False):
        msg = getattr(llama, "_last_error_message", None) or msg
    return {"status": "error", "command": "llm.start", "message": msg}
```

配套修改 `LlamaServerRuntime.start()` 在失败时存储诊断信息：
```python
def start(self) -> bool:
    ...
    if not ok:
        self._last_error_message = f"startup failed (model={model_path}, exe={exe})"
        if not self._cuda_failed:
            self._cuda_failed = True
            return self._try_start(exe, model_path, llm_cfg, force_cpu=True)
    return ok
```

---

### LLM-03 — CLI `llm stop` handler 总是返回 success，即使 cooldown 失败

**等级**: 代码质量 / 低
**位置**: `cli/handlers.py:242-243`

**问题代码**:

```python
# cli/handlers.py:242-243
if args.action == "stop":
    self._runtime.cooldown_llm()
    return {"status": "success", "command": "llm.stop"}
```

**根因分析**:

`cooldown_llm()` 内部捕获所有异常并仅记录 warning：

```python
# core/service/runtime.py:904-908
def cooldown_llm(self) -> None:
    try:
        self._llm_runtime_instance.stop()
    except Exception as exc:
        self._logger.warning("cooldown_llm 异常: %s", exc)
```

若 `_llm_runtime_instance` 初始化失败（如配置异常），或 `stop()` 本身抛出异常（如进程已终止但清理失败），异常被吞掉。handler 无条件返回 `"success"`，调用方无法得知操作实际失败。

**与 SYS-01 的共性**：LLM-03 和 SYS-01（`system disconnect`）共享同一根因——生命周期方法内部 `except Exception: pass/warning` 后不返回状态，handler 无条件返回 success。

**影响面**:
- **低**：`llm stop` 通常不会失败。但极端情况（进程已死、权限不足）下用户获得误导性成功响应。

**修复建议**:

```python
if args.action == "stop":
    try:
        self._runtime.cooldown_llm()
        return {"status": "success", "command": "llm.stop"}
    except Exception as exc:
        return {"status": "error", "command": "llm.stop", "message": str(exc)}
```

配套修改 `cooldown_llm()` 在失败时抛出异常：
```python
def cooldown_llm(self) -> None:
    self._llm_runtime_instance.stop()  # 让异常传播给调用方
```

---

### SYS-01 — CLI `system disconnect` handler 总是返回 success，即使 disconnect 失败

**等级**: 代码质量 / 低
**位置**: `cli/handlers.py:116-117`

**问题代码**:

```python
# cli/handlers.py:116-117
if args.action == "disconnect":
    self._runtime.execute("system.disconnect", {"serial": args.serial})
    return {"status": "success", "connected": self._runtime.connected}
```

**根因分析**:

`runtime.disconnect()` 内部捕获所有异常并记录 error 日志：

```python
# core/service/runtime.py:282-286
for target in targets:
    runtime = self._maaend_clients.get(target)
    if runtime is None:
        continue
    try:
        runtime.disconnect()
    except Exception as e:
        self._logger.error(LogCategory.MAIN, "断开连接异常", serial=target, error=str(e))
    self._maaend_clients.pop(target, None)
```

异常被吞掉后，handler 无条件返回 `{"status": "success"}`。调用方（如 GUI 断开按钮、自动化脚本）看到成功响应但实际连接未清理（进程仍在运行、scrcpy 通道未关闭）。

**与 LLM-03 的共性**：同一根因——生命周期方法内部捕获异常后不返回状态。

**影响面**:
- **低**：正常操作路径中 disconnect 通常成功。但若底层 `runtime.disconnect()` 抛出异常（如进程已死、文件锁），用户获得误导性成功响应。

**修复建议**:

```python
if args.action == "disconnect":
    try:
        self._runtime.execute("system.disconnect", {"serial": args.serial})
        return {"status": "success", "connected": self._runtime.connected}
    except Exception as exc:
        return {"status": "error", "message": str(exc), "connected": self._runtime.connected}
```

配套修改 `runtime.disconnect()` 在捕获异常后汇总错误信息返回：

```python
errors = []
for target in targets:
    runtime = self._maaend_clients.get(target)
    if runtime is None:
        continue
    try:
        runtime.disconnect()
    except Exception as e:
        errors.append(f"{target}: {e}")
    self._maaend_clients.pop(target, None)
...
if errors:
    raise RuntimeError(f"disconnect failed for: {', '.join(errors)}")
```

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| 用户体验（低） | 1 | LLM-02 (llm start 无诊断信息) |
| 代码质量（低） | 2 | LLM-03 (llm stop 总是成功), SYS-01 (disconnect 总是成功) |
| 高风险 | 0 | — |
| 中风险 | 0 | — |

**本轮无中高风险发现。**

---

*批次 93 报告 | 仅分析，无文件修改*
