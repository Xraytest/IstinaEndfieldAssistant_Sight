# README — Usage Guide and Troubleshooting (Consolidated)

> **Consolidated below from** `GUI_CLI_AND_AUTOMATION.md` in full (heading levels uniformly demoted by one).

## Project Documentation Map

| Document | Contents |
|------|------|
| `docs/ARCHITECTURE.md` | Consolidated architecture reference: architecture overview, runtime/device/MaaEnd integration, GUI log categories, LLM and navigation, recognition/pipeline/task system, GUI startup parallel-loading design |
| `docs/README.md` | This document: GUI/CLI usage, task queue troubleshooting, device preview design, issue list |
| `docs/WORKFLOW.md` | Workflow rules (Git commits, four-stage problem analysis) |
| `docs/TASK_LOG.md` | Work log (tasks and modifications recorded by date) |
| `reports/` | One-off analysis/audit/incident reports (organized under audits / incidents / implementation / analysis / reference / archive) |

## How to Run

- GUI: `3rd-part/python/python.exe src/gui/pyqt6/main.py`
- CLI: `3rd-part/python/python.exe scripts/istina.py <subcommand>`
- For environment and entry-point details, see the repository-root `README.md` and `CLAUDE.md`.


---

> **Consolidated below from** `GUI_CLI_AND_AUTOMATION.md` in full (heading levels uniformly demoted by one).
## GUI, CLI, and Task Automation

### 1. Analysis of GUI Task Queue Execution Failures

#### 1.1 Delegation-Chain Execution Path

```
GUI (MaaEndControlPage)
├── _run_queue()                    # click the "Run" button
│   └── _start_execution()
│       └── TaskRunWorker (QThread)
│           └── _runtime_queue_runner()
│               ├── for entry in self._queue_items:
│               │   ├── _sync_execute("preset run {name}")  or
│               │   └── _sync_execute("task run {name} --options {payload}")
│               │       └── QEventLoop waits for the commandFinished signal
│               └── returns True/False
└── _on_execution_finished(success)
    └── _update_execution_ui()
```

Workflow of `_sync_execute()`:
1. Create a `QEventLoop`
2. Connect the `commandFinished` signal to `_on_finished`
3. Call `self._bridge.execute(command, params)` → launch the CLI subprocess
4. `QTimer.singleShot(timeout_ms, loop.quit)` starts the timeout timer
5. `loop.exec()` blocks and waits
6. On receiving the signal or timing out, disconnect and return the result

---

#### 1.2 Five Key Bugs Found

##### Bug 1: Default timeout of 1200ms (P0 — Fixed: now defaults to 300000ms)

**Location**: The `_sync_execute()` default argument was originally `timeout_ms: int = 1200`, now changed to `300000` (`maaend_control_page.py:319`)

**Symptom**:
```python
def _sync_execute(self, command, params=None, timeout_ms=1200):
    ...
    QTimer.singleShot(timeout_ms, loop.quit)  # force-exit after 1.2 seconds
    loop.exec()
```

**Root cause**:
- Task execution (`task run` / `preset run`) usually takes **seconds to minutes**
- A 1.2-second timeout is far too short, so `loop.exec()` times out and exits before the task completes
- It returns `None`, and `_runtime_queue_runner` judges it a failure:
  ```python
  ok = bool(result and result.get("status") == "success")  # result is None → False
  ```
- After the first task in the queue fails, it immediately `return False`, and all subsequent tasks are skipped

**Impact (before fix)**: All task queue executions in the GUI would time out and fail after 1.2 seconds. The default has now been raised to `300000`ms, so this problem no longer occurs.

---

##### Bug 2: Preview timer interferes with task execution (P1 — causes intermittent failures)

**Location**: `_preview_timer` triggers `_refresh_preview()` every 1500ms

**Symptom**:
```python
self._preview_timer = QTimer(self)
self._preview_timer.setInterval(1500)  # 1.5 seconds
self._preview_timer.timeout.connect(self._refresh_preview)

def _refresh_preview(self):
    result = self._sync_execute("screenshot")  # also goes through _sync_execute
    ...
```

**Root cause**:
- During task execution, the preview timer keeps running (started in `showEvent`, stopped in `hideEvent`)
- Each timer trigger calls `_sync_execute("screenshot")`, sending a `screenshot` command to the same CLI process
- The CLI process is single-process; commands in the `_pending_commands` queue are queued up
- If the `screenshot` command cuts in front of the running task command, or competes with it, this can cause:
  - The task command to be delayed
  - The signal matching of `_sync_execute` to be confused (`cmd == expected`)
  - The task to time out or return the wrong result

