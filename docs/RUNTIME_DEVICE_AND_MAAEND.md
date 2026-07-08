# 运行时、设备与 MaaEnd 集成

## 1. 委托链完整路径

```
┌─────────────────────────────────────────────────────────────────────┐
│ 用户操作 (GUI 按钮 / CLI 命令)                                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ IstinaRuntime.execute(command, params)                               │
│   - 路由 daily.run / task.run / preset.run / screenshot 等          │
└───────────────────────────────┬─────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ IstinaRuntime._daily_run / _run_task / _run_preset                  │
│   - 调用 self.maaend(serial) 获取 MaaEndRuntime                     │
│   - 调用 _ensure_maaend_ready() 确保连接和资源加载                   │
└───────────────────────────────┬─────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ MaaEndRuntime.connect()                                              │
│   1. Toolkit.init_option()                                          │
│   2. _start_agent() → 启动 go-service.exe (AgentClient)            │
│   3. AdbController(adb_path, address, screencap, input_methods=3)  │
│   4. controller.post_connection() → ADB 连接设备                     │
│   5. controller.post_screencap() → 测试截图                          │
│   6. Tasker.bind(resource, controller)                               │
│   7. AgentClient.bind/register_sink/connect                          │
└───────────────────────────────┬─────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ MaaEndRuntime.load_resource()                                        │
│   - post_bundle(resource/) → 加载 Pipeline 图像资源                  │
│   - post_bundle(resource_adb/) → 加载 ADB 专用资源                   │
└───────────────────────────────┬─────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│ MaaEndRuntime.run_task() / run_preset()                              │
│   - build_pipeline_override() → 解析 option 生成 override           │
│   - tasker.post_task(entry, override) → MaaFramework 执行            │
│   - Pipeline FSM: 识别 → 操作 → 跳转 → ...                          │
└─────────────────────────────────────────────────────────────────────┘
```

## 2. 跨模块调用链检查

### 2.1 Runtime → MaaEnd → Device

| 调用链 | 状态 | 备注 |
|--------|------|------|
| `IstinaRuntime.maaend()` → `MaaEndRuntime` | ✅ | 结构正确 |
| `IstinaRuntime.android()` → `AndroidRuntimeProxy` → `AndroidRuntime` → `_Daemon` | ✅ | `_Daemon._dispatch()` 已统一使用 `params.get("serial", self._serial)` |
| `IstinaRuntime.disconnect()` → `MaaEndRuntime.disconnect()` | ✅ | `disconnect()` 已调用 `_cleanup_partial()` 终止 agent 进程 |

### 2.2 Scene → Recognizer → Backends

| 调用链 | 状态 | 备注 |
|--------|------|------|
| `SceneUnderstandingService.identify()` → `EndfieldElementRecognizer.recognize()` | ✅ | |
| `EndfieldElementRecognizer` → `TemplateBackend/OCRBackend/ColorBackend/YOLOBackend` | ✅ | |
| `EndfieldElementRecognizer` → `PipelineRunner` (via TemplateBackend) | ⚠️ | MaaFW 注入仅在 TemplateBackend 中，TaskRunner 路径缺失（见下文 High #2） |

### 2.3 CLI/GUI → Runtime

| 调用链 | 状态 | 备注 |
|--------|------|------|
| `CLIDispatch.dispatch()` → `runtime.execute()` | ✅ | 19 个分支全部映射 |
| `MaaEndControlPage._sync_execute()` → `CLIBridge.execute()` | ✅ | 存在死代码（见下文 Low #7） |
| GUI 选项序列化 → Runtime options | ⚠️ | 合并顺序错误（见下文 High #2） |

### 2.4 LLM & Navigation

| 调用链 | 状态 | 备注 |
|--------|------|------|
| `LlamaServerRuntime` → `llama-server` 进程 | ✅ | 死锁风险（见下文 Medium #4） |
| `LlmClient.chat()` → `/v1/chat/completions` | ✅ | |
| `Navigator.to_coords_vlm()` → `VlmWalkNavigator` | ✅ | `level_id` 回退不一致（见下文 Medium #5） |
| `_vlm_keyevent()` → `AndroidRuntimeProxy.keyevent()` | ✅ | 签名匹配 |

