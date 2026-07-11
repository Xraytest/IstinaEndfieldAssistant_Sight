# 审计批次 94 — NAV-DRAIN 守护线程泄漏 / SCRCPY-SILENT connect 静默 scrcpy 失败 / AUTO-PARAMS 配置读取静默吞错 / PLAYER-SILENT 脚本回放动作失败静默 + 审计批次 93

**生成时间**: 2026-07-11 23:51
**覆盖文件**: `core/capability/device/android_runtime.py`, `core/service/runtime.py`, `gui/pyqt6/pages/maaend_control_page.py`, `gui/pyqt6/scripting/player.py`
**审计方法**: 静态代码逻辑分析，无测试执行
**前置去重**: 已读取 `reports/CODE_REVIEW_WARNS.md`，新发现跳过 FP-01~08、FX-01~10、DUP-A~J、O-01~O-24

---

## 审计结论（批次 93）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 93 | LLM-02 (`llm start` 无诊断信息) | **结论正确**。`cli/handlers.py:239-240` 在 `warmup_llm()` 返回 False 时仅返回 `{"status": "error"}` 不含 message 字段，而 `LlamaServerRuntime.start()` 内部记录详细失败原因但不暴露。 |
| 批次 93 | LLM-03 (`llm stop` 总是成功) | **结论正确**。`cli/handlers.py:242-243` 无条件返回 success，`cooldown_llm()` 内部 `except Exception: warning` 吞掉异常，handler 无法感知失败。 |
| 批次 93 | SYS-01 (`disconnect` 总是成功) | **结论正确**。`cli/handlers.py:116-117` 无条件返回 success，`runtime.disconnect()` 内部 `except Exception: error` 吞掉异常，handler 无法感知失败。 |

**批次 93 全部新发现经本批次逐项源码复核确认准确，无需修正。**

**补充观察**：LLM-03 和 SYS-01 共享的根因（生命周期方法内部 `except Exception` 后不返回状态，handler 无条件返回 success）在 `core/service/runtime.py:268-294` 的 `disconnect` 方法中同样存在——该方法捕获所有异常并仅记录 error 日志，不向调用方返回失败信息。但 SYS-01 修复建议中已包含修改 `runtime.disconnect()` 使其汇总错误后抛出，因此该补充已纳入 SYS-01 修复范围，不单独立项。

---

## 新增发现（4 项）

### NAV-DRAIN — `_drain_pipe` / `_accept_loop` / `_handle_client` 守护线程未 join，清理时泄漏文件描述符

**等级**: 代码质量 / 中
**位置**: `core/capability/device/android_runtime.py:233, 494, 534`

**问题代码**:

```python
# android_runtime.py:233 — scrcpy-server 输出管道守护线程
threading.Thread(target=self._drain_pipe, args=(self._server_proc.stdout,), daemon=True).start()

# android_runtime.py:494 — IPC 守护线程
threading.Thread(target=self._accept_loop, daemon=True).start()

# android_runtime.py:534 — 客户端处理守护线程
threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
```

**根因分析**:

`AndroidRuntimeProxy.stop()` 仅 join 主线程（`_run`），对 `_drain_pipe`、`_accept_loop`、`_handle_client` 三个 daemon 线程不做 join：

```python
# android_runtime.py:95-101
def stop(self, serial=None) -> None:
    self._stop_event.set()
    if self._thread is not None and self._thread.is_alive():
        self._thread.join(timeout=5)  # 仅 join 主 _run 线程
    self._thread = None
    self._close_codec()
    self._cleanup()
```

- `_drain_pipe` 在 `pipe.read(4096)` 上阻塞（line 421），server 进程被 kill 后 pipe 返回 EOF 才会退出，但中间可能有延迟；
- `_accept_loop` 在 `self._listener.accept()` 上阻塞（line 531），listener 被 close 后才抛出异常退出；
- `_handle_client` 在 `conn.poll(30)` 或 `conn.recv_bytes()` 上阻塞（line 540-543），对端断开后才退出。

