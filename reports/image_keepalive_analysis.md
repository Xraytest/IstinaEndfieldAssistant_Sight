# 图像传递链接无法正确保活的根因分析

> 分析时间：2026-07-11  
> 分析范围：`src/core/capability/device/android_runtime.py`、`src/core/service/runtime.py`、`src/gui/pyqt6/main_window.py`、`src/gui/pyqt6/cli_bridge.py`  
> 关联文档：`docs/README.md` §5.3.2 / §5.5B

---

## 1. 根因分析

### 1.1 直接原因

`_ScrcpySession._decode_loop()` 被文档描述为 "Continuous keep-alive"，但实现上**没有任何主动心跳、超时重连或健康检测机制**。它只是在一个 `while not self._stop_event.is_set()` 循环里被动读取 scrcpy 视频帧。一旦设备侧 server 停发帧（例如设备休眠、app 被切到后台、ADB forward 失效、server 进程崩溃），socket 读操作返回空字节，循环 `break` 退出，线程死亡。此后：

- daemon 的 `screenshot`  handler 调用 `get_latest_frame()` 永远返回 `None`，直接返回 `{"error": "scrcpy not ready"}`；
- `AndroidRuntime.screenshot()` 返回 `None`；
- `IstinaRuntime._screenshot()` 回退到 `MaaEndRuntime.screenshot()`（ADB screencap），预览退化为慢速路径；
- **没有人尝试重启 scrcpy 会话**。`_ScrcpySession` 实例仍然保留在 daemon 中，但内部线程已死；下次 GUI 调用 `startScrcpy` 时，daemon 发现 `self._scrcpy_session is not None`，直接跳过重建，导致该非空引用永久阻止重试。

### 1.2 根本原因

| 层面 | 问题 | 代码位置 |
|------|------|----------|
| **通道层** | `_decode_loop` 只有被动读帧，没有 keep-alive 逻辑；断流后 session 静默死亡 | `android_runtime.py:206-318` |
| **恢复层** | daemon 的 `startScrcpy` 不会重建已死亡的 session；`_ScrcpySession.start()` 只在线程 `is_alive()` 为 False 时重启，但外部调用者（`runtime.connect()`）不会在每次预览前检查/重启 | `android_runtime.py:504-513`、`runtime.py:234-240` |
| **观测层** | `runtime.connect()` 调用 `start_scrcpy()` 后**不检查返回值**，无条件记 success；失败时用户看不到告警，预览静默降级 | `runtime.py:237-238` |
| **架构层** | GUI 预览 (`main_window.py:330-331`) 仍走 `_sync_execute("screenshot")` → QProcess → CLI → daemon → mmap 的旧链路，完全未使用 README §5.5B 设计的 `get_latest_frame()` 零开销直读路径；这导致预览帧率被进程启动/JSON 编解码/管道拷贝拖慢，且任何一环阻塞都会表现为 "图像传递链接断开" | `main_window.py:331`、`cli_bridge.py:104-116` |

### 1.3 调用链

```
MainWindow._refresh_preview() [1500ms timer]
  └── _sync_execute("screenshot", timeout_ms=5000)
        └── CLIBridge.execute() → QProcess stdin
              └── istina.py --interactive
                    └── CLIDispatch._handle_screenshot
                          └── IstinaRuntime._screenshot()
                                ├── android.screenshot(serial)
                                │     └── _Daemon._dispatch("screenshot")
                                │           ├── _ScrcpySession.get_latest_frame()  ← 返回 None（session 已死）
                                │           └── return {"error": "scrcpy not ready"}
                                └── [回退] MaaEndRuntime.screenshot()  ← ADB screencap，慢且不稳定
```

若 scrcpy session 健康，GUI 也不会走 `get_latest_frame()`，而是仍然执行上面那条冗长链路。

---

## 2. 修改方案

### 方案 A（最小修复）：让 scrcpy 通道具备基础保活与自动恢复能力

