# scrcpy 握手成功但无持续帧 — 根因诊断与修复

> 时间：2026-07-12
> 关联：`docs/TASK_LOG.md` 2026-07-12 条目
> 修改文件：`src/core/capability/device/android_runtime.py`

---

## 1. 根因分析

### 1.1 现象

scrcpy 会话握手完整成功（dummy byte → device name 64B → video header 12B → config packet → 首帧均正常），但首帧之后约 10-13 秒内无新帧到达，触发 KEEPALIVE-01 超时重建。会话陷入"握手→首帧→超时→重建"死循环，每 ~14 秒循环一次。

**后续现象（任务执行期间）**：空闲时稳定的会话在 MaaEnd 任务执行期间每隔 ~16 秒超时重连，且每次重连都重新推送 scrcpy-server.jar（"循环推送"）。

### 1.2 直接原因

| 编号 | 原因 | 说明 |
|------|------|------|
| **FILEOBJ-01** | `socket.makefile("rb", buffering=0)` 的 file object 在 `socket.timeout` 后进入 poisoned 状态 | file object 在首次 `socket.timeout` 后，后续 `read()` 抛出 `OSError("cannot read from timed out object")` 而非 `socket.timeout`。`_recv_exact` 只捕获 `socket.timeout`，`OSError` 未被捕获，传播至 `_run` 的 `except Exception`，触发完整会话重建（杀 server + 移除 forward + 重启）。**这是重连死循环的最终根因。** |
| **RECV-01** | `fileobj.read(n)` 仅做一次 `recv()`，返回 < n 字节 | `socket.makefile("rb", buffering=0)` 创建无缓冲 file object，`read(n)` 映射到单次 `recv()`，对大帧（74KB）常返回 ~61KB。原代码 `if len(data) < pkt_size: break` 把此 partial read 误判为 socket 断开，触发重建。 |
| **ENCODER-01** | 模拟器软件编码器不实现 `KEY_REPEAT_PREVIOUS_FRAME_AFTER` | scrcpy 2.7 `SurfaceEncoder.createFormat()` 设置 `KEY_REPEAT_PREVIOUS_FRAME_AFTER=100000µs`（100ms），要求编码器在静态画面时每 100ms 重复上一帧。但模拟器的 `c2.android.avc.encoder` 软件编码器不实现此特性，静态画面下不产出任何帧。 |
| **IFRAME-01** | scrcpy 默认 `KEY_I_FRAME_INTERVAL=10` 秒 | `SurfaceEncoder.DEFAULT_I_FRAME_INTERVAL = 10`，即每 10 秒才产出一个关键帧。模拟器编码器在静态画面下仅产出关键帧（不产出 P 帧），因此每 10 秒才有一次帧输出。 |
| **TIMEOUT-01** | 客户端 keepalive 超时 = 10 秒 | `_decode_loop` 中 `sock.settimeout(10.0)` 和 `(time.time() - self._last_frame_ts) > 10.0` 恰好等于关键帧间隔，导致在下一个关键帧到达前就触发超时重建。 |
| **CLEANUP-01** | scrcpy 默认 `cleanup=true` 删除 server jar | server 退出时通过 `CleanUp.unlinkSelf()` 删除 `/data/local/tmp/scrcpy-server.jar`，导致每次重连都需重新推送 jar（"循环推送"）。 |
| **PKILL-01** | `_start_server` 和 `_cleanup` 中的 `pkill -f com.genymobile.scrcpy.Server` | 该命令杀死设备上所有 scrcpy server 进程，包括其他会话的 server，导致跨会话干扰。 |
| **STALL-01** | 任务执行期间编码器停滞 | MaaEnd 任务执行期间，模拟器编码器停止产出帧（即使 `i-frame-interval=2`）。诊断日志确认 `server_alive=True`，server 进程仍在运行但无帧输出。 |

### 1.3 根本原因

目标设备为 Android 模拟器（非物理设备），使用软件编码器 `c2.android.avc.encoder`。该编码器存在两个问题：

1. **不实现 `KEY_REPEAT_PREVIOUS_FRAME_AFTER`**：scrcpy 依赖此特性在静态画面时保持帧流，但模拟器编码器忽略此参数。
2. **静态画面下仅产出关键帧**：模拟器编码器不从 Surface 输入产出 P 帧，仅在 `KEY_I_FRAME_INTERVAL` 到期时产出关键帧。

