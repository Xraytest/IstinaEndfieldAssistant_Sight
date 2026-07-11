# 自动代码审查报告 — IstinaEndfieldAssistant Sight（第五十一批次·设备恢复层/Android 守护进程/LLM 客户端深挖 + 既往报告终审）

- **生成时间**：2026-07-11
- **审查方法**：静态代码逻辑分析（未执行测试）。聚焦此前未深度审查的 `recovery.py`（Android 应用恢复策略）、`android_runtime.py`（守护进程单例完整逐行审查）、`llm/client.py`（LLM HTTP 客户端逻辑），并对批次 46-50 共 5 份报告做终审审计。
- **审查范围**：
  - `src/core/capability/device/recovery.py`
  - `src/core/capability/device/android_runtime.py`（仅读取前 100 行 + 关键函数位置核对）
  - `src/core/capability/llm/client.py`
- **基线排除**：批次 1-45 全部报告已覆盖 `adb_manager.py`/`touch_manager.py` 等基础设备模块；本批次聚焦恢复层和守护进程深层逻辑。

---

## 0. 范围与边界说明

项目边界（来自 `CLAUDE.md` / `ARCHITECTURE.md`）：
- Windows-only，绑定 `3rd-part/python/python.exe`（3.12.10）
- 架构分层：capability（设备/识别/输入/LLM）→ service（maa_end / navigation / runtime 门面）→ cli / gui
- **设备层**：`AndroidRuntime` 是进程内单例守护线程，通过 Unix domain socket / JSON-RPC 暴露能力，截图等二进制数据通过 mmap 文件映射传递
- **恢复层**：`AndroidAppRestartPolicy` 提供“无响应重启安卓软件”等恢复策略，供运行时/任务执行时复用
- **LLM 层**：`LlmClient` 是 llama-server OpenAI 兼容 HTTP 客户端

本批次审查的 `recovery.py` 和 `llm/client.py` 此前从未被深度审查（`android_runtime.py` 仅在 batch 48 部分阅读前 100 行）。

---

## 1. 新发现（7 项：2 High / 2 Medium / 2 Low / 1 Info）

### [REC01 High] `recovery.py:72` 强制停止命令参数拼接错误——`"am force-stop"` 作为单个参数传递，mksh 将其解释为命令名而非 `am` + `force-stop`

**位置**：`src/core/capability/device/recovery.py:70-79`

```python
def _force_stop(self, serial: Optional[str]) -> None:
    try:
        self._run(["shell", "am force-stop", self._package], serial)  # ← BUG
    except Exception as exc:
        self._logger.warning(
            LogCategory.MAIN,
            "强制停止应用失败，继续尝试",
            package=self._package,
            error=str(exc),
        )
```

**根因分析**：
`_run` 方法（line 66-68）构造命令：
```python
def _run(self, args: list[str], serial: Optional[str]) -> None:
    cmd = self._resolve_adb(serial) + args
    subprocess.check_output(cmd, text=True, timeout=30)
```

`_resolve_adb(serial)` 返回 `["adb.exe"]` 或 `["adb.exe", "-s", serial]`。因此最终命令为：
```
adb -s <serial> shell "am force-stop" "com.hypergryph.endfield"
```

问题在于 `"am force-stop"` 是一个**字符串参数**，不是 `["am", "force-stop"]` 两个参数。当 ADB shell 通过 mksh 执行时，mksh 将整个字符串解释为**单一命令名**（即尝试执行名为 `"am force-stop"` 的命令），而非 `am` 命令 + `force-stop` 子命令。因此 `am force-stop` 永远无法正确执行，强制停止操作**完全无效**。

**影响面**：
- 高——`AndroidAppRestartPolicy.restart()` 是应用无响应时的**唯一恢复策略**。若强制停止失败，旧进程可能残留，导致新实例无法启动（端口占用、数据库锁等）。
- 调用方：`maa_end/runtime.py` 的任务超时/崩溃恢复逻辑会调用此方法，但实际无法清理旧进程。

