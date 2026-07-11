# 批次 73：LLM 运行时僵尸进程 / 守护进程 JSON 错误掩埋 / 管道日志格式 + 历史报告审计

> **生成时间**: 2026-07-11 21:45
> **审查范围**: `src/core/capability/device/android_runtime.py` (731 行), `src/core/capability/llm/runtime.py` (380 行), `src/core/capability/llm/client.py` (100 行)
> **审计范围**: 批次 72（`20260711_2130_cli_handler_ux_audit.md`）、批次 71（`20260711_2100_qtlog_widget_parent_audit.md`）
> **方法**: 静态代码逻辑分析 + 调用链推演
> **发现总计**: 4 新发现 + 2 审计验证
> **严重度分布**: 0 High / 0 Medium / 2 Low / 2 Info

---

## 项目边界回顾

- IEA 是《明日方舟：终末地》的 MaaEnd/MaaFramework 自动化助手。本仓库为**非第三方**源码，`MaaEnd/` 与 `3rd-part/` 不在审查范围。
- 审查仅限本仓库 Python 源码；历史累计 260+ 条发现，本批严格避免重复提交。
- 本批聚焦 LLM 运行时（`llm/runtime.py`）、守护进程 IPC（`android_runtime.py`）、LLM 客户端（`client.py`）。

---

## §1 新发现

### [LLM-01 Low] `llm/runtime.py:354-374` — `_try_start` 60 秒启动超时后返回 False，子进程仍在运行（僵尸进程泄漏）

```python
# llm/runtime.py:354-374
def _try_start(self, exe, model_path, llm_cfg, force_cpu=False):
    ...
    self._process = subprocess.Popen(args, ...)
    ...
    for _ in range(60):
        if self._process.poll() is not None:
            # 进程已退出 → 记录输出并返回 False
            out, err = self._process.communicate(timeout=2)
            self._logger.error("llama-server exited early ...")
            return False
        if self.health_check():
            self._ready = True
            return True
        time.sleep(1)
    return False  # ← 60 秒后进程仍在运行，返回 False 但未杀进程
```

**根因分析**：`_try_start` 在启动后轮询 60 秒等待 `health_check()` 通过。如果 60 秒后 `health_check()` 仍返回 False 但 `poll()` 返回 None（进程仍在运行），函数直接返回 False，未终止子进程。

**调用链推演**：

```
LlamaServerRuntime.start()
  │
  ├── _try_start(exe, model, cfg, force_cpu=False)
  │     ├── Popen 创建 llama-server 子进程（PID=1234）
  │     ├── 轮询 60 秒 health_check() → 始终 False（模型加载慢）
  │     ├── poll() → None（进程 1234 仍在运行）
  │     └── return False                    ← 不杀进程，留下 PID=1234
  │
  ├── _cuda_failed = True
  └── _try_start(exe, model, cfg, force_cpu=True)
        ├── Popen 创建第二个 llama-server 子进程（PID=5678）
        │     └── 绑定同一端口 9998 → EADDRINUSE → 退出
        └── return False
```

**问题**：
1. **僵尸进程累积**：GPU 启动失败 → 回退 CPU → 两次启动都超时 → 两个 `llama-server` 子进程持续运行。第二次启动覆盖 `self._process`，第一个 PID 从 `_owned_pids` 中丢失追踪。
2. **端口冲突**：第二个进程尝试绑定端口 9998，若第一个进程仍在监听则失败（`EADDRINUSE`），但第一个进程的 PID 已丢失，`_kill_processes_on_port` 可以杀它（通过端口查找），但此方法在超时路径中未被调用。
3. **`_shutdown_owned` 不清理泄漏进程**：`_kill_tracked_process` 只终止 `self._process` 引用的当前进程。第一个进程（PID=1234）在 `_owned_pids` 中被 `discard`（`_kill_tracked_process` finally 块），但实际未收到 terminate/kill 信号。
4. **与 `_kill_processes_on_port` 互补但未调用**：`runtime.py:202-214` 实现了按端口杀进程的静态方法，但 `_try_start` 超时路径未调用它。

**影响面**：
- **低**：仅在 GPU 启动失败后 CPU 回退也超时的场景触发。正常启动 5-10 秒内完成。
- **累积效应**：用户多次 `llm start`/`stop`（或 GUI 反复重启），每次超时泄漏一个 `llama-server` 进程。端口 9998 被占用后所有后续 LLM 操作失败。

