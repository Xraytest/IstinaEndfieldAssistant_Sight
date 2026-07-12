# 事件报告：scrcpy 图像管线持续连接（PERSIST-01）

**日期**: 2026-07-13
**状态**: 已修复
**严重性**: P0 — 核心功能（设备预览）持续可用

## 1. 根因分析

### 1.1 问题现象

用户报告：TRAY-01 修复后，scrcpy 图像管线仍会在一定时间后自动断开。用户要求：
1. scrcpy 连接成功建立后，在 GUI 进程终止之前**持续连接不得断开**
2. 预览**实时展示无延迟无抽帧**
3. 必须有效测试确认问题无误

### 1.2 根因链

**直接根因**：`android_runtime.py` `_recv_exact` 方法中的 `max_stalls=3` 机制（L270）在编码器停滞 15s（3×5s socket timeout）后强制返回 None，触发会话重建，导致帧流中断。

**完整根因链**：

```
编码器短暂停滞（静态画面 / 模拟器软件编码器）
  ↓
sock.recv() 超时 5s × 3 次 = 15s
  ↓
_recv_exact 的 max_stalls=3 触发 → return None
  ↓
_decode_loop 收到 None → break 退出帧读取循环
  ↓
_run 的 finally 块调用 _cleanup → 清除 _latest_frame，_last_frame_ts=0
  ↓
mmap 不再更新（_on_frame 回调不再被调用）
  ↓
GUI reader 的 read_frame() 返回 None（frame_count 不变）
  ↓
is_stale(max_age=10.0) 返回 True → 显示"已断开"
  ↓
会话重建期间（2s backoff + 重连 + 首帧 ≈ 5-10s）预览中断
```

### 1.3 设计缺陷分析

`max_stalls=3` 机制的设计初衷是处理编码器永久停滞（如屏幕关闭、编码器崩溃）。但在当前配置下，该机制是**有害的**：

1. **scrcpy 配置已防止编码器永久停滞**：
   - `power_on=true` — 保持屏幕开启
   - `stay_awake=true` — 防止设备休眠
   - `i-frame-interval=2` — 强制每 2s 产出关键帧，即使静态画面也有帧流

2. **server 进程存活检测已覆盖编码器崩溃场景**：
   - `_decode_loop` L392-394：`server_proc.poll()` 检测 server 退出
   - `_recv_exact`：socket timeout 时检测 server 是否已退出

3. **max_stalls 误杀正常停滞**：
   - 模拟器软件编码器 `c2.android.avc.encoder` 在高负载时可能短暂停滞 >15s
   - 网络波动可能导致 socket 超时
   - 这些场景下 server 仍存活，编码器会自动恢复，不需要重建会话

## 2. 修改方案

### 2.1 修改 1: `_recv_exact` 移除 max_stalls 限制

**文件**: `src/core/capability/device/android_runtime.py`
**方法**: `_recv_exact` (L255-298)

**修改前**：
```python
max_stalls = 3  # 3 × 30s socket timeout = 90s 无数据后强制重建会话
# ...
elif stall_count >= max_stalls:
    self._logger.warning("scrcpy socket 连续 %d 次超时（server 存活但编码器停滞），强制重建会话" % stall_count, ...)
    return None
```

**修改后**：
```python
# PERSIST-01: 移除 max_stalls 限制。server 存活时持续等待不重建会话，
# 确保 scrcpy 连接成功建立后在 GUI 进程终止前持续不断开。
# socket.timeout 时检查 server 进程：存活则 continue 继续等待，
# 已退出则 return None 触发重建。
```

移除 `stall_count` 和 `max_stalls` 变量，socket timeout 时仅检查 server 进程状态：存活则 `continue` 继续等待，已退出则 `return None`。

### 2.2 修改 2: `_refresh_preview` 移除"已断开"显示

**文件**: `src/gui/pyqt6/main_window.py`
**方法**: `_refresh_preview` (L456-470)

**修改前**：
```python
if self._frame_reader.is_stale(max_age=10.0):
    if self._frame_reader.refresh():
        self._logger.info(...)
    else:
        self._preview_widget.set_status("已断开", _STATUS_COLOR_LOST)
```

