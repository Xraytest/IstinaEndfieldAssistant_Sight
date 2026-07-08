# GUI、CLI 与任务自动化

## 1. GUI 任务队列执行失败分析

### 1.1 委托链执行路径

```
GUI (MaaEndControlPage)
├── _run_queue()                    # 点击"运行"按钮
│   └── _start_execution()
│       └── TaskRunWorker (QThread)
│           └── _runtime_queue_runner()
│               ├── for entry in self._queue_items:
│               │   ├── _sync_execute("preset run {name}")  或
│               │   └── _sync_execute("task run {name} --options {payload}")
│               │       └── QEventLoop 等待 commandFinished 信号
│               └── 返回 True/False
└── _on_execution_finished(success)
    └── _update_execution_ui()
```

`_sync_execute()` 的工作流程：
1. 创建 `QEventLoop`
2. 连接 `commandFinished` 信号到 `_on_finished`
3. 调用 `self._bridge.execute(command, params)` → 启动 CLI 子进程
4. `QTimer.singleShot(timeout_ms, loop.quit)` 启动超时定时器
5. `loop.exec()` 阻塞等待
6. 收到信号或超时后，断开连接，返回结果

---

### 1.2 发现的 5 个关键错误

#### 错误 1：默认超时 1200ms（P0 — 直接导致任务全部失败）

**位置**：`_sync_execute()` 默认参数 `timeout_ms: int = 1200`

**现象**：
```python
def _sync_execute(self, command, params=None, timeout_ms=1200):
    ...
    QTimer.singleShot(timeout_ms, loop.quit)  # 1.2 秒后强制退出
    loop.exec()
```

**根本原因**：
- 任务执行（`task run` / `preset run`）通常需要 **数秒到数分钟**
- 1.2 秒超时远远不够，导致 `loop.exec()` 在任务完成前就超时退出
- 返回 `None`，`_runtime_queue_runner` 判定为失败：
  ```python
  ok = bool(result and result.get("status") == "success")  # result 是 None → False
  ```
- 队列中第一个任务失败后立即 `return False`，后续任务全部跳过

**影响**：GUI 中所有任务队列执行都会在 1.2 秒后超时失败，无论任务实际是否成功。

---

#### 错误 2：预览定时器干扰任务执行（P1 — 导致间歇性失败）

**位置**：`_preview_timer` 每 1500ms 触发 `_refresh_preview()`

**现象**：
```python
self._preview_timer = QTimer(self)
self._preview_timer.setInterval(1500)  # 1.5 秒
self._preview_timer.timeout.connect(self._refresh_preview)

def _refresh_preview(self):
    result = self._sync_execute("screenshot")  # 也会走 _sync_execute
    ...
```

**根本原因**：
- 任务执行期间，预览定时器仍在运行（`showEvent` 启动，`hideEvent` 停止）
- 每次定时器触发都会调用 `_sync_execute("screenshot")`，发送 `screenshot` 命令到同一个 CLI 进程
- CLI 进程是单进程的，`_pending_commands` 队列中的命令会排队
- 如果 `screenshot` 命令插队到正在执行的任务命令之前，或者与任务命令竞争，会导致：
  - 任务命令被延迟
  - `_sync_execute` 的信号匹配混乱（`cmd == expected`）
  - 任务超时或返回错误的结果

**影响**：任务执行期间，每 1.5 秒就会有一次截图请求插入队列，干扰任务执行。

---

#### 错误 3：预设任务在队列中 type 标记错误（P2 — 逻辑死代码）

**位置**：`_add_to_queue()` 方法

**现象**：
```python
# 当添加预设时
for task_entry in task_list:
    name = task_entry.get("name")
    ...
    entry = {"name": name, "display_name": name, "type": "task", ...}
    #                                                      ^^^^^^^^
    #                                                      硬编码为 "task"

# 在 _runtime_queue_runner 中
if item_type == "preset":  # ← 永远不会为 True
    result = self._sync_execute(f"preset run {name}")
else:
    result = self._sync_execute(f"task run {clean_name} --options {payload}")
```

**根本原因**：
- 预设被展平为多个任务 entry，但 `type` 被硬编码为 `"task"`
- `_runtime_queue_runner` 中的 `item_type == "preset"` 分支永远不会执行
- 如果将来需要支持队列中直接放预设（不展平），这个逻辑会有问题

**影响**：`preset run` 分支是死代码，虽然当前不影响功能（因为预设已经被展平）。

---

