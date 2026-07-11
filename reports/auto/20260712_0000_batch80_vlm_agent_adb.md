# 审计批次 80 — VLM 行走导航帧编码防护 / MaaEnd Agent 诊断输出丢失 / ADB 库降级日志 + 审计批次 79

**生成时间**: 2026-07-12 00:00
**覆盖文件**: `vlm_walk_navigator.py`, `maa_end/runtime.py`, `adb_manager.py`
**审计方法**: 静态代码逻辑分析，无测试执行

---

## 新增发现（3 项）

### VLM-01 — `_frame_to_base64` 对 `cv2.imencode` 失败无防护，VLM 行走导航在帧编码失败时崩溃

**等级**: BUG / 低
**位置**: `vlm_walk_navigator.py:331-333`

**问题代码**:

```python
# vlm_walk_navigator.py:331-333
def _frame_to_base64(self, frame: np.ndarray) -> str:
    _, buf = cv2.imencode(".png", frame)
    return base64.b64encode(buf).decode("ascii")
```

**根因分析**:

`cv2.imencode()` 返回 `(retval, buf)` 元组。当编码失败时（如 frame 内存损坏、shape 异常、极端内存不足），`retval` 为 `False`，`buf` 为 `None`。代码直接对 `buf` 调用 `base64.b64encode(buf)`，触发 `AttributeError: 'NoneType' object has no attribute 'tobytes'`。

**调用链推演**:

```
walk_to() step loop
  │
  ├── _grab_frame() → 解码成功返回 np.ndarray
  ├── _locator.locate(frame) → (可能返回 None)
  ├── _frame_to_base64(frame)
  │     │
  │     ├── cv2.imencode(".png", frame) → (False, None)
  │     │     ↑ 触发条件：frame 数据异常（scrcpy 丢帧、解码不完整）
  │     └── base64.b64encode(None) → AttributeError 崩溃
  │
  └── 整个 walk_to 循环中断，导航失败
```

**触发条件**:
- scrcpy 视频流丢帧导致解码后的 frame 含有异常数据（如全零、shape 异常）
- 内存极端不足导致 OpenCV 内部分配失败
- frame 来源为外部截图且格式不标准

**影响面**:
- **低**：正常 scrcpy 帧流几乎不会触发，但作为防御性编程缺失，一旦触发则 VLM 行走导航完全中断。`walk_to()` 的通用 `except Exception` 块会捕获此错误并记录为 `"vlm_error"`，但日志仅包含 `str(exc)`，无法区分是"帧编码失败"还是"LLM 调用失败"，调试困难。

**修复建议**:

```python
def _frame_to_base64(self, frame: np.ndarray) -> str:
    ret, buf = cv2.imencode(".png", frame)
    if not ret or buf is None:
        raise ValueError("frame encoding failed")
    return base64.b64encode(buf).decode("ascii")
```

---

### MAA-07 — `_start_agent` 将 go-service 的 stdout/stderr 重定向到 DEVNULL，Agent 启动失败时诊断输出永久丢失

**等级**: 代码质量 / 低
**位置**: `maa_end/runtime.py:458-464`

**问题代码**:

```python
# maa_end/runtime.py:458-464
process = subprocess.Popen(
    [str(agent_exe), agent_id],
    cwd=str(agent_root),
    stdout=subprocess.DEVNULL,   # ← 正常输出丢弃
    stderr=subprocess.DEVNULL,   # ← 错误输出丢弃
    env=agent_env,
)
```

**根因分析**:

`_start_agent` 启动 go-service 进程后，通过轮询 `process.poll()` 检测进程是否退出（轮询 10 次 × 0.5s = 5 秒）。但 go-service 退出的**原因**完全不可见——stdout 和 stderr 均被重定向到 `DEVNULL`。

常见的 go-service 启动失败原因：
- DLL 缺失（`MAAFW_BINARY_PATH` 指向错误路径）
- 端口冲突（agent_id 已被占用）
- 权限不足（无法写入日志/缓存目录）
- go-service 内部 panic

这些错误信息全部被丢弃，开发者只能看到 `"go-service 进程启动后立即退出"` 的通用日志，无法定位根因。

**对比**:

| 文件 | 方法 | 输出处理 | 诊断能力 |
|------|------|----------|----------|
| `llm/runtime.py:344` | `_try_start` Popen | `stdout=PIPE, stderr=PIPE` | ✓ 启动失败时读取输出 |
| `maa_end/runtime.py:458` | `_start_agent` Popen | `stdout=DEVNULL, stderr=DEVNULL` | ✗ 输出永久丢弃 |

**影响面**:
- **低**：不影响正常功能（go-service 成功启动时无需输出）。但 Agent 启动失败时，缺少诊断信息导致排查困难。与 LLM-01（`_try_start` 60s 超时未清理进程）不同：LLM-01 是关于超时后进程泄漏，这里是启动时输出被丢弃。