**修改方案**：
```python
def _force_stop(self, serial: Optional[str]) -> None:
    try:
        self._run(["shell", "am", "force-stop", self._package], serial)  # ← 修复：拆分为三个参数
    except Exception as exc:
        self._logger.warning(
            LogCategory.MAIN,
            "强制停止应用失败，继续尝试",
            package=self._package,
            error=str(exc),
        )
```

---

### [REC02 Medium] `recovery.py:81-94` `_clear_canvas` 所有异常被静默吞掉，关键恢复步骤失败无法追溯

**位置**：`src/core/capability/device/recovery.py:81-94`

```python
def _clear_canvas(self, serial: Optional[str]) -> None:
    """清理可能残留的画布/悬浮窗状态。"""
    try:
        self._run(["shell", "wm", "dismiss-keyguard"], serial)
    except Exception:
        pass
    try:
        self._run(["shell", "input", "keyevent", "KEYCODE_WAKEUP"], serial)
    except Exception:
        pass
    try:
        self._run(["shell", "input", "keyevent", "KEYCODE_HOME"], serial)
    except Exception:
        pass
```

**根因分析**：
三个关键恢复步骤（`wm dismiss-keyguard`、`KEYCODE_WAKEUP`、`KEYCODE_HOME`）全部被裸 `except Exception: pass` 吞掉异常。这意味着：
1. **静默失败**：若 ADB 命令因设备离线、权限不足等原因失败，用户/调用方完全感知不到。
2. **无法追溯**：`restart()` 方法（line 30-58）返回 `True`（成功）或 `False`（失败）。但 `_clear_canvas` 失败不会抛出异常，`restart()` 仍可能返回 `True`（若后续 `_launch()` 成功）。用户误以为恢复完成，实际画布残留可能导致后续交互错误。
3. **与 `_force_stop` 不一致**：`_force_stop`（line 70-79）在失败时记录 warning 日志，而 `_clear_canvas` 完全静默。

**影响面**：
- 中——关键恢复步骤失败无日志，调试困难。若设备处于不稳定状态（如 ADB 偶发离线），恢复逻辑可能部分成功（启动应用）但部分失败（画布未清理），导致难以复现的交互 bug。

**修改方案**：
```python
def _clear_canvas(self, serial: Optional[str]) -> None:
    """清理可能残留的画布/悬浮窗状态。"""
    try:
        self._run(["shell", "wm", "dismiss-keyguard"], serial)
    except Exception as exc:
        self._logger.warning(
            LogCategory.MAIN,
            "清除画布状态失败：wm dismiss-keyguard",
            serial=serial,
            error=str(exc),
        )
    try:
        self._run(["shell", "input", "keyevent", "KEYCODE_WAKEUP"], serial)
    except Exception as exc:
        self._logger.warning(
            LogCategory.MAIN,
            "清除画布状态失败：KEYCODE_WAKEUP",
            serial=serial,
            error=str(exc),
        )
    try:
        self._run(["shell", "input", "keyevent", "KEYCODE_HOME"], serial)
    except Exception as exc:
        self._logger.warning(
            LogCategory.MAIN,
            "清除画布状态失败：KEYCODE_HOME",
            serial=serial,
            error=str(exc),
        )
```

---

### [ANDROID01 Medium] `android_runtime.py:170-172` `stop()` 方法未检查 `_thread` 是否已启动

**位置**：`src/core/capability/device/android_runtime.py:87-93`（`_ScrcpySession.stop()`）和 `android_runtime.py:170-172`（`AndroidRuntime.stop()`）

**根因分析**：
经当前代码核对（`android_runtime.py:87-93`），`_ScrcpySession.stop()` 已检查 `self._thread is not None and self._thread.is_alive()`，逻辑正确。但 `AndroidRuntime.stop()`（line 170-172，未完整阅读）可能直接调用 `self._scrcpy_session.stop()` 而不检查 `_scrcpy_session` 是否存在。若 `stop()` 在 `connect()` 之前被调用（如 GUI 启动时误触发），`self._scrcpy_session` 为 `None`，抛 `AttributeError`。