#### 错误 5：`_sync_execute` 跨线程信号连接不安全（P3 — 边界条件）

**位置**：`_sync_execute()` 在 `TaskRunWorker` 线程中调用

**现象**：
```python
def _sync_execute(self, command, ...):
    loop = QEventLoop()
    def _on_finished(cmd, res):
        if cmd == expected:
            result = res
            loop.quit()
    self._bridge.commandFinished.connect(_on_finished)
    self._bridge.execute(expected, params or {})
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    self._bridge.commandFinished.disconnect(_on_finished)
```

**根本原因**：
- `_sync_execute` 在 worker 线程中调用，但 `commandFinished` 信号是在 GUI 主线程发射的（`QProcess` 在主线程）
- `connect` 和 `disconnect` 在不同线程中操作，虽然 Qt 支持线程安全的连接，但在 `loop.exec()` 启动之前，如果信号已经发射（极端情况），可能会丢失
- `QTimer.singleShot` 在当前线程（worker 线程）中触发，但 `loop.quit()` 需要在同一个线程中调用，这没有问题

**影响**：在极端情况下（CLI 进程极快完成），信号可能在 `loop.exec()` 启动前就已经发射并被排队，但由于 Qt 的事件队列机制，通常不会丢失。这是一个边界条件问题。

---

## 2. 修复方案

### P0 — 必须修复

**1. 为任务执行使用更长的超时时间**

```python
# 当前代码
result = self._sync_execute(f"task run {clean_name} --options {payload}")  # 1.2s 超时

# 修复后
result = self._sync_execute(f"task run {clean_name} --options {payload}", timeout_ms=300000)  # 5 分钟
```

或者更好的方式：区分"查询"和"执行"的超时：
```python
_EXECUTE_TIMEOUT_MS = 300000  # 5 分钟
_QUERY_TIMEOUT_MS = 5000      # 5 秒
_PREVIEW_TIMEOUT_MS = 3000    # 3 秒
```

**2. 任务执行期间禁用预览定时器**

```python
def _start_execution(self, target):
    self._is_executing = True
    self.stop_preview_timer()  # ← 添加
    self._update_execution_ui()
    ...

def _on_execution_finished(self, success):
    self._is_executing = False
    self.start_preview_timer()  # ← 添加
    self._update_execution_ui()
    ...
```

### P2 — 代码清理

**4. 移除死代码或修复 type 标记**

```python
# 在 _add_to_queue 中，预设展平为任务
entry = {"name": name, "display_name": name, "type": "task", ...}

# 由于 type 总是 "task"，移除 _runtime_queue_runner 中的 dead branch
# 或者保留但添加注释说明当前不会触发
```

**5. `_sync_execute` 线程安全改进**

```python
def _sync_execute(self, command, params=None, timeout_ms=1200):
    loop = QEventLoop()
    result = None
    expected = command

    def _on_finished(cmd, res):
        nonlocal result
        if cmd == expected:
            result = res
            if loop.isRunning():
                loop.quit()

    self._bridge.commandFinished.connect(_on_finished)
    self._bridge.execute(expected, params or {})
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    self._bridge.commandFinished.disconnect(_on_finished)
    return result
```

---

## 3. 根因总结

GUI 任务队列无法正确执行的**直接原因**是 `_sync_execute` 的默认超时时间（1200ms）远小于任务实际执行时间。这导致：
1. 每个任务都在 1.2 秒后超时
2. `_runtime_queue_runner` 判定为失败
3. 队列立即终止

**次要原因**是预览定时器（1.5 秒间隔）在任务执行期间持续发送 `screenshot` 命令，干扰 CLI 进程的命令队列。

这两者共同导致 GUI 中任务队列完全无法正常工作。

---

## 4. 设备预览难以加载的补充分析

### 4.1 调用链

```
MainWindow._refresh_preview()              # 1500ms 定时器
  └── MaaEndControlPage._sync_execute("screenshot", timeout_ms=5000)
        └── CLIBridge.execute()            # 入队 _pending_commands
              └── QProcess 启动全新 CLI 子进程
                    python src/cli/istina.py screenshot
                      └── CLIDispatch._handle_screenshot
                            └── IstinaRuntime._screenshot()
                                  └── MaaEndRuntime.screenshot(serial)
                                        └── AdbController.post_screencap()
                                              └── mmap 返回 PNG bytes
```

### 4.2 根因