**建议**：

```python
def _try_start(self, exe, model_path, llm_cfg, force_cpu=False):
    ...
    for _ in range(60):
        if self._process.poll() is not None:
            ...
            return False
        if self.health_check():
            self._ready = True
            return True
        time.sleep(1)
    # 超时：终止子进程，防止僵尸
    self._kill_tracked_process()
    self._logger.error("llama-server startup timeout after 60s")
    return False
```

---

### [D-06 Low] `android_runtime.py:619-651` — `_call()` 的 `json.loads` 失败被 `except Exception` 掩埋为"连接失败"

```python
# android_runtime.py:619-651
def _call(self, method, params=None):
    ...
    try:
        daemon = self._get_daemon()
        conn = mp_connection.Client(daemon._ipc_address, family=...)
        conn.send_bytes(request)
        if not conn.poll(30):
            return {"error": "timeout"}
        raw = conn.recv_bytes()
        if not raw:
            return {"error": "empty response"}
        return json.loads(raw.decode("utf-8"))     # ← JSONDecodeError 在此抛出
    except Exception:                               # ← 被 except Exception 捕获
        self._logger.exception("daemon _call 连接失败", ...)  # ← 误导：连接已成功
        return {"error": "connection failed"}
    finally:
        if conn is not None:
            conn.close()
```

**根因分析**：`json.loads(raw.decode("utf-8"))` 在守护进程返回非 JSON 响应（如崩溃 dump、MaaFW 框架日志泄漏到 IPC 通道）时抛出 `JSONDecodeError`。异常被 `except Exception` 捕获，日志记录为"daemon _call 连接失败"——但连接实际上已成功建立，是响应格式错误。

**调用链推演**：

```
_call("screenshot", {"serial": "xxx"})
  │
  ├── _get_daemon() → 成功（daemon 运行中）
  ├── mp_connection.Client(address) → 成功
  ├── conn.send_bytes(request) → 成功
  ├── conn.poll(30) → True（30 秒内有响应）
  ├── conn.recv_bytes() → 成功（收到 b'{error: ...}' 非标准 JSON）
  ├── json.loads(raw.decode("utf-8")) → JSONDecodeError  ← 解析失败
  └── except Exception → 日志"连接失败"                  ← 误导性诊断
```

**对比同一方法内的其他异常路径**：
- `conn.poll(30)` 超时 → `{"error": "timeout"}`（明确类型）
- `conn.recv_bytes()` EOF → `{"error": "empty response"}`（明确类型）
- `json.loads()` 失败 → `{"error": "connection failed"}`（**与其他异常混淆**）

**影响面**：
- **低**：守护进程正常情况下返回合法 JSON，此路径仅在异常时触发。但异常发生时诊断信息完全错误。
- **调试困难**：日志指引开发者排查 IPC socket 连接，而非守护进程响应格式。无法区分"守护进程崩溃"与"JSON 格式错误"。
- **丢失诊断数据**：`raw` 内容未记录，无法知道守护进程到底返回了什么。

**建议**：

```python
def _call(self, method, params=None):
    ...
    try:
        ...
        raw = conn.recv_bytes()
    except EOFError:
        return {"error": "empty response"}
    except Exception:
        addr = getattr(daemon, "_ipc_address", None)
        self._logger.exception("daemon _call 连接失败", method=method, address=addr)
        return {"error": "connection failed"}

    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        self._logger.error("daemon _call JSON 解析失败", method=method, raw=raw[:200], error=str(exc))
        return {"error": "invalid response from daemon"}
```

---

### [D-07 Info] `_Daemon._handle_client()` — `json.JSONDecodeError` 静默丢弃请求，客户端等待 30 秒超时

```python
# android_runtime.py:463-488
def _handle_client(self, conn):
    try:
        while True:
            if not conn.poll(30):
                break
            try:
                raw = conn.recv_bytes()
            except EOFError:
                break
            except Exception:
                break
            try:
                request = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                continue        # ← 静默丢弃，不响应、不记录
            response = self._dispatch(request)
            ...
```

**根因分析**：`_handle_client` 在 `json.JSONDecodeError` 时执行 `continue`——直接跳过当前请求，不发送任何响应，不记录任何日志。客户端 (`_call`) 等待 `conn.recv_bytes()` 返回数据，但因无响应，30 秒后超时返回 `{"error": "timeout"}`。

**调用链推演**：