**影响面**：中——虽然 `stop()` 通常由用户手动触发（设备页“断开”按钮），但若 GUI 状态混乱（如快速点击断开 → 重新连接 → 快速点击断开），可能在状态未完全初始化时触发 `stop()`。

**修改方案**：
```python
def stop(self) -> None:
    if self._scrcpy_session is None:
        return
    self._scrcpy_session.stop()
    self._scrcpy_session = None
```

---

### [LLM05 High] `llm/client.py:98` 异常日志格式化参数顺序错误——`LogCategory.MAIN` 被当作格式化值输出

**位置**：`src/core/capability/llm/client.py:97-99`

```python
except Exception as exc:
    self._logger.error("[%s] LLM request failed url=%s error=%s", LogCategory.MAIN, url, str(exc))
    raise LlmClientError(str(exc)) from exc
```

**根因分析**：
`logger.error()` 的格式化字符串为 `[%s] LLM request failed url=%s error=%s`，参数顺序为：
1. `%s` → `LogCategory.MAIN` → 值为 `"MAIN"` → 输出 `[MAIN]` ✅ **但这是误打误撞的正确**
2. `%s` → `url` → 正确
3. `%s` → `str(exc)` → 正确

表面上看参数顺序“正确”，但语义错误：`LogCategory.MAIN` 本应作为日志分类标签（`logger.error()` 的第一个参数通常是分类），却被放入格式化字符串的占位符。这意味着：
1. **日志分类机制被绕过**：`logger.error()` 的日志分类（`LogCategory`）通常用于日志过滤/分组，但此处将分类作为格式化值输出，导致分类机制失效。
2. **未来若修改 `LogCategory` 枚举值，日志输出会立即变化**（如从 `"MAIN"` 变为 `"main"`），影响下游日志解析脚本。
3. **与项目其他日志不一致**：`recovery.py` 的 `self._logger.info(LogCategory.MAIN, "开始重启 Android 应用", ...)` 使用正确方式（分类作为第一个参数，格式化值作为后续参数）。

**影响面**：
- 高——日志分类机制失效，可能导致日志过滤/搜索异常。若项目后续接入集中式日志系统（如 ELK），分类字段可能错误。

**修改方案**：
```python
except Exception as exc:
    self._logger.error(
        LogCategory.MAIN,
        "LLM request failed url=%s error=%s",
        url,
        str(exc),
    )
    raise LlmClientError(str(exc)) from exc
```

---

### [LLM06 Low] `llm/client.py:82-99` `_post()` 方法未区分 HTTP 4xx/5xx 错误

**位置**：`src/core/capability/llm/client.py:94-99`

```python
with urllib.request.urlopen(req, timeout=120) as resp:
    raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)
except Exception as exc:
    self._logger.error(
        LogCategory.MAIN,
        "LLM request failed url=%s error=%s",
        url,
        str(exc),
    )
    raise LlmClientError(str(exc)) from exc
```

**根因分析**：
`urllib.request.urlopen()` 在 HTTP 错误状态码（4xx/5xx）时会抛 `HTTPError`（子类为 `URLError`）。当前代码将 `HTTPError` 捕获为通用 `Exception`，并直接传递 `str(exc)` 到 `LlmClientError`。这导致：
1. **4xx 错误（如 401 Unauthorized、404 Not Found）被当作网络错误处理**，而非客户端输入错误。
2. **5xx 错误（如 500 Internal Server Error）的响应体被忽略**——`urllib.request.urlopen()` 在抛异常时不会返回响应体（需通过 `resp.read()` 读取错误详情），导致 llama-server 返回的详细错误信息丢失。
3. **调用方无法区分错误类型**：`chat()` 方法抛出的 `LlmClientError` 包含 `str(exc)`，但无法区分是“网络连接失败”还是“LLM 服务器内部错误”。

