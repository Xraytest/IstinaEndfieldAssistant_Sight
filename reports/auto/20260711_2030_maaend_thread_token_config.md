# 批次 76：守护线程竞态 / save_config 非原子写入 / _replace_tokens 级联替换 / PRTS 重复启动保护 / 审计批次 75

> **生成时间**: 2026-07-11 20:30
> **审查范围**: `src/core/service/maa_end/runtime.py` (952 行), `src/core/service/runtime.py` (949 行), `src/gui/pyqt6/prts_full_intelligence_page.py` (272 行)
> **审计范围**: 批次 75（`20260711_2230_tray_quit_i18n_atomic.md`）
> **方法**: 静态代码逻辑分析 + 调用链推演
> **发现总计**: 5 新发现 + 1 审计验证
> **严重度分布**: 0 High / 2 Medium / 1 Low / 2 Info

---

## 项目边界回顾

- IEA 是《明日方舟：终末地》的 MaaEnd/MaaFramework 自动化助手。本仓库为**非第三方**源码，`MaaEnd/` 与 `3rd-part/` 不在审查范围。
- 审查仅限本仓库 Python 源码；历史累计 280+ 条发现，本批严格避免重复提交。
- 本批聚焦 `maa_end/runtime.py` 的守护线程安全性与 token 替换逻辑、`runtime.py` 的配置写入原子性、PRTS 页面的 LLM 启动保护。

---

## §1 新发现

### [MAA-04 Medium] `maa_end/runtime.py:334-353` — `_connect_with_timeout` 守护线程在超时时销毁资源后仍被 join

```python
# maa_end/runtime.py:334-353
def _connect_with_timeout(self, timeout: int) -> bool:
    result = {"success": False}

    def target() -> None:
        try:
            result["success"] = self._connect_once()
        except Exception as exc:
            result["success"] = False
            self.logger.exception(...)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        self.logger.error(...)
        self._cleanup_partial()
        return False

    return result["success"]
```

**根因分析**：当 `thread.join(timeout)` 超时时，守护线程仍在运行。`self._cleanup_partial()` 被调用，将 `_resource`、`_controller`、`_tasker`、`_agent_client`、`_agent_process` 全部置为 `None` 并销毁原生对象。但守护线程的 `target()` 函数仍在执行 `self._connect_once()`，此时它引用的 `self._resource`、`self._controller` 等已被销毁。

**调用链推演**：

```
_connect_with_timeout(timeout=20)
  │
  ├── thread = threading.Thread(target=target, daemon=True)
  ├── thread.start()
  │     └── target() 开始执行
  │           └── self._connect_once()
  │                 ├── self._resource = Resource()      ← 创建资源
  │                 ├── self._controller = AdbController(...)
  │                 ├── self._tasker = Tasker()
  │                 └── ... (耗时操作)
  │
  ├── thread.join(timeout=20)
  │     └── 20 秒后超时，thread.is_alive() == True
  │
  ├── self._cleanup_partial()
  │     ├── self._resource.destroy() → 释放原生资源
  │     ├── self._controller = None
  │     ├── self._tasker = None
  │     ├── self._agent_client.disconnect()
  │     └── self._agent_process.terminate()
  │
  ├── return False  ← 主线程认为连接已清理
  │
  └── target() 仍在运行！
        ├── self._resource (已销毁) → AttributeError 或访问已释放内存
        ├── self._controller (已 None) → AttributeError
        └── self._tasker.bind(self._resource, self._controller) → 崩溃！
```

**问题**：
1. **Use-After-Free 风险**：守护线程在 `_cleanup_partial` 之后继续访问已被销毁的原生对象（MaaFW Resource、AdbController、Tasker），可能导致段错误或 Python 层 AttributeError。
2. **状态不一致**：`_connected` 标志未被设置（`_connect_once` 未完成），但守护线程仍在修改 `self._resource`、`self._controller` 等属性。
3. **无法恢复**：后续 `connect()` 调用时，`_resource` 可能已被守护线程部分重建，或处于不一致状态。

**影响面**：
- **稳定性**：ADB 连接超时时，守护线程可能在后台继续执行，访问已销毁资源，导致进程崩溃。
- **数据一致性**：`_connect_once` 的部分副作用（如已创建但未绑定的 Tasker）可能残留在对象状态中。

**建议**：

方案 1（推荐）：在 `target()` 中定期检查 `_connected` 标志，超时后主动退出：