## 3. Runtime & Device 层问题

### High

1. **`MaaEndRuntime.disconnect()` 泄漏 agent 进程** — ✅ 已修复
   `disconnect()` 已直接调用 `self._cleanup_partial()`（`src/core/service/maa_end/runtime.py:282`）。

2. **Daemon 忽略 `serial` 参数（tap/swipe/keyevent/shell）** — ✅ 已修复
   `_Daemon._dispatch()` 已统一使用 `params.get("serial", self._serial)`（`src/core/capability/device/android_runtime.py:470-488`）。

### Medium

3. **`AndroidRuntimeProxy.adb_manager` 命名误导**
   `src/core/service/runtime.py:39-40` 返回 `AndroidRuntime`，而非 `ADBDeviceManager`。
   **修复**：改名为 `default_client` 或返回真实管理器。

4. **`MaaEndRuntime.screenshot()` 缺少 `serial` 参数**
   `src/core/service/maa_end/runtime.py:529` 与 `AndroidRuntime.screenshot(serial)` 签名不一致。
   **修复**：添加可选 `serial` 或文档说明其 per-device 约束。

5. **`device_address` 默认值不一致**
   `MaaEndRuntime` 默认 `"localhost:16512"`，但 `IstinaRuntime.maaend()` 回退到 `"default"`，会导致 `AdbController` 连接失败。
   **修复**：统一默认地址或在 `MaaEndRuntime.__init__` 中校验。

6. **`version()` 未暴露给 `AndroidRuntimeProxy`**
   Daemon 与 `AndroidRuntime` 已实现，但 Proxy 未转发。
   **修复**：在 Proxy 中添加 `version()`。

7. **`ADBDeviceManager` 路径解析策略不一致**
   `AndroidRuntime` 使用 `get_project_root()` 拼接，`MaaEndRuntime` 按原始路径解析。
   **修复**：统一使用 `get_project_root()`。

8. **`tasks()`/`presets()` 在空字典时反复重载**
   `self._tasks or self.load_tasks()` 在空 dict 时为 falsy，导致每次调用都走磁盘。
   **修复**：改为 `if not self._tasks: self.load_tasks(); return self._tasks`。

9. **`load_interface()` 缺少异常处理**
   `src/core/service/maa_end/runtime.py:104-108` 未 try/except，`load_tasks()`/`load_presets()` 均已包裹。
   **修复**：添加异常处理并返回 `{}`。

### Low

10. **不可达的 `if not self.connected` 块**
    `_daily_run/_harvest_run/_analyze_run/_explore_run/_nav_to` 中，`_ensure_maaend_ready()` 之后必然 connected。
    **修复**：移除死代码或将检查前移。

12. **误导性类名**
    - `IstinaRuntime` 实际是 Facade/Dispatcher。
    - `AndroidRuntimeProxy` 是 Adapter。
    - `MaaEndRuntime` docstring 声称 "mirror MaaEnd" 但实为本地 bridge。
    **修复**：重命名或更新 docstring。

## 4. MaaEnd 集成问题

### 4.1 双 MaaEnd 副本路径不一致（最严重）

**现象**：项目同时存在两个 MaaEnd 副本，内容不同步：

| 副本 | 路径 | 内容 | 用途 |
|------|------|------|------|
| `3rd-part/maaend/` | `3rd-part/maaend/` | 编译好的二进制文件 + 旧版任务/资源 | IEA 默认加载 |
| `MaaEnd/` | `MaaEnd/` | 源码 + 最新任务/资源 | 开发/构建源 |

**关键差异**（已通过 diff 验证）：

```diff
# DailyFull.json
<                     "name": "AndroidOpenGame",
<                     "option": { "ClientVersion": "CN" }
<                 },

# AutoCollect.json
+         "AutoCollectStashBackpackSubTask": {
+             "type": "switch",
+             "default_case": "Yes",
+             ...
+         }

# Interface/Scene.json
<             "[JumpBack]UserProtocol"
---
>             "[JumpBack]__ScenePrivateAnyExit"
```

