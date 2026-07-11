# 审计批次 86 — DAEMON-01 daemon 层 cv2.imencode 返回值丢弃 / MW-01 私有属性跨类访问 + 审计批次 85

**生成时间**: 2026-07-12 09:30
**覆盖文件**: `android_runtime.py`, `main_window.py`, `handlers.py`, `maa_end/runtime.py`, `vlm_walk_navigator.py`
**审计方法**: 静态代码逻辑分析，无测试执行
**前置去重**: 已读取 `reports/CODE_REVIEW_WARNS.md`，新发现跳过 FP-01~08、FX-01~10、DUP-A~J、O-01~O-24

---

## 新增发现（2 项）

### DAEMON-01 — 守护进程 screenshot  handler 丢弃 `cv2.imencode` 返回值

**等级**: 代码质量 / 低
**位置**: `android_runtime.py:583-584`

**问题代码**:

```python
# android_runtime.py:583-584
if frame is not None:
    self._logger.debug("daemon screenshot 使用 scrcpy 帧", serial=serial, frame_shape=frame.shape if hasattr(frame, 'shape') else None)
    _, buf = cv2.imencode(".png", frame)
    return self._encode_binary(buf.tobytes())
```

**根因分析**:

`cv2.imencode` 返回 `(retval, buf)` 元组。当编码失败时（frame 内存损坏、shape 异常、极端内存不足），`retval` 为 `False`，`buf` 为 `None`。

代码使用 `_, buf` 丢弃返回值。`buf` 为 `None` 时 `buf.tobytes()` 抛 `AttributeError: 'NoneType' object has no attribute 'tobytes'`，导致 daemon 的 screenshot RPC 方法崩溃。

**与 O-22/VLM-03 的关系**: O-22 覆盖 `vlm_walk_navigator.py:331-333` 的 `_frame_to_base64`，描述相同问题但位于不同文件（VLM 层）。DAEMON-01 位于 `android_runtime.py` 的 daemon 层 screenshot handler，是同一根因在不同执行路径上的新实例。不属于 DUP-A~J 覆盖的任何主题（DUP-A 仅覆盖非原子写入模式）。

**调用链**:

```
AndroidRuntime.screenshot()
  ├── _call("screenshot", {"serial": ...})
  │     └── _Daemon._dispatch("screenshot")
  │           ├── _ScrcpySession.get_latest_frame() → np.ndarray
  │           ├── cv2.imencode(".png", frame) → (False, None)
  │           └── buf.tobytes() → AttributeError 崩溃
  └── {"error": "AttributeError: ..."} 返回客户端
```

**项目内对比**:

| 文件 | 方法 | 处理方式 |
|------|------|----------|
| `vlm_walk_navigator.py:331-333` | `_frame_to_base64` | ✗ 丢弃返回值（O-22/VLM-03） |
| `android_runtime.py:583-584` | `_Daemon._dispatch` screenshot | ✗ 丢弃返回值（DAEMON-01，本次新增） |
| `maa_end/runtime.py:946-947` | `screenshot` | ✓ `success, buf = cv2.imencode(...)` + `if success` 检查 |

**影响面**:
- **低**：正常 scrcpy 帧流几乎不触发编码失败，但一旦触发则 daemon screenshot RPC 完全中断。客户端收到 `{"error": "AttributeError: ..."}` 而非明确错误信息。

**修复建议**:

```python
if frame is not None:
    self._logger.debug("daemon screenshot 使用 scrcpy 帧", serial=serial, frame_shape=frame.shape if hasattr(frame, 'shape') else None)
    ok, buf = cv2.imencode(".png", frame)
    if not ok or buf is None:
        return {"error": "frame encoding failed"}
    return self._encode_binary(buf.tobytes())
```

---

### MW-01 — `_refresh_preview` 跨类访问 `MaaEndControlPage` 私有属性

**等级**: 代码质量 / 低
**位置**: `main_window.py:394-452`

**问题代码**:

```python
# main_window.py:394-399
def _refresh_preview(self) -> None:
    self._logger.debug(LogCategory.GUI, "预览定时器触发", connected=self._maaend_page._connected, executing=self._maaend_page._is_executing)
    if self._preview_widget is None:
        return
    if not self._maaend_page._connected:
        return
    if self._maaend_page._is_executing:
        return
    result = self._maaend_page._sync_execute("screenshot", timeout_ms=5000)
```