```python
def _connect_with_timeout(self, timeout: int) -> bool:
    result = {"success": False}

    def target() -> None:
        try:
            # 检查主线程是否已标记超时
            if getattr(self, '_connect_aborted', False):
                return
            result["success"] = self._connect_once()
        except Exception as exc:
            if getattr(self, '_connect_aborted', False):
                return  # 超时后静默退出，不记录无关异常
            result["success"] = False
            self.logger.exception(...)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        self._connect_aborted = True
        self.logger.error(...)
        self._cleanup_partial()
        # 等待守护线程感知超时标志并退出（给一个短暂宽限期）
        thread.join(timeout=2)
        self._connect_aborted = False
        return False

    return result["success"]
```

方案 2（最小）：将守护线程改为非守护线程，超时后强制终止：

```python
thread = threading.Thread(target=target)  # 非守护
thread.start()
thread.join(timeout=timeout)
if thread.is_alive():
    # Python 无法强制终止线程，但非守护线程在进程退出时会等待
    self._connect_aborted = True
    self._cleanup_partial()
    return False
```

---

### [MAA-05 Medium] `maa_end/runtime.py:654-676` — `_wait_job` 守护线程在超时后仍持有 job 引用

```python
# maa_end/runtime.py:654-676
def _wait_job(self, job: Any, timeout: Optional[float]) -> bool:
    if timeout is None or timeout <= 0:
        return job.wait()
    result: Dict[str, Any] = {}

    def _target() -> None:
        try:
            result["ok"] = job.wait()
        except Exception:
            result["ok"] = False

    worker = threading.Thread(target=_target, daemon=True)
    worker.start()
    worker.join(float(timeout))
    if worker.is_alive():
        self.logger.warning(...)
        return False
    return result.get("ok", False)
```

**根因分析**：与 MAA-04 同一模式。当 `worker.join(timeout)` 超时时，守护线程仍在执行 `job.wait()`。`job` 是 MaaFW 的异步任务对象，其 `wait()` 方法会阻塞直到任务完成或内部超时。

**调用链推演**：

```
_wait_job(job, timeout=10)
  │
  ├── worker = threading.Thread(target=_target, daemon=True)
  ├── worker.start()
  │     └── _target()
  │           └── job.wait()  ← 阻塞，可能长时间运行
  │
  ├── worker.join(timeout=10)
  │     └── 10 秒后超时，worker.is_alive() == True
  │
  ├── return False  ← 主线程认为任务已超时
  │
  └── worker 仍在运行！
        └── job.wait() 仍在阻塞
```

**问题**：
1. **资源泄漏**：守护线程持有 `job` 引用，`job` 持有 MaaFW 原生资源（如 Tasker 的内部状态、图像缓冲区），这些资源不会被释放直到线程结束。
2. **无法取消**：Python 无法强制终止守护线程。`job.wait()` 无法被中断，守护线程将一直阻塞到任务完成或 MaaFW 内部超时。
3. **重复调用风险**：`_wait_job` 被 `run_pipeline`、`run_task`、`_retry_task` 调用。若多次超时，多个守护线程同时持有 job 引用，资源泄漏累积。

**影响面**：
- **内存泄漏**：每次超时创建一个泄漏的守护线程，持有 MaaFW 原生资源。
- **频率**：任务执行超时场景（网络抖动、设备卡顿）可能频繁触发。

**建议**：

方案 1（推荐）：在 job 对象上设置超时标志，让 `_target` 检查并提前退出：

```python
def _wait_job(self, job: Any, timeout: Optional[float]) -> bool:
    if timeout is None or timeout <= 0:
        return job.wait()
    result: Dict[str, Any] = {}
    abort = threading.Event()

    def _target() -> None:
        try:
            # 分段等待，定期检查 abort 标志
            deadline = time.time() + timeout
            while time.time() < deadline:
                if abort.is_set():
                    result["ok"] = False
                    return
                remaining = deadline - time.time()
                if remaining <= 0:
                    result["ok"] = False
                    return
                # MaaFW job.wait() 通常支持超时参数
                ok = job.wait(timeout=min(remaining, 1.0))
                result["ok"] = ok
                return
        except Exception:
            result["ok"] = False

    worker = threading.Thread(target=_target, daemon=True)
    worker.start()
    worker.join(timeout + 1)  # 额外宽限期
    if worker.is_alive():
        abort.set()  # 通知后台线程退出
        self.logger.warning(...)
        return False
    return result.get("ok", False)
```

方案 2（最小）：记录泄漏线程数，达到阈值时告警：

```python
self._leaked_workers = 0

def _wait_job(self, ...):
    ...
    if worker.is_alive():
        self._leaked_workers += 1
        if self._leaked_workers > 5:
            self.logger.error("过多泄漏的 job 等待线程", count=self._leaked_workers)
        return False
```