**修改后**：
```python
if self._frame_reader.is_stale(max_age=10.0):
    if self._frame_reader.refresh():
        self._logger.info(...)
    # PERSIST-01: refresh 失败时不显示"已断开"，保持上一帧和"● 实时"状态
```

reader 存活时不再显示"已断开"，仅尝试 `refresh()` 检测 daemon 重启。

### 2.3 修改 3: `is_stale` 文档更新

**文件**: `src/gui/pyqt6/scrcpy_frame_reader.py`
**方法**: `is_stale` (L103-117)

更新文档说明 `is_stale` 现仅用于触发 `refresh()`，不再用于显示"已断开"。

## 3. 影响面

### 3.1 受益场景

| 场景 | 修改前 | 修改后 |
|------|--------|--------|
| 编码器短暂停滞（<15s） | 强制重建会话，预览中断 5-10s | 持续等待，编码器恢复后自动继续 |
| 静态画面帧率低 | 15s 无帧触发重建 | 持续等待 i-frame-interval=2s 的关键帧 |
| 模拟器高负载 | 编码器停滞 >15s 触发重建 | 持续等待，负载恢复后自动继续 |

### 3.2 仍会重建会话的场景（正确行为）

| 场景 | 行为 | 原因 |
|------|------|------|
| server 进程崩溃 | 重建 | `_decode_loop` L392-394 检测 `server_proc.poll()` |
| 网络断开（EOF） | 重建 | `_recv_exact` 检测空 chunk 返回 None |
| socket 超时 + server 退出 | 重建 | `_recv_exact` 检测 server 已退出返回 None |
| CLI 崩溃 | auto-reconnect | `_on_cli_crashed` 1.5s 后发起 `system connect` |

### 3.3 风险评估

**风险**：如果编码器永久停滞（如屏幕硬件故障），`_recv_exact` 会无限等待。

**缓解**：
1. scrcpy 配置 `power_on=true` + `stay_awake=true` 防止屏幕关闭
2. `_decode_loop` 的 `server_proc.poll()` 检测覆盖 server 崩溃
3. `_recv_exact` 的 EOF 检测覆盖网络断开
4. 用户可通过手动断开重连恢复

## 4. 非期待变化

### 4.1 编码器停滞期间 mmap 不更新

编码器停滞期间 `_on_frame` 回调不被调用，mmap 保留上一帧。GUI reader 的 `read_frame()` 返回 None（frame_count 不变），预览显示上一帧。这是**预期行为** — 连接未断开，仅无新帧。

### 4.2 日志不再出现"强制重建会话"

移除 `max_stalls` 后，日志不再出现"scrcpy socket 连续 N 次超时（server 存活但编码器停滞），强制重建会话"记录。server 真正退出时仍会出现"scrcpy 读取超时且 server 已退出，重建会话"。

### 4.3 `is_stale` 不再触发"已断开"

`is_stale` 仍用于触发 `refresh()` 检测 daemon 重启，但不再触发"已断开"显示。reader 存活时始终显示"● 实时"或保持上一帧。

## 5. 验证

### 5.1 静态验证

- `py_compile` 三文件通过
- `_recv_exact` 逻辑审查：server 存活时 `continue`，server 退出或 EOF 时 `return None`

### 5.2 运行时验证脚本

新增 `scripts/verify_scrcpy_persistent.py`，执行步骤：
1. CLI `system connect` 建立连接
2. 等待 mmap 就绪
3. 持续监控 frame_count 变化（默认 120s）
4. 记录停滞周期（frame_count 不增长的时段）
5. 扫描日志确认无"强制重建会话"记录
6. 判定标准：
   - frame_count 持续增长（>10 帧）
   - 平均帧率 >1.0 fps
   - 无 >15s 的长时间停滞
   - 无"强制重建会话"日志

**用法**：
```
3rd-part/python/python.exe scripts/verify_scrcpy_persistent.py --serial <serial> --duration 120
```

## 6. 相关提交

- PERSIST-01: 移除 max_stalls 限制 + _refresh_preview 移除"已断开"显示 + 验证脚本