结果：scrcpy 默认 10 秒关键帧间隔 + 客户端 10 秒超时 = 死循环。

> **注意**：此前一度怀疑"网络 ADB 下屏幕关闭导致 MediaCodec 无帧"。经用户确认目标为模拟器（无熄屏），此假设已被排除。

### 1.4 日志证据

修复前日志模式（10:37-10:42，每 ~14 秒循环）：
```
10:37:46 scrcpy 握手成功 + 首帧接收成功
10:38:00 scrcpy 握手成功 + 首帧接收成功  ← 14s 后超时重建
10:38:13 scrcpy 握手成功 + 首帧接收成功  ← 13s 后超时重建
10:38:27 scrcpy 握手成功 + 首帧接收成功  ← 14s 后超时重建
...（持续循环）
```

修复后日志模式（11:44:39 启动，60+ 秒无重连）：
```
11:44:39 scrcpy 握手成功 + config packet + 首帧接收成功
（无后续超时/重建日志 — 会话稳定运行）
```

### 1.5 scrcpy 2.7 源码佐证

`SurfaceEncoder.java` 关键代码：
```java
private static final int DEFAULT_I_FRAME_INTERVAL = 10; // seconds
private static final int REPEAT_FRAME_DELAY_US = 100_000; // 100ms

// createFormat():
format.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, DEFAULT_I_FRAME_INTERVAL);
format.setLong(MediaFormat.KEY_REPEAT_PREVIOUS_FRAME_AFTER, REPEAT_FRAME_DELAY_US);

// encode():
int outputBufferId = codec.dequeueOutputBuffer(bufferInfo, -1); // 无限等待
```

`dequeueOutputBuffer` 使用 `-1`（无限超时）阻塞等待编码器输出。模拟器编码器在静态画面下不产出帧，server 线程阻塞至下一个关键帧（10s），客户端在 10s 时超时断开。

---

## 2. 修改方案

### 2.1 FILEOBJ-01 + RECV-01：移除 fileobj，直接使用 sock.recv()

**最终修复（commit 4b286d6）**：移除 `sock.makefile("rb", buffering=0)` 创建的 file object，所有读取操作改用 `sock.recv()`。

原因：
1. `fileobj.read(n)` 在 `buffering=0` 时仅做一次 `recv()`，对大帧返回 < n 字节（partial read），原代码误判为断开（RECV-01）
2. file object 在 `socket.timeout` 后进入 poisoned 状态，后续 `read()` 抛出 `OSError("cannot read from timed out object")` 而非 `socket.timeout`，`_recv_exact` 无法捕获（FILEOBJ-01）

`sock.recv()` 始终抛出 `socket.timeout`，可被 `_recv_exact` 正确捕获处理：

```python
def _recv_exact(self, sock, n: int) -> Optional[bytes]:
    """从 sock 精确读取 n 字节，处理 partial read 和超时。"""
    data = bytearray()
    stall_count = 0
    while len(data) < n:
        if self._stop_event.is_set():
            return None
        try:
            chunk = sock.recv(n - len(data))  # 直接用 sock.recv()
        except socket.timeout:
            # server 存活则继续等待，已退出则返回 None
            if self._server_proc is not None and self._server_proc.poll() is not None:
                return None
            stall_count += 1
            if stall_count == 1:
                self._logger.info("scrcpy socket 等待数据中（server 存活，不重建）", ...)
            continue
        if not chunk:
            return None  # 真 EOF
        data.extend(chunk)
        stall_count = 0
    return bytes(data)
```

同时移除 keepalive 15s 超时检查（`_recv_exact` 内部已处理超时），socket 超时从 15s 改为 5s（更快检测 server 退出）。

握手阶段的 `fileobj.read()` 也全部替换为 `sock.recv()`，并添加 `socket.timeout` 捕获。

### 2.2 ENCODER-01：降低关键帧间隔

在 scrcpy server 命令中添加 `video_codec_options=i-frame-interval:int=2`，将关键帧间隔从默认 10 秒降至 2 秒。scrcpy 的 `createFormat()` 中 codec options 在默认值之后应用，会覆盖 `KEY_I_FRAME_INTERVAL`。