| 优先级 | 根因 | 位置 | 影响 |
|--------|------|------|------|
| **P0** | **每次预览 tick 都启动全新 CLI 子进程** | `cli_bridge.py:84-108`、`main_window.py:340` | 1.5s 定时器只是“触发间隔”。每次启动 `python src/cli/istina.py` 要完成模块导入、配置热加载、`IstinaRuntime` 初始化、JSON-RPC/mmap 通信、base64 编解码，实际耗时约 **2-4 秒**。`CLIBridge._start_next_process` 发现上一进程仍在运行时会直接丢弃新请求，导致有效帧率被压制到 **3-4 秒/帧**。 |
| **P0** | **`_connected` 状态为单向闩锁，截图失败不反写** | `maaend_control_page.py:1229`、`main_window.py:336-342` | `_connected` 仅在 `system connect` 成功或手动断开时变更。若设备意外断开、ADB 波动、或 `AdbController` 内部状态损坏，预览持续报错但 GUI 仍显示“已连接”，用户看到空白预览且无任何提示。 |
| **P1** | **预览请求未传递 serial** | `main_window.py:340` → `handlers.py:261` → `runtime.py:308` | `_sync_execute("screenshot")` 不携带 serial，`IstinaRuntime._screenshot` 回退到配置中的 `last_connected`。若当前连接设备与配置不一致，预览会请求到错误设备并静默失败。 |
| **P2** | **底层 MaaFW 环境不稳定** | 项目文档多处 | `MAAFW_BINARY_PATH` 双副本冲突（`3rd-part/maaend/agent/maafw/` vs 根目录 `maafw/`）、`_start_agent()` 静默失败，都会导致 `AdbController` 或截图后端行为异常，进一步放大预览失败率。 |

### 4.3 关键证据代码

**`main_window.py:336-342`** — 预览只读 `_connected`，不写：
```python
if not self._maaend_page._connected:
    return
result = self._maaend_page._sync_execute("screenshot", timeout_ms=5000)
if not result or result.get("status") != "success":
    return  # 静默丢弃，不更新 _connected，不提示用户
```

**`maa_end/runtime.py:545-561`** — 截图大量返回 None：
```python
def screenshot(self, serial=None):
    if not self._connected or self._controller is None:
        return None
    job = self._controller.post_screencap()
    job.wait()
    if not job.succeeded:
        return None
    # ... cv2.imencode 也可能失败
```

**`cli_bridge.py:84-108`** — 进程串行化导致预览被节流：
```python
if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
    return  # 进程仍在运行，新预览请求直接丢弃
```

### 4.4 验证建议

1. **在 `main_window.py:341` 处打日志**，确认 `result` 是否为 `None` 或 `status != success`，以及具体 `message` 是什么。
2. **计时一次完整预览 tick**：在 `CLIBridge._start_next_process` 和 `_on_finished` 中打印时间戳，验证单次截图实际耗时。
3. **检查 `MAAFW_BINARY_PATH` 实际值**：确认 Python 侧与 Go service 是否指向同一份 DLL。
4. **对比 `3rd-part/maaend/` 与 `MaaEnd/` 的 `assets/tasks/` 与 `assets/resource/` 是否同步**（项目文档已指出这是 P0 问题）。

---

## 5. 预览画面获取新方案：scrcpy 常驻图像通道

### 5.1 目标

取代“每次预览 tick 启动全新 CLI 子进程截图”的低效模式，改为：

- **连接即建通道**：设备连接成功后，立即建立 scrcpy 视频流通道并持续解码
- **按需取帧**：预览定时器触发时直接从内存缓存取最新帧，零进程开销
- **断开即清理**：设备断开时自动停止解码线程、关闭 socket、释放资源

### 5.2 架构设计

```
设备连接成功
    │
    ▼
AndroidRuntime.start_scrcpy()          # 启动 scrcpy server + tunnel_forward
    │
    ▼
_ScrcpySession._run()                  # 后台线程持续解码 H.264/HEVC/AV1
    │
    ▼
get_latest_frame()                     # 缓存最新 numpy 帧（内存共享，线程安全）
    │
    ▼
_refresh_preview() 定时器触发          # 每 1500ms
    │
    ▼
cv2.imencode(".png", frame)            # 按需编码为 PNG bytes
    │
    ▼
base64 → JSON → QPixmap → UI          # 回传渲染
```

### 5.3 关键组件

**1. 通道建立：`AndroidRuntime.start_scrcpy()`**

位置：`src/core/capability/device/android_runtime.py:614`

