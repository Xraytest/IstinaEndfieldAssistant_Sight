# scrcpy 画面管道频繁断开 — 根因分析报告

> 日期: 2026-07-11
> 模块: `src/core/capability/device/android_runtime.py` — `_ScrcpySession` / `_Daemon`
> 类型: 行为异常（画面管道频繁断开 + 重建循环）
> 日志范围: 2026-07-08 ~ 2026-07-11 main.log

## 1. 根因分析

### 1.1 症状与模式

scrcpy 预览通道在 **网络 ADB**（`serial=192.168.1.12:16512`）下频繁断开，呈现稳定的 **启动 → 短暂工作 → 超时 → 重建** 循环：

| 会话 | 启动时间 | 超时时间 | 寿命 | socket 超时 |
|---|---|---|---|---|
| #1 (07-11 21:38) | 21:38:15 | 21:38:46 | ~31s | 30s（修复前） |
| #2 (07-11 21:50) | 21:50:34 | 21:50:45 | ~11s | 10s（修复后） |
| #3 (07-11 21:50) | 21:50:47 | 21:50:58 | ~11s | 10s |
| #4 (07-11 21:51) | 21:51:02 | 21:51:08 | ~6s | 10s |

会话寿命与 socket 超时正相关性极强：30s 超时→~31s 寿命；10s 超时→~11s 寿命。这表明 **scrcpy 流在交付初始关键帧后即停止发送数据**，socket 超时是唯一检测手段。

### 1.2 核心证据

1. **所有断开均发生在网络 ADB**：日志中 100+ 条 `scrcpy 无帧` 和全部 `socket 读取超时` 事件的 serial 均为 `192.168.1.12:16512`。本地/USB 连接（`serial=None`）无此问题。
2. **初始帧能成功交付**：每个会话的首个 screenshot 返回有效帧（data_size=538524 或 616453 bytes），说明握手和初始编码正常。
3. **后续帧停止到达**：连续 screenshot 的 data_size 保持不变（如 616453 重复 3 次），说明 `get_latest_frame()` 返回的是同一缓存帧，stream 无新帧到达。
4. **`_server_proc` 状态不可观测**：`_drain_pipe` 丢弃所有 stdout/stderr，无法确认 scrcpy server 是否已退出。

### 1.3 根因链

```
scrcpy server 在设备端退出/停滞（根因 — 无法直接观测，见 1.4 推理）
    ↓
localabstract:scrcpy socket 关闭，但 ADB forward 隧道（网络 ADB）未及时检测
    ↓
Python 客户端 fileobj.read(12) 阻塞，无数据到达
    ↓
socket 超时（10s/30s）→ TimeoutError → _cleanup() → 会话重建
    ↓
下次 screenshot 遇到新会话未就绪 → "scrcpy 无帧" → 返回 error
    ↓
再次 screenshot（3s 后）→ 新会话已交付初始帧 → 成功
    ↓
循环重复
```

### 1.4 scrcpy server 退出/停滞的推理

无法直接确认 server 是否退出（`_drain_pipe` 丢弃输出），但以下间接证据支持此判断：

**a) 会话寿命与 socket 超时强相关**

如果 server 持续运行且持续编码（即使屏幕静态，默认 `i_frame_interval=10s` 也会产生关键帧），则 `fileobj.read(12)` 应在每次 i_frame_interval 内收到数据，socket 不会超时。但实际寿命 ≈ socket 超时，说明 **在初始帧之后，server 未再向 socket 写入任何数据**。

**b) 非网络因素排除**

- `stay_awake=true` 已设置，不应因设备休眠导致编码停止
- `control=false` + `video=true` 配置正确
- 握手成功（dummy byte + device name + video header 均正确读取），codec 初始化正常
- 本地/USB 连接无此问题，排除代码逻辑错误

**c) 可能的 server 退出原因**

| 假设 | 可能性 | 依据 |
|---|---|---|
| server 进程被 `pkill` 误杀 | 低 | `_start_server` 和 `_cleanup` 的 `pkill` 在时序上不重叠 |
| 设备端 codec/encoder 异常 | 中 | 网络延迟可能导致 ADB shell 进程 stdout 写入阻塞，间接影响 server |
| ADB forward 隧道半开 | 中 | 网络 ADB 的 TCP 连接可能半开（设备 Wi-Fi 间歇性中断），隧道未及时检测 |
| `_drain_pipe` 异常关闭管道 | 低 | `except Exception: pass` + `finally: pipe.close()` 在异常时可能提前关管道，导致 `adb shell` 进程 SIGPIPE |
| server jar 版本/协议不匹配 | 低 | 命令行指定 `2.7` 协议版本，jar git revision `292adf2` |