1. **在 daemon 的 `startScrcpy` 中增加 session 健康检查**：若 `_scrcpy_session` 非空但线程已死，先 `stop()` 清理再重建。
2. **在 `_ScrcpySession._decode_loop` 中增加帧超时检测**：引入 `_last_frame_ts`，若超过 N 秒（如 5s）未收到新帧，视为通道异常，主动清理并退出，以便外部感知并重建。
3. **在 `runtime.connect()` 中校验 `start_scrcpy` 返回值**：若返回 `{"error": ...}`，记录 warning 并清理 daemon 中死亡 session，允许后续重试；日志区分成功/失败。

### 方案 B（架构修复）：按 README §5.5B 将预览改为直读 scrcpy 帧

1. **修改 `MainWindow._refresh_preview()`**：直接调用 `self._maaend_page.runtime().android(serial).get_latest_frame()`，跳过 QProcess/CLI/daemon/mmap 整条链路。
2. **当 `get_latest_frame()` 返回 None 且持续超过阈值时**，在 GUI 层标记预览异常，并触发 scrcpy 通道重建（`start_scrcpy`）。
3. **保留 CLI `screenshot` 作为兜底**：供非预览场景（如 scene analyze、llm vision）使用。

> 推荐先执行方案 A 修复保活，再视情况推进方案 B 的预览直读改造。方案 A 改动小、风险低，且直接解决 "session 死后无法恢复" 的根本问题。

---

## 3. 影响面

| 组件 | 影响 | 说明 |
|------|------|------|
| `_ScrcpySession` | 增加 `_last_frame_ts` 字段和帧超时逻辑 | 只读操作加时间戳，不影响解码主循环 |
| `_Daemon._dispatch` `startScrcpy` | 增加 `_scrcpy_session` 存活检查 | 可能改变 session 生命周期，但语义正确 |
| `IstinaRuntime.connect()` | 增加返回值校验与 session 清理 | 日志行为变化（失败不再误报成功） |
| `MainWindow._refresh_preview()` | 若走方案 B，移除对 `_sync_execute("screenshot")` 的依赖 | 预览定时器不再受 CLI 子进程状态阻塞 |
| `CLIBridge` | 方案 B 下预览不再经过 QProcess，降低 bridge 负载 | 不影响其他命令路由 |
| `MaaEndRuntime.screenshot()` | 若预览直读成功，ADB screencap 回退路径调用频率下降 | 正面影响，降低设备负载 |

---

## 4. 非期待变化

1. **`_decode_loop` 增加超时退出后，`_run` 的 `finally` 会执行 `_cleanup()`**：这会移除 ADB forward 并杀掉 scrcpy server 进程。若上层未及时重建，设备上的 `/data/local/tmp/scrcpy-server.jar` 不会残留，但下次 `start()` 会重新推送 jar，增加约 1–2s 启动开销。
2. **`runtime.connect()` 日志从 "scrcpy 预览通道启动成功" 变为条件性成功**：现有日志消费者（如 GUI 启动序列、自动化脚本）若依赖该字符串判断连接状态，可能需要同步调整。但当前代码中无其他模块解析该日志，风险可控。
3. **方案 B 的预览直读会绕过 CLI 的 `_write_or_base64` 及 mmap 机制**：在 preview 场景下不再产生 base64 字符串和 mmap 文件，减少了 `cache/ipc/` 的磁盘写入和 GUI 的 `json.loads`/`base64.b64decode` 开销。但对 `screenshot` CLI 子命令和 scene analyze 等仍保留原有路径，不影响功能。
4. **帧超时阈值（如 5s）在低性能设备上可能过于激进**：若设备卡顿导致连续 5 秒无帧，可能误触发重建。建议初期设为 8–10s，或做成可配置项。

---

## 5. 总结

"图像传递链接无法正确保活" 的**直接根因**是 `_ScrcpySession` 缺乏 keep-alive 和自动恢复机制，断流后静默死亡且无法重连；**深层根因**是 GUI 预览未采用 README 设计的 scrcpy 直读架构，仍然依赖脆弱的 QProcess/CLI 子进程链路，导致任何底层异常都会被放大为"图像传递链接断开"。
