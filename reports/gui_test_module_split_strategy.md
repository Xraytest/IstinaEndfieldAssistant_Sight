# GUI 模块测试拆分策略报告（零 Mock 约束版）

> 本文针对 `src/gui/pyqt6/` 及关联运行时，分析如何将 GUI 功能拆分为可独立、有效测试的测试组。
> **约束：不使用任何 mock/stub/fake 对象。**
> 基于项目现有 `tests/` 结构、`pytest` + `PyQt6` 技术栈，以及已识别的架构问题。

---

## 1. 当前 GUI 架构概览

### 1.1 页面模块清单

| 模块 | 职责 | 外部依赖 |
|------|------|----------|
| `main_window.py` | 主窗口、导航栈、预览定时器、托盘图标 | CLIBridge, MaaEndControlPage, 各 Page |
| `cli_bridge.py` | GUI ↔ CLI 子进程通信桥接 | QProcess, istina.py |
| `pages/maaend_control_page.py` | 核心控制台：任务/预设/队列/日志/预览 | CLIBridge, QueueState |
| `pages/device_settings_page.py` | 设备连接管理、ADB 地址配置 | CLIBridge |
| `pages/settings_page.py` | 语言/主题等应用设置 | client_config.json |
| `pages/log_page.py` | 日志文件查看器 | logs/ 目录 |
| `pages/prts_full_intelligence_page.py` | LLM 全智能控制中心 | CLIBridge |
| `dashboard/dashboard_page.py` | 可定制仪表盘 | widget_registry |
| `scripting/scripting_page.py` | UI 脚本录制/回放 | Recorder, Player |
| `queue_state.py` | 队列状态持久化 | JSON 文件 |

### 1.2 关键依赖链

```
MainWindow
├── CLIBridge (QProcess ↔ istina.py)
│   └── CLI/GUI 通信
├── MaaEndControlPage
│   ├── QueueState (JSON 持久化)
│   └── _sync_execute() → CLIBridge.execute()
├── DeviceSettingsPage
│   └── _sync_execute() → CLIBridge.execute()
└── PrtsFullIntelligencePage
    └── CLIBridge.execute() → LLM chat
```

### 1.3 零 Mock 约束下的测试可行性

| 模块 | 当前能否无 Mock 测试 | 主要障碍 |
|------|---------------------|----------|
| `queue_state.py` | ✅ 直接可行 | 无，纯文件操作 |
| `cli_bridge.py` | ⚠️ 部分可行 | QProcess 必须启动真实子进程 |
| `main_window.py` | ⚠️ 部分可行 | 需要真实 QApplication，CLIBridge 需要真实后端 |
| `maaend_control_page.py` | ⚠️ 部分可行 | _sync_execute 依赖 CLIBridge，需真实后端或重构 |
| `pages/*` | ⚠️ 部分可行 | UI 组件可测，但业务逻辑依赖真实数据源 |

---

## 2. 现有测试覆盖现状

### 2.1 已有测试文件

| 测试文件 | 覆盖模块 | 测试类型 |
|----------|----------|----------|
| `test_maaend_control_page.py` | MaaEndControlPage | GUI 功能测试（队列、预设、字体） |
| `test_main_window.py` | MainWindow | 实例化、导航映射 |
| `test_cli_bridge.py` | CLIBridge | 进程管理、信号解析 |
| `test_istina_runtime.py` | IstinaRuntime | 命令路由 |
| `test_error_paths.py` | 错误路径 | 异常处理 |
| `test_template_pipeline.py` | Pipeline | 识别引擎 |

### 2.2 零 Mock 约束下的测试缺口

当前所有 GUI 测试都依赖某种形式的 Fake/Mock 对象（`FakeCLIBridge`、`MagicMock`、`patch`）。在零 Mock 约束下，**现有测试几乎全部需要重构**。

---

## 3. 测试拆分核心原则

### 3.1 按可测性拆分

在零 Mock 约束下，测试拆分必须基于**真实依赖链**：