daemon=True 保证进程退出时线程终止，但在进程生命周期内，反复 start/stop 会导致：
1. 旧线程持有已关闭 pipe/listener/socket 的文件描述符；
2. 新线程创建时可能与旧线程竞争（如旧 `_accept_loop` 在 listener close 后仍尝试 accept）；
3. 极端情况下 fd 耗尽导致新连接无法建立。

**调用链**:
```
用户点击"断开设备"
  → AndroidRuntimeProxy.stop()
    → self._thread.join(timeout=5)  # 仅等 _run 线程
    → self._cleanup()               # kill server proc, close codec
    → _drain_pipe/_accept_loop/_handle_client 仍存活，持有 fd
```

**影响面**:
- **中**：反复 start/stop scrcpy（如预览开启/关闭切换）时，守护线程持续累积。正常单次连接/断开影响不大，但自动化场景（每次任务前后启停 scrcpy）会导致 fd 泄漏。

**修复建议**:

```python
def stop(self, serial=None) -> None:
    self._stop_event.set()
    # 先关闭 listener 和 pipe，触发守护线程退出
    if self._listener is not None:
        try:
            self._listener.close()
        except Exception:
            pass
    if self._server_proc is not None and self._server_proc.stdout is not None:
        try:
            self._server_proc.stdout.close()
        except Exception:
            pass
    # join 所有守护线程
    threads_to_join = []
    # 需要追踪所有守护线程的引用（见下方配套修改）
    for t in threads_to_join:
        if t is not None and t.is_alive():
            t.join(timeout=3)
    if self._thread is not None and self._thread.is_alive():
        self._thread.join(timeout=5)
    ...
```

配套修改：为 `_drain_pipe`、`_accept_loop`、`_handle_client` 守护线程保存引用，在 stop 时 join。

---

### SCRCPY-SILENT — `connect()` 总是返回 True，即使 scrcpy 预览通道启动失败

**等级**: 用户体验 / 中
**位置**: `core/service/runtime.py:222-254`

**问题代码**:

```python
# runtime.py:222-254
def connect(self, serial=None) -> bool:
    ...
    # 连接成功后立即启动 scrcpy 常驻图像通道，供预览按需取用。
    try:
        self.android(serial).start_scrcpy(serial=serial)
        if isinstance(result, dict) and result.get("error"):
            self._logger.warning(...)  # 仅记录 warning
            try:
                self.android(serial).stop_scrcpy(serial=serial)
            except Exception:
                pass
        else:
            self._logger.info(...)
    except Exception as exc:
        self._logger.warning(...)  # 仅记录 warning
        try:
            self.android(serial).stop_scrcpy(serial=serial)
        except Exception:
            pass
    self._logger.info("MaaEnd runtime 已就绪")
    return True  # ← 无条件 True
```

**根因分析**:

`connect()` 在 scrcpy 预览通道启动失败时仅记录 warning，但最终 `return True`。这意味着：
1. GUI 侧 `_ensure_connected` 收到 True，认为连接完全成功；
2. 预览画面始终显示"No preview"（因为 scrcpy 未运行），但用户不知道为何；
3. `navigator.py` 的 `_get_frame` 调用 `self._screenshot_fn()` 返回 None，导航失败但用户只看到"no screenshot available"，不知道根本原因是 scrcpy 未启动。

**与同类代码的对比**:

| 方法 | 返回值 | scrcpy 失败处理 |
|------|--------|-----------------|
| `connect()` (line 254) | 无条件 True | 仅 warning，不反映在返回值 |
| `_ensure_maaend_ready()` (line 256-265) | True (因为 connect() 返回 True) | 不感知 |
| `maaend_control_page._ensure_connected()` (line 1742) | True | QMessageBox 只展示 MaaEnd 连接失败 |

**调用链**:
```
用户点击"连接"
  → _ensure_connected → _sync_execute("system connect")
    → runtime.connect()
      → runtime.connect() 返回 True（scrcpy 失败被吞掉）
    → _sync_execute 返回 {"status": "success"}
  → GUI 显示"Connected"，但预览无画面
```

