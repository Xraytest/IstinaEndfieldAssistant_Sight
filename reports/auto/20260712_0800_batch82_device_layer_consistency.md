# 审计批次 82 — 设备层异常处理一致性 / 健康检查静默 / 设置页读取防护缺失 + 审计批次 81

**生成时间**: 2026-07-12 08:00
**覆盖文件**: `touch_manager.py`, `recovery.py`, `client.py`, `settings_page.py`, `runtime.py`
**审计方法**: 静态代码逻辑分析，无测试执行
**前置去重**: 已读取 `reports/CODE_REVIEW_WARNS.md`，新发现跳过 FP-01~08、FX-01~10、DUP-A~J、O-01~O-24

---

## 新增发现（5 项）

### TOUCH-01 — `back()` 方法无异常处理，与同类方法不一致

**等级**: 代码质量 / 低
**位置**: `touch_manager.py:54-57`

**问题代码**:

```python
# touch_manager.py:54-57
def back(self, serial: Optional[str] = None) -> None:
    import subprocess
    args = self._adb_base_args(serial) + ["shell", "input", "keyevent", "KEYCODE_BACK"]
    subprocess.check_output(args, timeout=10)
```

**根因分析**:

`TouchManager` 的 4 个公共方法中，3 个（`tap`、`swipe`、`long_press`）均采用 `try/except Exception as e` → 日志记录 + re-raise 模式：

| 方法 | 异常处理 |
|------|---------|
| `tap()` (line 25-31) | ✓ try/except + error log + raise |
| `swipe()` (line 33-39) | ✓ try/except + error log + raise |
| `long_press()` (line 47-52) | ✓ try/except + error log + raise |
| `back()` (line 54-57) | ✗ 无任何异常处理 |

`subprocess.check_output` 在 ADB 设备离线、超时、或命令执行失败时抛出 `subprocess.CalledProcessError` 或 `TimeoutError`。这些异常从 `back()` 直接向上传播，调用方（如 `AndroidRuntime.keyevent()` 或 `runtime._vlm_keyevent()`）可能未预期此异常类型，导致调用栈意外中断。

**与 FX-08 的区别**: FX-08 覆盖 `handlers.py` 中 tap/swipe 坐标验证的**部分修复**。TOUCH-01 关注 `TouchManager` 内部方法间的**异常处理一致性缺失**，与坐标验证无关。

**影响面**:
- **低**：`back()` 调用频率低于 tap/swipe，且调用方通常有外层异常捕获。但同类方法的不一致性增加了维护风险——修改异常处理策略时容易遗漏 `back()`。

**修复建议**:

```python
def back(self, serial: Optional[str] = None) -> None:
    try:
        self._adb_back(serial)
    except Exception as e:
        self._logger.error(LogCategory.EXECUTION, "返回键失败", error=str(e))
        raise
```

---

### REC-01 — `_clear_canvas` 三个 ADB 命令连续静默失败，恢复策略完整性不可见

**等级**: 代码质量 / 低
**位置**: `recovery.py:81-94`

**问题代码**:

```python
# recovery.py:81-94
def _clear_canvas(self, serial: Optional[str]) -> None:
    try:
        self._run(["shell", "wm", "dismiss-keyguard"], serial)
    except Exception:
        pass          # ← 1: 忽略 keyguard 解除失败
    try:
        self._run(["shell", "input", "keyevent", "KEYCODE_WAKEUP"], serial)
    except Exception:
        pass          # ← 2: 忽略唤醒失败
    try:
        self._run(["shell", "input", "keyevent", "KEYCODE_HOME"], serial)
    except Exception:
        pass          # ← 3: 忽略 HOME 键失败
```

**根因分析**:

`_clear_canvas` 是 `restart()` 的中间步骤，执行 3 个顺序 ADB 命令清理设备状态。每个命令的失败都被 `except Exception: pass` 完全忽略。可能的失败场景：

- `wm dismiss-keyguard` 失败：设备处于加密锁定状态，ADB 无法操作
- `KEYCODE_WAKEUP` 失败：设备已唤醒或屏幕已亮
- `KEYCODE_HOME` 失败：设备无 launcher 或处于特殊模式

虽然每个命令的失败在语义上可能是"可容忍"的（如屏幕已亮时 `KEYCODE_WAKEUP` 失败），但**完全不可见**。`restart()` 的外层 try 只捕获整个流程的异常，无法区分是 `_force_stop` 失败、`_clear_canvas` 某一步失败、还是 `_launch` 失败。

