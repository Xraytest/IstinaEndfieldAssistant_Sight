# ARCHITECTURE — Consolidated Architecture Reference

> This file is consolidated from the following source documents (heading levels uniformly demoted by one; no content removed):
> `ARCHITECTURE.md`, `RUNTIME_DEVICE_AND_MAAEND.md`, `GUI_LOG_CATEGORIES.md`, `LLM_AND_NAVIGATION.md`, `RECOGNITION_PIPELINE_AND_TASKS.md`, `superpowers/specs/2026-07-09-gui-parallel-startup-design.md`


---

> **Consolidated below from** `ARCHITECTURE.md`

## 1. Project Overview

IstinaEndfieldAssistant (IEA) is an automation assistant for *Arknights: Endfield*, built on top of MaaEnd/MaaFramework.

Core capabilities:

- **Scene recognition**: template matching, OCR, color detection, YOLO object detection
- **Task automation**: pipeline task system, preset queues
- **Intelligent navigation**: VLM visual navigation, coordinate navigation
- **Device management**: ADB connection, scrcpy preview, multi-device support
- **LLM integration**: local llama-server, scene understanding, decision support

## 2. Directory Structure

```
src/
├── core/                  # core business logic
│   ├── capability/        # capability layer (device, recognition, navigation, LLM)
│   ├── service/           # service layer (scene understanding, task scheduling)
│   └── runtime/           # runtime (IstinaRuntime facade)
├── cli/                   # CLI entry point and command dispatch
├── gui/                   # GUI (PyQt6)
└── infra/                 # infrastructure (config, logging, i18n)
```

## 3. Core Architecture Layers

(The subsequent content of the original document is preserved)

See the consolidated topic sections below for details.

---

> **Consolidated below from** `RUNTIME_DEVICE_AND_MAAEND.md`

## Runtime, Device, and MaaEnd Integration

This document consolidates the architecture and implementation details of the IEA runtime facade, the device capability layer (Android/ADB/scrcpy), and the MaaEnd/MaaFramework integration.

### 1. The IstinaRuntime Facade

`IstinaRuntime` (`src/core/runtime/istina_runtime.py`) is the system's unified entry facade, aggregating all capabilities and services.

```python
class IstinaRuntime:
    def __init__(self, config_path=None):
        self._config = load_config(config_path)
        self._maaend = None      # lazily loaded MaaEndRuntime
        self._android = None     # lazily loaded AndroidRuntime
        self._llm = None         # lazily loaded LlmClient
        self._scene = None       # lazily loaded SceneUnderstandingService
```

Key design points:

- **Lazy loading**: each capability/service is initialized on demand, avoiding loading everything at startup
- **Singleton caching**: each capability/service is created and cached on first access
- **Config-driven**: all paths and parameters are read from `config/` JSON files

### 2. Device Capability Layer

#### 2.1 AndroidRuntime

`AndroidRuntime` (`src/core/capability/device/android_runtime.py`) wraps ADB and scrcpy operations.

```python
class AndroidRuntime:
    def __init__(self, serial=None):
        self._serial = serial
        self._daemon = None
        self._scrcpy_session = None
```

Core methods:

| Method | Function |
|------|------|
| `connect(serial)` | establish an ADB connection |
| `screenshot()` | ADB screenshot |
| `start_scrcpy()` | start the scrcpy video stream |
| `get_latest_frame()` | get the latest frame |
| `keyevent(code)` | send a key event |
| `input_swipe(...)` | swipe operation |

#### 2.2 The scrcpy Preview Channel

The scrcpy channel provides high-frame-rate device preview, replacing the inefficient ADB screenshot polling. See "GUI Startup Parallel-Loading Design" below and the dedicated analysis for details.

### 3. MaaEnd/MaaFramework Integration

#### 3.1 MaaEndRuntime

`MaaEndRuntime` (`src/core/service/maa_end/runtime.py`) wraps the MaaEnd/MaaFramework calls.

```python
class MaaEndRuntime:
    def __init__(self, config):
        self._config = config
        self._resource = None    # MaaFW Resource
        self._controller = None  # AdbController
        self._tasker = None      # Tasker
```