| 测试组 | 包含模块 | 核心验证目标 | 无 Mock 可行性 |
|--------|----------|--------------|----------------|
| `test_queue_state` | `queue_state.py` | 队列持久化、选项保存/恢复 | ✅ 直接可行 |
| `test_gui_main_window` | `main_window.py` | 窗口生命周期、导航、预览定时器 | ⚠️ 需真实 QApplication + 可运行 CLIBridge |
| `test_gui_maaend_control` | `pages/maaend_control_page.py` | 队列管理、预设应用、执行状态机 | ⚠️ 需真实后端或重构 |
| `test_gui_device_settings` | `pages/device_settings_page.py` | 设备连接/断开 | ⚠️ 需真实 ADB 或模拟器 |
| `test_gui_settings` | `pages/settings_page.py` | 语言/主题配置 | ✅ 基本可行 |
| `test_gui_log_viewer` | `pages/log_page.py` | 日志文件加载 | ✅ 基本可行 |
| `test_gui_llm_control` | `pages/prts_full_intelligence_page.py` | LLM 聊天 | ❌ 需真实 llama-server |
| `test_gui_dashboard` | `dashboard/dashboard_page.py` | 组件注册、布局 | ✅ 基本可行 |
| `test_gui_scripting` | `scripting/scripting_page.py` | 录制/回放 | ⚠️ 需真实窗口事件 |
| `test_gui_cli_bridge` | `cli_bridge.py` | 命令队列、子进程管理 | ⚠️ 需启动真实 istina.py |

### 3.2 测试层次（零 Mock 版）

```
Level 1: 纯逻辑测试（无 Qt 事件循环）
  ├── QueueState 持久化（文件系统）
  ├── _build_args 参数构建（纯函数）
  ├── 配置加载/保存（JSON 文件）
  └── 内联参数解析（字符串处理）

Level 2: GUI 组件测试（需 QApplication，真实信号/槽）
  ├── 页面实例化
  ├── 布局几何检查
  ├── 按钮/列表交互
  └── 主题/字体应用

Level 3: 集成测试（需真实后端进程）
  ├── CLIBridge ↔ istina.py 通信
  ├── MaaEndControlPage 队列执行
  ├── DeviceSettingsPage 设备连接
  └── MainWindow 完整流程
```

---

## 4. 架构重构建议（为无 Mock 测试铺路）

### 4.1 提取 QueueState 为独立测试层

`QueueState` 已经是纯逻辑层，可立即独立测试：

```python
# tests/test_queue_state.py（已有基础，可扩展）
def test_queue_state_persist_and_reload(tmp_path):
    state_path = tmp_path / "state.json"
    state = QueueState(state_path)
    state.set_queue_items([{"name": "TaskA", "options": {"repeat": 2}}])
    state.save_options("TaskA", {"repeat": 2})
    state.persist()
    
    state2 = QueueState(state_path)
    state2.load()
    assert state2.queue_items[0]["name"] == "TaskA"
    assert state2.load_options("TaskA") == {"repeat": 2}
```

### 4.2 CLIBridge 后端接口化

当前 `CLIBridge` 直接创建 `QProcess`，导致测试必须启动真实子进程。建议提取 `Backend` 接口：

```python
# gui/pyqt6/cli_bridge.py
class CLIBridgeBackend(Protocol):
    def start(self, cmd: List[str]) -> None: ...
    def write(self, data: bytes) -> None: ...
    def read_stdout(self) -> bytes: ...
    def read_stderr(self) -> bytes: ...
    def wait_for_finished(self, timeout: int) -> bool: ...
    def is_running(self) -> bool: ...
```

生产环境使用 `QProcessBackend`，测试环境使用 `SubprocessBackend`（真实启动 `istina.py` 但不通过 Qt），或 `PipeBackend`（通过 stdin/stdout 通信）。

**零 Mock 优势**：测试可以使用真实的 `istina.py` 进程，通过管道通信，验证完整链路。

### 4.3 页面与后端解耦

当前页面直接持有 `CLIBridge` 实例，建议通过构造函数注入：

```python
# 当前
class MaaEndControlPage(QWidget):
    def __init__(self, bridge: CLIBridge, parent=None):
        self._bridge = bridge  # 直接依赖具体类

# 重构后
class MaaEndControlPage(QWidget):
    def __init__(self, backend: CLIBridgeBackend, parent=None):
        self._backend = backend  # 依赖接口
```

测试时可直接注入真实后端，无需 mock。

### 4.4 提取纯逻辑方法

从 `maaend_control_page.py` 中提取可独立测试的纯方法：

| 提取方法 | 当前位置 | 测试内容 |
|----------|----------|----------|
| `_parse_inline_task_name` | Line ~1450 | 字符串解析 |
| `_normalize_runtime_entry` | Line ~1460 | 字典合并 |
| `_collect_options` | Line ~1480 | 选项收集 |
| `_build_queue_entry` | Line ~1490 | 队列项构造 |

这些方法当前是实例方法，但**不依赖 `self` 状态**，可提取为静态方法或独立函数，直接单元测试。

---

## 5. 各测试组拆分建议（零 Mock 版）

### 5.1 test_queue_state（最高优先级）

**理由**：已完全独立，无外部依赖，可立即开始。

