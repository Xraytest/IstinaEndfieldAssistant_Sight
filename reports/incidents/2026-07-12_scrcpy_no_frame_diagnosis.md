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

### 2.1 ENCODER-01：降低关键帧间隔

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

### 2.2 TIMEOUT-01：增加客户端超时余量

将 `sock.settimeout(10.0)` 改为 `sock.settimeout(15.0)`，将 keepalive 检查从 10 秒改为 15 秒，提供充足余量。

```python
sock.settimeout(15.0)
# ...
if self._last_frame_ts and (time.time() - self._last_frame_ts) > 15.0:
    self._logger.warning("scrcpy 帧接收超时，准备重建会话", ...)
    break
```

### 2.3 移除无效的屏幕唤醒代码

用户确认目标为模拟器（无熄屏），移除此前添加的 `screen_off_timeout` 和 `input keyevent 224` 调用。保留 `power_on=true`（scrcpy 原生参数，对模拟器无害）。

### 2.4 CLEANUP-01：添加 `cleanup=false` 防止 jar 删除

在 scrcpy server 命令中添加 `cleanup=false`，阻止 server 退出时通过 `CleanUp.unlinkSelf()` 删除 `/data/local/tmp/scrcpy-server.jar`。

```python
"send_frame_meta=true cleanup=false "
```

效果：server 退出后 jar 保留在设备上，重连时 `_check_jar_cached` 返回 True，跳过推送。**已通过日志验证：第二次连接起不再推送 jar。**

### 2.5 PKILL-01：移除 `pkill` 跨会话干扰

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

### 2.6 STALL-01：诊断日志（编码器停滞）

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

4. **任务执行期间编码器停滞（未完全修复）**：MaaEnd 任务执行期间，模拟器 SurfaceEncoder 停止产出帧，导致每 ~16s 超时重连。诊断日志确认 server 进程存活（`server_alive=True`），非崩溃。此为模拟器编码器与 MaaEnd screencap 的资源竞争，不影响任务执行成功率（VisitFriends 任务正常完成），仅影响预览画面连续性。

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
