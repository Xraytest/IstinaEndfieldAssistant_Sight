# 审计批次 88 — DEVICE-04 commandError 不重置连接状态 + CLI-04 设备信息 handler 误导性成功 + 审计批次 87

**生成时间**: 2026-07-12 10:00
**覆盖文件**: `device_settings_page.py`, `handlers.py`, `android_runtime.py`
**审计方法**: 静态代码逻辑分析，无测试执行
**前置去重**: 已读取 `reports/CODE_REVIEW_WARNS.md`，新发现跳过 FP-01~08、FX-01~10、DUP-A~J、O-01~O-24

---

## 新增发现（2 项）

### DEVICE-04 — `commandError` 不重置 `_connected` 状态

**等级**: 代码质量 / 低
**位置**: `device_settings_page.py:217-223`

**问题代码**:

```python
# device_settings_page.py:217-223
def _on_command_error(self, command: str, message: str) -> None:
    self._append_log(locale.tr("command_failed", "Command failed: {command}").format(command=command) + f" {message}")
    if command.startswith("system connect") or command.startswith("system disconnect"):
        self._connect_btn.setEnabled(True)
        self._disconnect_btn.setEnabled(True)
        self._refresh_btn.setEnabled(True)
        self._connection_status.setText(locale.tr("connection_failed", "Connection Failed"))
```

**根因分析**:

`_on_command_error` 处理 bridge 发出的 `commandError` 信号（命令执行异常，非正常结果返回）。当 `system connect` 或 `system disconnect` 命令出错时（如 daemon 未运行、超时、进程崩溃），该方法恢复按钮状态并显示 "Connection Failed"，但**不重置 `self._connected`**。

对比 `_on_command_finished`（line 181-197）处理 connect 结果的逻辑：
```python
elif command.startswith("system connect"):
    ok = bool(result.get("status") == "success")
    self._connected = ok  # ← 正确：根据结果设置
```

**调用链对比**:

| 路径 | 处理 | `_connected` 更新 |
|------|------|-------------------|
| `commandFinished` (connect 成功) | `_on_command_finished` | `self._connected = True` ✓ |
| `commandFinished` (connect 失败) | `_on_command_finished` | `self._connected = False` ✓ |
| `commandError` (connect 异常) | `_on_command_error` | **不更新** ✗ |

**触发场景**:
1. 设备已连接（`_connected = True`）
2. Daemon 崩溃/重启 → bridge 对正在进行的 connect 命令发出 `commandError`
3. `_on_command_error` 显示 "Connection Failed" 但 `_connected` 仍为 `True`
4. `MainWindow._refresh_preview` 检查 `self._maaend_page._connected` → True → 尝试截图 → 失败

**影响面**:
- **低**：连接状态不一致仅在 daemon 异常时短暂存在。后续手动操作（如重新连接）会修正状态。但预览刷新、自动重连等依赖 `_connected` 的功能会在此期间行为异常。

**修复建议**:

```python
def _on_command_error(self, command: str, message: str) -> None:
    self._append_log(locale.tr("command_failed", "Command failed: {command}").format(command=command) + f" {message}")
    if command.startswith("system connect") or command.startswith("system disconnect"):
        self._connect_btn.setEnabled(True)
        self._disconnect_btn.setEnabled(True)
        self._refresh_btn.setEnabled(True)
        self._connection_status.setText(locale.tr("connection_failed", "Connection Failed"))
        if command.startswith("system connect"):
            self._connected = False  # connect 异常视为连接失败
        elif command.startswith("system disconnect"):
            self._connected = False  # disconnect 异常也应确保状态正确
```

---

### CLI-04 — 设备信息/monitor handler 返回误导性 "success" 空结果

**等级**: 用户体验 / 低
**位置**: `handlers.py:400-406`, `handlers.py:486-496`

**问题代码**:

```python
# handlers.py:400-406
def _handle_device_info(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    android = runtime.android()
    devices = android.get_devices()
    return {
        "status": "success",
        "devices": [{"serial": d.serial, "state": d.state} for d in devices],
    }

# handlers.py:486-496
def _handle_device_monitor(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    try:
        android = runtime.android()
        devices = android.get_devices()
        return {
            "status": "success",
            "device_count": len(devices),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
```

**根因分析**:

两个 handler 均未检查 `android.default_client is None`。当 daemon 未运行或设备未连接时：
- `android.get_devices()` 通过 daemon `_call("getDevices")` 获取设备列表
- Daemon 未运行时 `_get_daemon()` 会创建并启动新 daemon，`_call` 返回 `{"result": []}`（空设备列表）
- Handler 返回 `{"status": "success", "devices": []}` 或 `{"status": "success", "device_count": 0}`

用户看到"成功"结果但设备列表为空，无法区分是"daemon 未运行"还是"确实无设备连接"。

**与 O-10 的关系**: O-10 覆盖 `_handle_device_screenshot/tap` 缺少 `default_client is None` 检查（崩溃风险）。CLI-04 覆盖 `_handle_device_info/monitor` 缺少相同检查（UX 误导），属于同一根因的不同表现层。

**影响面**:
- **低**：不崩溃，但用户难以诊断连接问题。`_handle_device_monitor` 有 try/except 防护，`_handle_device_info` 无防护但 daemon 错误返回空列表而非异常。

**修复建议**:

```python
def _handle_device_info(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    android = runtime.android()
    if android.default_client is None:
        return {"status": "error", "message": "no device connected"}
    devices = android.get_devices()
    return {
        "status": "success",
        "devices": [{"serial": d.serial, "state": d.state} for d in devices],
    }

def _handle_device_monitor(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    android = runtime.android()
    if android.default_client is None:
        return {"status": "error", "message": "no device connected"}
    devices = android.get_devices()
    return {
        "status": "success",
        "device_count": len(devices),
        "timestamp": datetime.now().isoformat(),
    }
```

---

## 审计结论（批次 87）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 87 | DEVICE-01 (disconnect 成功后 reconnect timer 仍启动) | **结论正确**。`device_settings_page.py:205-206` 在 `system disconnect` 成功后无条件 `self._reconnect_timer.start()`。用户主动断开后 5 秒内自动重连被触发，与用户意图矛盾。 |
| 批次 87 | DEVICE-03 (`_on_auto_reconnect_toggled` 断连时启用自动重连不启动 timer) | **结论正确**。`device_settings_page.py:137-142` 条件 `if checked and self._connected` 在 `_connected=False` 时执行 `else` 分支停止 timer。断连状态下启用自动重连后 `_attempt_reconnect` 永远不会被调用。 |

**批次 87 全部 2 项新发现经本批次逐项源码复核确认准确，无需修正。**

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| 用户体验（低） | 1 | CLI-04 (设备信息/monitor handler 误导性成功) |
| 代码质量（低） | 1 | DEVICE-04 (commandError 不重置连接状态) |
| 高风险 | 0 | — |
| 中风险 | 0 | — |

**本轮无中高风险发现。**

---

*批次 88 报告 | 仅分析，无文件修改*