**Impact**: During task execution, a screenshot request is inserted into the queue every 1.5 seconds, interfering with task execution.

---

##### Bug 3: Preset tasks mislabeled with type in the queue (P2 — dead logic)

**Location**: The `_add_to_queue()` method

**Symptom**:
```python
# When adding a preset
for task_entry in task_list:
    name = task_entry.get("name")
    ...
    entry = {"name": name, "display_name": name, "type": "task", ...}
    #                                                      ^^^^^^^^
    #                                                      hardcoded as "task"

# In _runtime_queue_runner
if item_type == "preset":  # ← never True
    result = self._sync_execute(f"preset run {name}")
else:
    result = self._sync_execute(f"task run {clean_name} --options {payload}")
```

**Root cause**:
- A preset is flattened into multiple task entries, but `type` is hardcoded as `"task"`
- The `item_type == "preset"` branch in `_runtime_queue_runner` is never executed
- If future support is needed to put presets directly in the queue (without flattening), this logic would be problematic

**Impact**: The `preset run` branch is dead code; it does not currently affect functionality (because presets are already flattened).

---

##### Bug 5: `_sync_execute` cross-thread signal connection is unsafe (P3 — edge case)

**Location**: `_sync_execute()` is called on the `TaskRunWorker` thread

**Symptom**:
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

**Root cause**:
- `_sync_execute` is called on the worker thread, but the `commandFinished` signal is emitted on the GUI main thread (`QProcess` runs on the main thread)
- `connect` and `disconnect` operate across different threads; although Qt supports thread-safe connections, if the signal is already emitted before `loop.exec()` starts (extreme case), it may be lost
- `QTimer.singleShot` fires on the current thread (worker thread), but `loop.quit()` must be called on the same thread, which is fine

**Impact**: In extreme cases (the CLI process finishes extremely fast), the signal might be emitted and queued before `loop.exec()` starts; however, due to Qt's event-queue mechanism, it is usually not lost. This is an edge-case issue.

---

### 2. Fix Plan

#### P0 — Must Fix

**1. Use a longer timeout for task execution** — ✅ Fixed

```python
# Current implementation (maaend_control_page.py:319)
# _sync_execute defaults to timeout_ms=300000 (5 minutes); task execution no longer needs a separate timeout
result = self._sync_execute(f"task run {clean_name} --options {payload}")
```

Or, better, distinguish "query" and "execution" timeouts:
```python
_EXECUTE_TIMEOUT_MS = 300000  # 5 minutes
_QUERY_TIMEOUT_MS = 5000      # 5 seconds
_PREVIEW_TIMEOUT_MS = 3000    # 3 seconds
```

**2. Disable the preview timer during task execution**

```python
def _start_execution(self, target):
    self._is_executing = True
    self.stop_preview_timer()  # ← add
    self._update_execution_ui()
    ...

def _on_execution_finished(self, success):
    self._is_executing = False
    self.start_preview_timer()  # ← add
    self._update_execution_ui()
    ...
```

#### P2 — Code Cleanup

**4. Remove dead code or fix the type label**

```python
# In _add_to_queue, a preset is flattened into tasks
entry = {"name": name, "display_name": name, "type": "task", ...}

# Since type is always "task", remove the dead branch in _runtime_queue_runner
# or keep it but add a comment noting it is currently never triggered
```

**5. `_sync_execute` thread-safety improvement**

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

### 3. Root-Cause Summary

The **direct cause** of the GUI task queue failing to execute correctly is that the default timeout of `_sync_execute` (1200ms) is far shorter than the actual task execution time. This causes:
1. Every task times out after 1.2 seconds
2. `_runtime_queue_runner` judges it a failure
3. The queue terminates immediately

The **secondary cause** is that the preview timer (1.5-second interval) keeps sending `screenshot` commands during task execution, interfering with the CLI process's command queue.

Together, these make the task queue in the GUI completely unable to work properly.

> **Current status**: Bug 1 (`_sync_execute` default timeout) has been fixed to `300000`ms at `maaend_control_page.py:319`, and the GUI task queue can now execute normally. Bug 2 (preview-timer interference) still requires pausing the preview during task execution (see §2 P1).

---

### 4. Supplementary Analysis of Device Preview Loading Difficulties

#### 4.1 Call Chain

```
MainWindow._refresh_preview()              # 1500ms timer
  └── MaaEndControlPage._sync_execute("screenshot", timeout_ms=5000)
        └── CLIBridge.execute()            # enqueue into _pending_commands
              └── QProcess starts a brand-new CLI subprocess
                    python src/cli/istina.py screenshot
                      └── CLIDispatch._handle_screenshot
                            └── IstinaRuntime._screenshot()
                                  └── MaaEndRuntime.screenshot(serial)
                                        └── AdbController.post_screencap()
                                              └── mmap returns PNG bytes
```

