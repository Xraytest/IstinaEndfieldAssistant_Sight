# 审计批次 90 — SHELL-01 shell() 不检查 daemon 错误 / PRTS-05 启动结果未校验 + 审计批次 89

**生成时间**: 2026-07-12 10:30
**覆盖文件**: `android_runtime.py`, `handlers.py`, `prts_full_intelligence_page.py`, `cli_bridge.py`
**审计方法**: 静态代码逻辑分析，无测试执行
**前置去重**: 已读取 `reports/CODE_REVIEW_WARNS.md`，新发现跳过 FP-01~08、FX-01~10、DUP-A~J、O-01~O-24

---

## 新增发现（2 项）

### SHELL-01 — `AndroidRuntime.shell()` 不检查 daemon 错误，与同类方法不一致

**等级**: 代码质量 / 低
**位置**: `android_runtime.py:824-826`

**问题代码**:

```python
# android_runtime.py:824-826
def shell(self, cmd: str, serial: Optional[str] = None) -> str:
    response = self._call("shell", {"cmd": cmd, "serial": serial or self._serial})
    return response.get("result", "")
```

**根因分析**:

`AndroidRuntime` 的五个公开方法中，`shell()` 是唯一不检查 daemon 错误的：

| 方法 | 错误检查 | 行为 |
|------|---------|------|
| `tap()` (line 766-769) | ✓ `response.get("error")` → raise | 异常传播 |
| `swipe()` (line 771-777) | ✓ `response.get("error")` → raise | 异常传播 |
| `keyevent()` (line 779-783) | ✓ `response.get("error")` → raise | 异常传播 |
| `screenshot()` (line 720-748) | ✓ `response.get("result") is None` → 返回 None | 安全降级 |
| **`shell()`** (line 824-826) | **✗ 不检查** | 返回 `""` |

当 daemon 返回 `{"error": "connection failed"}` 或 `{"error": "shell command not allowed"}` 时，`shell()` 返回 `response.get("result", "")` → `""`。调用方无法区分"命令成功但输出为空"和"daemon 错误"。

**调用链示例**:

```
_handle_shell("input keyevent KEYCODE_INVALID")
  ├── android.shell("input keyevent KEYCODE_INVALID")
  │     ├── _call("shell", ...)
  │     │     └── daemon 返回 {"error": "invalid keyevent: 'KEYCODE_INVALID'"}
  │     └── shell() 返回 ""  ← 错误被吞掉
  └── handler 返回 {"status": "success", "output": ""}  ← 误导性成功
```

**与 CLI-03 的叠加效应**: CLI-03 已报告 handler 层校验粒度不一致。SHELL-01 是同一调用链的下游问题——即使 handler 放行了无效 keyevent，daemon 会拒绝它并返回错误。但由于 `shell()` 不检查错误，用户看到的是 `{"status": "success", "output": ""}` 而非明确的错误信息。

**影响面**:
- **低**：正常操作路径中 daemon 错误较少。但一旦发生（daemon 崩溃、连接超时、命令被拒绝），用户看到误导性成功响应，难以诊断问题。

**修复建议**:

```python
def shell(self, cmd: str, serial: Optional[str] = None) -> str:
    response = self._call("shell", {"cmd": cmd, "serial": serial or self._serial})
    if response.get("error"):
        raise AndroidRuntimeError(f"shell 失败: {response['error']}")
    return response.get("result", "")
```

---

### PRTS-05 — `_start_llm` 不检查 "llm start" 命令结果，启动失败静默

**等级**: 用户体验 / 低
**位置**: `prts_full_intelligence_page.py:172-181`

**问题代码**:

```python
# prts_full_intelligence_page.py:172-181
def _start_llm(self) -> None:
    self._append_chat("系统", locale.tr("llm_starting", "Starting LLM..."))
    self._status_label.setText(locale.tr("llm_starting", "Starting..."))
    self._status_label.setStyleSheet(BLUE_STYLE)
    self._bridge.execute("llm start", {})
    self._startup_poll_count = 0
    if self._startup_timer is None:
        self._startup_timer = QTimer(self)
        self._startup_timer.timeout.connect(self._poll_startup_status)
    self._startup_timer.start(2000)
```