#### 3.2 Resource Loading

MaaFW resources are loaded from `3rd-part/maaend/`:

```
3rd-part/maaend/
├── MaaEnd.exe
├── agent/                 # Python agent (custom recognition/actions)
├── maafw/                 # MaaFramework runtime (DLL + Python bindings)
├── resource*/             # recognition resources (templates, OCR models, pipeline JSON)
├── tasks/                 # task definitions
└── interface.json         # interface definition (flat layout)
```

#### 3.3 Key Integration Points

- **Resource loading**: `resource.post_bundle(path)` loads recognition resources
- **Controller binding**: `AdbController(adb_path, serial, screencap_method, input_method)`
- **Tasker execution**: `tasker.post_task(entry, param)` executes a pipeline task
- **Agent communication**: the Python agent communicates with MaaFW over a socket, providing custom recognition/actions

### 4. Runtime Initialization Flow

```
IstinaRuntime()
    │
    ├── load_config()               # load config/*.json
    │
    ├── maaend()                    # triggered on first access
    │   └── MaaEndRuntime(config)
    │       ├── _init_resource()    # load resource bundle
    │       ├── _init_controller()  # bind the ADB device
    │       ├── _start_agent()      # start the Python agent process
    │       └── _init_tasker()      # create the Tasker
    │
    └── android()                   # triggered on first access
        └── AndroidRuntime(serial)
```

### 5. Known Issues and Caveats

| Issue | Location | Notes |
|------|------|------|
| MAAFW_BINARY_PATH dual-copy conflict | `3rd-part/maaend/agent/maafw/` vs. root-level `maafw/` | May load the wrong DLL |
| `_start_agent()` silent failure | `runtime.py` | Agent startup failure does not raise, making custom recognition unavailable |
| Screenshot returns None | `runtime.py:545-561` | Several failure paths all return None, making it hard for the caller to distinguish the cause |

---

> **Consolidated below from** `GUI_LOG_CATEGORIES.md`

## GUI Log Categories

### 1. Log Categorization System

The IEA GUI's logging system splits logs into multiple categories to make filtering and troubleshooting easier for users.

### 2. Log Categories

| Category | Tag | Purpose |
|------|------|------|
| System | `系统` | System-level events (startup, connect, disconnect) |
| Task | `任务` | Task execution status |
| Recognition | `识别` | Scene recognition results |
| Navigation | `导航` | Navigation decisions and movement |
| LLM | `LLM` | LLM calls and responses |
| Error | `错误` | Errors and exceptions |

### 3. Log Levels

| Level | Purpose |
|------|------|
| DEBUG | Debug information |
| INFO | General information |
| WARNING | Warnings |
| ERROR | Errors |

### 4. Logging Implementation

Logging is implemented via the `src/infra/logging/` module; on the GUI side it is displayed in real time through the signal-slot mechanism.

---

> **Consolidated below from** `LLM_AND_NAVIGATION.md`

## LLM and Navigation

This document consolidates the architecture and tuning guide for LLM integration and visual navigation.

### 1. LLM Integration

#### 1.1 LlamaServerRuntime

`LlamaServerRuntime` (`src/core/capability/llm/llama_server.py`) manages the local `llama-server` process.

```python
class LlamaServerRuntime:
    def __init__(self, config):
        self._config = config
        self._process = None
        self._base_url = None
```

Key methods:

- `start()`: start the `llama-server` subprocess
- `stop()`: terminate the process
- `health_check()`: check the service health status

#### 1.2 LlmClient

`LlmClient` (`src/core/capability/llm/client.py`) wraps the LLM API calls.

```python
class LlmClient:
    def chat(self, messages, **kwargs):
        # POST /v1/chat/completions
        ...
```

### 2. Visual Navigation

#### 2.1 Navigator

`Navigator` (`src/core/capability/navigation/navigator.py`) provides multiple navigation strategies.

| Method | Strategy |
|------|------|
| `to_coords()` | coordinate navigation |
| `to_coords_vlm()` | VLM visual navigation |
| `to_scene()` | scene navigation |

#### 2.2 VlmWalkNavigator

