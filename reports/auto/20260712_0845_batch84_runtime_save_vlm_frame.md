# 审计批次 84 — runtime.save_config 非原子写入 / VLM _frame_to_base64 仍未修复 + 审计批次 83

**生成时间**: 2026-07-12 08:45
**覆盖文件**: `runtime.py`, `vlm_walk_navigator.py`, `cli_bridge.py`, `template_backend.py`
**审计方法**: 静态代码逻辑分析，无测试执行
**前置去重**: 已读取 `reports/CODE_REVIEW_WARNS.md`，新发现跳过 FP-01~08、FX-01~10、DUP-A~J、O-01~O-24

---

## 新增发现（3 项）

### RUNTIME-03 — `save_config` 仍用非原子写入，崩溃导致配置损坏

**等级**: 代码质量 / 中
**位置**: `runtime.py:506-510`

**问题代码**:

```python
# runtime.py:506-510
def save_config(self) -> None:
    path = self._resolve_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(self._config, f, ensure_ascii=False, indent=2)
```

**根因分析**:

`save_config` 直接打开目标文件并写入 JSON，非原子操作。若写入过程中进程崩溃、断电或磁盘满，配置文件处于半写入状态（JSON 截断），后续 `_load_config` 的 `json.loads` 将抛出 `JSONDecodeError`，返回 `{}`，用户配置全部丢失。

**与项目内原子写入模式的对比**:

| 文件 | 方法 | 原子性 |
|------|------|--------|
| `settings_page.py:196-211` | `tempfile.mkstemp` + `os.replace` | ✓ 原子 |
| `queue_state.py:122-124` | `.with_suffix(".tmp")` + `os.replace` | ✓ 原子 |
| `runtime.py:506-510` | `open().write()` | ✗ 非原子 |

**触发场景**:
- 用户在设置页修改 LLM 参数（端口/线程/路径），`_save_settings` 调用 `runtime.save_config()`（通过 `reload_config` 或直接调用）
- 保存过程中进程崩溃/断电 → 配置文件截断
- 下次启动时 `_load_config` 返回 `{}`，LLM 配置恢复默认值

**与 O-11 的关系**: O-11 覆盖 `--out`/`--config` 路径越界（路径遍历漏洞）。RUNTIME-03 关注的是**写入原子性**（崩溃时数据完整性），与 O-11 不重叠。

**影响面**:
- **中**：`save_config` 在配置变更时被调用，是用户配置持久化的唯一路径。非原子写入导致崩溃时配置损坏，用户需要手动恢复或重新配置。

**修复建议**:

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

### VLM-03 — `_frame_to_base64` 未检查 `cv2.imencode` 返回值，O-22 仍未修复

**等级**: BUG / 中
**位置**: `vlm_walk_navigator.py:331-333`

**问题代码**:

```python
# vlm_walk_navigator.py:331-333
def _frame_to_base64(self, frame: np.ndarray) -> str:
    _, buf = cv2.imencode(".png", frame)
    return base64.b64encode(buf).decode("ascii")
```

**根因分析**:

`cv2.imencode` 返回 `(retval, buf)` 元组。当编码失败时（frame 内存损坏、shape 异常、极端内存不足），`retval` 为 `False`，`buf` 为 `None`。

代码使用 `_, buf` 丢弃返回值。`buf` 为 `None` 时 `base64.b64encode(None)` 抛 `TypeError: a bytes-like object is required, not 'NoneType'`，导致 VLM 行走导航循环崩溃。

**与 O-22 的关系**: O-22 在 CODE_REVIEW_WARNS.md 中记录为有效 Open 项，描述相同问题。当前代码**仍未修复**。batch 80 报告建议了修复方案但代码未采纳。

**调用链**:

```
walk_to() step loop
  ├── _grab_frame() → cv2.imdecode 成功 → np.ndarray
  ├── _locator.locate(frame)
  ├── _frame_to_base64(frame)
  │     ├── cv2.imencode(".png", frame) → (False, None)
  │     └── base64.b64encode(None) → TypeError 崩溃
  └── 整个 walk_to 循环中断
```

**影响面**:
- **中**：正常 scrcpy 帧流几乎不触发，但一旦触发则 VLM 行走导航完全中断。`walk_to` 的通用 `except Exception` 块会捕获此错误并记录 `"vlm_error"`，但日志仅包含 `str(exc)`，无法区分是"帧编码失败"还是"LLM 调用失败"。

**修复建议**:

```python
def _frame_to_base64(self, frame: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", frame)
    if not ok or buf is None:
        raise ValueError("frame encoding failed")
    return base64.b64encode(buf).decode("ascii")
```

---

### CLI-02 — 交互模式 `_crash_count` 正常退出时不重置，跨会话累积

**等级**: 代码质量 / 低
**位置**: `cli_bridge.py:207-257`

**问题代码**:

```python
# cli_bridge.py:207-257
def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
    ...
    if self._interactive:
        if crashed:
            # 崩溃 → 安排重启
            if self._crash_count < self._max_crashes:
                self._restart_pending = True
                QTimer.singleShot(1000, self._restart_last_command)
            else:
                self._show_crash_dialog()
        # 正常退出（非 crashed）→ 仅清理，不重置 _crash_count
        self._finalize_current_process()
        return
    # 非交互模式：正常退出时重置
    if exit_code == 0:
        self._crash_count = 0
```

**根因分析**:

`_crash_count` 仅在非交互模式（line 255）和 `_start_interactive_process` 初始化（line 69）时被重置。交互模式（CLI `--interactive` 长驻进程）的正常退出路径（line 229-231）**不重置** `_crash_count`。

这意味着：
- 交互进程之前崩溃 3 次（`_crash_count=3`），然后正常重启
- 用户重启 GUI → 新交互进程启动 → `_crash_count` 从旧值 3 开始（而非 0）
- 再崩溃 2 次后达到 `_max_crashes=5` → 弹出崩溃对话框（实际只连续崩溃 2 次）

**影响面**:
- **低**：交互模式重启机制正常工作，崩溃计数仍然在连续崩溃场景下有效。但跨会话的 crash count 泄漏导致 `_max_crashes` 的容忍度在正常重启后被"预扣减"。

**修复建议**:

在交互模式正常退出路径中重置 `_crash_count`：

```python
if self._interactive:
    if crashed:
        ...
    else:
        self._crash_count = 0  # 正常退出重置计数
    self._finalize_current_process()
    return
```

---

## 审计结论（批次 83）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 83 | MAAEND-01 (手动停止后自动重试仍触发) | **结论正确**。当前代码仍为 `_stop_execution` 不取消定时器 + `_on_execution_finished` 安排重试的模式（未修复）。 |
| 批次 83 | RUNTIME-02 (`_ensure_maaend_ready` 不验证连接活性) | **结论正确**。当前代码仍为 `if runtime.connected: return True`（未修复）。 |

**批次 83 全部 2 项结论经本批次逐项源码复核确认准确，无需修正。**

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| 代码质量（中） | 2 | RUNTIME-03 (save_config 非原子写入), VLM-03 (_frame_to_base64 O-22 仍未修复) |
| 代码质量（低） | 1 | CLI-02 (交互模式 _crash_count 不重置) |
| 高风险 | 0 | — |
| 低风险 | 0 | — |

---

*批次 84 报告 | 仅分析，无文件修改*