**影响面**:
- **中**：scrcpy 预览是导航和 VLM 功能的前提。如果 scrcpy 未启动但 GUI 显示连接成功，用户启动导航时会收到"no screenshot available"错误，无法定位根因。需要额外查看日志才能发现 scrcpy 失败。

**修复建议**:

```python
def connect(self, serial=None) -> dict:  # 返回 dict 而非 bool
    ...
    scrcpy_ok = True
    try:
        result = self.android(serial).start_scrcpy(serial=serial)
        if isinstance(result, dict) and result.get("error"):
            scrcpy_ok = False
            ...
    except Exception as exc:
        scrcpy_ok = False
        ...
    return {
        "maaend_connected": True,
        "scrcpy_available": scrcpy_ok,
    }
```

或至少让 `connect()` 在 scrcpy 失败时返回 `False`，由调用方决定是否继续。最小修改：

```python
def connect(self, serial=None) -> bool:
    ...
    scrcpy_ok = True
    try:
        result = self.android(serial).start_scrcpy(serial=serial)
        if isinstance(result, dict) and result.get("error"):
            scrcpy_ok = False
            ...
    except Exception as exc:
        scrcpy_ok = False
        ...
    self._logger.info("MaaEnd runtime 已就绪")
    return scrcpy_ok  # 改为反映实际就绪状态
```

---

### AUTO-PARAMS — `_resolve_connect_params` 裸 except 吞掉配置读取错误，自动连接无诊断

**等级**: 用户体验 / 低
**位置**: `gui/pyqt6/pages/maaend_control_page.py:412-424`

**问题代码**:

```python
# maaend_control_page.py:412-424
def _resolve_connect_params(self) -> Dict[str, Any]:
    try:
        from core.foundation.paths import get_project_root
        config_path = Path(get_project_root()) / "config" / "client_config.json"
        if config_path.is_file():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            serial = (((data.get("device") or {}).get("last_connected"))
                      or ((data.get("device") or {}).get("serial")))
            if serial:
                return {"serial": serial}
    except Exception:
        pass  # ← 所有错误（权限、IO、JSON、导入）全部静默
    return {}
```

**根因分析**:

`_resolve_connect_params` 在读取 `client_config.json` 时捕获所有异常并静默返回空 dict。这意味着：
1. 配置文件损坏（JSON 解码失败）→ 自动连接静默放弃，用户不知道为何；
2. 配置文件权限不足 → 自动连接静默放弃，用户不知道为何；
3. `get_project_root()` 导入失败 → 自动连接静默放弃，用户不知道为何。

这些错误场景下，调用方（`_connect` 或 `_attempt_reconnect`）收到 `{}` 后不会发起连接，用户只看到"连接失败"或"无响应"，需要额外查看日志才能诊断。

**与同类代码的对比**:

| 读取配置方法 | 异常处理 |
|-------------|---------|
| `settings_page._read_config` (line 221-228) | JSON 解码失败时 QMessageBox 警告 |
| `device_settings_page._read_config` (line 301-307) | JSON 解码失败时返回 `{}`，但方法名暗示"读取配置" |
| **`maaend_control_page._resolve_connect_params`** | **所有异常全部吞掉** |

**调用链**:
```
页面切换显示 → QTimer.singleShot(50, self.refresh)
  → refresh → _ensure_connected → _resolve_connect_params
    → config 读取失败 → 静默返回 {}
    → _ensure_connected 收到 {} → 不发起连接 → 返回 False
  → 用户看到空白页面，不知道为何未自动连接
```

**影响面**:
- **低**：仅影响自动连接场景（页面切换时）。手动连接不受影响。但配置文件损坏时，用户会困惑于为何自动连接不工作。

**修复建议**:

```python
def _resolve_connect_params(self) -> Dict[str, Any]:
    try:
        from core.foundation.paths import get_project_root
        config_path = Path(get_project_root()) / "config" / "client_config.json"
        if not config_path.is_file():
            return {}
        data = json.loads(config_path.read_text(encoding="utf-8"))
        serial = (((data.get("device") or {}).get("last_connected"))
                  or ((data.get("device") or {}).get("serial")))
        if serial:
            return {"serial": serial}
        return {}
    except json.JSONDecodeError as exc:
        self._logger.warning("client_config.json 解析失败: %s", exc)
        return {}
    except PermissionError as exc:
        self._logger.warning("client_config.json 权限不足: %s", exc)
        return {}
    except Exception as exc:
        self._logger.warning("读取 client_config.json 失败: %s", exc)
        return {}
```

最小修改：将 `except Exception: pass` 改为至少记录 warning。

---

### PLAYER-SILENT — 脚本回放动作失败后静默继续，用户不知情

**等级**: 用户体验 / 低
**位置**: `gui/pyqt6/scripting/player.py:135-138`

**问题代码**:

```python
# scripting/player.py:135-138
def _execute_action(self) -> None:
    ...
    try:
        if action.action_type == "click":
            self._do_click(widget, action)
        elif action.action_type in ("text_changed", "combo_changed"):
            self._do_text(widget, action)
    except Exception as e:
        logger.warning("Failed to execute action %s: %s", action.action_type, e)
        # ← 仅记录 warning，无用户反馈，回放继续
    self._schedule_next(self._default_delay_ms)  # ← 继续执行下一个动作
```

**根因分析**:

当脚本回放中的某个动作（点击或文本设置）执行失败时，`_execute_action` 捕获异常并记录 warning 日志，但：
1. 不更新 UI 状态标签（用户看不到哪个动作失败了）；
2. 继续执行后续动作（可能导致连锁错误）；
3. `playback_stopped`/`playback_finished` 信号正常发出，用户以为回放正常完成。

**调用链**:
```
用户点击"播放"
  → Player.play() → _schedule_next → _execute_action
    → _do_click 失败（widget 已销毁、坐标越界）
    → logger.warning（用户看不到）
    → _schedule_next → 继续下一个动作
  → playback_finished 发出
  → 用户以为回放成功完成，但实际中间有动作失败
```

**影响面**:
- **低**：脚本回放是辅助功能，非核心自动化路径。但脚本回放失败静默会让用户误以为自动化序列正确执行，可能导致实际任务执行偏差。

**修复建议**:

```python
def _execute_action(self) -> None:
    ...
    action_failed = False
    try:
        if action.action_type == "click":
            self._do_click(widget, action)
        elif action.action_type in ("text_changed", "combo_changed"):
            self._do_text(widget, action)
    except Exception as e:
        logger.warning("Failed to execute action %s: %s", action.action_type, e)
        action_failed = True

    if action_failed:
        self._on_finished()  # 提前终止回放
        self.playback_stopped.emit()
        return

    self._schedule_next(self._default_delay_ms)
```

或在回放结束后更新状态标签，提示用户有动作失败。

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| 用户体验（中） | 2 | NAV-DRAIN (守护线程泄漏), SCRCPY-SILENT (connect 静默 scrcpy 失败) |
| 用户体验（低） | 2 | AUTO-PARAMS (配置读取静默吞错), PLAYER-SILENT (脚本回放动作失败静默) |
| 代码质量（中） | 1 | NAV-DRAIN (守护线程未 join) |
| 高风险 | 0 | — |
| 中风险 | 0 | — |

**本轮无中高风险发现。**

---

## 审计方法说明

本批次新增发现均来自以下文件的静态分析：
- `android_runtime.py`：守护线程生命周期管理
- `runtime.py`：`connect()` 返回值与实际就绪状态的不一致
- `maaend_control_page.py`：`_resolve_connect_params` 异常处理
- `scripting/player.py`：脚本回放错误处理

所有发现均已对照 `CODE_REVIEW_WARNS.md` 去重，不重复 FP-01~08、FX-01~10、DUP-A~J、O-01~O-24。

---

*批次 94 报告 | 仅分析，无文件修改*