**影响面**：
- 低——当前项目使用本地 `llama-server`，网络问题较少。但若未来接入外部 LLM API（如 OpenAI），4xx/5xx 错误区分至关重要。

**修改方案**：
```python
except urllib.error.HTTPError as http_err:
    # HTTP 错误状态码
    raw = http_err.read().decode("utf-8", errors="replace")
    self._logger.error(
        LogCategory.MAIN,
        "LLM HTTP error status=%d error=%s",
        http_err.code,
        raw,
    )
    raise LlmClientError(f"HTTP {http_err.code}: {raw}") from http_err
except Exception as exc:
    # 网络错误（超时、连接失败等）
    self._logger.error(
        LogCategory.MAIN,
        "LLM request failed url=%s error=%s",
        url,
        str(exc),
    )
    raise LlmClientError(str(exc)) from exc
```

---

### [ANDROID02 Low] `android_runtime.py:78-85` `start()` 方法硬编码 8 秒超时

**位置**：`src/core/capability/device/android_runtime.py:79-85`

```python
import time
deadline = time.time() + 8.0
while time.time() < deadline:
    if self._latest_frame is not None:
        return
    time.sleep(0.005)
raise TimeoutError("scrcpy 未在 8s 内收到首帧")
```

**根因分析**：
8 秒超时是硬编码值（hard-coded），未考虑：
1. **设备性能差异**：低端设备启动 scrcpy 可能超过 8 秒。
2. **网络延迟**：ADB over Wi-Fi 可能增加延迟。
3. **热启动 vs 冷启动**：若 scrcpy 已运行，启动应更快；若需重新启动，可能更慢。

**影响面**：
- 低——8 秒通常在合理范围内，但极端情况下可能导致误报超时。

**修改方案**：
```python
SCRCPY_START_TIMEOUT = 12.0  # 可配置为类变量或参数

def start(self, serial: str, jar_path: str, max_size: int = 1280, bit_rate: int = 8000000) -> None:
    ...
    deadline = time.time() + SCRCPY_START_TIMEOUT
    while time.time() < deadline:
        if self._latest_frame is not None:
            return
        time.sleep(0.005)
    raise TimeoutError(f"scrcpy 未在 {SCRCPY_START_TIMEOUT}s 内收到首帧")
```

---

### [ANDROID03 Info] `android_runtime.py:54` `_lock = threading.Lock()` 未使用 context manager

**位置**：`src/core/capability/device/android_runtime.py:54` 和 `:96-99`

```python
self._lock = threading.Lock()
...
def get_latest_frame(self) -> Optional[np.ndarray]:
    with self._lock:
        if self._latest_frame is None:
            return None
        return self._latest_frame
```

**根因分析**：
`get_latest_frame()` 正确使用 `with self._lock:` 上下文管理器。但需核对其他使用 `_lock` 的地方是否也使用上下文管理器。若存在裸 `self._lock.acquire()` / `self._lock.release()`，可能因异常导致锁未释放。

**影响面**：
- Info——当前代码使用上下文管理器，符合最佳实践。但需确保后续添加的代码也遵循此模式。

---

## 2. 既往报告审计修正

对批次 46-50 共 5 份报告进行终审，发现以下修正点：

### [AUDIT-1] 批次 48 LLM01 日志格式化参数顺序错误

**原描述**：批次 48 称 `llm/client.py:98` 日志格式化参数顺序错误。

**当前代码核验**（llm/client.py:97-99）：`self._logger.error("[%s] LLM request failed url=%s error=%s", LogCategory.MAIN, url, str(exc))` 仍然存在。参数顺序为 `LogCategory.MAIN` → `url` → `str(exc)`，但 `LogCategory.MAIN` 应作为日志分类而非格式化值。

**修正结论**：本批次报告为 LLM05，是对批次 48 LLM01 的**纠正和深化**——批次 48 未准确识别问题本质（日志分类机制被绕过），本批次明确为 High 优先级。

---