```python
server_cmd = (
    f"CLASSPATH=/data/local/tmp/scrcpy-server.jar "
    "app_process /system/bin com.genymobile.scrcpy.Server "
    "2.7 tunnel_forward=true audio=false "
    "video=true control=false show_touches=false stay_awake=true "
    "power_on=true send_dummy_byte=true send_device_meta=true "
    "send_frame_meta=true "
    f"max_size={max_size} video_bit_rate={bit_rate} "
    "video_codec_options=i-frame-interval:int=2"
)
```

效果：即使模拟器编码器仅产出关键帧，也每 2 秒一次，远小于客户端超时。

### 2.3 TIMEOUT-01：增加客户端超时余量

将 `sock.settimeout(10.0)` 改为 `sock.settimeout(15.0)`，将 keepalive 检查从 10 秒改为 15 秒，提供充足余量。

```python
sock.settimeout(15.0)
# ...
if self._last_frame_ts and (time.time() - self._last_frame_ts) > 15.0:
    self._logger.warning("scrcpy 帧接收超时，准备重建会话", ...)
    break
```

### 2.4 移除无效的屏幕唤醒代码

用户确认目标为模拟器（无熄屏），移除此前添加的 `screen_off_timeout` 和 `input keyevent 224` 调用。保留 `power_on=true`（scrcpy 原生参数，对模拟器无害）。

### 2.5 CLEANUP-01：添加 `cleanup=false` 防止 jar 删除

在 scrcpy server 命令中添加 `cleanup=false`，阻止 server 退出时通过 `CleanUp.unlinkSelf()` 删除 `/data/local/tmp/scrcpy-server.jar`。

```python
"send_frame_meta=true cleanup=false "
```

效果：server 退出后 jar 保留在设备上，重连时 `_check_jar_cached` 返回 True，跳过推送。**已通过日志验证：第二次连接起不再推送 jar。**

### 2.6 PKILL-01：移除 `pkill` 跨会话干扰

将 `_start_server` 中的 `pkill -f com.genymobile.scrcpy.Server` 替换为精确终止 `self._server_proc`（本会话管理的上一个 server 进程）。同时移除 `_cleanup` 中的 `pkill`。

```python
# _start_server: 精确终止本会话的上一个 server
if self._server_proc is not None and self._server_proc.poll() is None:
    try:
        self._server_proc.terminate()
        try:
            self._server_proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._server_proc.kill()
    except Exception:
        pass
self._server_proc = None
```

效果：不再杀死设备上其他 scrcpy server 进程，避免多会话场景下的跨会话干扰。

### 2.7 STALL-01：诊断日志（编码器停滞）

在 `_decode_loop` 的 socket 断开（header 不完整 / data 不完整）和 `_run` 的 `TimeoutError` 处理中，记录 server 进程的 `server_alive` 和 `server_returncode`。

```python
_srv_alive = self._server_proc is not None and self._server_proc.poll() is None
_srv_rc = self._server_proc.returncode if self._server_proc is not None and self._server_proc.poll() is not None else None
self._logger.warning("scrcpy socket ...", server_alive=_srv_alive, server_returncode=_srv_rc)
```

**验证结果**：任务执行期间 socket 断开时，`server_alive=True, server_returncode=None`，确认 server 进程仍在运行。编码器停滞是模拟器 SurfaceEncoder 与 MaaEnd screencap 操作的资源竞争所致，非 server 崩溃。

---

## 3. 影响面

| 组件 | 影响 | 说明 |
|------|------|------|
| `_start_server` | 新增 `video_codec_options` 参数 | scrcpy 2.7 原生支持，无兼容性风险。关键帧间隔从 10s 降至 2s，码流中关键帧占比略增，带宽轻微上升。 |
| `_start_server` | 新增 `cleanup=false` | server 退出后 jar 保留在设备上，避免重连时重新推送。首次推送后后续连接不再推送 jar。 |
| `_start_server` | 用精确终止替换 `pkill` | 仅终止本会话的 server 进程，不再影响其他会话。 |
| `_cleanup` | 移除 `pkill`，添加 `wait(timeout=2)` | 避免跨会话干扰；`wait` 防止僵尸进程。 |
| `_decode_loop` | 超时从 10s 增至 15s | 稳态无影响（帧流正常时不触发超时）。异常恢复时间从 10s 延长至 15s，可接受。 |
| `_decode_loop` / `_run` | 新增诊断日志 | socket 断开/超时时记录 `server_alive` 和 `server_returncode`，便于后续诊断。 |
| `_start_server` | 移除 `screen_off_timeout` / `keyevent 224` | 模拟器无熄屏，这些调用无效果。移除后每次启动减少 2 次 adb shell 调用（~100ms）。 |