**修复建议**:

```python
process = subprocess.Popen(
    [str(agent_exe), agent_id],
    cwd=str(agent_root),
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=agent_env,
)
```

启动轮询后，若进程退出，读取 `process.communicate(timeout=2)` 获取输出并记录到日志。若成功启动，可保持管道不读取（go-service 的 stdout/stderr 在正常运行期间无输出），或在启动成功后关闭管道。

---

### ADB-01 — `adb_manager.py` 的 adbutils 失败回退到 subprocess 不记录原始异常，调试困难

**等级**: 代码质量 / 低
**位置**: `adb_manager.py:89-90`（`shell` 方法）、`adb_manager.py:102-103`（`screencap` 方法）

**问题代码**:

```python
# adb_manager.py:85-90
def shell(self, cmd: str, serial: Optional[str] = None) -> str:
    try:
        import adbutils
        adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
        device = adb.device(serial=serial or self._first_device_serial())
        if device is None:
            raise RuntimeError("未找到 ADB 设备")
        return device.shell(cmd)
    except Exception:                    # ← 原始异常被吞掉
        return self._shell_via_subprocess(cmd, serial)  # ← 静默回退

# adb_manager.py:98-103
def screencap(self, serial: Optional[str] = None) -> bytes:
    try:
        import adbutils
        ...
        return device.screencap()
    except Exception:                    # ← 原始异常被吞掉
        return self._screencap_via_subprocess(serial)  # ← 静默回退
```

**根因分析**:

两个方法在 adbutils 调用失败时，直接回退到 subprocess 实现，不记录原始异常的原因。adbutils 的常见失败原因：
- `adbutils.AdbClient` 连接 ADB server 失败（ADB server 未启动）
- `adb.device(serial)` 返回 None（设备离线）
- adbutils 库本身版本不兼容

这些失败原因全部不可见。用户/开发者无法区分"adbutils 可用且正常工作"和"adbutils 持续失败但 subprocess 回退掩盖了问题"。

**对比**: `get_devices()`（line 55-57）在 adbutils 失败时记录了 warning 日志：`"adbutils 获取设备列表失败，回退 subprocess"`。`shell` 和 `screencap` 应该采用同样的策略。

**影响面**:
- **低**：subprocess 回退保证功能不中断。但调试时无法知道 adbutils 为何失败，可能掩盖 ADB server 问题或设备连接问题。

**修复建议**:

```python
def shell(self, cmd: str, serial: Optional[str] = None) -> str:
    try:
        import adbutils
        ...
    except Exception as exc:
        self._logger.warning(LogCategory.ADB, "adbutils shell 失败，回退 subprocess", error=str(exc))
        return self._shell_via_subprocess(cmd, serial)
```

---

## 审计结论（批次 79）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 79 | MAEEND-01 (select 控件 falsy 0) | **结论正确**。`_get_current_case` 和 `_collect_option_recursive` 两处均使用 `if data` 判断 `QVariant` 返回值。当 case name 为 `int(0)` 时，`int(0)` 为 falsy，代码回退到 `currentText()`，分别导致子选项面板不显示和管道覆盖选项值错误。修复方案 `data is not None` 正确。 |
| 批次 79 | MAEEND-02 (导出文件非原子写入) | **结论正确**。`maaend_control_page.py:872` 使用 `Path.write_text` 写入导出文件，非原子操作。对比 `queue_state.py:122-124` 的 `.with_suffix(".tmp") + os.replace` 原子写入模式，差异准确。影响面评估合理（导出文件由用户选择路径，非项目内部配置，但写入中断导致文件损坏时用户体验不佳）。 |

**批次 79 全部 2 项结论经本批次逐项源码复核确认准确，无需修正。**

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| BUG（低） | 1 | VLM-01 (VLM 帧编码失败无防护) |
| 代码质量（低） | 2 | MAA-07 (go-service 诊断输出丢弃), ADB-01 (ADB 库降级无日志) |

**无新发现中高风险项。**

本轮审计聚焦 VLM 行走导航的帧编码路径、MaaEnd Agent 进程的启动诊断输出、ADB 库的降级回退路径。发现 `_frame_to_base64` 对 `cv2.imencode` 返回值缺乏防护（帧编码失败时崩溃），`_start_agent` 将 go-service 的 stdout/stderr 丢弃到 DEVNULL（Agent 启动失败时无诊断信息），以及 `adb_manager.py` 的 adbutils 降级回退不记录原始异常（调试困难）。批次 79 的 2 项结论均经源码逐行复核确认准确。

---

*批次 80 报告 | 仅分析，无文件修改*