---

### [RUNTIME-01 Low] `runtime.py:509-510` — `save_config` 非原子写入

```python
# runtime.py:506-510
def save_config(self) -> None:
    path = self._resolve_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(self._config, f, ensure_ascii=False, indent=2)
```

**根因分析**：`save_config` 使用 `open(path, "w")` 直接写入目标文件。若进程在写入中途被中断，配置文件将处于半写状态——JSON 截断或不完整，导致后续 `json.loads` 抛出 `JSONDecodeError`。

**与项目内其他写入对比**：

| 位置 | 写入方式 | 原子保护 |
|------|---------|---------|
| `settings_page.py:196-211` | `tempfile.mkstemp` + `os.replace` | ✓ 原子 |
| `queue_state.py:122-124` | `.with_suffix(".tmp")` + `os.replace` | ✓ 原子 |
| `runtime.py:509` | `open(path, "w")` | ✗ 非原子 |
| `device_settings_page.py:311` | `write_text` | ✗ 非原子 |
| `maaend_control_page.py:872` | `write_text` | ✗ 非原子 |
| `maaend_control_page.py:1575` | `write_text` | ✗ 非原子 |
| `models.py:53` | `write_text` | ✗ 非原子 |

**调用链推演**：

```
用户修改设置 → settings_page._save_settings()
  ├── 使用 tempfile.mkstemp + os.replace ✓ 原子写入
  └── client_config.json 完整 ✓

IstinaRuntime.save_config() 被调用（如 CLI config 命令）
  ├── open(path, "w") 直接写入
  ├── 进程被中断（崩溃/断电/强制终止）
  └── client_config.json 截断/损坏 ✗

下次启动 → _load_config()
  ├── json.loads() → JSONDecodeError
  ├── 返回 {}
  └── 用户配置全部丢失！
```

**问题**：
1. **数据完整性风险**：`save_config` 的写入中断会导致配置文件损坏，且无备份机制。
2. **与项目内原子写入模式不一致**：`settings_page.py` 和 `queue_state.py` 已使用原子写入，但 `runtime.py` 未跟进。

**影响面**：
- **数据丢失**：CLI 配置修改（如 `istina config set`）中断时配置文件损坏。
- **频率**：低（配置修改频率不高），但一旦发生影响严重。

**建议**：

```python
def save_config(self) -> None:
    path = self._resolve_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    import os
    data = json.dumps(self._config, ensure_ascii=False, indent=2)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
```

---

### [GUI-08 Info] `prts_full_intelligence_page.py:172-177` — 无 LLM 重复启动保护

```python
# prts_full_intelligence_page.py:172-177
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

**根因分析**：`_start_llm` 在启动 LLM 前未检查 LLM 是否已在运行。用户快速多次点击"Start LLM"按钮，会发送多个 `"llm start"` 命令。

**与 `_send_chat` 的对比**：

`_send_chat` (line 234) 有防护：
```python
if self._worker is not None:
    return  # 防止并发发送
```

但 `_start_llm` 没有等效检查。

**调用链推演**：

```
用户快速点击"Start LLM" 3 次
  │
  ├── 第 1 次: _start_llm()
  │     ├── self._bridge.execute("llm start", {})
  │     ├── self._startup_timer.start(2000)
  │     └── LLM 进程开始启动...
  │
  ├── 第 2 次: _start_llm()
  │     ├── self._bridge.execute("llm start", {})  ← 重复！
  │     ├── self._startup_timer.start(2000)         ← 重启轮询
  │     └── 第二个 LLM 进程开始启动...
  │
  ├── 第 3 次: _start_llm()
  │     └── 第三个 LLM 进程开始启动...
  │
  └── 3 个 LLM 进程争夺同一端口 (9998)
        └── 端口冲突 → 部分进程失败 → 状态混乱
```

**问题**：
1. **重复启动**：多次点击发送多个 `"llm start"` 命令，可能启动多个 LLM 进程。
2. **端口冲突**：多个 LLM 进程绑定同一端口 (9998)，导致地址冲突。
3. **轮询重置**：每次点击重启 `_startup_timer`，之前的轮询状态丢失。

**影响面**：
- **资源浪费**：多个 LLM 进程占用大量显存（每个 ~1-2 GB）。
- **UX 困惑**：用户看到"Starting..."状态反复重置，不确定 LLM 是否真正启动。

**建议**：

```python
def _start_llm(self) -> None:
    # 防止重复启动
    if self._startup_timer is not None and self._startup_timer.isActive():
        self._append_chat("系统", locale.tr("llm_already_starting", "LLM is already starting..."))
        return
    if self._status_label.text() == locale.tr("llm_ready", "Ready"):
        self._append_chat("系统", locale.tr("llm_already_running", "LLM is already running."))
        return
    ...