`_on_command_finished` 仅处理 "llm status" 和 "llm chat" 结果，不处理 "llm start"：

```python
# prts_full_intelligence_page.py:209-224
def _on_command_finished(self, command: str, result: dict) -> None:
    cmd_parts = command.split()
    if len(cmd_parts) >= 2 and cmd_parts[0] == "llm" and cmd_parts[1] == "status":
        ...
    elif len(cmd_parts) >= 2 and cmd_parts[0] == "llm" and cmd_parts[1] == "chat":
        ...
    # "llm start" 和 "llm stop" 结果被静默忽略
```

**根因分析**:

当用户点击"Start LLM"按钮：
1. `_start_llm()` 发送 "llm start" 命令并启动轮询 timer
2. Bridge 返回 "llm start" 结果（可能包含错误信息）
3. `_on_command_finished` 不匹配 "llm start" → 结果被静默忽略
4. 轮询 timer 每 2 秒发送 "llm status" 查询
5. 若启动失败，LLM 进程不存在，"llm status" 返回 `ready=False`
6. `_finalize_startup_status(False)` 显示 "Not Ready"（红色）
7. 但用户不知道启动命令本身是否失败——可能是"正在启动中"或"启动失败"

**触发场景**:
- llama-server 二进制不存在 → "llm start" 立即返回错误 → 用户需等待 60 秒超时才看到 "Timeout"
- 端口占用 → "llm start" 返回错误 → 同上
- 模型文件缺失 → "llm start" 返回错误 → 同上

**与 O-09 的关系**: O-09 覆盖 `LlmChatWorker` 在 `execute()` 异步未完成时 emit 假 error。PRTS-05 覆盖 PRTS 页面启动流程中命令结果未检查，属于不同模块和不同根因。

**影响面**:
- **低**：功能正确性不受影响——轮询 timer 最终会检测到 LLM 未就绪。但用户体验受损——启动失败需要等待 60 秒超时才能看到明确状态，而非即时反馈。

**修复建议**:

在 `_on_command_finished` 中增加 "llm start" 结果处理：

```python
def _on_command_finished(self, command: str, result: dict) -> None:
    cmd_parts = command.split()
    if len(cmd_parts) >= 2 and cmd_parts[0] == "llm" and cmd_parts[1] == "start":
        if result.get("status") != "success":
            self._append_chat("系统", f"LLM 启动失败: {result.get('message', 'unknown')}")
            self._startup_timer.stop()
            self._status_label.setText(locale.tr("llm_start_failed", "Start Failed"))
            self._status_label.setStyleSheet(RED_STYLE)
            return
        # 启动命令成功，继续轮询确认就绪
        self._append_chat("系统", locale.tr("llm_start_success", "LLM process started, waiting for ready..."))
    elif ...
```

---

## 审计结论（批次 89）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 89 | REC-02 (`_extract_features` 异常静默返回空特征字典) | **结论正确**。`recognizer.py:407-432` 使用 `except Exception: return {}`，无警告日志。页面分类降级时用户无感知。 |
| 批次 89 | REC-03 (`_load_catalog` 异常静默且日志级别过低) | **结论正确**。`recognizer.py:453-469` 使用 `except Exception as e: logger.debug(...)`，catalog 损坏仅 debug 日志。`TemplateBackend.__init__` (line 62-68) 同样使用 `except Exception: pass` 静默忽略 catalog 加载失败。 |

**批次 89 全部 2 项新发现经本批次逐项源码复核确认准确，无需修正。**

**补充观察**：`TemplateBackend.__init__` (line 62-68) 存在与 REC-03 相同的模式：
```python
if catalog_path and Path(catalog_path).exists():
    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._catalog = data.get("elements", {})
    except Exception:
        pass
```
这进一步印证了 REC-03 的系统性——catalog 加载异常静默是跨模块的模式，不仅是 `recognizer.py` 的问题。

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| 代码质量（低） | 1 | SHELL-01 (shell() 不检查 daemon 错误) |
| 用户体验（低） | 1 | PRTS-05 (启动结果未校验) |
| 高风险 | 0 | — |
| 中风险 | 0 | — |

**本轮无中高风险发现。**

---

*批次 90 报告 | 仅分析，无文件修改*