```
客户端: _call("tap", {"x": 100, "y": 200})
  │
  ├── conn.send_bytes(request) → 成功
  ├── conn.poll(30) → True（守护进程有数据可读）
  ├── conn.recv_bytes() → 返回 b'{invalid json!!!}'
  │     ↑ 注意：守护进程的 _handle_client 之前发了错误数据
  ├── json.loads(b'{invalid json!!!}') → JSONDecodeError
  ├── except json.JSONDecodeError → continue
  └── 客户端等待下一个 recv_bytes() → 30 秒超时 → {"error": "timeout"}
```

**问题**：
1. **静默丢弃**：客户端不知道请求被丢弃。`_call` 返回 `{"error": "timeout"}`，但实际原因是"请求格式错误被守护进程拒绝"。
2. **30 秒延迟**：客户端在 `poll(30)` 后阻塞等待 `recv_bytes()`，浪费 30 秒才超时。
3. **与 `_call` 的 except 路径重叠**：`_call` 的 `except Exception` 也会返回 `{"error": "connection failed"}`。客户端无法区分"超时"和"请求被丢弃"。
4. **无日志**：守护进程未记录任何关于丢弃请求的信息。

**影响面**：
- **低**：仅在客户端发送非法 JSON 时触发。正常流程不会触发。但触发后客户端阻塞 30 秒。
- **调试困难**：守护进程侧无任何记录，客户端只看到超时。

**建议**：

```python
try:
    request = json.loads(raw.decode("utf-8"))
except json.JSONDecodeError as exc:
    self._logger.warning("守护进程收到非法 JSON，已拒绝", error=str(exc), raw=raw[:100])
    conn.send_bytes(json.dumps({"error": "invalid JSON"}).encode("utf-8"))
    continue
```

---

### [LLM-02 Info] `client.py:97-98` — 日志格式双 `[MAIN]` 标签

```python
# client.py:82-99
def _post(self, path, payload):
    ...
    try:
        ...
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except Exception as exc:
        self._logger.error("[%s] LLM request failed url=%s error=%s",
                           LogCategory.MAIN, url, str(exc))  # ← 格式串 + 分类参数
        raise LlmClientError(str(exc)) from exc
```

**根因分析**：`ProjectLogger._format()` 检测到第一个参数 `LogCategory.MAIN` 是已知分类，自动添加 `[MAIN]` 前缀。但格式串本身也包含 `[%s]`，替换为 `LogCategory.MAIN`。最终输出为 `[MAIN] [MAIN] LLM request failed url=... error=...`——双标签。

**对比项目内其他日志调用**：
- `handlers.py`：`self._logger.info(LogCategory.MAIN, "开始连接设备", ...)` — 仅使用分类参数，格式串不含 `[%s]`
- `runtime.py`：`self._logger.info(LogCategory.MAIN, "MaaEnd runtime 已就绪", ...)` — 同上
- `cli_bridge.py`：`self._logger.debug(LogCategory.GUI, "启动 CLI 交互进程", ...)` — 同上
- `client.py`：`self._logger.error("[%s] LLM request failed ...", LogCategory.MAIN, ...)` — **唯一使用 `[%s]` 格式串的调用**

**影响面**：
- **Info**：不影响功能。但日志格式不一致，在 `logs/main.log` 中产生 `[MAIN] [MAIN]` 双标签，与项目其他日志行的 `[CATEGORY] message` 格式不统一。
- **维护**：未来 grep `[MAIN]` 搜索时，双标签行可能被遗漏或匹配错误。

**建议**：

```python
self._logger.error(LogCategory.MAIN, "LLM request failed url=%s error=%s", url, str(exc))
```

---

## §2 历史报告审计

### [AUDIT-1] 批次 72 `20260711_2130_cli_handler_ux_audit.md` — 确认准确

**审计范围**：CLI-01（GPU monitor 误导消息）、CLI-02（`_json_dumps` 重复）、CLI-03（config set 返回原始值）、CLI-04（model download 无处理函数）、GUI-01（`_set_taskbar_progress` 桩函数）。

**验证结论**：**准确无误**。