```

并禁用按钮防止重复点击：
```python
self._start_btn.setEnabled(False)
```

---

### [TOKEN-01 Info] `maa_end/runtime.py:637-643` — `_replace_tokens` 级联替换风险

```python
# maa_end/runtime.py:637-643
def _replace_tokens(self, text: str, values: Dict[str, Any]) -> str:
    result = text
    for token, replacement in values.items():
        placeholder = "{" + token + "}"
        if placeholder in result:
            result = result.replace(placeholder, str(replacement))
    return result
```

**根因分析**：`_replace_tokens` 使用 `str.replace` 逐个替换占位符。由于 `str.replace` 替换所有匹配项，如果 replacement 值本身包含 `{...}` 模式，可能被后续迭代替换。

**调用链推演**：

```python
# pipeline_override 包含:
{"greeting": "Hello {name}!", "farewell": "Goodbye {name}!"}

# values 包含:
{"name": "Player", "farewell": "See you later"}

# 迭代顺序不确定（Python 3.7+ dict 保持插入顺序）:
# 假设先替换 "greeting":
result = "Hello {name}!" → "Hello Player!"  ✓

# 再替换 "farewell":
# 注意: replacement "See you later" 不含 {name}，所以没问题

# 但考虑更危险的情况:
# pipeline_override: {"a": "{b}", "b": "{c}"}
# values: {"b": "middle", "c": "final"}

# 迭代顺序: a → b → c
# 1. result = "{b}" → "middle"         (a 被替换)
# 2. result = "middle" → "middle"       (b 被替换，但 "{b}" 已在步骤 1 中消失)
# 3. result = "middle" → "middle"       (c 未被引用)

# 但如果 values 中 a 的替换值包含 {c}:
# pipeline_override: {"a": "prefix {c} suffix"}
# values: {"a": "value_with_{c}", "c": "final"}

# 迭代: a → c
# 1. result = "prefix {c} suffix" → "prefix value_with_{c} suffix"
# 2. result = "prefix value_with_{c} suffix" → "prefix value_with_final suffix"  ← 级联！
```

**问题**：
1. **非预期替换**：replacement 值中的 `{...}` 模式可能被后续迭代替换，导致输出不符合预期。
2. **依赖迭代顺序**：级联替换的结果取决于 dict 迭代顺序，行为不确定。
3. **安全风险**：如果 replacement 来自用户输入，可能被注入额外占位符。

**影响面**：
- **低**：当前 pipeline override 数据来自 MaaEnd JSON 配置文件，replacement 值通常不含 `{...}` 模式。
- **潜在风险**：若未来支持用户自定义选项值，级联替换可能导致意外行为。

**建议**：

使用单次替换（避免迭代级联）：

```python
def _replace_tokens(self, text: str, values: Dict[str, Any]) -> str:
    import re
    def replacer(match):
        token = match.group(1)
        return str(values.get(token, match.group(0)))
    return re.sub(r'\{(\w+)\}', replacer, text)
```

此方案在单次正则替换中处理所有占位符，replacement 值中的 `{...}` 不会被二次替换。

---

### [MAA-06 Info] `maa_end/runtime.py:376-434` — `_cleanup_partial` 存在重复清理代码

```python
# maa_end/runtime.py:376-434
def _cleanup_partial(self) -> None:
    # 循环清理 _resource 和 _controller
    for attr in ("_resource", "_controller"):
        val = getattr(self, attr, None)
        if val is not None:
            try:
                destroy = getattr(val, "destroy", None)
                if callable(destroy):
                    destroy()
            except Exception as exc:
                ...
            try:
                setattr(self, attr, None)
            except Exception:
                pass

    # ... 清理 _tasker ...

    # 再次单独清理 _controller 和 _resource
    try:
        if self._controller is not None:
            self._controller = None
    except Exception as exc:
        ...
    try:
        if self._resource is not None:
            self._resource = None
    except Exception as exc:
        ...