**对比 O-24**: O-24 覆盖 `adb_manager.py` 的 adbutils 回退不记录原始异常。REC-01 是**不同问题**：`_clear_canvas` 使用的是 `_run()` → `subprocess.check_output`（非 adbutils），且每个命令独立静默失败，而非回退路径。

**影响面**:
- **低**：`_clear_canvas` 是可选的清理步骤，失败不影响核心重启流程。但设备处于异常状态（如加密锁定）时，`_clear_canvas` 的静默失败掩盖了设备状态的异常，导致后续 `_launch` 也失败，最终 `restart()` 返回 `False` 但日志只显示"重启失败"而非"设备加密锁定导致无法清理"。

**修复建议**:

```python
def _clear_canvas(self, serial: Optional[str]) -> None:
    steps = [
        ("dismiss-keyguard", ["shell", "wm", "dismiss-keyguard"]),
        ("KEYCODE_WAKEUP", ["shell", "input", "keyevent", "KEYCODE_WAKEUP"]),
        ("KEYCODE_HOME", ["shell", "input", "keyevent", "KEYCODE_HOME"]),
    ]
    for name, args in steps:
        try:
            self._run(args, serial)
        except Exception as exc:
            self._logger.debug("清理步骤失败: %s (serial=%s)", name, serial, error=str(exc))
```

---

### CLI-01 — `health_check()` 吞掉所有异常返回 False，错误原因完全不可见

**等级**: 代码质量 / 低
**位置**: `client.py:70-80`

**问题代码**:

```python
# client.py:70-80
def health_check(self) -> bool:
    import urllib.request
    url = f"{self._base_url.split('/v1', 1)[0]}/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False
```

**根因分析**:

`health_check()` 在 LLM 启动轮询（`llm/runtime.py:370`）中被调用以检测 llama-server 是否就绪。当返回 `False` 时，调用方只知道"未就绪"但不知道原因：

- 网络不可达（DNS 失败、ConnectionRefused）→ `False`
-  llama-server 启动中但尚未监听 → `False`
- URL 构造错误（`_base_url` 格式异常）→ `False`
- 超时 → `False`

这 4 种原因全部混为同一个 `False` 返回值。`_try_start` 的轮询循环（`for _ in range(60): time.sleep(1)`）在 60 秒内每 1 秒调用一次 `health_check()`，每次失败都 indistinguishable。

**对比 LLM-02**: LLM-02 覆盖 `_try_start` 中 `communicate()` 异常丢弃导致误导性日志。CLI-01 是**不同问题**：关注 `health_check()` 的异常吞掉导致启动轮询阶段的原因不可见。

**影响面**:
- **低**：health_check 失败后 `_try_start` 继续轮询，最终超时返回 False 时 LLM runtime 会记录错误。但中间 60 次轮询的失败原因完全不可见，调试启动问题时只能靠猜测。

**修复建议**:

```python
def health_check(self) -> bool:
    import urllib.request
    url = f"{self._base_url.split('/v1', 1)[0]}/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as exc:
        self._logger.debug("[%s] health_check 失败: url=%s error=%s", LogCategory.MAIN, url, str(exc))
        return False
```

---

### SET-01 — `_read_config` 仅捕获 `JSONDecodeError`，配置文件不可读时崩溃

**等级**: 代码质量 / 低
**位置**: `settings_page.py:221-228`

**问题代码**:

```python
# settings_page.py:221-228
def _read_config(self) -> Dict[str, Any]:
    if not self._config_path.exists():
        return {}
    try:
        return json.loads(self._config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        QMessageBox.warning(self, ...)
        return {}
```

**根因分析**:

`_read_config` 只捕获 `json.JSONDecodeError`（JSON 解析失败），但不捕获其他文件读取异常：

- `PermissionError`: 配置文件被其他进程锁定或无读取权限
- `OSError`: 磁盘错误、文件系统异常
- `IsADirectoryError`: 路径指向目录而非文件

如果任何上述异常发生，它们从 `_read_config` 向上传播到 `_load_settings` → `_setup_ui` → `__init__`，最终导致 `SettingsPage` 构造失败，整个设置页面无法显示。

**对比 `runtime.py:470-486`**: `IstinaRuntime._load_config` 采用分层异常处理，分别捕获 `json.JSONDecodeError`、`PermissionError`、`OSError`，每种异常给出不同的错误日志。`settings_page._read_config` 应该采用相同的策略。

**影响面**:
- **低**：配置文件由用户手动编辑或被其他程序锁定的场景较少。但一旦发生，后果严重——整个设置页面崩溃，用户无法修改任何配置。

**修复建议**:

```python
def _read_config(self) -> Dict[str, Any]:
    if not self._config_path.exists():
        return {}
    try:
        return json.loads(self._config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        QMessageBox.warning(self, ...)
        return {}
    except PermissionError as exc:
        self._logger.error("配置文件无读取权限", path=str(self._config_path), error=str(exc))
        return {}
    except OSError as exc:
        self._logger.error("配置读取失败", path=str(self._config_path), error=str(exc))
        return {}
```

---

### RUNTIME-01 — `connect()` 中 `stop_scrcpy` 清理异常静默吞掉，失败原因不可见

**等级**: 代码质量 / 低
**位置**: `runtime.py:241-252`

**问题代码**:

```python
# runtime.py:235-252
try:
    result = self.android(serial).start_scrcpy(serial=serial)
    if isinstance(result, dict) and result.get("error"):
        self._logger.warning("scrcpy 预览通道启动失败", error=result["error"], ...)
        try:
            self.android(serial).stop_scrcpy(serial=serial)
        except Exception:
            pass                    # ← 清理失败被吞掉
    else:
        ...
except Exception as exc:
    self._logger.warning("scrcpy 预览通道启动失败", error=str(exc), ...)
    try:
        self.android(serial).stop_scrcpy(serial=serial)
    except Exception:
        pass                    # ← 清理失败被吞掉
```

**根因分析**:

当 `start_scrcpy` 失败时，代码尝试调用 `stop_scrcpy` 清理残留会话。但 `stop_scrcpy` 的失败被 `except Exception: pass` 完全忽略。这意味着：

- 如果 scrcpy 会话部分启动（如 server 进程已创建但 socket 未建立），`start_scrcpy` 返回错误 dict，`stop_scrcpy` 尝试清理但可能因同样的原因失败
- 如果 `stop_scrcpy` 在 except 块中失败（如 `android(serial)` 返回 None），异常被吞掉，没有任何日志

**与 O-21 的关系**: O-21 是托盘退出被拦截（GUI 层问题）。RUNTIME-01 是设备连接时 scrcpy 清理失败（服务层问题），不重叠。

**影响面**:
- **低**：scrcpy 预览通道是可选的（不影响核心自动化功能）。但残留的 scrcpy 会话可能占用端口或资源，导致下次连接时 `start_scrcpy` 再次失败。

**修复建议**:

```python
try:
    self.android(serial).stop_scrcpy(serial=serial)
except Exception as stop_exc:
    self._logger.debug("scrcpy 清理失败 (serial=%s): %s", serial, stop_exc)
```

---

## 审计结论（批次 81）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 81 | LLM-02 (`_try_start` communicate() 异常丢弃误导日志) | **结论正确**。当前代码仍为 `except Exception: pass`（未修复），对应 CODE_REVIEW_WARNS.md 未收录项。批 81 准确描述了 `communicate()` 异常导致误导性日志的根因。 |
| 批次 81 | MAA-08 (`_start_agent` kill() 异常静默吞噬) | **结论正确**。当前代码仍为嵌套 `except Exception: pass`（未修复），对应 CODE_REVIEW_WARNS.md 未收录项。批 81 准确区分了 MAA-08 与 O-06/O-07（线程 join 超时）的不同问题范围。 |

**批次 81 全部 2 项结论经本批次逐项源码复核确认准确，无需修正。**

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| 代码质量（低） | 5 | TOUCH-01 (back() 无异常处理), REC-01 (clear_canvas 3x 静默), CLI-01 (health_check 吞异常), SET-01 (read_config 缺异常类型), RUNTIME-01 (stop_scrcpy 清理静默) |
| BUG（中/高） | 0 | — |
| 漏洞 | 0 | — |

**本轮无中高风险发现。**

本轮审计聚焦设备层（`touch_manager.py`、`recovery.py`）、LLM 客户端（`client.py`）、GUI 设置页（`settings_page.py`）和统一运行时（`runtime.py`）。发现 5 项低严重度的异常处理一致性问题：`TouchManager.back()` 与同类方法异常处理不一致；`AndroidAppRestartPolicy._clear_canvas` 三个 ADB 命令连续静默失败；`LlmClient.health_check` 吞掉所有异常导致启动轮询原因不可见；`SettingsPage._read_config` 仅捕获 `JSONDecodeError` 而遗漏 `PermissionError`/`OSError`；`IstinaRuntime.connect` 的 scrcpy 清理异常静默吞掉。批次 81 的 2 项结论均经源码逐行复核确认准确。

---

*批次 82 报告 | 仅分析，无文件修改*