`VlmWalkNavigator` (`src/core/capability/navigation/vlm_walk.py`) uses a VLM for real-time visual navigation.

Workflow:

1. Capture the current frame
2. The VLM analyzes the frame and outputs a movement direction
3. Send the movement command
4. Loop until the target is reached

### 3. Tuning Guide

#### 3.1 LLM Parameter Tuning

| Parameter | Notes | Suggested value |
|------|------|------|
| `temperature` | sampling temperature | 0.1-0.3 (for decision-type tasks) |
| `max_tokens` | maximum tokens generated | 512-1024 |
| `top_p` | nucleus sampling | 0.9 |

#### 3.2 Navigation Tuning

- **Screenshot frequency**: 1-2 frames/sec is recommended for VLM navigation; too high increases latency
- **Movement step**: adjust per scene to avoid overshooting
- **Timeout setting**: 30-60 seconds is recommended per single navigation

---

> **Consolidated below from** `RECOGNITION_PIPELINE_AND_TASKS.md`

## Recognition, Pipeline, and Task System

This document consolidates the architecture and implementation of scene recognition, pipeline execution, and the task system.

### 1. Scene Recognition

#### 1.1 EndfieldElementRecognizer

`EndfieldElementRecognizer` (`src/core/capability/recognition/recognizer.py`) is the unified entry point of the recognition layer.

```python
class EndfieldElementRecognizer:
    def recognize(self, screenshot, element):
        # dispatch to different backends based on the element type
        ...
```

#### 1.2 Recognition Backends

| Backend | Purpose | Implementation |
|------|------|------|
| TemplateBackend | template matching | MaaFW pipeline |
| OCRBackend | text recognition | MaaFW OCR |
| ColorBackend | color detection | OpenCV |
| YOLOBackend | object detection | ONNX |

### 2. Pipeline Execution

#### 2.1 PipelineRunner

`PipelineRunner` (`src/core/service/pipeline/runner.py`) executes MaaFW pipeline tasks.

```python
class PipelineRunner:
    def run(self, entry, param=None):
        # call tasker.post_task
        ...
```

#### 2.2 Pipeline Definition

Pipeline tasks are defined in JSON and stored in `3rd-part/maaend/resource*/pipeline/`.

```json
{
  "TaskName": {
    "recognition": "TemplateMatch",
    "template": "xxx.png",
    "action": "Click",
    "next": ["NextTask"]
  }
}
```

### 3. Task System

#### 3.1 Task Definition

Tasks are defined in JSON, containing fields such as `name`, `entry`, and `options`.

#### 3.2 Preset System

A preset is an ordered collection of tasks, supporting batch execution.

```json
{
  "preset_name": "daily",
  "tasks": [
    {"name": "task1", "options": {...}},
    {"name": "task2", "options": {...}}
  ]
}
```

#### 3.3 Task Queue

The task queue manages tasks pending execution and supports persistence to `config/maaend_task_state.json`.

### 4. Known Issues

| Issue | Location | Notes |
|------|------|------|
| MaaFW injection only in TemplateBackend | `recognizer.py` | The TaskRunner path lacks MaaFW injection |
| Recognition result caching missing | `recognizer.py` | Recognition is recomputed every time |

---

> **Consolidated below from** `superpowers/specs/2026-07-09-gui-parallel-startup-design.md`

## GUI Startup Parallel-Loading Design

### 1. Background

On GUI startup, several components must be initialized (config, device, MaaEnd, LLM). Serial loading makes startup slow.

### 2. Goal

Shorten GUI startup time via parallel loading.

### 3. Design

#### 3.1 Parallel-Loaded Components

```
GUI startup
    │
    ├── [thread 1] load config
    ├── [thread 2] initialize device connection
    ├── [thread 3] start MaaEnd
    └── [thread 4] start the LLM server
```

#### 3.2 Synchronization Point

The GUI main window is shown only after all components finish loading.

### 4. Implementation Points

- Use `QThreadPool` to manage the loading threads
- Each component emits a signal when its loading completes
- The main window listens for all signals and is shown once all are complete

### 5. Risks and Fallback

- Parallel loading may introduce race conditions
- If parallel loading fails, fall back to serial loading