**根本原因**：
- `MaaEndRuntime._default_maaend_root()` 硬编码返回 `3rd-part/maaend`
- 但 `MaaEnd/` 目录下的 `assets/tasks/` 和 `assets/resource/` 已更新
- 如果用户手动修改了 `MaaEnd/` 的任务/资源，IEA 不会加载这些修改
- 反之，如果 `3rd-part/maaend/` 未同步更新，会加载过时的任务定义

**影响**：任务执行时 pipeline override 与实际资源不匹配，导致识别失败、操作错误。

### 4.2 `MAAFW_BINARY_PATH` 环境变量冲突

**现象**：DLL 加载路径被多个地方设置，可能导致版本冲突。

**代码路径**：

```python
# src/core/service/maa_end/runtime.py [模块导入时]
_maaend_agent_dir = get_project_root() / "3rd-part" / "maaend" / "agent"
_maafw_dir = _maaend_agent_dir / "maafw"
if _maafw_dir.is_dir():
    os.environ["MAAFW_BINARY_PATH"] = str(_maafw_dir.resolve())
    # → 设置为: <project>/3rd-part/maaend/agent/maafw/

# src/core/service/maa_end/runtime.py [_start_agent()]
agent_env = os.environ.copy()
agent_env["MAAFW_BINARY_PATH"] = str((agent_root / "maafw").resolve())
# → 覆盖为: <project>/3rd-part/maaend/agent/maafw/ (相同路径)
```

```go
// MaaEnd/agent/go-service/main.go [Go service 启动时]
libDir := filepath.Join(getCwd(), "maafw")
maa.Init(maa.WithLibDir(libDir))
// → 使用: <cwd>/maafw/ (即 3rd-part/maaend/agent/maafw/)
```

**项目中的 DLL 分布**：
```
<project>/maafw/                          ← Python MaaFw 包可能使用
<project>/3rd-part/maaend/agent/maafw/   ← Go service 使用
<project>/3rd-part/maaend/maafw/         ← 存在但未被引用
```

**根本原因**：
- Python `MaaFw` 包、Go service、IEA 代码三方对 `MAAFW_BINARY_PATH` 的设置不一致
- 如果 `maafw/`（根目录）和 `3rd-part/maaend/agent/maafw/` 的 DLL 版本不同，会导致：
  - Python 端加载的 MaaFramework 版本与 Go 端不一致
  - 数据结构/函数签名不匹配，导致崩溃或静默错误

**影响**：设备控制时 MaaFramework 内部状态不一致，截图/点击/识别全部失效。

### 4.3 Agent 进程启动的静默失败

**现象**：`_start_agent()` 启动 `go-service.exe` 失败时只记录 warning，继续执行。

```python
def _start_agent(self) -> None:
    agent_exe = agent_root / "go-service.exe"
    if AgentClient is None or not agent_exe.exists():
        return  # ← 静默跳过
    try:
        self._agent_process = _sp.Popen(...)
        self._agent_client = AgentClient(str(agent_port))
    except Exception as exc:
        self.logger.warning(LogCategory.MAIN, "启动 Agent 失败", error=str(exc))
        # ← 仅打 warning，不向上传递
        self._agent_client = None
        self._agent_process = None
```

**根本原因**：
- `go-service.exe` 可能不存在于 `3rd-part/maaend/agent/`（如果只部署了源码）
- Go service 初始化失败（DLL 缺失、端口冲突等）被吞掉
- `connect()` 不检查 `_agent_client` 是否成功初始化

**影响**：
- 依赖 Go 自定义逻辑的任务（`AutoFight`、`EssenceFilter`、`PuzzleSolver`、`MapTracker` 等）静默失败
- 任务执行到 Custom Action 时无响应或回退到默认行为
- 用户看到"任务执行失败"但不知道是 Agent 未启动

### 4.4 `input_methods` 使用枚举值

当前 `MaaEndRuntime` 使用 `MaaAdbInputMethodEnum.AdbShell` 枚举值（`src/core/service/maa_end/runtime.py:193`），无 MaaFramework 时回退为 `1`（`AdbShell`）。非硬编码字面量 `3`。

### 4.5 legacy 兼容代码干扰连接状态

**现象**：`_ensure_maaend_ready()` 包含 legacy 兼容代码，可能错误修改 `_connected`。