```

**根因分析**：`_resource` 和 `_controller` 在循环中已被置为 `None`，但方法末尾又分别检查并置为 `None`。后两段代码永远不会执行（条件永远为 `False`）。

**问题**：
1. **冗余代码**：后两段 `try/except` 块永远不会执行，增加维护负担。
2. **误导性**：阅读者可能以为循环未覆盖某些场景，或怀疑存在并发修改。
3. **维护风险**：若未来修改循环逻辑，后两段代码可能产生冲突。

**影响面**：
- **代码质量**：冗余代码降低可读性，增加维护成本。
- **功能**：无直接影响（代码行为正确，只是冗余）。

**建议**：

删除末尾的重复清理代码：

```python
def _cleanup_partial(self) -> None:
    for attr in ("_resource", "_controller"):
        val = getattr(self, attr, None)
        if val is not None:
            try:
                destroy = getattr(val, "destroy", None)
                if callable(destroy):
                    destroy()
            except Exception as exc:
                self.logger.warning(...)
            setattr(self, attr, None)  # 不需要 try/except，setattr(None) 不会失败
    # ... 其余清理
```

---

## §2 审计：历史报告验证

### [AUDIT-1] 批次 75 — 全部 9 项发现确认准确

**审计范围**：`20260711_2230_tray_quit_i18n_atomic.md`

**验证方法**：逐项重新阅读相关源码文件，核对代码行号、调用链、严重度评估。

**验证结论**：**全部准确，无错误或不必要建议**。

| 批次 75 发现 | 验证状态 | 备注 |
|---|---|---|
| GUI-05（托盘退出失效） | ✓ 准确 | `QApplication.quit()` → `closeAllWindows()` → `event.ignore()` 调用链正确 |
| GUI-04（默认页硬编码中文） | ✓ 准确 | `"标准推理"` 比较在英文环境下必然失败 |
| SEC-03（device_settings_page 非原子写入） | ✓ 准确 | `write_text` 无原子保护 |
| GUI-07（LLM 超时后进程泄漏） | ✓ 准确 | 60s 后仅停止轮询，不终止 LLM |
| I18N-04（选项 locale 硬编码中文） | ✓ 准确 | `zh_cn.json` 硬编码路径 |
| I18N-05（logger.py 绕过 get_project_root） | ✓ 准确 | `Path(__file__).resolve().parent.parent.parent.parent` |
| SEC-04（models.py 非原子写入） | ✓ 准确 | `write_text` 无原子保护 |
| REC-02（recorder.py 路径错误） | ✓ 准确 | 4 级 parent 链同 GUI-03 |
| GUI-06（PRTS 页面自动启动 LLM） | ✓ 准确 | `showEvent` → `_start_llm()` |

**审计结论**：批次 75 的所有发现均经得起源码复核，修改建议可行，严重度评估合理。无错误建议或不必要报告。

---

## §3 发现统计

| 类别 | 条目 | 严重度 | 状态 |
|------|------|--------|------|
| 新发现 | MAA-04（`_connect_with_timeout` 守护线程竞态） | Medium | 历史未覆盖 |
| 新发现 | MAA-05（`_wait_job` 守护线程竞态） | Medium | 历史未覆盖 |
| 新发现 | RUNTIME-01（`save_config` 非原子写入） | Low | 历史未覆盖 |
| 新发现 | GUI-08（PRTS 无 LLM 重复启动保护） | Info | 历史未覆盖 |
| 新发现 | TOKEN-01（`_replace_tokens` 级联替换） | Info | 历史未覆盖 |
| 新发现 | MAA-06（`_cleanup_partial` 重复清理代码） | Info | 历史未覆盖 |
| 审计验证 | AUDIT-1（批次 75 全部 9 项确认准确） | — | 确认无误 |
| **合计** | **6 新 + 1 审计** | **2M + 1L + 3I** | — |

---

## §4 跨批次一致性验证

- **批次 75 GUI-05/04/07/06 + SEC-03/04 + I18N-04/05 + REC-02** → 本批审计验证确认准确，不重复
- **批次 74 GUI-02/03 + QS-01** → 与本批独立文件/模块，不冲突
- **批次 73 LLM-01/D-06/D-07/LLM-02** → 与本批独立文件/模块，不冲突
- **批次 71 MAA71-01/02/03** → 与本批独立文件/模块，不冲突
- **批次 28 D01** → `_resolve_input_tokens` 深拷贝问题已报告；本批 TOKEN-01 为同一函数的子问题（级联替换），为新增维度
- **批次 8 NAV-01** → `find_by_name("")` 已审计验证，不重复

---

## §5 验证方法

- 全部发现基于对 `maa_end/runtime.py`、`runtime.py`、`prts_full_intelligence_page.py` 的**逐行静态阅读**与调用链推演。
- **未执行任何测试**，未修改任何业务代码。
- 重复检测：交叉核对 38+ 份历史报告确认本批 6 项新发现无重复。
- 审计部分基于对批次 75 报告中 9 项发现的源码逐项复核。
- 本批严格遵循"避免重复提交历史已覆盖问题"原则。