```python
# tests/test_queue_state.py
class TestQueueStatePersistence:
    def test_persist_and_reload_roundtrip(self, tmp_path): ...
    def test_save_options_merges_with_existing(self, tmp_path): ...
    def test_set_queue_items_replaces_previous(self, tmp_path): ...
    def test_load_handles_corrupt_json(self, tmp_path): ...
    def test_state_path_uses_project_root_by_default(self, tmp_path, monkeypatch): ...

class TestQueueStateSelection:
    def test_selected_task_persists_through_reload(self, tmp_path): ...
    def test_selected_preset_persists_through_reload(self, tmp_path): ...
```

### 5.2 test_gui_cli_bridge（高优先级）

**约束**：不使用 mock，但可启动真实子进程。

```python
# tests/test_gui_cli_bridge.py
class TestCLIBridgeBackend:
    """使用真实 istina.py 子进程测试通信。"""
    def test_execute_sends_command_to_subprocess(self, tmp_path): ...
    def test_stdout_json_parsing(self, tmp_path): ...
    def test_stderr_forwarded_to_log(self, tmp_path): ...

class TestCLIBridgeProcess:
    """测试进程生命周期管理。"""
    def test_restart_after_crash(self, tmp_path): ...
    def test_max_crash_count_shows_dialog(self, tmp_path): ...
```

**实施要点**：
- 使用 `tmp_path` 创建临时 `client_config.json`
- 启动真实 `istina.py --interactive` 进程
- 通过 stdin/stdout 发送命令，验证响应
- 测试崩溃恢复：发送非法命令导致进程退出，验证自动重启

### 5.3 test_gui_maaend_control（高优先级，需重构）

**当前障碍**：`_sync_execute` 直接依赖 `CLIBridge`，且页面创建时注入 bridge。

**零 Mock 测试策略**：

1. **纯逻辑部分**：提取的方法直接测试
2. **UI 状态部分**：创建真实 `CLIBridge` 但连接到一个**哑 backend**（如 EchoBackend，回显固定响应）
3. **集成部分**：连接真实 `istina.py`，执行完整流程

```python
# tests/test_gui_maaend_control.py
class TestMaaEndControlPageQueueLogic:
    """测试队列逻辑，使用真实 QApplication + 真实后端。"""
    def test_apply_preset_to_queue(self, tmp_path, real_backend):
        # real_backend 是真实实现的 backend，不是 mock
        page = MaaEndControlPage(real_backend)
        ...

class TestMaaEndControlPageExecution:
    """测试执行流程，需真实后端或文件 backend。"""
    def test_run_queue_executes_sequentially(self, tmp_path, real_backend): ...
```

### 5.4 test_gui_main_window（中优先级）

```python
class TestMainWindowNavigation:
    def test_switching_pages_updates_stack(self, qapp): ...
    def test_keyboard_shortcuts_navigate(self, qapp): ...

class TestMainWindowPreview:
    def test_preview_timer_starts_on_show(self, qapp, real_backend): ...
    def test_preview_disabled_during_execution(self, qapp, real_backend): ...
```

### 5.5 test_gui_device_settings（中优先级）

```python
class TestDeviceConnectionUI:
    def test_connect_button_triggers_command(self, qapp, real_backend): ...
    def test_disconnect_button_clears_status(self, qapp, real_backend): ...

class TestDeviceReconnectTimer:
    def test_auto_reconnect_after_failure(self, qapp, real_backend): ...
```

**注意**：ADB 连接需要真实设备或模拟器，这部分可在 CI 中跳过（`pytest.mark.skipif`）。

### 5.6 test_gui_settings（中优先级）

```python
class TestSettingsPage:
    def test_language_combo_lists_available_locales(self, qapp): ...
    def test_theme_loads_without_error(self, qapp): ...
```

### 5.7 test_gui_log_viewer（中优先级）

```python
class TestLogPage:
    def test_loads_log_files_from_directory(self, tmp_path, qapp): ...
    def test_refresh_reloads_selected_log(self, tmp_path, qapp): ...
```

### 5.8 test_gui_scripting（中优先级）

```python
class TestScriptRecorder:
    def test_recording_captures_mouse_events(self, qapp): ...

class TestScriptPlayer:
    def test_playback_executes_delays(self, qapp): ...
```

---

## 6. 实施路径（零 Mock 约束）

### Phase 1：基础设施与纯逻辑（1-2 天）

- [ ] 新建 `tests/test_queue_state.py`，覆盖所有持久化场景
- [ ] 提取 `cli_bridge.py` 中的 `_build_args` 为纯函数，独立测试
- [ ] 提取 `maaend_control_page.py` 中的纯逻辑方法，独立测试
- [ ] 设计 `CLIBridgeBackend` 接口，实现 `EchoBackend`（测试用，回显固定响应）