#### 4.2 Root Causes

| Priority | Root cause | Location | Impact |
|--------|------|------|------|
| **P0** | **Every preview tick starts a brand-new CLI subprocess** | `cli_bridge.py:84-108`, `main_window.py:340` | The 1.5s timer is only a "trigger interval." Each launch of `python src/cli/istina.py` must complete module imports, config hot-reload, `IstinaRuntime` initialization, JSON-RPC/mmap communication, and base64 encode/decode, actually taking about **2-4 seconds**. When `CLIBridge._start_next_process` finds the previous process still running, it discards the new request outright, throttling the effective frame rate down to **3-4 seconds/frame**. |
| **P0** | **`_connected` state is a one-way latch; screenshot failures are not written back** | `maaend_control_page.py:1229`, `main_window.py:336-342` | `_connected` only changes on a successful `system connect` or a manual disconnect. If the device unexpectedly disconnects, ADB fluctuates, or the internal state of `AdbController` is corrupted, the preview keeps erroring while the GUI still shows "connected"; the user sees a blank preview with no prompt whatsoever. |
| **P1** | **Preview requests do not pass serial** | `main_window.py:340` → `handlers.py:261` → `runtime.py:308` | `_sync_execute("screenshot")` carries no serial, so `IstinaRuntime._screenshot` falls back to `last_connected` in the config. If the currently connected device differs from the config, the preview requests the wrong device and silently fails. |
| **P2** | **The underlying MaaFW environment is unstable** | Multiple places in the project docs | `MAAFW_BINARY_PATH` dual-copy conflict (`3rd-part/maaend/agent/maafw/` vs. root-level `maafw/`) and silent failure of `_start_agent()` both cause abnormal behavior of `AdbController` or the screenshot backend, further amplifying the preview failure rate. |

#### 4.3 Key Evidence Code

**`main_window.py:336-342`** — Preview reads `_connected` only, never writes it:
```python
if not self._maaend_page._connected:
    return
result = self._maaend_page._sync_execute("screenshot", timeout_ms=5000)
if not result or result.get("status") != "success":
    return  # silently discarded, does not update _connected, does not prompt the user
```

**`maa_end/runtime.py:545-561`** — Screenshot returns None in many cases:
```python
def screenshot(self, serial=None):
    if not self._connected or self._controller is None:
        return None
    job = self._controller.post_screencap()
    job.wait()
    if not job.succeeded:
        return None
    # ... cv2.imencode may also fail
```

**`cli_bridge.py:84-108`** — Process serialization throttles the preview:
```python
if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
    return  # process still running, new preview request discarded outright
```

#### 4.4 Verification Suggestions

1. **Log at `main_window.py:341`** to confirm whether `result` is `None` or `status != success`, and what the specific `message` is.
2. **Time a full preview tick**: print timestamps in `CLIBridge._start_next_process` and `_on_finished` to verify the actual duration of a single screenshot.
3. **Check the actual value of `MAAFW_BINARY_PATH`**: confirm whether the Python side and the Go service point to the same DLL.
4. **Compare whether `assets/tasks/` and `assets/resource/` in `3rd-part/maaend/` and `MaaEnd/` are in sync** (the project docs have flagged this as a P0 issue).

---

### 5. New Approach to Preview Capture: A Persistent scrcpy Image Channel

#### 5.1 Goal

Replace the inefficient pattern of "starting a brand-new CLI subprocess for a screenshot on every preview tick" with:

- **Establish a channel on connect**: as soon as the device connects, immediately establish a scrcpy video-stream channel and keep decoding
- **Fetch frames on demand**: when the preview timer fires, directly fetch the latest frame from the in-memory cache with zero process overhead
- **Clean up on disconnect**: when the device disconnects, automatically stop the decode thread, close the socket, and release resources

#### 5.2 Architecture Design

```
Device connected successfully
    │
    ▼
AndroidRuntime.start_scrcpy()          # start scrcpy server + tunnel_forward
    │
    ▼
_ScrcpySession._run()                  # background thread continuously decodes H.264/HEVC/AV1
    │
    ▼
get_latest_frame()                     # cache the latest numpy frame (shared memory, thread-safe)
    │
    ▼
_refresh_preview() timer fires         # every 1500ms
    │
    ▼
cv2.imencode(".png", frame)            # encode to PNG bytes on demand
    │
    ▼
base64 → JSON → QPixmap → UI          # send back for rendering
```

#### 5.3 Key Components

