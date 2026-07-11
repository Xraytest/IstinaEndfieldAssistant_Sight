# scrcpy 握手成功但无帧 — 根因诊断与修复

> 时间：2026-07-12
> 关联：`reports/image_keepalive_analysis.md`、`docs/TASK_LOG.md` 2026-07-12 09:00 条目
> 修改文件：`src/core/capability/device/android_runtime.py`

---

## 1. 根因分析

### 1.1 现象

scrcpy 会话握手完整成功（dummy byte → device name 64B → video header 12B 均已收到，codec 已创建并 open），但帧读取循环中 10 秒内无任何帧数据到达，触发 KEEPALIVE-01 超时重建。上一轮修复（`_last_frame_ts` 重置 + 指数退避）只降低了重建频率，未解决"为何无帧"。

### 1.2 直接原因（三个并列）

| 编号 | 原因 | 代码位置 | 说明 |
|------|------|----------|------|
| **DIAG-01** | `_drain_pipe` 完全丢弃 server stdout/stderr | 旧 L389-401 | scrcpy-server 的启动日志、编码器错误、协议警告全部被 `pipe.read(65536)` 读后丢弃，导致**零诊断可见性**。无法判断是编码器初始化失败、屏幕关闭、还是协议不匹配。 |
| **POWER-01** | 网络ADB下 `stay_awake=true` 无效 | `_start_server` 旧 L210 | 设备 serial 为 `192.168.1.12:16512`（网络 ADB）。scrcpy 的 `stay_awake` 依赖 USB 充电状态判断，仅在 USB 连接时生效。屏幕关闭后，Android 视频编码器（MediaCodec）不产生帧，scrcpy-server 无帧可发。 |
| **SILENT-01** | 帧循环中所有异常/断开被静默吞掉 | 旧 L313-348 | `len(header) < 12`、`len(data) < pkt_size`、解码异常均 `break` 或 `pass` 无日志；config packet 解码失败也静默。无法区分"server 不发帧"和"发了但解码失败"。 |

### 1.3 根本原因

scrcpy 作为串流方案，server 启动后应持续产生帧。握手成功（video header 含 codec_id/width/height）证明编码器已创建，但**设备屏幕关闭时 Android SurfaceFlinger 不向编码器送画面，MediaCodec 输出队列长期为空**。叠加 `_drain_pipe` 丢弃 server 日志，使得"屏幕关闭"这一可恢复原因被掩盖为"scrcpy 通道异常"，走入无限重建死循环。

### 1.4 调用链

```
_ScrcpySession._run()
  └── _start_server(max_size, bit_rate)
        ├── _host_shell("pkill ...")              # 清理旧 server
        ├── _ensure_device_online()
        ├── [旧] 无 power_on，无 keyevent wakeup   ← POWER-01：屏幕可能关闭
        └── Popen(app_process ... scrcpy 2.7 ...)
              └── _drain_pipe(stdout)              ← DIAG-01：输出被丢弃
  └── _decode_loop()
        ├── dummy byte ✓ / device name ✓ / video header ✓
        ├── codec.open() ✓                        ← 编码器已创建
        └── while: fileobj.read(12) → 10s 超时     ← 无帧：屏幕关闭，MediaCodec 空输出
              └── break（旧：无日志）               ← SILENT-01
```

---

## 2. 修改方案

### 2.1 DIAG-01：`_drain_pipe` 记录 server 输出

将"读取即丢弃"改为按行读取并记录到 logger，使 scrcpy-server 的 `INFO:`/`WARN:`/`ERROR:` 日志全部可见。

```python
# 修改后
def _drain_pipe(self, pipe) -> None:
    buf = b""
    try:
        while True:
            chunk = pipe.read(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.decode("utf-8", errors="replace").rstrip("\r")
                if text.strip():
                    self._logger.info("scrcpy-server: " + text)
        # 处理尾部未换行内容
        ...
```

### 2.2 POWER-01：`_start_server` 增加电源唤醒

1. 显式添加 `power_on=true` 参数 — scrcpy 2.7 server 端调 `PowerManager.wakeUp()`，不需要 `control=true`。
2. 启动 server 前通过 `input keyevent 224`（KEYCODE_WAKEUP）唤醒屏幕，作为双保险。

```python
# 修改后
try:
    self._host_shell("input keyevent 224")
except Exception:
    pass
server_cmd = (
    ... "power_on=true" ...
)
```

### 2.3 SILENT-01：`_decode_loop` 增加诊断日志

在以下关键点增加日志：
- 握手成功后：记录 device name / codec / 分辨率 / port
- config packet 收到时：记录 size
- 首帧收到时：记录 codec / 分辨率
- `len(header) < 12`：记录 frames_received
- `len(data) < pkt_size`：记录 expected / got / frames_received
- 异常包大小：记录 pkt_size / pts_flags
- config 解码失败：记录 error
- 帧解码失败：记录 error / pkt_size / is_keyframe（不再 `pass` 静默）

---

## 3. 影响面

| 组件 | 影响 | 说明 |
|------|------|------|
| `_drain_pipe` | 输出从丢弃改为记录 | 日志量增加（server 启动时约 5-10 行 INFO），但提供关键诊断能力。使用 4096 字节分块读取 + 按行切分，不阻塞。 |
| `_start_server` | 增加 `input keyevent 224` + `power_on=true` | 每次启动多一次 adb shell 调用（~50ms）。`power_on=true` 是 scrcpy 2.7 原生参数，无兼容性风险。 |
| `_decode_loop` | 增加 frame_counter / first_frame_logged 局部变量 | 仅局部变量，不影响线程安全。日志在首帧和异常路径触发，稳态不产生额外日志。 |
| 日志系统 | 新增 `scrcpy-server:` 前缀日志 | 可被日志过滤器捕获。server 输出的 ERROR 级别内容以 INFO 记录（因为来自 stdout 合并流），但内容本身包含 ERROR 文本可检索。 |
| `_run` 退避逻辑 | 不变 | 保留上一轮的指数退避（2s→60s），作为兜底。根因修复后退避极少触发。 |

---

## 4. 非期待变化

1. **日志量增加**：`_drain_pipe` 现在会记录 server 的所有输出。scrcpy-server 启动时约输出 5-10 行（如 "INFO: Device: ..."），正常运行中偶尔输出。若 server 进入异常循环，日志可能刷屏。**回退策略**：可在 logger 配置中对 `scrcpy-server:` 前缀做速率限制，或降级为 DEBUG 级别。

2. **`input keyevent 224` 在某些设备上可能唤醒锁屏**：如果设备有锁屏密码，唤醒后停在锁屏界面，scrcpy 仍能拿到帧（锁屏画面），但用户可能不期望。**回退策略**：keyevent 调用包在 try/except 中，失败不影响 server 启动；如需移除只需删 3 行。

3. **`power_on=true` 在不支持该参数的 scrcpy 版本上会被忽略**：scrcpy 2.7 支持，更低版本可能报 unknown option。当前 jar 为 2.7，无风险。若未来降级 jar 版本，需移除该参数。

4. **首帧日志仅记录一次**：`first_frame_logged` 标志在每次 `_decode_loop` 进入时重置（局部变量），所以每次重建会话后首帧都会记录一条 INFO。这是预期行为，用于确认重建后帧流恢复。

5. **帧解码失败不再静默**：以前 `except Exception: pass` 会吞掉所有解码错误，现在记录为 warning。如果存在持续性的解码问题（如码流损坏），日志中会出现多条 `scrcpy 帧解码失败` warning。这是正面变化——让问题可见而非掩盖。