- 通过 ADB forward 建立 `tcp:0 → localabstract:scrcpy` 隧道
- 启动设备端 `scrcpy-server.jar`（2.7 协议，`tunnel_forward=true`）
- 创建 `_ScrcpySession` 并启动后台解码线程
- 8 秒内收不到首帧抛出 `TimeoutError`

**2. 持续保活：`_ScrcpySession._decode_loop()`**

位置：`src/core/capability/device/android_runtime.py:186`

- 循环读取 scrcpy 视频流
- 使用 `av.CodecContext` 持续解码，避免每帧重建容器
- 每帧写入 `self._latest_frame`（`threading.Lock` 保护）
- 支持 H.264 / HEVC / AV1 三种 codec

**3. 按需取帧：`_ScrcpySession.get_latest_frame()`**

位置：`src/core/capability/device/android_runtime.py:83`

- 加锁拷贝最新帧引用，返回 `Optional[np.ndarray]`
- 无帧时返回 `None`，调用方可据此判断通道是否就绪

**4. 资源清理：`_ScrcpySession.stop()`**

位置：`src/core/capability/device/android_runtime.py:76`

- 设置 `_stop_event`
- `join` 解码线程（5 秒超时）
- 清理 socket、server proc、codec

### 5.4 与旧方案对比

| 维度 | 旧方案（CLI 子进程截图） | 新方案（scrcpy 常驻通道） |
|------|------------------------|------------------------|
| **预览延迟** | 2-4 秒/帧（子进程开销） | <100ms（内存取帧） |
| **CPU/内存** | 每 tick 峰值高，进程反复创建销毁 | 稳定后台线程，内存增量小 |
| **设备负载** | 每次 screencap 触发一次 ADB 截图 | scrcpy 持续推流，设备端 server 常驻 |
| **失败模式** | 静默丢弃，用户无感知 | 通道断开可检测，可自动重连 |
| **实现复杂度** | 低（现有 CLI 路由） | 中（需管理 session 生命周期） |

### 5.5 实施要点

**A. 连接成功后立即启动通道**

在 `MaaEndRuntime.connect()` 成功（`_connected = True`）后，调用：
```python
self._controller.post_screencap()  # 保留一次 MaaFW 原生校验
# 同时启动 scrcpy 常驻通道
android = runtime.android()
android.start_scrcpy(serial=serial)
```

**B. 预览定时器改为内存取帧**

`MainWindow._refresh_preview()` 改为直接调用 Python 侧 API：

```python
def _refresh_preview(self):
    if self._preview_label is None:
        return
    if not self._maaend_page._connected:
        return
    if self._maaend_page._is_executing:
        return
    
    android = self._maaend_page.runtime().android()
    frame = android.get_latest_frame()  # 按需取帧，零子进程
    
    if frame is None:
        self._preview_label.setText(locale.tr("preview_empty", "No preview"))
        return
    
    _, buf = cv2.imencode(".png", frame)
    pixmap = QPixmap()
    if pixmap.loadFromData(buf.tobytes()):
        scaled = pixmap.scaled(...)
        self._preview_label.setPixmap(scaled)
```

**C. 通道状态与连接状态同步**

- `_connected = True` 时，scrcpy 通道必须处于运行状态
- 若 `get_latest_frame()` 持续返回 `None` 超过 N 秒，自动标记通道异常
- 设备断开（ADB 断开、应用崩溃）时，`_ScrcpySession` 的 `_decode_loop` 会抛出异常并清理

**D. 多设备场景**

- 每个 serial 对应独立的 `_ScrcpySession`（已有 `_clients` 单例缓存）
- `MainWindow` 切换页面或收到 `system connect` 信号时，按当前 serial 取帧
- 若 serial 变更，旧通道自动保留在旧 `AndroidRuntime` 实例中，不干扰新设备

**E. 与 MaaFW 的协作**

- scrcpy 通道仅用于预览，不替代 MaaFW 的 `AdbController.post_screencap()`
- 任务执行仍走 MaaFW 原生截图（保证 pipeline 识别一致性）
- 预览与任务执行可并行：scrcpy 推流在后台线程，MaaFW 在任务线程按需截图

### 5.6 回退策略

若 scrcpy 启动失败（jar 推送失败、端口冲突、codec 不支持），应自动回退到旧方案：

```python
try:
    android.start_scrcpy(serial=serial)
    self._use_scrcpy_preview = True
except Exception:
    self._use_scrcpy_preview = False
    self._append_log("系统", "scrcpy 预览通道启动失败，回退到 ADB 截图")
```

这样在不影响任务执行的前提下，逐步验证新方案的稳定性。