```python
def _ensure_maaend_ready(self, runtime: MaaEndRuntime) -> bool:
    if runtime.connected:
        return True
    legacy = getattr(self, "_maaend", None)
    if legacy is runtime and getattr(runtime, "_connect_result", None) is not None:
        if hasattr(runtime, "_connected"):
            runtime._connected = bool(getattr(runtime, "_connect_result", False))
        if runtime.connected:
            return True
    # ...
```

**根本原因**：
- 代码假设 `runtime._connect_result` 存在（旧版 API），但新版 `MaaEndRuntime` 没有这个属性
- 如果 `legacy is runtime` 为 True（多设备场景下可能触发），会尝试读取不存在的属性
- `getattr(runtime, "_connect_result", None)` 返回 `None`，`bool(None)` 为 `False`
- 不会直接导致错误，但表明代码路径混乱，维护困难

**影响**：连接逻辑难以追踪，可能在边界条件下产生意外行为。

### 4.6 多设备 serial 处理不一致

**现象**：`maaend(serial)` 按 serial 缓存 runtime，但 `connect()` 未传递 serial。

```python
def maaend(self, serial: Optional[str] = None) -> MaaEndRuntime:
    resolved = serial or device_cfg.get("last_connected") or device_cfg.get("serial") or "default"
    runtime = self._maaend_clients.get(resolved)
    if runtime is None:
        runtime = MaaEndRuntime(device_address=resolved, ...)
        self._maaend_clients[resolved] = runtime
    return runtime

def connect(self, serial: Optional[str] = None) -> bool:
    runtime = self.maaend(serial)  # ← 正确获取对应 serial 的 runtime
    if not runtime.connected:
        ok = runtime.connect()  # ← runtime 已包含正确的 device_address
```

**表面上看没问题**，但存在以下缺陷：

1. **`_ensure_maaend_ready()` 的 serial 传递问题**：
   ```python
   def _run_task(self, params):
       serial = params.get("serial")
       runtime = self.maaend(serial)
       if not self._ensure_maaend_ready(runtime):
           return False
       return bool(runtime.run_task(name, options, timeout_s=timeout_s))
   ```
   `_ensure_maaend_ready(runtime)` 接收 runtime，但内部通过 `getattr(self, "_maaend", None)` 检查 legacy，不涉及 serial。

2. **设备地址缓存失效**：
   - 如果用户先连接设备 A，再连接设备 B
   - `maaend_clients` 中同时存在 A 和 B 的 runtime
   - 但 `_ensure_maaend_ready()` 不会区分不同 runtime 的连接状态

**影响**：多设备场景下，连接状态管理混乱。

### 4.7 `_start_agent()` 在 AdbController 之前启动

**现象**：Agent 进程在控制器创建之前启动。

```python
def connect(self) -> bool:
    self._resource = Resource()
    self._start_agent()  # ← 先启动 Agent
    input_method = 3
    self._controller = AdbController(...)  # ← 后创建控制器
    job = self._controller.post_connection()
    # ...
    self._tasker = Tasker()
    if self._agent_client is not None:
        self._agent_client.bind(self._resource)
        self._agent_client.register_sink(self._resource, self._controller, self._tasker)
```

**根本原因**：
- Go service 启动时需要初始化 MaaFramework
- 但此时 `_controller` 和 `_tasker` 还不存在
- `AgentClient.register_sink()` 在控制器创建后才调用，此时 Go service 可能已超时或进入错误状态

**影响**：Agent 初始化时序错误，可能导致：
- Go 自定义 Recognition/Action 无法正确注册
- Tasker 事件无法正确传递给 Go service

### 4.8 `Toolkit.init_option()` 路径可能无效

**现象**：MaaFramework 初始化路径可能不正确。

```python
if Toolkit is not None:
    try:
        Toolkit.init_option(
            Path(self._maaend_root / "config") if (self._maaend_root / "config").exists() else Path(self._maaend_root)
        )
    except Exception:
        pass  # ← 静默忽略
```

**根本原因**：
- `3rd-part/maaend/config` 存在，但内容可能不是有效的 MaaFramework 配置
- 如果路径无效，MaaFramework 使用默认配置，可能导致：
  - 日志级别错误
  - 临时目录错误
  - 插件路径错误
- 异常被完全吞掉，用户无法得知

**影响**：MaaFramework 使用错误的配置运行，行为不可预测。