**根因分析**:

`MainWindow._refresh_preview` 直接访问 `MaaEndControlPage` 的私有属性 `_connected` 和 `_is_executing`。这些属性在 `MaaEndControlPage` 内部维护，通过 `execution_state_changed` 信号对外暴露状态变更。

直接读取私有属性违反了封装原则：若 `MaaEndControlPage` 重命名或重构这些属性（如改为 `_conn_state` 或通过 property 暴露），`MainWindow` 的预览逻辑将 silently break（AttributeError）。

**调用链**:

```
QTimer (preview_timer) timeout
  └── MainWindow._refresh_preview()
        ├── self._maaend_page._connected      ← 直接读取私有属性
        ├── self._maaend_page._is_executing   ← 直接读取私有属性
        └── self._maaend_page._sync_execute("screenshot")
```

**影响面**:
- **低**：当前代码稳定运行，私有属性名尚未变更。但重构风险存在——任何对 `MaaEndControlPage` 内部状态属性的重命名都会导致预览功能无声崩溃。

**修复建议**:

方案 A（推荐）：通过信号获取状态：
```python
# 在 MaaEndControlPage 中已有 execution_state_changed 信号
# MainWindow 已连接此信号（line 284），可在此槽中缓存状态
# _refresh_preview 改用 self._cached_maaend_state 判断
```

方案 B（最小改动）：改用 property 或 getter 方法：
```python
# MaaEndControlPage 新增
@property
def is_connected(self) -> bool:
    return self._connected

@property
def is_executing(self) -> bool:
    return self._is_executing
```

---

## 审计结论（批次 85）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 85 | CLI-03 (keyevent 校验粒度不一致) | **结论正确**。`handlers.py:477` 使用 `key.startswith("KEYCODE_")`，放行任何 KEYCODE_ 前缀字符串；`shell_security.py:110-112` 使用 `s in KNOWN_KEYEVENT_NAMES`，仅白名单放行。CLI handler 放行 → daemon shell 路径（`_is_allowed_shell_cmd`）仅检查前缀 → 到达 Android 设备 → 返回 shell 错误。错误信息不明确，用户难以区分拼写错误与 ADB 连接问题。 |
| 批次 85 | O-10 范围延伸 (keyevent/monitor handlers 缺少 default_client 检查) | **结论正确**。`_handle_device_keyevent` (line 471) 和 `_handle_device_monitor` (line 486) 均无 `android.default_client is None` 检查。与 screenshot/tap/swipe 同属一个根因（device handler 间异常处理不一致）。 |
| 批次 85 | 批次 84 审计 | **结论正确**。逐项复核 RUNTIME-03 (`runtime.py:506-510` 非原子写入)、VLM-03 (`vlm_walk_navigator.py:331-333` imencode 返回值丢弃)、CLI-02 (`cli_bridge.py:229-231` 交互模式 _crash_count 不重置)，全部结论准确。 |

**批次 85 全部 2 项新发现 + 1 项范围延伸 + 批次 84 审计均经本批次逐项源码复核确认准确，无需修正。**

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| 代码质量（低） | 2 | DAEMON-01 (daemon 层 cv2.imencode 返回值丢弃), MW-01 (跨类私有属性访问) |
| 高风险 | 0 | — |
| 中风险 | 0 | — |

**本轮无中高风险发现。**

---

## 跨批次模式观察

DAEMON-01 与 O-22/VLM-03 属于同一根因（`cv2.imencode` 返回值丢弃），但位于不同文件和执行路径：

| 维度 | O-22/VLM-03 | DAEMON-01 |
|------|-------------|-----------|
| 文件 | `vlm_walk_navigator.py` | `android_runtime.py` |
| 调用路径 | VLM 行走导航 → 帧编码 → base64 | daemon screenshot → 帧编码 → mmap |
| 影响 | VLM 导航循环崩溃 | daemon screenshot RPC 崩溃 |
| 修复状态 | 未修复（Open） | 本次新增 |

**建议**：引入统一的 `safe_imencode(frame, fmt=".png")` helper 函数，在 `core/foundation/` 层集中处理返回值校验，消除整类重复。

---

*批次 86 报告 | 仅分析，无文件修改*