**1. Channel establishment: `AndroidRuntime.start_scrcpy()`**

Location: `src/core/capability/device/android_runtime.py:614`

- Establish a `tcp:0 → localabstract:scrcpy` tunnel via ADB forward
- Start the device-side `scrcpy-server.jar` (2.7 protocol, `tunnel_forward=true`)
- Create a `_ScrcpySession` and start the background decode thread
- Raise `TimeoutError` if the first frame is not received within 8 seconds

**2. Continuous keep-alive: `_ScrcpySession._decode_loop()`**

Location: `src/core/capability/device/android_runtime.py:186`

- Loop and read the scrcpy video stream
- Use `av.CodecContext` to keep decoding, avoiding rebuilding the container per frame
- Write each frame into `self._latest_frame` (protected by `threading.Lock`)
- Support the three codecs H.264 / HEVC / AV1

**3. On-demand frame fetch: `_ScrcpySession.get_latest_frame()`**

Location: `src/core/capability/device/android_runtime.py:83`

- Copy the latest frame reference under lock; return `Optional[np.ndarray]`
- Return `None` when there is no frame, so the caller can determine whether the channel is ready

**4. Resource cleanup: `_ScrcpySession.stop()`**

Location: `src/core/capability/device/android_runtime.py:76`

- Set `_stop_event`
- `join` the decode thread (5-second timeout)
- Clean up socket, server proc, and codec

#### 5.4 Comparison with the Old Approach

| Dimension | Old approach (CLI subprocess screenshot) | New approach (persistent scrcpy channel) |
|------|------------------------|------------------------|
| **Preview latency** | 2-4 seconds/frame (subprocess overhead) | <100ms (in-memory frame fetch) |
| **CPU/memory** | High peak per tick; process repeatedly created/destroyed | Steady background thread; small memory increment |
| **Device load** | Each screencap triggers one ADB screenshot | scrcpy keeps streaming; the device-side server stays resident |
| **Failure mode** | Silently discarded; user unaware | Channel disconnection is detectable; can auto-reconnect |
| **Implementation complexity** | Low (existing CLI routing) | Medium (must manage the session lifecycle) |

#### 5.5 Implementation Points

**A. Start the channel immediately after a successful connection**

After `MaaEndRuntime.connect()` succeeds (`_connected = True`), call:
```python
self._controller.post_screencap()  # keep one native MaaFW validation
# also start the persistent scrcpy channel
android = runtime.android()
android.start_scrcpy(serial=serial)
```

**B. Change the preview timer to in-memory frame fetching**

Change `MainWindow._refresh_preview()` to call the Python-side API directly:

```python
def _refresh_preview(self):
    if self._preview_label is None:
        return
    if not self._maaend_page._connected:
        return
    if self._maaend_page._is_executing:
        return
    
    android = self._maaend_page.runtime().android()
    frame = android.get_latest_frame()  # fetch on demand, zero subprocess
    
    if frame is None:
        self._preview_label.setText(locale.tr("preview_empty", "No preview"))
        return
    
    _, buf = cv2.imencode(".png", frame)
    pixmap = QPixmap()
    if pixmap.loadFromData(buf.tobytes()):
        scaled = pixmap.scaled(...)
        self._preview_label.setPixmap(scaled)
```

**C. Sync channel state with connection state**

- When `_connected = True`, the scrcpy channel must be running
- If `get_latest_frame()` keeps returning `None` for more than N seconds, automatically flag the channel as abnormal
- On device disconnect (ADB disconnect, app crash), `_ScrcpySession`'s `_decode_loop` throws an exception and cleans up

**D. Multi-device scenarios**

- Each serial corresponds to an independent `_ScrcpySession` (there is already a `_clients` singleton cache)
- When `MainWindow` switches pages or receives a `system connect` signal, fetch frames by the current serial
- If the serial changes, the old channel automatically remains in the old `AndroidRuntime` instance and does not interfere with the new device

**E. Cooperation with MaaFW**

- The scrcpy channel is used for preview only; it does not replace MaaFW's `AdbController.post_screencap()`
- Task execution still uses MaaFW native screenshots (to guarantee pipeline recognition consistency)
- Preview and task execution can run in parallel: scrcpy streams on a background thread, while MaaFW takes screenshots on demand on the task thread

#### 5.6 Fallback Strategy

If scrcpy fails to start (jar push failure, port conflict, unsupported codec), it should automatically fall back to the old approach:

```python
try:
    android.start_scrcpy(serial=serial)
    self._use_scrcpy_preview = True
except Exception:
    self._use_scrcpy_preview = False
    self._append_log("System", "scrcpy preview channel failed to start; falling back to ADB screenshot")
```

