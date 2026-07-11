# 审计批次 87 — DEVICE-01 手动断开后自动重连仍触发 / DEVICE-03 断连时启用自动重连不启动 timer + 审计批次 86

**生成时间**: 2026-07-12 09:45
**覆盖文件**: `device_settings_page.py`, `main_window.py`, `handlers.py`, `android_runtime.py`
**审计方法**: 静态代码逻辑分析，无测试执行
**前置去重**: 已读取 `reports/CODE_REVIEW_WARNS.md`，新发现跳过 FP-01~08、FX-01~10、DUP-A~J、O-01~O-24

---

## 新增发现（2 项）

### DEVICE-01 — 手动断开连接后自动重连 timer 仍启动

**等级**: 用户体验 / 低
**位置**: `device_settings_page.py:198-206`

**问题代码**:

```python
# device_settings_page.py:198-206
elif command.startswith("system disconnect"):
    self._connected = False
    self._connection_status.setText(locale.tr("connection_disconnected", "Disconnected"))
    self._append_log(locale.tr("disconnect_result", "Disconnect result: {result}").format(result=result))
    self._connect_btn.setEnabled(True)
    self._disconnect_btn.setEnabled(True)
    self._refresh_btn.setEnabled(True)
    if self._reconnect_enabled:
        self._reconnect_timer.start()
```

**根因分析**:

用户点击"断开"按钮（`_disconnect`）发送 `system disconnect` 命令。命令成功后 `_on_command_finished` 处理 disconnect 结果，将 `_connected` 设为 False，然后无条件启动 `_reconnect_timer`（若 `_reconnect_enabled` 为 True）。

这意味着：
1. 用户主动断开设备连接
2. 5 秒后 `_attempt_reconnect` 自动触发，发送 `system connect` 命令
3. 设备被自动重新连接，与用户意图矛盾

**与 O-08 的关系**: O-08 覆盖 `device_settings_page.py:197`（connect 失败后 timer 停止）。DEVICE-01 是同一文件中的相反行为——disconnect 成功后 timer 启动。两者不重叠。

**调用链**:

```
用户点击"断开"按钮
  └── _disconnect() → bridge.execute("system disconnect")
        └── _on_command_finished("system disconnect", ...)
              ├── self._connected = False
              └── if self._reconnect_enabled:
                    self._reconnect_timer.start()  ← 不应启动
                          └── _attempt_reconnect() → bridge.execute("system connect")
                                └── 设备被自动重连
```

**影响面**:
- **低**：功能正确性不受影响，但用户体验受损——用户主动断开后设备被自动重连，需再次手动断开。

**修复建议**:

```python
elif command.startswith("system disconnect"):
    self._connected = False
    ...
    # 手动断开后不启动自动重连，尊重用户意图
    self._reconnect_timer.stop()
```

---

### DEVICE-03 — 断连状态下启用自动重连 checkbox 不启动 timer

**等级**: 用户体验 / 低
**位置**: `device_settings_page.py:137-142`

**问题代码**:

```python
# device_settings_page.py:137-142
def _on_auto_reconnect_toggled(self, checked: bool) -> None:
    self._reconnect_enabled = checked
    if checked and self._connected:
        self._reconnect_timer.start()
    else:
        self._reconnect_timer.stop()
```

**根因分析**:

当用户勾选"自动重连" checkbox 时，`_on_auto_reconnect_toggled(True)` 被调用。如果设备当前未连接（`self._connected = False`），条件 `checked and self._connected` 为 False，执行 `else` 分支——timer 被停止。

这意味着：
- 设备已连接 + 启用自动重连 → timer 启动（正确）
- 设备未连接 + 启用自动重连 → timer 停止（**错误**，应启动以开始重连尝试）
- 设备未连接 + 禁用自动重连 → timer 停止（正确）

`_attempt_reconnect`（line 144-145）检查 `self._connected or not self._reconnect_enabled` 并提前返回。如果 timer 在断连状态下不启动，`_attempt_reconnect` 永远不会被调用，自动重连功能在断连场景下完全失效。

**触发场景**:
1. 应用启动 → 设备未连接 → 用户勾选"自动重连" → timer 不启动 → 永远不会自动重连
2. 用户手动断开 → 用户重新勾选"自动重连" → timer 不启动 → 同上

**与 O-08 的关系**: O-08 覆盖 connect 失败后 timer 停止（单次连接失败路径）。DEVICE-03 覆盖 toggle checkbox 路径（断连状态下启用自动重连）。两者不同。

**影响面**:
- **低**：自动重连在设备已连接场景下正常工作（断开后 timer 会启动）。但在设备从未连接或手动断开后启用自动重连的场景下，功能完全失效。

**修复建议**:

```python
def _on_auto_reconnect_toggled(self, checked: bool) -> None:
    self._reconnect_enabled = checked
    if checked:
        if not self._connected:
            self._reconnect_timer.start()  # 断连时启用自动重连应启动 timer
    else:
        self._reconnect_timer.stop()
```

---

## 审计结论（批次 86）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 86 | DAEMON-01 (daemon 层 cv2.imencode 返回值丢弃) | **结论正确**。`android_runtime.py:583-584` 使用 `_, buf = cv2.imencode(".png", frame)` 丢弃返回值。与 O-22/VLM-03 同一根因但位于不同文件（daemon 层）和执行路径（screenshot RPC）。`maa_end/runtime.py:946-947` 已正确使用 `success, buf = cv2.imencode(...)` 并检查返回值。 |
| 批次 86 | MW-01 (`_refresh_preview` 跨类访问私有属性) | **结论正确**。`main_window.py:394-452` 直接读取 `self._maaend_page._connected` 和 `self._maaend_page._is_executing`。`MaaEndControlPage` 已通过 `execution_state_changed` 信号对外暴露状态变更，`MainWindow` 已连接此信号（line 284），但 `_refresh_preview` 未使用信号缓存的状态。 |

**批次 86 全部 2 项新发现经本批次逐项源码复核确认准确，无需修正。**

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| 用户体验（低） | 2 | DEVICE-01 (手动断开后自动重连仍触发), DEVICE-03 (断连时启用自动重连不启动 timer) |
| 代码质量（低） | 0 | — |
| 高风险 | 0 | — |
| 中风险 | 0 | — |

**本轮无中高风险发现。**

---

*批次 87 报告 | 仅分析，无文件修改*