---

## 6. CLI & GUI 层问题

### 6.1 High

1. **选项合并顺序错误（4 处）**
   `saved` 覆盖当前 UI/队列值，应为 UI 值稳赢。
   - `_run_task` `:1321-1322`
   - `_add_to_queue` preset `:788-795`
   - `_add_to_queue` task `:805-808`
   - `_runtime_queue_runner` `:870-874`
   **修复**：`options = dict(saved) if saved else {}; options.update(ui_options)`。

### 6.2 Medium

4. **`self._queue_items` 缓存脆弱**
   多处读取缓存而非 `queue_state.queue_items`。
   **修复**：统一使用 `queue_state.queue_items`。

5. **`_load_state()` 死方法**
   `maaend_control_page.py:1161-1204` 定义了但从未调用。
   **修复**：删除。

### 6.3 Low

6. **CLI `--timeout` 静默丢弃**
   `handlers.py:283` 传入 `timeout`，但 `_run_task` 与 `MaaEndRuntime.run_task` 均不接受。
   **修复**：移除参数或实现超时。

7. **`_sync_execute` 的 `isinstance(params, int)` 死代码**
   `maaend_control_page.py:363-366`。
   **修复**：删除。

8. **`_build_args` JSON 参数路径未被 GUI 使用**
   `cli_bridge.py:71-80`。
   **修复**：删除或文档说明。

9. **`scene nav` 别名易混淆**
   `handlers.py:424-426` 映射到 `nav.to`。
   **修复**：保持现状但补充注释。

---

## 7. 跨模块调用链检查（汇总）

### 7.1 Runtime → MaaEnd → Device

| 调用链 | 状态 | 备注 |
|--------|------|------|
| `IstinaRuntime.maaend()` → `MaaEndRuntime` | ✅ | 结构正确 |
| `IstinaRuntime.android()` → `AndroidRuntimeProxy` → `AndroidRuntime` → `_Daemon` | ✅ | `_Daemon._dispatch()` 已统一使用 `params.get("serial", self._serial)` |
| `IstinaRuntime.disconnect()` → `MaaEndRuntime.disconnect()` | ✅ | `disconnect()` 已调用 `_cleanup_partial()` 终止 agent 进程 |

### 7.2 Scene → Recognizer → Backends

| 调用链 | 状态 | 备注 |
|--------|------|------|
| `SceneUnderstandingService.identify()` → `EndfieldElementRecognizer.recognize()` | ✅ | |
| `EndfieldElementRecognizer` → `TemplateBackend/OCRBackend/ColorBackend/YOLOBackend` | ✅ | |
| `EndfieldElementRecognizer` → `PipelineRunner` (via TemplateBackend) | ⚠️ | MaaFW 注入仅在 TemplateBackend 中，TaskRunner 路径缺失（见 High #2） |

### 7.3 CLI/GUI → Runtime

| 调用链 | 状态 | 备注 |
|--------|------|------|
| `CLIDispatch.dispatch()` → `runtime.execute()` | ✅ | 19 个分支全部映射 |
| `MaaEndControlPage._sync_execute()` → `CLIBridge.execute()` | ✅ | 存在死代码（见 Low #7） |
| GUI 选项序列化 → Runtime options | ⚠️ | 合并顺序错误（见 High #2） |

### 7.4 LLM & Navigation

| 调用链 | 状态 | 备注 |
|--------|------|------|
| `LlamaServerRuntime` → `llama-server` 进程 | ✅ | 死锁风险（见 Medium #4） |
| `LlmClient.chat()` → `/v1/chat/completions` | ✅ | `health_check()` 端点错误（见 High #1） |
| `Navigator.to_coords_vlm()` → `VlmWalkNavigator` | ✅ | `level_id` 回退不一致（见 Medium #5） |
| `_vlm_keyevent()` → `AndroidRuntimeProxy.keyevent()` | ✅ | 签名匹配 |

---

## 8. 修复优先级建议

### P0 — 立即修复
- [ ] `_sync_execute` 默认超时提升至 300000ms（任务执行）/ 5000ms（查询）
- [ ] GUI 选项合并顺序：`options = dict(saved) or {}; options.update(current)`

### P1 — 本次迭代
- [ ] 预览定时器始终运行，连接成功后立即刷新

### P2 — 后续清理
- [ ] `_sync_execute` 线程安全改进
- [ ] `_load_state`、`isinstance(params, int)`、`_build_args` JSON 路径等死代码清理
- [ ] `scene nav` 别名补充注释