### 1.5 加剧因素 — `get_latest_frame()` 破坏 KEEPALIVE-01

**[BUG 确认]** `get_latest_frame()` (line 103-108) 在读取缓存帧时更新 `_last_frame_ts`：

```python
def get_latest_frame(self) -> Optional[np.ndarray]:
    with self._lock:
        if self._latest_frame is None:
            return None
        self._last_frame_ts = time.time()  # ← BUG: 读缓存也更新时间戳
        return self._latest_frame
```

`_last_frame_ts` 本意是 **"最后一次从 scrcpy 流收到新帧的时间"**（在 line 318 的 decode loop 中更新）。但 `get_latest_frame()` 的 line 107 在 **读取缓存帧** 时也更新它，导致：

- screenshot 每 3s 请求一次 → `_last_frame_ts` 每 3s 更新一次
- KEEPALIVE-01 检查 `time.time() - self._last_frame_ts > 10.0` **永远为 False**
- KEEPALIVE-01 成为完全无效的死代码

这意味着即使 decode loop 在两次 `read()` 之间迭代，keep-alive 检查也不会触发。**socket 超时是唯一的断流检测机制。**

### 1.6 加剧因素 — 无 server 进程存活检测

decode loop (line 280-285) 从不检查 `_server_proc.poll()`。如果 `adb shell` 进程已退出（因为 scrcpy server 崩溃），decode loop 无法感知，继续等待 socket 数据直到超时。这导致 **10-30s 的无效等待**，而非立即重建。

### 1.7 加剧因素 — `_drain_pipe` 丢弃诊断信息

`_drain_pipe` (line 368-380) 读取并丢弃 `adb shell` 进程的全部 stdout/stderr，不记录任何内容。这使 scrcpy server 的错误输出、崩溃日志、退出码完全不可见，严重阻碍根因定位。

### 1.8 次要问题 — `_check_jar_cached` 始终失败

```python
["shell", "ls /data/local/tmp/scrcpy-server.jar 2>/dev/null"]
```

整个 `ls ... 2>/dev/null` 作为单个参数传给 `adb shell`。`2>/dev/null` 的 redirect 语义取决于设备端 shell，且 `ls` 对不存在文件返回非零退出码。结果：**每次会话启动都推送 jar**（~1s 额外延迟），尽管 jar 已存在于设备上。

## 2. 修改方案

> 本报告为分析任务，以下为建议方案，未实施。按优先级排序。

### P0: 修复 `get_latest_frame()` 时间戳污染

**问题**：line 107 `self._last_frame_ts = time.time()` 使 KEEPALIVE-01 失效。

**方案**：删除 line 107。`_last_frame_ts` 应仅在 decode loop 收到新帧时更新（line 318）。

```python
def get_latest_frame(self) -> Optional[np.ndarray]:
    with self._lock:
        if self._latest_frame is None:
            return None
        return self._latest_frame  # 不更新 _last_frame_ts
```

### P0: `_drain_pipe` 记录 server 退出诊断

**问题**：server 输出被丢弃，无法诊断退出原因。

**方案**：`_drain_pipe` 退出时记录 `_server_proc.returncode` 和最后 N 字节输出：

```python
def _drain_pipe(self, pipe) -> None:
    tail = b""
    try:
        while True:
            chunk = pipe.read(65536)
            if not chunk:
                break
            tail = (tail + chunk)[-2048:]  # 保留最后 2KB
    except Exception:
        pass
    finally:
        try:
            pipe.close()
        except Exception:
            pass
        rc = self._server_proc.poll() if self._server_proc else None
        self._logger.warning("scrcpy server 进程退出", returncode=rc, tail=tail.decode("utf-8", errors="replace")[-512:])
```

### P1: decode loop 添加 server 存活检测

**问题**：server 退出后 decode loop 无感知，无效等待至超时。

**方案**：在 `fileobj.read(12)` 前检查 `_server_proc.poll()`：

```python
while not self._stop_event.is_set():
    if self._server_proc and self._server_proc.poll() is not None:
        self._logger.warning("scrcpy server 进程已退出，准备重建会话", returncode=self._server_proc.returncode)
        break
    if self._last_frame_ts and (time.time() - self._last_frame_ts) > 10.0:
        ...
```

### P1: 修复 `_check_jar_cached`

**问题**：`ls ... 2>/dev/null` 始终返回非零，导致每次推送 jar。

**方案**：改用 `test -f` 判断，或忽略退出码只检查输出内容：