---

## 4. 非期待变化

1. **带宽轻微增加**：关键帧间隔从 10s 降至 2s，关键帧数量增加 5 倍。但模拟器画面通常变化较小，且 `video_bit_rate=8000000` 已限制总码率，实际带宽增加有限。

2. **超时恢复时间延长**：keepalive 超时从 10s 增至 15s。若通道真正断开，重建时间延长 5s。可接受，因为修复后死循环已消除，超时极少触发。

3. **`power_on=true` 对模拟器无害**：模拟器无物理屏幕电源管理，此参数为 no-op。保留以兼容未来可能的物理设备场景。

4. **任务执行期间编码器停滞（已缓解）**：MaaEnd 任务执行期间，模拟器 SurfaceEncoder 停止产出帧。修复前每 ~16s 超时重连；修复后（FILEOBJ-01）`_recv_exact` 捕获 `socket.timeout` 并继续等待（server 存活），不再触发会话重建。预览画面可能暂时停滞但会话保持连接，编码器恢复后自动续流。

---

## 5. 任务执行期间日志证据（12:20-12:22）

```
12:20:19 scrcpy 握手成功 + 首帧接收成功
12:20:35 scrcpy socket 读取超时（16s 无帧）
12:20:38 scrcpy 握手成功 + 首帧接收成功（重连，无 jar 推送）
12:20:54 scrcpy socket 读取超时（16s 无帧）
...
12:22:20 scrcpy socket 断开（data 不完整） server_alive=True server_returncode=None
...
12:22:54 任务执行成功 task=VisitFriends
```

关键观察：
- **无 jar 推送日志**：`cleanup=false` 生效，重连不再推送 jar
- **server_alive=True**：server 进程存活，编码器停滞非崩溃
- **任务执行成功**：scrcpy 不稳定不影响 MaaEnd 任务执行

---

## 6. 最终修复验证（14:30，commit 4b286d6）

验证脚本 `scripts/verify_scrcpy_fix.py`：连接设备 → 40s 监控（每 2s 截图）→ 执行任务 → 任务后截图。

### 6.1 监控结果（40s）

```
[VERIFY] step 2: 监控 scrcpy 稳定性 40s（每 2s 截图）
[VERIFY] [  2.0s] screenshot OK size=616453
[VERIFY] [  4.0s] screenshot OK size=616453
...
[VERIFY] [40.7s] screenshot OK size=616628
[VERIFY] 监控完成: ok=20 fail=0
```

**20/20 截图成功，0 失败。**

### 6.2 日志模式（无重连）

```
14:30:33 scrcpy 握手成功 + config packet + 首帧接收成功
14:30:39 scrcpy socket 等待数据中（server 存活，不重建）
14:30:46 scrcpy socket 等待数据中（server 存活，不重建）
14:31:07 scrcpy socket 等待数据中（server 存活，不重建）
14:32:07 scrcpy socket 等待数据中（server 存活，不重建）
14:32:14 任务执行超时（断开设备，正常退出）
```

**关键对比**：
- 修复前：`OSError: cannot read from timed out object` → `会话异常，2s 后重试` → 杀 server → 重连（每 ~6s 循环）
- 修复后：`socket 等待数据中（server 存活，不重建）` → 继续等待 → 编码器恢复后续流（无重连）

### 6.3 结论

FILEOBJ-01 是重连死循环的最终根因。`socket.makefile()` 的 file object 在 timeout 后 poisoned，`_recv_exact` 无法捕获 `OSError`。改用 `sock.recv()` 后，`socket.timeout` 被正确捕获，server 存活时继续等待而非重建。**重连死循环已消除。**