This gradually validates the stability of the new approach without affecting task execution.

---

### 6. CLI & GUI Layer Issues

#### 6.1 High

1. **Wrong option-merge order (4 places)**
   `saved` overrides the current UI/queue value, but the UI value should win.
   - `_run_task` `:1321-1322`
   - `_add_to_queue` preset `:788-795`
   - `_add_to_queue` task `:805-808`
   - `_runtime_queue_runner` `:870-874`
   **Fix**: `options = dict(saved) if saved else {}; options.update(ui_options)`.

#### 6.2 Medium

4. **`self._queue_items` cache is fragile**
   Many places read the cache instead of `queue_state.queue_items`.
   **Fix**: uniformly use `queue_state.queue_items`.

5. **`_load_state()` dead method** — ✅ Fixed (removed)
   The `_load_state()` originally defined at `maaend_control_page.py:1161-1204` has been completely removed; 0 references across the entire codebase.

#### 6.3 Low

6. **CLI `--timeout` silently discarded**
   `handlers.py:283` passes in `timeout`, but neither `_run_task` nor `MaaEndRuntime.run_task` accepts it.
   **Fix**: remove the argument or implement the timeout.

7. **`_sync_execute`'s `isinstance(params, int)` dead code**
   `maaend_control_page.py:363-366`.
   **Fix**: delete.

8. **`_build_args` JSON-argument path unused by the GUI**
   `cli_bridge.py:71-80`.
   **Fix**: delete or document.

9. **`scene nav` alias is confusing**
   `handlers.py:424-426` maps to `nav.to`.
   **Fix**: keep as-is but add a comment.

---

### 7. Cross-Module Call-Chain Review (Summary)

#### 7.1 Runtime → MaaEnd → Device

| Call chain | Status | Notes |
|--------|------|------|
| `IstinaRuntime.maaend()` → `MaaEndRuntime` | ✅ | Structure correct |
| `IstinaRuntime.android()` → `AndroidRuntimeProxy` → `AndroidRuntime` → `_Daemon` | ✅ | `_Daemon._dispatch()` now uniformly uses `params.get("serial", self._serial)` |
| `IstinaRuntime.disconnect()` → `MaaEndRuntime.disconnect()` | ✅ | `disconnect()` now calls `_cleanup_partial()` to terminate the agent process |

#### 7.2 Scene → Recognizer → Backends

| Call chain | Status | Notes |
|--------|------|------|
| `SceneUnderstandingService.identify()` → `EndfieldElementRecognizer.recognize()` | ✅ | |
| `EndfieldElementRecognizer` → `TemplateBackend/OCRBackend/ColorBackend/YOLOBackend` | ✅ | |
| `EndfieldElementRecognizer` → `PipelineRunner` (via TemplateBackend) | ⚠️ | MaaFW injection is only in TemplateBackend; the TaskRunner path is missing (see High #2) |

#### 7.3 CLI/GUI → Runtime

| Call chain | Status | Notes |
|--------|------|------|
| `CLIDispatch.dispatch()` → `runtime.execute()` | ✅ | All 21 branches mapped |
| `MaaEndControlPage._sync_execute()` → `CLIBridge.execute()` | ✅ | Dead code exists (see Low #7) |
| GUI option serialization → Runtime options | ⚠️ | Wrong merge order (see High #2) |

#### 7.4 LLM & Navigation

| Call chain | Status | Notes |
|--------|------|------|
| `LlamaServerRuntime` → `llama-server` process | ✅ | Deadlock risk (see Medium #4) |
| `LlmClient.chat()` → `/v1/chat/completions` | ✅ | `health_check()` endpoint bug (see High #1) |
| `Navigator.to_coords_vlm()` → `VlmWalkNavigator` | ✅ | Inconsistent `level_id` fallback (see Medium #5) |
| `_vlm_keyevent()` → `AndroidRuntimeProxy.keyevent()` | ✅ | Signature matches |

---

### 8. Fix-Priority Recommendations

#### P0 — Fix Immediately
- [x] Raise `_sync_execute` default timeout to 300000ms (task execution) / 5000ms (query)
- [ ] GUI option-merge order: `options = dict(saved) or {}; options.update(current)`

#### P1 — This Iteration
- [ ] Keep the preview timer always running; refresh immediately after a successful connection

#### P2 — Later Cleanup
- [x] Clean up `_load_state` dead code (removed)
- [ ] `_sync_execute` thread-safety improvement
- [ ] Clean up dead code such as `isinstance(params, int)` and the `_build_args` JSON path
- [ ] Add a comment for the `scene nav` alias