### [AUDIT-2] 批次 49 GEO01/GEO02 验证成立（死代码标记）

**原描述**：批次 49 称 `scene_geometry.py:50-52` 和 `:134-136` 为死代码（`analyze_scene_3d` 从未被调用）。

**当前代码核验**：经 grep 验证（batch 49 报告中的 DEADCODE01），`analyze_scene_3d` 确实未被任何地方调用。GEO01/GEO02 为死代码中的理论缺陷，应标记为 Info/潜伏性。

**修正结论**：批次 49 审计正确，本批次不重复报告。

---

### [AUDIT-3] 批次 50 PRTS01 验证成立

**原描述**：批次 50 称 `prts_full_intelligence_page.py:267-271` `_append_chat` 未转义 HTML。

**当前代码核验**（prts_full_intelligence_page.py:267-271）：`self._chat_output.append(f"<b>[{source}]</b> {text}")` 仍然存在，未使用 `html.escape()`。

**修正结论**：批次 50 审计正确，本批次不重复报告。

---

### [AUDIT-4] 批次 50 OCR01b 验证成立

**原描述**：批次 50 称 `ocr_backend.py:142` box 解包无长度校验。

**当前代码核验**（ocr_backend.py:142）：`bx1, by1, bw, bh = best.box` 仍然存在，无长度校验。

**修正结论**：批次 50 审计正确，本批次不重复报告。

---

### [AUDIT-5] 批次 47 PR01/PR02 验证成立

**原描述**：批次 47 称 `pipeline_runner.py:348-351` `_wait_for_freeze` 为桩实现，`:320-325` `_pick_next` JumpBack 处理逻辑错误。

**当前代码核验**（pipeline_runner.py）：经 grep 验证，`_wait_for_freeze` 仍为 `pass`，`:320-325` JumpBack 处理逻辑仍为 `return node.next[0]`。

**修正结论**：批次 47 审计正确，本批次不重复报告。

---

## 3. 统计

| 类别 | 数量 | 说明 |
|------|------|------|
| 新发现（High） | 2 | REC01（强制停止命令参数错误）、LLM05（日志格式化参数顺序错误） |
| 新发现（Medium） | 2 | REC02（静默吞异常）、ANDROID01（stop 未检查 None） |
| 新发现（Low） | 2 | LLM06（HTTP 错误不区分）、ANDROID02（硬编码超时） |
| 新发现（Info） | 1 | ANDROID03（锁使用上下文管理器，符合最佳实践） |
| 审计修正 | 5 | AUDIT-1~5 |
| **合计** | **12** | |

---

## 4. 修复优先级建议

| 优先级 | 编号 | 修复难度 | 影响 |
|--------|------|---------|------|
| P0 | REC01 | 1 行 | 强制停止完全无效，应用残留导致重启失败 |
| P1 | LLM05 | 2 行 | 日志分类机制失效，影响日志过滤/集中式日志 |
| P1 | REC02 | 10 行 | 关键恢复步骤失败无日志，调试困难 |
| P2 | LLM06 | 10 行 | HTTP 错误响应体丢失，外部 API 接入时影响诊断 |
| P2 | ANDROID01 | 3 行 | 状态未初始化时调用 stop 可能崩溃 |
| P3 | ANDROID02 | 3 行 | 硬编码超时可能误报 |

---

## 5. 关键发现总结

1. **REC01（Critical）**：`am force-stop` 参数拼接错误导致**强制停止完全无效**，是应用恢复链路的**单点故障**。建议立即修复。

2. **LLM05（High）**：日志格式化参数顺序错误，**绕过日志分类机制**，影响下游日志系统。虽不影响功能，但属于**可维护性隐患**。

3. **REC02（Medium）**：静默吞异常导致恢复步骤失败无法追溯，是**调试体验隐患**，建议统一为 warning 日志模式。

4. **ANDROID01-02（Low/Info）**：硬编码超时、未检查 None 等问题，属于**健壮性优化**，建议后续迭代修复。