## 5. 委托链失败的根本原因总结

| 错误 | 严重程度 | 根本原因 | 影响 |
|------|----------|----------|------|
| 双副本不一致 | **P0** | `3rd-part/maaend/` 与 `MaaEnd/` 内容不同步，IEA 默认加载旧副本 | 任务定义与资源不匹配，识别/操作全部失效 |
| DLL 路径冲突 | **P0** | `MAAFW_BINARY_PATH` 被多个组件设置，可能加载不同版本的 DLL | Python 与 Go 端的 MaaFramework 状态不一致，崩溃或静默错误 |
| Agent 静默失败 | **P1** | `_start_agent()` 异常被吞，不向上传递 | Go 自定义逻辑全部失效，任务执行到 Custom Action 时失败 |
| 多设备 serial 处理 | **P2** | 连接状态检查未区分不同 runtime | 多设备场景下状态混乱 |
| Agent 启动时序 | **P2** | Agent 在控制器之前启动 | Go 初始化时序错误 |
| Toolkit 路径 | **P3** | 配置路径可能无效，异常被吞 | MaaFramework 使用默认配置 |

## 6. 修复建议优先级

### P0 — 立即修复

1. **统一 MaaEnd 副本路径**
   - 删除或同步 `3rd-part/maaend/` 和 `MaaEnd/` 的内容
   - 在 `MaaEndRuntime` 中支持通过 `config/client_config.json` 配置 `maaend_root`
   - 或者在 `MaaEnd/` 根目录创建 `interface.json` 符号链接/复制

2. **统一 DLL 加载路径**
   - 在项目启动时只设置一次 `MAAFW_BINARY_PATH`
   - 确保 Python `MaaFw` 包和 Go service 使用完全相同的 DLL
   - 建议统一使用 `3rd-part/maaend/agent/maafw/`

### P1 — 短期修复

3. **Agent 启动失败应抛出异常**
   - `_start_agent()` 失败时应该让 `connect()` 返回 `False`
   - 或者至少记录 error 级别日志，明确告知用户 Agent 未启动

### P2 — 中期修复

4. **Agent 启动时序调整**
   - 将 `_start_agent()` 移到 `Tasker.bind()` 之后
   - 确保控制器和 Tasker 已就绪再启动 Agent

### P3 — 长期改进

5. **Toolkit 配置验证**
   - `init_option()` 失败时记录 warning
   - 提供有效的配置文件或使用项目默认配置

## 7. 快速验证方法

用户可以通过以下方式验证问题：

```bash
# 1. 检查 DLL 版本是否一致
diff <(ls "C:/.../maafw/") <(ls "C:/.../3rd-part/maaend/agent/maafw/")

# 2. 检查任务定义是否同步
diff -r "C:/.../3rd-part/maaend/tasks" "C:/.../MaaEnd/assets/tasks"

# 3. 检查 go-service.exe 是否存在
ls "C:/.../3rd-part/maaend/agent/go-service.exe"

# 4. 检查环境变量
python -c "import os; print(os.environ.get('MAAFW_BINARY_PATH'))"
```

## 8. 附录：命名 vs 实现对照表

| 函数/类 | 命名暗示 | 实际实现 | 结论 |
|---------|----------|----------|------|
| `AndroidRuntimeProxy.adb_manager` | 返回 ADBDeviceManager | 返回 AndroidRuntime | ❌ 不匹配 |
| `AndroidRuntimeProxy` | 透明代理 | 手动转发每个方法 | ⚠️ 适配器而非代理 |
| `IstinaRuntime` | 单一运行时 | 多运行时门面/调度器 | ⚠️ 命名过宽 |
| `MaaEndRuntime` | 镜像 MaaEnd 进程 | 本地资源加载 + Tasker bridge | ⚠️ docstring 需更新 |
| `PipelineRunner` | 纯图执行器 | 嵌入 MaaFW SDK + 颜色匹配 | ❌ 违反 SRP |
| `ColorBackend.recognize_gameplay_scene` | 颜色匹配 | 3D 场景理解 | ❌ 职责错位 |
| `EndfieldElementRecognizer` 模块 docstring | 5 种后端 | 4 种后端 + 1 个后处理 | ❌ 描述不准确 |