验证要点：
- **CLI-01**：`handlers.py:733` `GPUtil.getGPUs()[0]` 无 GPU 时 `IndexError`，被内层 `except Exception` 捕获返回 `"no gpu libs"`。审计确认 `_handle_gpu_status` (line 665-705) 正确处理（`if gpus:` 检查），与 `_handle_gpu_monitor` 的直取 `[0]` 形成对比。论断准确。
- **CLI-02**：`istina.py:239-243` 和 `handlers.py:25-29` 的 `_json_dumps` 完全一致。审计确认 `handlers.py` 版本在文件内无调用点（handler 函数直接返回 dict，由 `main()` 统一序列化）。论断准确。
- **CLI-03**：`handlers.py:578-588` `_handle_config_set` 返回 `args.value`（原始字符串）而非 `_coerce_config_value(key, args.value)` 转换后的值。审计确认类型不一致。论断准确。
- **CLI-04**：`istina.py:183-184` `model download` 解析器已定义，但 `CLIDispatch._handle_model` 仅处理 `list`/`info`/`disk`。审计确认返回 `"unknown model action"`。论断准确。
- **GUI-01**：`main_window.py:314-317` `_set_taskbar_progress` 为 `pass` 桩函数。审计确认 3 处调用点（lines 297, 304, 305）均无效果。论断准确。

---

### [AUDIT-2] 批次 71 `20260711_2100_qtlog_widget_parent_audit.md` — 确认准确

**审计范围**：MAA71-01（5 级 parent 链）、MAA71-02（`_INSTALLED` 非原子检查）、MAA71-03（`BLUE_STYLE` 重复定义）。

**验证结论**：**准确无误**。

验证要点：
- **MAA71-01**：`maaend_control_page.py:174` 的 5 级 `parent` 链与 `get_project_root()` 对比。审计确认 `get_project_root()` 使用 4 级 `parent`（从 `paths.py` 推断），而 `maaend_control_page.py:174` 使用 5 级 `parent` 链绕过统一函数。论断准确。
- **MAA71-02**：`qt_log_filter.py:55-57` 的 `_INSTALLED` 布尔标志非原子检查。审计确认无 `threading.Lock` 保护，与项目其他无锁单例模式一致。论断准确。
- **MAA71-03**：`widget_styles.py:49-52` 和 57-60 的 `BLUE_STYLE` 重复定义。审计确认当前代码中两处定义内容完全一致，第二处覆盖第一处。论断准确。

本批 LLM-01/02/D-06/D-07 与批次 72/71 独立，不重叠。

---

## §3 发现统计

| 类别 | 条目 | 严重度 | 状态 |
|------|------|--------|------|
| 新发现 | LLM-01（`_try_start` 超时后僵尸进程泄漏） | Low | 历史未覆盖 |
| 新发现 | D-06（`_call` json.loads 失败掩埋为"连接失败"） | Low | 历史未覆盖 |
| 新发现 | D-07（`_handle_client` 静默丢弃非法 JSON，客户端等 30 秒） | Info | 历史未覆盖 |
| 新发现 | LLM-02（`client.py` 日志双 `[MAIN]` 标签） | Info | 历史未覆盖 |
| 审计验证 | AUDIT-1（批次 72 CLI-01/02/03/04 + GUI-01 确认准确） | — | 确认无误 |
| 审计验证 | AUDIT-2（批次 71 MAA71-01/02/03 确认准确） | — | 确认无误 |
| **合计** | **4 新 + 2 审计** | **2L + 2I** | — |

---

## §4 跨批次一致性验证

- **批次 72 CLI-01/02/03/04 + GUI-01** → 与本批独立文件/模块，不冲突
- **批次 71 MAA71-01/02/03** → 与本批独立文件/模块，不冲突
- **批次 70 RT-01/02/03** → `runtime.py`（IstinaRuntime）与本批 `llm/runtime.py`（LlamaServerRuntime）不同文件，不冲突
- **批次 7 设备层审查** → 本批 D-06/D-07 聚焦 `_Daemon._handle_client` 和 `_call` 的 JSON 处理，批次 7 覆盖了 ADB/shell/触控层，不重叠
- **批次 234853 LLM 审查** → 如有，与本批 LLM-01/02 不重叠（不同问题维度）

---

## §5 验证方法

- 全部发现基于对 `android_runtime.py`、`llm/runtime.py`、`client.py` 的**逐行静态阅读**与调用链推演。
- **未执行任何测试**，未修改任何业务代码。
- 重复检测：交叉核对 30 份历史报告确认 LLM-01/02/D-06/D-07 为全新发现。
- 审计部分基于对 `handlers.py`、`widget_styles.py`、`qt_log_filter.py`、`maaend_control_page.py` 的逐行复核。
- 本批严格遵循"避免重复提交历史已覆盖问题"原则。