```python
def _check_jar_cached(self) -> bool:
    try:
        output = self._adb_manager.run_adb(
            ["shell", "test -f /data/local/tmp/scrcpy-server.jar && echo OK"],
            serial=self._serial or "",
        )
        return "OK" in str(output)
    except Exception:
        return False  # 异常时返回 False（保守策略：推送 jar）
```

### P2: 考虑 TCP keepalive 加速半开连接检测

**问题**：网络 ADB 隧道半开时，socket 超时是唯一检测手段（10-30s）。

**方案**：在 socket 上启用 TCP keepalive（Windows: `SIO_KEEPALIVE_VALS`），使 OS 在数秒内检测半开连接并抛出 `ConnectionResetError`，比 socket 超时更快。

## 3. 影响面

| 组件 | 当前行为 | 修复后预期 |
|---|---|---|
| `_ScrcpySession._decode_loop` | 靠 socket 超时检测断流（10-30s） | KEEPALIVE-01 恢复有效 + server 存活检测 → 秒级检测 |
| `_ScrcpySession.get_latest_frame` | 污染 `_last_frame_ts` | 仅返回缓存帧，不修改时间戳 |
| `_ScrcpySession._drain_pipe` | 静默丢弃 server 输出 | 记录退出码 + 尾部输出 |
| `_Daemon.screenshot` handler | 断流后首帧延迟（"无帧" error） | 同（仍需等新会话交付首帧） |
| `_check_jar_cached` | 始终失败 → 每次推送 jar | 正确判断 → 减少不必要推送 |
| 网络 ADB 会话寿命 | 10-30s（超时驱动） | 取决于 server 实际寿命（可能仍短，但诊断信息将揭示根因） |
| 日志 | `TimeoutError` WARNING（修复后）/ ERROR+traceback（修复前） | 增加 `server 进程退出` WARNING + returncode + tail |

## 4. 非期待变化

### 4.1 P0 修复 `get_latest_frame()` 的影响

- **正面**：KEEPALIVE-01 恢复有效，在 decode loop 迭代间可检测 10s 无新帧。
- **风险**：若 scrcpy 流的 `i_frame_interval` 默认值 ≥ 10s（屏幕静态时），KEEPALIVE-01 可能在正常情况下误触发重建。需确认 scrcpy 默认 `i_frame_interval`（通常 10s），可能需将 keep-alive 阈值上调至 15-20s。
- **缓解**：将 KEEPALIVE-01 阈值从 10s 调整为 15s，留出 i_frame_interval 余量。

### 4.2 P0 修复 `_drain_pipe` 的影响

- **正面**：server 退出原因可见，加速根因定位。
- **风险**：`tail` 保留 2KB 输出，可能包含设备敏感信息（设备名、路径等）。但已通过 logger 输出，与现有日志策略一致。
- **风险**：`_server_proc.poll()` 在 `_drain_pipe` 线程中调用 — `Popen.poll()` 是线程安全的（仅读取返回码），无并发风险。

### 4.3 P1 修复 server 存活检测的影响

- **正面**：server 退出后立即重建，不再等待 socket 超时。
- **风险**：`_server_proc.poll()` 在 decode loop 中调用 — 线程安全，同上。
- **风险**：如果 `_server_proc` 为 None（启动失败），`poll()` 返回 None，不会误触发。条件 `self._server_proc and self._server_proc.poll() is not None` 已防护。

### 4.4 不修复的风险

若不实施任何修复：
- 画面管道将继续每 10-30s 断开重建，用户体验差
- 每次"无帧" error 导致一次 screenshot 失败
- 无法诊断 scrcpy server 退出原因（`_drain_pipe` 丢弃输出）
- KEEPALIVE-01 保持无效（`get_latest_frame` 污染时间戳）

### 4.5 验证策略

1. **P0 修复后**：观察日志中是否出现 `scrcpy 帧接收超时` (KEEPALIVE-01 触发) 而非 `scrcpy socket 读取超时` (socket 超时触发)。若 KEEPALIVE-01 开始触发，说明修复有效。
2. **P0 `_drain_pipe` 修复后**：观察日志中 `scrcpy server 进程退出` 的 returncode 和 tail，确认 server 是否真的退出以及退出原因。
3. **P1 修复后**：观察会话寿命是否缩短（server 退出后立即重建，不再等 socket 超时）。
4. **`_check_jar_cached` 修复后**：观察 `scrcpy jar 缓存检查失败` WARNING 是否消失，`scrcpy jar 推送完成` 是否仅在首次出现。