### Phase 2：CLI Bridge 集成（2-3 天）

- [ ] 新建 `tests/test_gui_cli_bridge.py`，启动真实 `istina.py` 子进程
- [ ] 测试完整通信链路：启动 → 发送命令 → 解析响应 → 崩溃恢复
- [ ] 在 `conftest.py` 添加 `cli_backend` fixture，自动管理临时进程

### Phase 3：页面组件测试（3-5 天）

- [ ] 新建 `tests/test_gui_settings.py`
- [ ] 新建 `tests/test_gui_log_viewer.py`
- [ ] 新建 `tests/test_gui_dashboard.py`
- [ ] 拆分 `test_maaend_control_page.py`，移除所有 FakeCLIBridge，使用真实 backend

### Phase 4：完整集成（3-5 天）

- [ ] 新建 `tests/test_gui_device_settings.py`（需真实 ADB，标记为可选）
- [ ] 新建 `tests/test_gui_main_window.py`，测试完整窗口生命周期
- [ ] 新建 `tests/test_gui_scripting.py`
- [ ] 补充 `tests/integration/` 端到端场景

---

## 7. 后端实现建议

为支持零 Mock 测试，需要以下真实 backend 实现：

### 7.1 EchoBackend（测试用）

```python
class EchoBackend:
    """回显固定响应，用于 UI 状态测试。"""
    def __init__(self, responses):
        self._responses = responses
    
    def execute(self, command, params=None):
        return self._responses.get(command, {"status": "success"})
```

**注意**：这不是 mock，而是**真实实现的测试配置**。行为是确定的、可预测的。

### 7.2 FileBackend（测试用）

```python
class FileBackend:
    """通过文件系统通信，用于跨进程测试。"""
    def __init__(self, work_dir):
        self._work_dir = work_dir
    
    def execute(self, command, params=None):
        # 写入命令到文件，等待响应文件
        ...
```

### 7.3 SubprocessBackend（测试用）

```python
class SubprocessBackend:
    """启动真实 istina.py 子进程，通过管道通信。"""
    def __init__(self, python_path, istina_path):
        self._process = subprocess.Popen(
            [python_path, istina_path, "--interactive"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    
    def execute(self, command, params=None):
        self._process.stdin.write(f"{command}\n".encode())
        self._process.stdin.flush()
        return json.loads(self._process.stdout.readline())
```

---

## 8. 风险评估（零 Mock 约束）

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 启动真实子进程开销大 | CI 时间增长 | 使用 `SubprocessBackend` 复用进程；标记重型测试为 `slow` |
| 需要真实 ADB/设备 | CI 环境限制 | 使用 `pytest.mark.skipif` 跳过设备依赖测试 |
| 架构重构改动面大 | 引入新 bug | 分阶段迁移，保持向后兼容 |
| 线程/信号测试不稳定 | 偶发失败 | 使用 `QTest.qWait()` 替代 `time.sleep()` |
| EchoBackend 可能失真 | 测试不覆盖真实行为 | 仅用于 UI 状态测试，业务逻辑必须通过 SubprocessBackend 验证 |

---

## 9. 总结

零 Mock 约束下的 GUI 测试拆分核心思路：

1. **先测纯逻辑**：`QueueState`、参数构建、内联解析等可直接单元测试
2. **再测组件**：使用真实 `QApplication` + 真实 backend（非 mock）测试 UI 交互
3. **最后测集成**：启动真实子进程验证完整链路
4. **架构先行**：通过提取 `Backend` 接口和解耦页面与后端，使测试成为可能

当前最大障碍是 `CLIBridge` 与 `QProcess` 紧耦合。建议优先提取后端接口，这是所有 GUI 测试可测试化的前提。

---

## 10. 附录：零 Mock 测试检查清单

### 可立即开始（无阻塞）

- [ ] `tests/test_queue_state.py` — 扩展覆盖
- [ ] `tests/test_gui_settings.py` — 新建
- [ ] `tests/test_gui_log_viewer.py` — 新建
- [ ] `tests/test_gui_dashboard.py` — 新建

### 需架构变更（有阻塞）

- [ ] `CLIBridgeBackend` 接口定义
- [ ] `EchoBackend` / `SubprocessBackend` 实现
- [ ] `MaaEndControlPage` 构造函数注入 backend
- [ ] 纯逻辑方法提取为独立函数

### 需外部依赖

- [ ] 真实 `istina.py` 子进程（CI 中）
- [ ] 真实 ADB 设备（可选，本地）
- [ ] 真实 `llama-server`（可选，本地）
